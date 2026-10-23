"""Portable project snapshots. Opening a project never loads an alignment model."""

from pathlib import Path
import json, os
from copy import deepcopy

PROJECT_NAME = "OTONova.otonova"
VERSION = 1


def signature(path):
    stat = Path(path).stat()
    return [stat.st_size, stat.st_mtime_ns]


def safe_audio(root, name):
    path = (Path(root) / name).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("Project audio path escapes its voicebank folder")
    return path


def scan_folder(folder, prefer_report=True, include_records=True):
    from vcv_core import read_existing_oto, RULES_VERSION
    import soundfile as sf

    root = Path(folder)
    inventory = {}
    entries = []
    failures = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() == ".wav":
            name = path.relative_to(root).as_posix()
            try:
                info = sf.info(path)
                inventory[name] = {
                    "signature": signature(path),
                    "duration": info.duration,
                    "sample_rate": info.samplerate,
                }
            except Exception as exc:
                failures.append({"wav": name, "error": str(exc)})
    actual_names = {name.casefold(): name for name in inventory}
    for path in sorted(root.rglob("oto.ini")):
        rows, _ = read_existing_oto(path)
        for original in rows or []:
            row = deepcopy(original)
            try:
                name = (
                    (path.parent / row["wav"].replace("\\", "/"))
                    .resolve()
                    .relative_to(root.resolve())
                    .as_posix()
                )
            except ValueError:
                continue
            name = actual_names.get(name.casefold(), name)
            if name not in inventory:
                continue
            off, fixed, cut, pre, overlap = [v / 1000 for v in row["values"]]
            end = off - cut if cut < 0 else inventory[name]["duration"] - cut
            row.update(
                wav=name,
                absolute=[off, off + overlap, off + pre, off + fixed, end],
                warnings=[],
                source_index=-1,
                preserve_alias=True,
                unmapped_template=True,
            )
            entries.append(row)
    records = {}
    cache_dirs = sorted(root.glob("auto-*/labels"))
    for name in inventory if include_records else []:
        candidates = [
            directory / Path(name).with_suffix(".json") for directory in cache_dirs
        ]
        # A nested voicebank may keep its cache beside its WAV files.
        audio = root / name
        candidates += [
            directory / audio.with_suffix(".json").name
            for directory in audio.parent.glob("auto-*/labels")
        ]
        for path in sorted(
            set(p for p in candidates if p.is_file()),
            key=lambda p: p.stat().st_mtime_ns,
            reverse=True,
        ):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                spans = record.get("intervals")
                if not isinstance(spans, list) or not spans:
                    continue
                import math

                if any(
                    len(span) != 3
                    or not isinstance(span[2], str)
                    or not all(
                        isinstance(v, (int, float)) and math.isfinite(v)
                        for v in span[:2]
                    )
                    or span[0] < 0
                    or span[1] < span[0]
                    or span[1] > inventory[name]["duration"] + 0.02
                    for span in spans
                ):
                    continue
                if (
                    abs(
                        record.get("duration", inventory[name]["duration"])
                        - inventory[name]["duration"]
                    )
                    > 0.02
                ):
                    continue
                # Old caches have no stat signature; verify their WAV hash when available.
                import hashlib

                if record.get("sha256"):
                    with audio.open("rb") as stream:
                        valid = (
                            hashlib.file_digest(stream, "sha256").hexdigest()
                            == record["sha256"]
                        )
                    if not valid:
                        continue
                record["wav"] = name
                record.setdefault("duration", inventory[name]["duration"])
                records[name] = record
                break
            except (ValueError, OSError, TypeError, KeyError):
                continue
    report = dict(
        mode="vcv",
        rules_version=RULES_VERSION,
        files=len(inventory),
        successful_files=len(inventory),
        entries=entries,
        failures=failures,
        duplicates_removed=0,
        inventory=list(inventory),
        uses_existing_oto=bool(entries),
        oto_encoding="utf-8",
    )
    for path in (
        sorted(
            root.glob("auto-*/report.json"),
            key=lambda p: p.stat().st_mtime_ns,
            reverse=True,
        )
        if prefer_report and not entries
        else []
    ):
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            if previous.get("rules_version") != RULES_VERSION or any(
                "source_index" not in r for r in previous["entries"]
            ):
                continue
            if not all(r["wav"] in inventory for r in previous["entries"]):
                continue
            previous["inventory"] = list(inventory)
            report = previous
            break
        except (OSError, ValueError, KeyError):
            continue
    return inventory, report, records


def save_project(
    path, folder, report, records, inventory, stage=1, selected=None, file_snapshot=None
):
    from vcv_core import atomic_write

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(
        type="OTONova project",
        version=VERSION,
        app_version="1.5",
        folder=os.path.relpath(Path(folder).resolve(), path.parent.resolve()),
        report=report,
        records=records,
        inventory=inventory,
        stage=stage,
        selected=selected,
        file_snapshot=file_snapshot,
    )
    atomic_write(path, json.dumps(data, ensure_ascii=False).encode("utf-8"))


def open_project(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("type") != "OTONova project" or data.get("version") != VERSION:
        raise ValueError("Unsupported OTONova project")
    folder = (path.parent / data["folder"]).resolve()
    changed = []
    for name, item in data["inventory"].items():
        audio = safe_audio(folder, name)
        if not audio.is_file() or signature(audio) != item["signature"]:
            changed.append(name)
            data["records"].pop(name, None)
    data.update(folder=str(folder), changed_files=changed)
    # Saved timings are retained; stale boundaries are never silently reused.
    for row in data["report"]["entries"]:
        safe_audio(folder, row["wav"])
        if row["wav"] in changed:
            row.setdefault("warnings", []).append(
                "WAV 변경 또는 누락: 저장 경계 사용 중지, 다시 추정 필요"
            )
    return data
