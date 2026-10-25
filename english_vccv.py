"""PaintedCz CORE VCCV notation and boundary-based, tutorial-specific oto rules."""

from pathlib import Path
from functools import lru_cache
from copy import deepcopy
import gzip, hashlib, json, re, sys

VERSION = 1
SECTIONS = ("CC-", "CCV", "CV", "CVC_CV", "CV_CVC", "V", "VC", "VCC", "VV", "_CV")
VOWELS = set("a e i o u A E I O 9 6 3 Q 8 @ x 0 & 1 Ang Ank nn mm ll nng".split())
MAP = {p: [p] for p in "b d f g k l m n p r s t v w y z".split()}
MAP.update(
    {
        k: v.split()
        for k, v in {
            "a": "aa",
            "e": "eh",
            "i": "ih",
            "o": "uw",
            "u": "ah",
            "A": "ey",
            "E": "iy",
            "I": "ay",
            "O": "ow",
            "9": "ao",
            "0": "ao",
            "6": "uh",
            "3": "er",
            "Q": "oy",
            "8": "aw",
            "@": "ae",
            "x": "ax",
            "&": "ae",
            "1": "ih",
            "h": "hh",
            "hh": "hh y",
            "j": "jh",
            "ch": "ch",
            "sh": "sh",
            "zh": "zh",
            "th": "th",
            "dh": "dh",
            "ng": "ng",
            "dd": "dx",
            "Ang": "ae ng",
            "Ank": "ae ng k",
            "nn": "ax n",
            "mm": "ax m",
            "ll": "ax l",
            "nng": "ax ng",
        }.items()
    }
)
APPROX = {"&", "1", "Ang", "Ank", "nn", "mm", "ll", "nng", "hh"}


@lru_cache(None)
def catalog():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return json.loads(
        gzip.decompress((root / "assets/vccv-core-catalog.json.gz").read_bytes())
    )


def fingerprint(name):
    return hashlib.sha256(name.encode()).hexdigest()[:24]


def tokens(text):
    alphabet = sorted(MAP, key=lambda p: (-len(p), p))
    result = []
    pos = 0
    while pos < len(text):
        symbol = next((p for p in alphabet if text.startswith(p, pos)), None)
        if symbol is None:
            raise ValueError("VCCV 미지원 기호: " + text[pos:] + " (" + text + ")")
        if symbol in ("Ang", "Ank"):
            result.append(
                dict(symbol="A", model=["ae"], kind="vowel", approximation="nasal ae")
            )
            result.append(
                dict(
                    symbol="ng" if symbol == "Ang" else "n",
                    model=["ng"],
                    kind="consonant",
                )
            )
            if symbol == "Ank":
                result.append(dict(symbol="k", model=["k"], kind="consonant"))
        else:
            result.append(
                dict(
                    symbol=symbol,
                    model=MAP[symbol],
                    kind="vowel" if symbol in VOWELS else "consonant",
                )
            )
        pos += len(symbol)
    if not result:
        raise ValueError("빈 VCCV 발음열")
    return result


def parse_recording(stem, section):
    """Leading category tags are organizational; underscores separate recorded syllables."""
    if section not in SECTIONS:
        raise ValueError("VCCV 구역을 확인해주세요: " + section)
    if section in ("CC-", "VC", "VCC"):
        parts = stem.split("_")
        parts = parts[1:]  # b__ / l_ / r__ are NOT uttered.
    else:
        parts = stem.split("_")
    parts = [p.strip("-") for p in parts if p.strip("-")]
    if section == "VV":
        if len(parts) != 1:
            raise ValueError("VCCV VV 파일명 형식을 확인해주세요.")
        seq = tokens(parts[0])
        # A nasal/rhotic tail belongs to the second vowel, not a third VV nucleus.
        return [seq]
    return [tokens(p) for p in parts]


def names(stem):
    yield stem
    base = re.sub(r"(?:[_ -]?[A-G][#b]?[0-9])$", "", stem)
    yield base
    parts = base.split("_")
    for i in range(len(parts)):
        for j in range(i + 1, len(parts) + 1):
            value = "_".join(parts[i:j])
            yield value
            # Prefixes may be attached to the obligatory leading - or _ marker.
            if not value.startswith(("-", "_")):
                yield "-" + value
                yield "_" + value


class VccvResolver:
    def __init__(self, folder):
        from arpasing_core import wav_files

        self.folder = Path(folder).resolve()
        self.files = wav_files(self.folder)
        self.data = catalog()["sections"]

    def resolve(self, path):
        path = Path(path).resolve()
        section = next(
            (
                p
                for p in reversed(path.relative_to(self.folder).parts[:-1])
                if p in SECTIONS
            ),
            None,
        )
        matches = []
        for name in dict.fromkeys(names(path.stem)):
            h = fingerprint(name)
            for key, entries in self.data.items():
                if section and section != key:
                    continue
                if h in entries:
                    matches.append((len(name), key, name, entries[h]))
        if matches:
            length = max(m[0] for m in matches)
            best = [m for m in matches if m[0] == length]
            families = {m[1] for m in best}
            if len(families) > 1:
                raise ValueError(
                    "VCCV 구역이 모호합니다. "
                    + ", ".join(sorted(families))
                    + " 폴더를 구분해주세요."
                )
            _, section, name, info = best[0]
            return section, name, info
        if section:
            name = re.sub(r"(?:[_ -]?[A-G][#b]?[0-9])$", "", path.stem)
            parse_recording(name, section)
            return (
                section,
                name,
                dict(
                    aliases=[],
                    listed=False,
                    warning="미등록 VCCV 변형 파일: 기존 oto 에일리어스가 필요합니다.",
                ),
            )
        raise ValueError(
            "CORE VCCV 리스트를 인식하지 못했습니다. 구역별 폴더/파일명을 확인해주세요: "
            + path.name
        )

    def metadata(self, path):
        path = Path(path).resolve()
        section, name, info = self.resolve(path)
        if not info["aliases"]:
            raise ValueError(
                "미등록 VCCV 파일: 공식 CORE 기본 에일리어스 계획이 없습니다. "
                + path.name
            )
        groups = parse_recording(name, section)
        phones = ["SP"]
        units = []
        mapped_groups = []
        notes = []
        for group in groups:
            ids = []
            for unit in group:
                indices = list(range(len(phones), len(phones) + len(unit["model"])))
                phones.extend(unit["model"])
                ids.append(len(units))
                units.append(dict(unit, indices=indices))
                if unit["symbol"] in APPROX or unit.get("approximation"):
                    notes.append(
                        unit["symbol"]
                        + " → "
                        + " ".join(unit["model"])
                        + " 근사: 비음화/음절성 차이 확인"
                    )
            mapped_groups.append(ids)
            # VV is one continuous recording; other underscore-separated syllables pause.
            phones.append("SP")
        if info.get("warning"):
            notes.append(info["warning"])
        if info.get("inferred_aliases"):
            notes.append(
                "공식 기본 oto의 빈/누락 에일리어스를 구역 규칙으로 보완: "
                + ", ".join(info["inferred_aliases"])
            )
        return dict(
            wav=path.relative_to(self.folder).as_posix(),
            format="en_vccv",
            phones=phones,
            vccv_version=VERSION,
            vccv_section=section,
            vccv_units=units,
            vccv_groups=mapped_groups,
            vccv_aliases=info["aliases"],
            vccv_registered=info.get("listed", False),
            vccv_inferred_aliases=info.get("inferred_aliases", []),
            arpasing_units=[
                dict(phone=u["symbol"], indices=u["indices"]) for u in units
            ],
            label_warnings=list(dict.fromkeys(notes)),
            input_source="CORE VCCV catalog",
        )


def detect(folder, template=None):
    resolver = VccvResolver(folder)
    counts = {}
    failures = []
    matched = 0
    details = []
    for p in resolver.files:
        try:
            section, _, info = resolver.resolve(p)
            counts[section] = counts.get(section, 0) + 1
            matched += bool(info.get("listed"))
            details.append(
                dict(
                    wav=p.relative_to(resolver.folder).as_posix(),
                    recognized=bool(info.get("listed")),
                    profiles=[section],
                )
            )
        except ValueError as exc:
            failures.append(
                dict(wav=p.relative_to(resolver.folder).as_posix(), error=str(exc))
            )
            details.append(
                dict(
                    wav=p.relative_to(resolver.folder).as_posix(),
                    recognized=False,
                    profiles=[],
                )
            )
    return dict(
        selected_mode="en_vccv",
        files=len(resolver.files),
        recognized_files=matched,
        sections=counts,
        input_failures=failures,
        file_details=details,
        warning=(str(len(failures)) + "개 VCCV 파일 인식 실패" if failures else ""),
        summary=f"PaintedCz CORE VCCV · WAV {matched}/{len(resolver.files)}개 공식 리스트 일치",
    )


def read_templates(folder):
    from vcv_core import read_existing_oto

    root = Path(folder)
    template, encoding = read_existing_oto(root / "oto.ini")
    if template is not None:
        return template, encoding
    rows = []
    encodings = []
    for path in sorted(root.rglob("oto.ini")):
        relative = path.relative_to(root)
        if any(s.startswith("auto-") for s in relative.parts[:-1]):
            continue
        items, enc = read_existing_oto(path)
        if items is None:
            continue
        encodings.append(enc)
        for row in items:
            row = deepcopy(row)
            row["wav"] = (relative.parent / row["wav"].replace("\\", "/")).as_posix()
            rows.append(row)
    return (rows, "utf-8") if encodings else (None, encoding)


def install_nested_oto(folder, backup=True, wav=None):
    """Write VCCV otos beside their WAVs; never leave stale nested templates active."""
    from datetime import datetime
    from vcv_core import output_dir, atomic_write, read_existing_oto

    root = Path(folder).resolve()
    report = json.loads(
        (output_dir(root, "en_vccv") / "report.json").read_text(encoding="utf-8")
    )
    grouped = {}
    only_parent = (root / wav.replace("\\", "/")).resolve().parent if wav else None
    for row in report["entries"]:
        wav = (root / row["wav"].replace("\\", "/")).resolve()
        try:
            wav.relative_to(root)
        except ValueError:
            raise ValueError("선택 폴더 밖의 WAV에는 VCCV oto를 저장하지 않습니다.")
        if only_parent is None or wav.parent == only_parent:
            grouped.setdefault(wav.parent / "oto.ini", []).append(
                dict(row, wav=wav.name)
            )
    writes = []
    for target, rows in grouped.items():
        _, encoding = read_existing_oto(target)
        content = "".join(
            row["wav"]
            + "="
            + row["alias"]
            + ","
            + ",".join(f"{v:.3f}" for v in row["values"])
            + "\n"
            for row in rows
        )
        writes.append((target, content.encode(encoding)))
    for target, data in writes:
        target.parent.mkdir(parents=True, exist_ok=True)
        if backup and target.exists():
            backup_path = target.with_name(
                "oto.backup." + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".ini"
            )
            backup_path.write_bytes(target.read_bytes())
        atomic_write(target, data)
    return root


def alias_kind(alias, section):
    if section == "VV":
        return "vv"
    if section == "CCV":
        return "start_cc" if alias.startswith("-") else "onset_cc"
    if section == "_CV":
        return "inner_cv"
    if section == "V":
        return (
            "start_v"
            if alias.startswith("-")
            else (
                "inner_v"
                if alias.startswith("_")
                else "v_tail" if alias.endswith("-") else "v"
            )
        )
    if section == "CV":
        return (
            "bridge" if " " in alias else "start_cv" if alias.startswith("-") else "cv"
        )
    if section == "CV_CVC":
        return (
            "bridge"
            if " " in alias
            else (
                "start_cv"
                if alias.startswith("-")
                else (
                    "vc_tail"
                    if alias.endswith("-")
                    else "cv" if not alias[0] in VOWELS else "vc"
                )
            )
        )
    if section == "CVC_CV":
        return (
            "bridge" if " " in alias else "start_cv" if alias.startswith("-") else "cv"
        )
    if section in ("VC", "VCC", "CC-"):
        ending = alias.endswith("-")
        if section == "CC-":
            return "cc_tail" if ending else "cc"
        # In VCC, aliases beginning in a consonant are the CC/CC- rows.
        starts_vowel = any(alias.startswith(s) for s in VOWELS)
        if section == "VCC" and not starts_vowel:
            return "cc_tail" if ending else "cc"
        return "vc_tail" if ending else "vc"
    raise ValueError("VCCV 에일리어스 형식을 확인해주세요: " + alias)


