"""Japanese VCV alignment and user-defined oto rules. Times are seconds internally."""

from pathlib import Path
import json
import unicodedata
import hashlib
import math
import sys
from copy import deepcopy
from datetime import datetime
from formats import FORMATS, is_korean

ROOT = Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", ROOT))
DEFAULT_FOLDER = Path.home() / "Music"
if not DEFAULT_FOLDER.is_dir():
    DEFAULT_FOLDER = Path.home()
if getattr(sys, "frozen", False):
    DEFAULT_FOLDER = Path.cwd() / "Natural"
    for candidate in [
        Path(sys.executable).parent / "Natural",
        Path(sys.executable).parent.parent.parent / "Natural",
    ]:
        if candidate.is_dir():
            DEFAULT_FOLDER = candidate
            break
from platform_support import workspace

WORKSPACE = workspace()
TABLE = RESOURCE_ROOT / "assets/kana2phonemes.table"
VOWELS = {"a", "i", "u", "e", "o", "N"}
FIXED_LEAD = 0.04
RULES_VERSION = 20
JP_PHONES = {
    line[2:]
    for line in (WORKSPACE / "Japanese/phonemes.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.startswith("B-")
}
CONSONANTS = (
    (JP_PHONES | {"dy", "fy", "py", "ty", "vy"})
    - VOWELS
    - {"A", "I", "U", "E", "O", "SP", "AP", "axh", "exh", "mlem", "vf"}
)
CONSONANT_KEYS = sorted(CONSONANTS, key=len, reverse=True)


def hiragana(text):
    text = unicodedata.normalize("NFKC", text)
    return "".join(chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c for c in text)


def load_kana_table():
    table = {}
    for line in TABLE.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and any("\u3040" <= c <= "\u30ff" for c in parts[0]):
            key = hiragana(parts[0])
            phones = [p.lower() if p in "AIUEO" else p for p in parts[1:]]
            table[key] = phones
    # Table omissions for this reclist; these are explicit kana transcription rules.
    table.update({"づぁ": ["z", "a"], "でぃぇ": ["dy", "e"], "でょ": ["dy", "o"]})
    for kana, consonant in [
        ("す", "s"),
        ("ぬ", "n"),
        ("ぶ", "b"),
        ("ぷ", "p"),
        ("む", "m"),
        ("る", "r"),
    ]:
        for small, vowel in zip("ぁぃぇぉ", "aieo"):
            table[kana + small] = [consonant, "w", vowel]
    table["ほぅ"] = ["h", "u"]
    return table


KANA = load_kana_table()
KANA_KEYS = sorted(KANA, key=len, reverse=True)


def parse_name(stem):
    text = hiragana(stem)
    tokens = []
    pos = 0
    keys = KANA_KEYS
    while pos < len(text):
        if text[pos] in "_ -":
            pos += 1
            continue
        if text[pos] in ("R", "息"):
            tokens.append({"kana": "R", "phones": ["pau"], "breath": True})
            pos += 1
            continue
        if "a" <= text[pos] <= "z":
            expanded = sorted(
                CONSONANTS | {p + "w" for p in CONSONANTS if p != "w"},
                key=len,
                reverse=True,
            )
            phone = next((p for p in expanded if text.startswith(p, pos)), text[pos])
            proxy = (
                phone[:-1]
                if phone.endswith("w") and phone[:-1] in CONSONANTS
                else phone
            )
            parts = (
                [proxy[0]]
                if proxy.endswith("y") and proxy not in JP_PHONES
                else [proxy]
            )
            tokens.append(
                {
                    "kana": phone,
                    "phones": parts,
                    "alias_phones": [phone],
                    "breath": False,
                }
            )
            pos += len(phone)
            continue
        if text[pos] == "ー" and tokens and tokens[-1]["phones"][-1] in VOWELS:
            tokens.append(
                {"kana": "ー", "phones": [tokens[-1]["phones"][-1]], "breath": False}
            )
            pos += 1
            continue
        key = next((k for k in keys if text.startswith(k, pos)), None)
        if key is None:
            raise ValueError(f"인식할 수 없는 파일명 문자: {text[pos:]}")
        original = KANA[key]
        phones = (
            [original[0]] + original[2:]
            if len(original) > 2 and original[1] == "w"
            else original
        )
        phones = [
            part
            for p in phones
            for part in ([p[0]] if p.endswith("y") and p not in JP_PHONES else [p])
        ]
        tokens.append(
            {"kana": key, "phones": phones, "alias_phones": original, "breath": False}
        )
        pos += len(key)
    if not tokens:
        raise ValueError("음소가 없는 파일명")
    return tokens


def two_thirds(interval):
    return interval[0] + (interval[1] - interval[0]) * 2 / 3


def make_entry(
    wav,
    alias,
    offset,
    overlap,
    pre,
    fixed,
    end,
    duration,
    notes,
    fixed_lead=FIXED_LEAD,
    allow_negative_overlap=False,
    allow_unordered_markers=False,
):
    raw = [offset, overlap, pre, fixed, end]
    offset = max(0.0, min(offset, duration))
    end = max(offset, min(end, duration))
    fixed = max(offset, end - fixed_lead)
    overlap = max(0.0 if allow_negative_overlap else offset, min(overlap, end))
    pre = (
        max(0.0, min(pre, end))
        if allow_unordered_markers
        else max(0.0 if allow_negative_overlap else offset, overlap, min(pre, end))
    )
    absolute = [offset, overlap, pre, fixed, end]
    warnings = list(notes)
    if any(abs(a - b) > 1e-8 for a, b in zip(raw, absolute)):
        warnings.append("WAV 범위 또는 짧은 구간 때문에 규칙값을 보정함")
    if fixed < pre:
        warnings.append("고정 끝이 선행보다 앞: 청음 검토 필요")
    values = [
        offset * 1000,
        (fixed - offset) * 1000,
        -(end - offset) * 1000,
        (pre - offset) * 1000,
        (overlap - offset) * 1000,
    ]
    return {
        "wav": wav,
        "alias": alias,
        "values": values,
        "absolute": absolute,
        "warnings": warnings,
    }


def consonant_entry(wav, alias, spans, index, duration):
    span = spans[index]
    following = next(
        (s for s in reversed(spans) if s[2] == "pau"), [span[1], duration, "pau"]
    )
    offset = two_thirds(span)
    pre = following[0]
    fixed = following[0] + (following[1] - following[0]) / 3
    row = make_entry(
        wav,
        alias,
        offset,
        (offset + pre) / 2,
        pre,
        fixed,
        fixed + 0.02,
        duration,
        [],
        fixed_lead=0.02,
        allow_negative_overlap=True,
        allow_unordered_markers=True,
    )
    row["consonant_interval_index"] = index
    row["consonant_only"] = True
    return row


def create_oto(wav, tokens, intervals, duration, mode="vcv"):
    if mode == "ja_cv":
        rows = []
        seen = set()
        for row in create_cvvc_oto(wav, tokens, intervals, duration):
            alias = row["alias"][2:] if row["alias"].startswith("- ") else row["alias"]
            if " " in alias or alias in seen:
                continue
            seen.add(alias)
            row["alias"] = alias
            rows.append(row)
        for i, row in enumerate(rows):
            row["source_index"] = i
        return rows
    if mode == "vcv_cvvc":
        entries = create_oto(wav, tokens, intervals, duration, "vcv")
        existing = {row["alias"] for row in entries}
        entries.extend(
            row
            for row in create_cvvc_oto(wav, tokens, intervals, duration)
            if row["alias"] not in existing
        )
        for i, row in enumerate(entries):
            row["source_index"] = i
        return entries
    if mode == "cvvc":
        return create_cvvc_oto(wav, tokens, intervals, duration)
    if mode != "vcv":
        raise ValueError("지원하지 않는 음원 형식: " + mode)
    entries = []
    index = 1  # leading pau
    previous = None
    for token in tokens:
        count = len(token["phones"])
        spans = intervals[index : index + count]
        if token["breath"]:
            if previous:
                off = two_thirds(previous)
                pre = spans[0][0]
                entries.append(
                    make_entry(
                        wav,
                        previous[2].lower() + " R",
                        off,
                        off + (pre - off) * 0.75,
                        pre,
                        pre + 0.7 - FIXED_LEAD,
                        pre + 0.7,
                        duration,
                        ["R 한숨: WFL SP 기준 경계 사용"],
                    )
                )
            index += count
            previous = None
            continue
        main = spans[-1]
        if main[2] not in VOWELS:
            entries.extend(
                consonant_entry(wav, alias, intervals, index, duration)
                for alias in (token["kana"], token["kana"] + " -")
            )
            index += count
            previous = None
            continue
        end = two_thirds(main)
        if previous is None:
            onset = intervals[index - 1][1]
            off, overlap = onset - 0.3, onset
            alias = "- " + token["kana"]
        else:
            off, overlap = two_thirds(previous), previous[1]
            alias = previous[2].lower() + " " + token["kana"]
        alias = alias.replace("ゔ", "ヴ")  # CP932 has ヴ but no hiragana ゔ.
        entries.append(
            make_entry(
                wav, alias, off, overlap, main[0], end - FIXED_LEAD, end, duration, []
            )
        )
        previous = main
        index += count
    if previous:
        pre = intervals[-1][0]
        off = two_thirds(previous)
        entries.append(
            make_entry(
                wav,
                previous[2].lower() + " -",
                off,
                off + (pre - off) * 0.75,
                pre,
                pre + 0.7 - FIXED_LEAD,
                pre + 0.7,
                duration,
                [],
            )
        )
    for i, row in enumerate(entries):
        row["source_index"] = i
    return entries


def create_cvvc_oto(wav, tokens, intervals, duration):
    """CVVC aliases: -CV/-V, CV/V, vowel+consonant, and vowel tail."""
    entries = []
    index = 1
    previous = None

    def append(alias, off, overlap, pre, end, notes=(), fixed_lead=0.2):
        entries.append(
            make_entry(
                wav,
                alias.replace("ゔ", "ヴ"),
                off,
                overlap,
                pre,
                end - fixed_lead,
                end,
                duration,
                notes,
                fixed_lead=fixed_lead,
                allow_negative_overlap=True,
            )
        )

    for token in tokens:
        count = len(token["phones"])
        spans = intervals[index : index + count]
        if token["breath"]:
            if previous:
                off, pre = two_thirds(previous), spans[0][0]
                append(
                    previous[2].lower() + " R",
                    off,
                    off + (pre - off) * 0.75,
                    pre,
                    pre + 0.7,
                    ["R 한숨: WFL SP 기준 경계 사용"],
                )
            previous = None
            index += count
            continue
        main = spans[-1]
        if main[2] not in VOWELS:
            if previous is not None:
                off = previous[0] + (previous[1] - previous[0]) * 4 / 5
                pre = spans[0][0]
                append(
                    previous[2].lower()
                    + " "
                    + "".join(token.get("alias_phones", token["phones"])),
                    off,
                    off + (pre - off) * 2 / 3,
                    pre,
                    pre + (main[1] - pre) / 2,
                    fixed_lead=0.015,
                )
            entries.extend(
                consonant_entry(wav, alias, intervals, index, duration)
                for alias in (token["kana"], token["kana"] + " -")
            )
            previous = None
            index += count
            continue
        end = two_thirds(main)
        if previous is None:
            onset = intervals[index - 1][1]
            append(
                "- " + token["kana"], onset - 0.3, onset, main[0], end, fixed_lead=0.07
            )
        if count > 1:
            # Compound onsets (e.g. k+w) span all consonants before the vowel.
            consonant = [spans[0][0], main[0]]
            off = consonant[0] + (consonant[1] - consonant[0]) / 3
            append(
                token["kana"],
                off,
                off + (main[0] - off) / 2,
                main[0],
                end,
                fixed_lead=0.07,
            )
            if previous is not None:
                off = previous[0] + (previous[1] - previous[0]) * 4 / 5
                pre = consonant[0]
                consonant_alias = "".join(
                    token.get("alias_phones", token["phones"])[:-1]
                )
                append(
                    previous[2].lower() + " " + consonant_alias,
                    off,
                    off + (pre - off) * 2 / 3,
                    pre,
                    consonant[0] + (consonant[1] - consonant[0]) / 2,
                    fixed_lead=0.015,
                )
        else:
            # A vowel-only syllable has no consonant interval; anchor V at its start.
            append(token["kana"], main[0], main[0], main[0], end, fixed_lead=0.07)
            if previous is not None:
                # VV uses the existing VCV rule, including its 40ms fixed lead.
                entries.append(
                    make_entry(
                        wav,
                        (previous[2].lower() + " " + token["kana"]).replace("ゔ", "ヴ"),
                        two_thirds(previous),
                        previous[1],
                        main[0],
                        end - FIXED_LEAD,
                        end,
                        duration,
                        [],
                    )
                )
        previous = main
        index += count
    if previous:
        off, pre = two_thirds(previous), intervals[-1][0]
        append(
            previous[2].lower() + " -", off, off + (pre - off) * 0.75, pre, pre + 0.7
        )
    for i, row in enumerate(entries):
        row["source_index"] = i
    return entries


def output_dir(folder, mode="vcv"):
    if mode not in FORMATS:
        raise ValueError("지원하지 않는 음원 형식: " + mode)
    return Path(folder) / ("auto-" + mode)


def deduplicate(entries):
    seen = set()
    kept = []
    for row in entries:
        if row["alias"] not in seen:
            seen.add(row["alias"])
            kept.append(row)
    return kept, len(entries) - len(kept)


def move_boundary(record, index, seconds):
    """Move a shared boundary; keep adjacent phonemes contiguous and nonempty."""
    spans = record["intervals"]
    if not 0 < index < len(spans) or not math.isfinite(seconds):
        raise ValueError("이동할 수 없는 경계")
    low = spans[index - 1][0] + 0.001
    high = min(spans[index][1] - 0.001, record["duration"])
    if high < low:
        raise ValueError("음소 구간이 너무 짧습니다")
    seconds = max(low, min(float(seconds), high))
    if "model_intervals" not in record:
        record["model_intervals"] = deepcopy(spans)
    spans[index - 1][1] = seconds
    spans[index][0] = seconds
    record["manually_edited"] = True
    return seconds


def recalculate_file(report, record, indices=None):
    if record.get("language") == "en":
        if record.get("format") == "en_vccv":
            from english_vccv import create_oto as create_english_oto
        elif record.get("format") == "en_cvvc":
            from english_cvvc import create_oto as create_english_oto
        else:
            from arpasing_core import create_oto as create_english_oto
        rows = create_english_oto(record)
    elif record.get("language") == "ko":
        from korean_core import create_oto as create_korean_oto

        rows = create_korean_oto(record, report.get("mode", "ko_cvvc"))
    else:
        rows = create_oto(
            record["wav"],
            parse_name(Path(record["wav"]).stem),
            record["intervals"],
            record["duration"],
            report.get("mode", "vcv"),
        )
    source = {r["source_index"]: r for r in rows}
    changed = []
    indices = range(len(report["entries"])) if indices is None else indices
    for index in indices:
        row = report["entries"][index]
        if (
            row["wav"].replace("\\", "/").casefold()
            == record["wav"].replace("\\", "/").casefold()
        ):
            if row.get("combined_alias"):
                from korean_combined import make_alias

                replacement = make_alias(row["combined_alias"], record)
                if replacement is not None:
                    replacement.update(source_index=row["source_index"])
                    if row.get("preserve_alias"):
                        replacement.update(alias=row["alias"], preserve_alias=True)
                    report["entries"][index] = replacement
                changed.append(index)
                continue
            if (
                row.get("derived_profile")
                and row.get("entry_kind") == "start_consonant"
            ):
                span = record["intervals"][row["phone_indices"][0]]
                cut = two_thirds(span)
                replacement = make_entry(
                    row["wav"],
                    row["alias"],
                    span[0] - 0.3,
                    span[0],
                    span[0],
                    cut - 0.07,
                    cut,
                    record["duration"],
                    [row["mapping_warning"]],
                    fixed_lead=0.07,
                    allow_negative_overlap=True,
                )
                row.update(replacement)
                changed.append(index)
                continue
            if "consonant_interval_index" in row:
                replacement = consonant_entry(
                    row["wav"],
                    row["alias"],
                    record["intervals"],
                    row["consonant_interval_index"],
                    record["duration"],
                )
                replacement["source_index"] = row["source_index"]
                if row.get("preserve_alias"):
                    replacement["preserve_alias"] = True
                report["entries"][index] = replacement
                changed.append(index)
                continue
            if row.get("unmapped_template"):
                anchors = row.get("boundary_anchors")
                if not anchors:
                    anchors = anchor_markers(row["absolute"], record["intervals"])
                    row["boundary_anchors"] = anchors
                absolute = [
                    record["intervals"][i][0]
                    + fraction * (record["intervals"][i][1] - record["intervals"][i][0])
                    for i, fraction in anchors
                ]
                off, overlap, pre, fixed, end = absolute
                row["absolute"] = absolute
                row["values"] = [
                    off * 1000,
                    (fixed - off) * 1000,
                    -(end - off) * 1000,
                    (pre - off) * 1000,
                    (overlap - off) * 1000,
                ]
                changed.append(index)
                continue
            replacement = deepcopy(source[row["source_index"]])
            if row.get("preserve_alias"):
                replacement["wav"] = row["wav"]
                replacement["alias"] = row["alias"]
                replacement["preserve_alias"] = True
            if row.get("derived_profile"):
                replacement["derived_profile"] = True
                replacement["template_alias"] = row.get("template_alias", row["alias"])
            if row.get("mapping_warning"):
                replacement["mapping_warning"] = row["mapping_warning"]
                replacement["warnings"].append(row["mapping_warning"])
            report["entries"][index] = replacement
            changed.append(index)
    return changed


def atomic_write(path, data):
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(data)
    temp.replace(path)


def persist_report(folder, report):
    output = output_dir(folder, report.get("mode", "vcv"))
    output.mkdir(exist_ok=True)
    lines = [
        r["wav"] + "=" + r["alias"] + "," + ",".join(f"{v:.3f}" for v in r["values"])
        for r in report["entries"]
    ]
    text = ("\n".join(lines) + "\n").encode(report.get("oto_encoding", "cp932"))
    report["updated"] = datetime.now().isoformat()
    atomic_write(output / "oto.preview.ini", text)
    atomic_write(
        output / "report.json",
        json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"),
    )


def save_record(folder, record):
    output = Path(folder) / "auto-vcv/labels"
    output.mkdir(parents=True, exist_ok=True)
    path = output / Path(record["wav"]).with_suffix(".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8"))
    labels = "".join(
        f"{round(s*1e7)} {round(e*1e7)} {p}\n" for s, e, p in record["intervals"]
    )
    atomic_write(path.with_suffix(".lab"), labels.encode("utf-8"))


