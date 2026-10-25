"""UTAU/OpenUtau singer metadata and portable voicebank export.

Schema reference: OpenUtau.Core/Classic/VoicebankConfig.cs and VoicebankLoader.cs.
"""

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import codecs
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile

import yaml

FIELDS = (
    "name",
    "author",
    "voice",
    "version",
    "web",
    "image",
    "sample",
    "portrait",
    "default_phonemizer",
)
EXCLUDED_DIRS = {
    ".git",
    ".otonova-cache",
    "__pycache__",
    ".cache",
    "cache",
    "caches",
    "labels",
    "logits",
    "label-cache",
    "label_cache",
}


METADATA_NAMES = (
    "character.txt",
    "character.yaml",
    "character.yml",
    "charactet.yaml",
    "readme.txt",
)


def metadata_file(folder, *names):
    root = Path(folder)
    if not root.is_dir():
        return root / names[0]
    existing = {
        p.name.casefold(): p
        for p in root.iterdir()
        if p.name.casefold() in names and p.is_file()
    }
    return next((existing[name] for name in names if name in existing), root / names[0])


def metadata_snapshot(folder):
    root = Path(folder)
    if not root.is_dir():
        return {}
    result = {}
    for path in root.iterdir():
        if path.name.casefold() in METADATA_NAMES and path.is_file():
            stat = path.stat()
            result[path.name.casefold()] = [stat.st_size, stat.st_mtime_ns]
    return result


def read_text(path, preferred=None, utf8_first=False):
    raw = Path(path).read_bytes()
    candidates = []
    if raw.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        candidates.append("utf-32")
    elif raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        candidates.append("utf-16")
    elif raw.startswith(b"\xef\xbb\xbf"):
        candidates.append("utf-8-sig")
    declared = re.search(rb"(?im)^#Charset:\s*([a-zA-Z0-9_-]+)", raw[:4096])
    candidates += [
        declared[1].decode("ascii") if declared else None,
        "utf-8" if utf8_first else None,
        preferred,
        "utf-8-sig",
        "cp932",
        "cp949",
    ]
    for encoding in dict.fromkeys(candidates):
        if not encoding:
            continue
        try:
            codec = "cp932" if encoding in {"shift_jis", "shift-jis"} else encoding
            text = raw.decode(codec)
            if "\x00" in text:
                continue
            return text, encoding
        except (UnicodeError, LookupError):
            pass
    raise ValueError("텍스트 인코딩을 읽을 수 없습니다: " + str(path))


def load_settings(folder):
    root = Path(folder)
    config = {}
    yaml_path = metadata_file(root, "character.yaml", "character.yml", "charactet.yaml")
    if yaml_path.exists():
        yaml_text, _ = read_text(yaml_path, "utf-8")
        config = yaml.safe_load(yaml_text) or {}
        if not isinstance(config, dict):
            raise ValueError("character.yaml은 항목 목록 형식이어야 합니다.")
    config = json.loads(json.dumps(config, default=str))
    preferred = config.get("text_file_encoding")
    info = {}
    extra = []
    txt_path = metadata_file(root, "character.txt")
    if txt_path.exists():
        text, encoding = read_text(txt_path, preferred)
        preferred = preferred or encoding
        for line in text.splitlines():
            parts = re.split(r"[=：:]", line, maxsplit=1)
            key = parts[0].strip().lower()
            key = {"名前": "name", "created by": "author", "cv": "voice"}.get(key, key)
            if key.startswith("voice"):
                key = "voice"
            if len(parts) == 2 and key in FIELDS:
                info[key] = parts[1].strip()
            else:
                extra.append(line)
    if not preferred and (root / "oto.ini").exists():
        _, preferred = read_text(root / "oto.ini")
    encoding = preferred or "utf-8"
    if encoding == "utf-8-sig":
        encoding = "utf-8"
    data = {
        key: (
            str(config[key])
            if config.get(key) is not None and str(config[key]).strip()
            else info.get(key, "")
        )
        for key in FIELDS
    }
    data["name"] = data["name"] or root.name
    data.update(
        text_file_encoding=encoding,
        portrait_opacity=config.get("portrait_opacity", 0.67),
        portrait_height=config.get("portrait_height", 0),
        subbanks=deepcopy(config.get("subbanks") or []),
        readme_enabled=metadata_file(root, "readme.txt").exists(),
        readme="",
        _yaml=deepcopy(config),
        _txt_extra=extra,
        _source_encoding=encoding,
        _metadata_snapshot=metadata_snapshot(root),
        _draft_dirty=False,
    )
    if data["readme_enabled"]:
        data["readme"], _ = read_text(metadata_file(root, "readme.txt"), preferred)
    return data