def create_oto(record):
    from vcv_core import make_entry

    spans = record["intervals"]
    duration = record["duration"]
    section = record["vccv_section"]
    rows = []
    units = [
        dict(u, start=spans[u["indices"][0]][0], end=spans[u["indices"][-1]][1])
        for u in record["vccv_units"]
    ]
    groups = [[units[i] for i in ids] for ids in record["vccv_groups"]]

    def geometry(alias, kind):
        index = 0
        if section == "CV_CVC" and kind == "vc":
            index = 1
        if kind in ("cv", "onset_cc", "inner_v", "vc_tail", "cc_tail"):
            index = (
                2
                if section == "CVC_CV"
                and kind == "cv"
                or section == "CV_CVC"
                and kind == "vc_tail"
                else 1
            )
        group = groups[min(index, len(groups) - 1)]
        vs = [u for u in group if u["kind"] == "vowel"]
        if not vs:
            raise ValueError("VCCV 모음 경계 없음: " + alias)
        vowel = vs[0]
        last_v = vs[-1]
        onset = [u for u in group if u["end"] <= vowel["start"] + 1e-8]
        coda = [u for u in group if u["start"] >= last_v["end"] - 1e-8]
        start = group[0]["start"]
        end = group[-1]["end"]
        notes = []
        if kind in ("start_cv", "cv", "inner_cv", "start_v", "inner_v"):
            pre = vowel["start"]
            off = (
                max(0, start - 0.12)
                if kind.startswith("start")
                else onset[-1]["start"] if onset else pre
            )
            if kind == "inner_cv" and len(onset) > 1:
                off = onset[-1]["start"]
            fixed = min(vowel["end"] - 0.005, pre + 0.06)
            cut = max(fixed + 0.005, last_v["end"] - 0.02)
        elif kind in ("start_cc", "onset_cc"):
            if len(onset) < 2:
                raise ValueError("VCCV 자음군 경계 부족: " + alias)
            pre = onset[-1]["start"]
            off = (
                max(0, onset[0]["start"] - 0.12)
                if kind == "start_cc"
                else onset[0]["start"]
            )
            fixed = onset[-1]["end"] + 0.02
            cut = max(fixed + 0.02, last_v["end"] - 0.02)
        elif kind == "bridge":
            left = groups[0]
            right = groups[1] if len(groups) > 1 else groups[0]
            lv = [u for u in left if u["kind"] == "vowel"][-1]
            right_c = next((u for u in right if u["kind"] == "consonant"), right[0])
            # A spaced C C bridge excludes the vowel; a V C bridge includes it.
            lhs = alias.split()[0]
            lhs_tokens = tokens(lhs)
            left_c = [u for u in left if u["start"] >= lv["end"] - 1e-8]
            consonant_only = all(u["kind"] == "consonant" for u in lhs_tokens)
            off = (
                left_c[0]["start"] if consonant_only and left_c else lv["start"] + 0.02
            )
            pre = left[-1]["end"] if section == "CVC_CV" else lv["end"]
            fixed = right_c["end"] + 0.02
            cut = fixed + 0.04
        elif kind in ("vc", "vc_tail", "cc", "cc_tail"):
            if not coda:
                raise ValueError("VCCV 말미 자음 경계 없음: " + alias)
            off = coda[0]["start"] if kind.startswith("cc") else vowel["start"] + 0.02
            if kind.endswith("tail"):
                pre = (
                    coda[0]["end"]
                    if section == "VCC"
                    and len(coda) > 1
                    or section == "CC-"
                    and len(coda) > 1
                    else last_v["end"]
                )
                fixed = coda[-1]["end"] + 0.02
                cut = fixed + 0.15
            else:
                pre = coda[-1]["end"]
                fixed = pre + 0.02
                cut = fixed + 0.02
                notes.append("기식 별도 경계 없음: 자음 끝을 선행 기준으로 사용")
        elif kind == "vv":
            if len(vs) < 2:
                raise ValueError("VCCV VV 모음 경계 부족: " + alias)
            off = vowel["start"] + 0.02
            pre = vs[1]["start"]
            fixed = min(vs[1]["end"] - 0.005, pre + 0.06)
            cut = max(fixed + 0.005, vs[-1]["end"] - 0.02)
        elif kind == "v":
            off = vowel["start"] + 0.02
            pre = off + 0.06
            fixed = pre + 0.06
            cut = max(fixed + 0.005, last_v["end"] - 0.02)
        elif kind == "v_tail":
            off = vowel["start"] + 0.02
            pre = last_v["end"]
            fixed = end + 0.02
            cut = fixed + 0.15
        else:
            raise ValueError(kind)
        if kind in ("vc_tail", "cc_tail", "v_tail") and index + 1 < len(groups):
            cut = min(cut, groups[index + 1][0]["start"])
        off = max(0, min(off, duration))
        cut = max(off, min(cut, duration))
        pre = max(off, min(pre, cut))
        fixed = min(fixed, cut)
        over = (off + pre) / 2
        return off, over, pre, fixed, cut, notes

    aliases = record["vccv_aliases"]
    if not aliases:
        raise ValueError("미등록 VCCV 파일: 기본 에일리어스 계획이 없습니다.")
    for source_index, alias in enumerate(aliases):
        kind = alias_kind(alias, section)
        off, over, pre, fixed, cut, notes = geometry(alias, kind)
        row = make_entry(
            record["wav"],
            alias,
            off,
            over,
            pre,
            fixed,
            cut,
            duration,
            notes,
            fixed_lead=cut - fixed,
        )
        if alias in record.get("vccv_inferred_aliases", []):
            row["warnings"].append(
                "공식 기본 oto의 빈/누락 에일리어스를 구역 규칙으로 생성: 확인 필요"
            )
        row.update(source_index=source_index, entry_kind="vccv_" + kind)
        # Absolute midpoint makes the required relative overlap = preutterance / 2.
        row["values"][4] = row["values"][3] / 2
        row["absolute"][1] = row["absolute"][0] + row["values"][4] / 1000
        rows.append(row)
    return rows


def match_template(template, generated, durations, records):
    from english_cvvc import match_template as match

    # Whitespace is semantic: V C must never be matched to VC.
    def key(value):
        return re.sub(r"\s+", " ", value.strip())

    rows = match(template, generated, durations, records, key_function=key)
    for row in rows:
        if row.get("unmapped_template"):
            row["warnings"] = [
                "VCCV 에일리어스 대응 불가: 기존 값 유지, 경계 이동 시 연동"
            ]
    return rows


from arpasing_core import EnglishEngine as _EnglishEngine


class EnglishVccvEngine(_EnglishEngine):
    def __init__(self, folder, progress=lambda _: None):
        super().__init__(folder, progress)
        self.resolver = VccvResolver(folder)
        self.oto_factory = create_oto

    def analyze(self, path, cache_dir, mode="en_vccv"):
        return super().analyze(path, cache_dir, mode)