class Engine:
    def __init__(self):
        from korean_core import KoreanEngine

        self.backend = KoreanEngine(model_dir=WORKSPACE / "Japanese", language="ja")

    def analyze(self, path, cache_dir, mode="vcv"):
        path = Path(path)
        tokens = parse_name(path.stem)
        internal = ["pau"] + [p for t in tokens for p in t["phones"]]
        if internal[-1] != "pau":
            internal.append("pau")
        phones = ["SP" if p == "pau" else p for p in internal]
        unsupported = set(phones) - JP_PHONES
        if unsupported:
            raise ValueError("일본어 모델 미지원 음소: " + str(unsupported))
        fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
        cache = Path(cache_dir) / (path.stem + ".json")
        signature = str((WORKSPACE / "Japanese/last.ckpt").stat().st_mtime_ns)
        if cache.exists():
            record = json.loads(cache.read_text(encoding="utf-8"))
            compatible = record.get("manually_edited") or (
                record.get("model") == "WFL-ASR-japanese"
                and record.get("model_signature") == signature
            )
            if (
                compatible
                and record.get("sha256") == fingerprint
                and record.get("phones") == internal
            ):
                return (
                    create_oto(
                        path.name, tokens, record["intervals"], record["duration"], mode
                    ),
                    record,
                )
        final = self.backend.request(path, phones)
        spans = final["intervals"]
        duration = final["duration"]
        boundaries = (
            [0]
            + [(spans[i - 1][1] + spans[i][0]) / 2 for i in range(1, len(spans))]
            + [duration]
        )
        if any(b <= a for a, b in zip(boundaries, boundaries[1:])):
            raise ValueError("日本語の境界が逆転しています")
        intervals = [
            [boundaries[i], boundaries[i + 1], p] for i, p in enumerate(internal)
        ]
        record = {
            "wav": path.name,
            "sha256": fingerprint,
            "phones": internal,
            "intervals": intervals,
            "duration": duration,
            "language": "ja",
            "model": "WFL-ASR-japanese",
            "model_signature": signature,
            "breath_proxy": any(t["breath"] for t in tokens),
        }
        cache.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(
            cache, json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
        )
        atomic_write(
            cache.with_suffix(".lab"),
            "".join(
                f"{round(s*1e7)} {round(e*1e7)} {p}\n" for s, e, p in intervals
            ).encode("utf-8"),
        )
        return create_oto(path.name, tokens, intervals, duration, mode), record

    def close(self):
        self.backend.close()


def read_existing_oto(path):
    path = Path(path)
    if not path.exists():
        return None, "cp932"
    data = path.read_bytes()
    encodings = (
        ["utf-8-sig"] if data.startswith(b"\xef\xbb\xbf") else ["utf-8", "cp932"]
    )
    for encoding in encodings:
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("기존 oto.ini 인코딩을 읽을 수 없습니다.")
    rows = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            wav, tail = line.split("=", 1)
            alias, *fields = tail.split(",")
            values = [float(value or 0) for value in fields]
            if not wav or len(values) != 5 or not all(math.isfinite(v) for v in values):
                raise ValueError()
        except ValueError:
            raise ValueError(
                f"기존 oto.ini {number}행 형식 오류. 기존 파일은 유지됩니다."
            )
        rows.append({"wav": wav, "alias": alias, "values": values})
    return rows, encoding


def anchor_markers(markers, intervals):
    """Keep original timing positions attached to their phoneme intervals."""
    anchors = []
    for marker in markers:
        index = min(
            range(len(intervals)),
            key=lambda i: max(intervals[i][0] - marker, marker - intervals[i][1], 0),
        )
        start, end, _ = intervals[index]
        anchors.append([index, (marker - start) / max(end - start, 1e-9)])
    return anchors


def template_alias(alias):
    text = "".join(hiragana(alias).replace("息", "R").split())
    # Reclists commonly spell the moraic nasal as lowercase n in VC aliases.
    if text.startswith("n") and len(text) > 1:
        text = "N" + text[1:]
    return text


def model_alias(alias):
    text = template_alias(alias)
    for consonant in sorted(CONSONANTS, key=len, reverse=True):
        if text.endswith(consonant + "w"):
            return text[:-1]
        if text.endswith(consonant + "w-"):
            return text[:-2] + "-"
    return text


def detect_template_affixes(template, grouped, records):
    aliases = ["".join(hiragana(r["alias"]).split()) for r in template]
    if len(set(aliases)) < 2:
        return "", ""

    def common(strings):
        result = strings[0]
        for value in strings[1:]:
            while result and not value.startswith(result):
                result = result[:-1]
        return result

    prefix = common(aliases)
    suffix = common([a[::-1] for a in aliases])[::-1]

    def score(left, right):
        matched = 0
        for original, alias in zip(template, aliases):
            if len(alias) <= left + right:
                continue
            sound = alias[left : len(alias) - right if right else None]
            candidates = grouped.get(original["wav"].casefold(), [])
            known = {model_alias(r["alias"]) for r in candidates}
            record = (records or {}).get(original["wav"].casefold(), {})
            phone = template_alias(sound).rstrip("-")
            if phone.endswith("w"):
                phone = phone[:-1]
            if model_alias(sound) in known or (
                phone in CONSONANTS and phone in record.get("phones", [])
            ):
                matched += 1
        return matched

    baseline = score(0, 0)
    best = (baseline, 0, 0)
    for left in range(len(prefix) + 1):
        for right in range(len(suffix) + 1):
            count = score(left, right)
            if count > best[0] or (
                count == best[0] and left + right < best[1] + best[2]
            ):
                best = (count, left, right)
    if best[0] <= baseline or best[0] < 2:
        return "", ""
    return prefix[: best[1]], suffix[len(suffix) - best[2] :] if best[2] else ""