def _inside(root, name):
    path = (root / name.replace("\\", "/")).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("음원 폴더 밖을 가리키는 상대 경로입니다: " + name)
    return path


def metadata_files(folder, settings):
    root = Path(folder)
    data = deepcopy(settings)
    files = {}
    for key in FIELDS:
        value = str(data.get(key, "")).strip()
        if any(c in value for c in "\r\n\0"):
            raise ValueError("가수 정보에는 줄바꿈을 넣을 수 없습니다: " + key)
        data[key] = value
    if not data["name"]:
        raise ValueError("가수 이름을 입력해주세요.")
    encoding = str(data.get("text_file_encoding", "utf-8"))
    codec = codecs.lookup(encoding).name
    output_codec = (
        "utf-8-sig"
        if codec == "utf-8"
        else "cp932" if codec == "shift_jis" else encoding
    )
    for key in ("image", "portrait", "sample"):
        name = data[key]
        if not name:
            continue
        path = Path(name) if Path(name).is_absolute() else _inside(root, name)
        if not path.is_file():
            raise ValueError("가수 설정의 파일을 찾을 수 없습니다: " + name)
        if path.resolve().is_relative_to(root.resolve()):
            data[key] = path.resolve().relative_to(root.resolve()).as_posix()
        else:
            content = path.read_bytes()
            relative = (
                "singer-assets/"
                + key
                + "-"
                + hashlib.sha256(content).hexdigest()[:12]
                + path.suffix.lower()
            )
            files[relative] = content
            data[key] = relative
    config = deepcopy(data.get("_yaml") or {})
    for key in FIELDS:
        if data[key]:
            config[key] = data[key]
        else:
            config.pop(key, None)
    config.update(
        singer_type="utau",
        text_file_encoding=encoding,
        portrait_opacity=float(data.get("portrait_opacity", 0.67)),
        portrait_height=int(data.get("portrait_height", 0)),
    )
    if not 0 <= config["portrait_opacity"] <= 1 or config["portrait_height"] < 0:
        raise ValueError("초상화 크기 또는 불투명도 값이 올바르지 않습니다.")
    subbanks = deepcopy(data.get("subbanks") or [])
    for bank in subbanks:
        ranges = bank.get("tone_ranges", [])
        if not isinstance(ranges, list) or any(
            not re.fullmatch(r"[A-G][#b]?-?\d+(?:-[A-G][#b]?-?\d+)?", str(t))
            for t in ranges
        ):
            raise ValueError("음역은 C1-B7 또는 C4 형식으로 입력해주세요.")
    if subbanks:
        config["subbanks"] = subbanks
    else:
        config.pop("subbanks", None)
    txt_keys = ("name", "image", "author", "voice", "sample", "web", "version")
    lines = [key + "=" + data[key] for key in txt_keys if data[key]]
    lines += data.get("_txt_extra", [])
    try:
        files["character.txt"] = ("\r\n".join(lines) + "\r\n").encode(output_codec)
    except UnicodeError as exc:
        raise ValueError(
            "가수 정보를 해당 인코딩으로 저장할 수 없습니다. UTF-8을 선택해주세요."
        ) from exc
    files["character.yaml"] = yaml.safe_dump(
        config, allow_unicode=True, sort_keys=False
    ).encode("utf-8")
    if data.get("readme_enabled"):
        files["readme.txt"] = str(data.get("readme", "")).encode("utf-8-sig")
    return files


def bank_files(folder):
    root = Path(folder).resolve()
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(
            d
            for d in dirs
            if d.casefold() not in EXCLUDED_DIRS
            and not d.casefold().startswith("auto-")
            and not (Path(directory) / d).is_symlink()
            and (Path(directory) / d).resolve().is_relative_to(root)
        )
        for name in sorted(names):
            path = Path(directory) / name
            relative = path.relative_to(root)
            if (
                path.is_symlink()
                or not path.resolve().is_relative_to(root)
                or path.suffix.lower()
                in {
                    ".otonova",
                    ".zip",
                    ".tmp",
                    ".log",
                    ".npz",
                    ".npy",
                    ".lab",
                    ".pyc",
                    ".pyo",
                }
                or ".backup." in name.lower()
                or name in {"Thumbs.db", ".DS_Store"}
            ):
                continue
            if path.suffix.casefold() == ".json":
                try:
                    cached = json.loads(path.read_text(encoding="utf-8-sig"))
                    if isinstance(cached, dict) and (
                        ("wav" in cached and "intervals" in cached)
                        or ("rules_version" in cached and "entries" in cached)
                    ):
                        continue
                except (OSError, ValueError):
                    pass
            if path.name.casefold() in {
                "oto.ini",
                "prefix.map",
                "character.txt",
                "character.yaml",
                "readme.txt",
            }:
                relative = relative.with_name(path.name.casefold())
            yield relative.as_posix(), path