def apply_oto_template(template, generated, durations, records=None):
    grouped = {}
    for row in generated:
        grouped.setdefault(row["wav"].casefold(), []).append(row)
    prefix, suffix = detect_template_affixes(template, grouped, records)
    result = []
    for original in template:
        candidates = grouped.get(original["wav"].casefold(), [])
        sound = "".join(hiragana(original["alias"]).split())
        sound = sound[len(prefix) : len(sound) - len(suffix) if suffix else None]
        alias = template_alias(sound)
        matches = [r for r in candidates if template_alias(r["alias"]) == alias]
        if not matches:
            matches = [
                r for r in candidates if model_alias(r["alias"]) == model_alias(sound)
            ]
        if matches:
            # Repeated syllables: retain the occurrence nearest the original preutterance.
            pre = (original["values"][0] + original["values"][3]) / 1000
            row = deepcopy(min(matches, key=lambda r: abs(r["absolute"][2] - pre)))
            row.update(
                wav=original["wav"], alias=original["alias"], preserve_alias=True
            )
        else:
            row = deepcopy(original)
            off, fixed, cut, pre, overlap = [v / 1000 for v in row["values"]]
            duration = durations.get(row["wav"].casefold(), max(off, off - cut))
            end = off - cut if cut < 0 else duration - cut
            row.update(
                source_index=-1,
                unmapped_template=True,
                preserve_alias=True,
                absolute=[off, off + overlap, off + pre, off + fixed, end],
                warnings=["기존 에일리어스 대응 경계를 찾지 못해 원래 시간값 유지"],
            )
            phone = alias.rstrip("-")
            if phone.endswith("w") and phone[:-1] in CONSONANTS:
                phone = phone[:-1]
            record = (records or {}).get(row["wav"].casefold())
            if record and record.get("intervals"):
                row["boundary_anchors"] = anchor_markers(
                    row["absolute"], record["intervals"]
                )
                row["warnings"] = [
                    "에일리어스 대응 불가: 기존 시간 위치를 경계에 연동하여 수정"
                ]
            if phone in CONSONANTS and record and phone in record["phones"]:
                target = (original["values"][0] + original["values"][3]) / 1000
                indices = [
                    i for i, span in enumerate(record["intervals"]) if span[2] == phone
                ]
                index = min(
                    indices,
                    key=lambda i: abs(
                        (record["intervals"][i][0] + record["intervals"][i][1]) / 2
                        - target
                    ),
                )
                row = consonant_entry(
                    original["wav"],
                    original["alias"],
                    record["intervals"],
                    index,
                    record["duration"],
                )
                row.update(source_index=-2, preserve_alias=True, consonant_only=True)
        if prefix or suffix:
            row.update(alias_prefix=prefix, alias_suffix=suffix)
        result.append(row)
    return result


def create_alignment_engine(folder, mode, progress=lambda s: None, review=None):
    """Create the selected backend for both GUI jobs and packaged smoke checks."""
    if mode == "en_vccv":
        from english_vccv import EnglishVccvEngine

        return EnglishVccvEngine(folder, progress)
    elif mode == "en_cvvc":
        from english_cvvc import EnglishCvvcEngine

        return EnglishCvvcEngine(folder, progress)
    elif mode == "en_arpasing":
        from arpasing_core import EnglishEngine

        return EnglishEngine(folder, progress)
    elif is_korean(mode):
        from korean_core import KoreanEngine

        return KoreanEngine(review, progress)
    else:
        return Engine()


def run_folder(
    folder,
    progress=lambda s: None,
    cancelled=lambda: False,
    mode="vcv",
    review=None,
    only_files=None,
    base_report=None,
):
    folder = Path(folder)
    from format_detection import resolve_mode

    template, encoding = read_existing_oto(folder / "oto.ini")
    if mode == "en_vccv":
        from english_vccv import read_templates

        template, encoding = read_templates(folder)
    mode, detection = resolve_mode(folder, mode, template)
    if detection:
        progress(detection["warning"] or "녹음 리스트 자동 인식 완료")
    output = output_dir(folder, mode)
    output.mkdir(exist_ok=True)
    engine = create_alignment_engine(folder, mode, progress, review)
    entries, failures = [], []
    durations = {}
    records = {}
    # Ordinary recording starts take priority over the starts of dedicated breath files.
    files = sorted(folder.glob("*.wav"), key=lambda p: (p.stem.endswith("R"), p.name))
    if mode in ("en_arpasing", "en_cvvc", "en_vccv"):
        from arpasing_core import wav_files

        files = wav_files(folder)
    if template is not None:
        names = {r["wav"].replace("\\", "/").casefold() for r in template}
        files = [
            p
            for p in files
            if (
                p.relative_to(folder).as_posix()
                if mode in ("en_arpasing", "en_cvvc", "en_vccv")
                else p.name
            ).casefold()
            in names
        ]
    if only_files is not None:
        requested = {str(name).replace("\\", "/").casefold() for name in only_files}
        files = [folder / name for name in only_files]
        if any(
            not path.resolve().is_relative_to(folder.resolve())
            or not path.is_file()
            or path.suffix.lower() != ".wav"
            for path in files
        ):
            engine.close()
            raise ValueError("선택한 WAV 파일을 찾을 수 없습니다.")
        if template is not None:
            template = [
                r
                for r in template
                if r["wav"].replace("\\", "/").casefold() in requested
            ]
    for i, path in enumerate(files):
        if cancelled():
            engine.close()
            raise RuntimeError("사용자가 중지했습니다. 기존 oto.ini는 유지됩니다.")
        progress(f"{i+1}/{len(files)}  {path.name}")
        try:
            # Share phoneme boundaries across formats, including manual corrections.
            cache_dir = folder / "auto-vcv/labels"
            if only_files is not None and not mode.startswith("en_"):
                cache_dir = cache_dir / path.relative_to(folder).parent
            rows, record = engine.analyze(path, cache_dir, mode)
            if only_files is not None:
                name = path.relative_to(folder).as_posix()
                record["wav"] = name
                for row in rows:
                    row["wav"] = name
                save_record(folder, record)
            durations[record["wav"].casefold()] = record["duration"]
            records[record["wav"].casefold()] = record
            entries.extend(rows)
        except Exception as exc:
            failures.append(
                {
                    "wav": (
                        path.relative_to(folder).as_posix()
                        if mode in ("en_arpasing", "en_cvvc", "en_vccv")
                        else path.name
                    ),
                    "error": str(exc),
                }
            )
            progress(f"실패: {path.name}: {exc}")
    engine.close()
    if template is not None:
        if mode == "en_vccv":
            from english_vccv import match_template

            entries = match_template(template, entries, durations, records)
        elif mode == "en_cvvc":
            from english_cvvc import match_template

            entries = match_template(template, entries, durations, records)
        elif mode == "en_arpasing":
            from arpasing_core import match_template

            entries = match_template(template, entries, durations, records)
        elif is_korean(mode):
            from korean_core import match_existing_template
            from korean_formats import match_template

            entries = (
                match_existing_template(template, entries, durations, records)
                if mode == "ko_cvvc"
                else match_template(template, entries, durations, records, mode)
            )
        else:
            entries = apply_oto_template(template, entries, durations, records)
        removed = 0
    else:
        entries, removed = deduplicate(entries)
    report = {
        "mode": mode,
        "detection": detection,
        "rules_version": RULES_VERSION,
        "files": len(files),
        "successful_files": len(files) - len(failures),
        "entries": entries,
        "duplicates_removed": removed,
        "uses_existing_oto": template is not None,
        "oto_encoding": encoding,
        "failures": failures,
        "created": datetime.now().isoformat(),
    }
    if only_files is not None:
        previous = deepcopy(base_report or {})
        failed_names = {r["wav"].replace("\\", "/").casefold() for r in failures}
        replaced = requested - failed_names
        report["entries"] = [
            r
            for r in previous.get("entries", [])
            if r["wav"].replace("\\", "/").casefold() not in replaced
        ] + report["entries"]
        report["failures"] = [
            r
            for r in previous.get("failures", [])
            if r["wav"].replace("\\", "/").casefold() not in requested
        ] + failures
        report["files"] = max(
            previous.get("files", 0),
            len(
                set(r["wav"] for r in report["entries"])
                | set(r["wav"] for r in report["failures"])
            ),
        )
        report["successful_files"] = max(0, report["files"] - len(report["failures"]))
        report["inventory"] = previous.get("inventory", [])
        report["processed_files"] = list(only_files)
    persist_report(folder, report)
    progress(
        f"완료: {len(files)-len(failures)}/{len(files)} WAV, {len(entries)}개 원설, 중복 {removed}개 제거"
    )
    return report


def install_oto(folder, mode="vcv"):
    folder = Path(folder)
    if mode == "en_vccv" and not (folder / "oto.ini").exists():
        from english_vccv import install_nested_oto

        return install_nested_oto(folder)
    source = output_dir(folder, mode) / "oto.preview.ini"
    target = folder / "oto.ini"
    if target.exists():
        backup = folder / (
            "oto.backup." + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".ini"
        )
        backup.write_bytes(target.read_bytes())
    atomic_write(target, source.read_bytes())
    return target


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--mode", choices=list(FORMATS), default="vcv")
    args = parser.parse_args()
    result = run_folder(args.folder, lambda s: print(s, flush=True), mode=args.mode)
    if args.install and result["entries"]:
        print(install_oto(args.folder, result["mode"]))
    if result["failures"]:
        raise SystemExit(1)


def edit_oto_marker(row, index, seconds, duration):
    """Edit one absolute oto marker, preserving the other four absolute positions."""
    markers = list(row["absolute"])
    markers[index] = max(0.0, min(duration, float(seconds)))
    offset, overlap, pre, fixed, end = markers
    row["absolute"] = markers
    row["values"] = [
        offset * 1000,
        (fixed - offset) * 1000,
        -(end - offset) * 1000,
        (pre - offset) * 1000,
        (overlap - offset) * 1000,
    ]
    row["manual_oto"] = True
    warnings = []
    if end <= offset:
        warnings.append("컷오프가 오프셋보다 앞이거나 같음")
    if fixed < offset or fixed > end:
        warnings.append("고정 끝이 사용 구간 밖에 있음")
    if pre < offset or pre > end:
        warnings.append("선행이 사용 구간 밖에 있음")
    if overlap > pre:
        warnings.append("오버랩이 선행보다 뒤에 있음")
    if fixed < pre:
        warnings.append("고정 끝이 선행보다 앞: 청음 검토 필요")
    if row.get("mapping_warning"):
        warnings.append(row["mapping_warning"])
    row["warnings"] = warnings
    return markers[index]