def generated_files(folder, data, report=None):
    files = metadata_files(folder, data)
    encoding = str(data.get("text_file_encoding", "utf-8"))
    output_codec = (
        "utf-8-sig"
        if codecs.lookup(encoding).name == "utf-8"
        else "cp932" if codecs.lookup(encoding).name == "shift_jis" else encoding
    )
    # The config's encoding applies to all OTO sets and pitch maps as well.
    for name, path in bank_files(folder):
        if (
            path.name.lower() in {"oto.ini", "prefix.map"}
            or path.suffix.lower() == ".map"
        ):
            text, _ = read_text(path, data.get("_source_encoding"))
            text = re.sub(r"^#Charset:.*(?:\r?\n|$)", "", text, flags=re.I | re.M)
            files[name] = text.encode(output_codec)
    if report and report.get("entries"):
        groups = {}
        known = set()
        for row in report["entries"]:
            audio = _inside(Path(folder), row["wav"])
            if not audio.is_file():
                raise ValueError("원설에 연결된 WAV를 찾을 수 없습니다: " + row["wav"])
            relative = audio.relative_to(Path(folder).resolve())
            known.add(relative.as_posix().casefold())
            oto = (relative.parent / "oto.ini").as_posix()
            groups.setdefault(oto, []).append(
                relative.name
                + "="
                + row["alias"]
                + ","
                + ",".join(f"{v:.3f}" for v in row["values"])
                + "\n"
            )
        for name, content in list(files.items()):
            if Path(name).name.casefold() != "oto.ini":
                continue
            kept = []
            for line in content.decode(output_codec).splitlines():
                raw_wav = line.split("=", 1)[0].replace("\\", "/")
                relative = (Path(name).parent / raw_wav).as_posix().casefold()
                if "=" not in line or relative not in known:
                    kept.append(line)
            files[name] = ("\n".join(kept) + ("\n" if kept else "")).encode(
                output_codec
            )
        for name, lines in groups.items():
            previous = (
                files.get(name, b"").decode(output_codec) if files.get(name) else ""
            )
            files[name] = (previous + "".join(lines)).encode(output_codec)
    return files


def save_settings(folder, data):
    from vcv_core import atomic_write

    root = Path(folder).resolve()
    files = generated_files(root, data)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    for name, content in files.items():
        target = _inside(root, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and target.read_bytes() != content:
            shutil.copy2(target, target.with_name(target.name + ".backup." + stamp))
        atomic_write(target, content)
    readme = root / "readme.txt"
    if not data.get("readme_enabled") and readme.exists():
        shutil.copy2(readme, readme.with_name("readme.txt.backup." + stamp))
        readme.unlink()


def export_zip(
    folder,
    destination,
    data,
    report=None,
    progress=lambda value: None,
    cancelled=lambda: False,
):
    root = Path(folder).resolve()
    destination = Path(destination).resolve()
    files = generated_files(root, data, report)
    sources = [
        (name, path) for name, path in bank_files(root) if path.resolve() != destination
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=".otonova-export-", suffix=".tmp", dir=destination.parent
    )
    os.close(handle)
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=True,
        ) as archive:
            for i, (name, path) in enumerate(sources):
                if cancelled():
                    raise RuntimeError("ZIP 내보내기를 취소했습니다.")
                if name in files or name.casefold() in {
                    "character.txt",
                    "character.yaml",
                    "character.yml",
                    "charactet.yaml",
                    "readme.txt",
                }:
                    continue
                before = path.stat()
                archive.write(path, root.name + "/" + name)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (
                    after.st_size,
                    after.st_mtime_ns,
                ):
                    raise ValueError("내보내는 동안 파일이 변경되었습니다: " + name)
                progress(f"ZIP {i+1}/{len(sources)} · {name}")
            for name, content in files.items():
                if cancelled():
                    raise RuntimeError("ZIP 내보내기를 취소했습니다.")
                archive.writestr(root.name + "/" + name, content)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination
