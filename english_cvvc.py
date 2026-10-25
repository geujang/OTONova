"""DELTA / Salem CVVC: original alias symbols, explicit English model mapping."""

from pathlib import Path
from functools import lru_cache
import gzip
import hashlib
import json
import re
import sys


def canonical(text):
    # Case distinguishes X-SAMPA phones: preserve it throughout recognition.
    return text.strip().lstrip("_+")


def fingerprint(text):
    return hashlib.sha256(canonical(text).encode()).hexdigest()[:24]


@lru_cache(None)
def catalog():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return json.loads(
        gzip.decompress((root / "assets/english-cvvc-catalog.json.gz").read_bytes())
    )


def candidates(stem):
    yield fingerprint(stem)
    base = re.sub(r"(?:[_ -]?[A-G][#b]?[0-9])$", "", stem)
    yield fingerprint(base)
    parts = base.split("_")
    for i in range(len(parts)):
        for j in range(i + 1, len(parts) + 1):
            yield fingerprint("_".join(parts[i:j]))


def read_lines(path):
    raw = path.read_bytes()
    encodings = (
        ["utf-16"]
        if raw.startswith((b"\xff\xfe", b"\xfe\xff"))
        else ["utf-8-sig", "cp932", "cp949", "cp1252"]
    )
    for encoding in encodings:
        try:
            return [
                line.strip()
                for line in raw.decode(encoding).splitlines()
                if line.strip()
            ]
        except UnicodeError:
            continue
    return []


def detect(folder, template=None):
    root = Path(folder)
    profiles = catalog()["profiles"]
    known = {key: set(p["fingerprints"]) for key, p in profiles.items()}
    wavs = sorted(
        (
            p
            for p in root.rglob("*")
            if p.is_file()
            and p.suffix.lower() == ".wav"
            and not any(
                part.startswith("auto-") for part in p.relative_to(root).parts[:-1]
            )
        ),
        key=str,
    )
    observed = [(p.relative_to(root).as_posix(), set(candidates(p.stem))) for p in wavs]
    list_groups = []
    for path in root.glob("*.txt"):
        if path.stat().st_size > 5_000_000:
            continue
        for line in read_lines(path):
            list_groups.append(set(candidates(line)))
    template_groups = [
        set(candidates(Path(row["wav"].replace("\\", "/")).stem))
        for row in (template or [])
    ]
    ranked = []
    for key, hashes in known.items():
        matches = sum(bool(values & hashes) for _, values in observed)
        lists = sum(bool(values & hashes) for values in list_groups)
        templates = sum(bool(values & hashes) for values in template_groups)
        if matches or lists or templates:
            ranked.append(
                dict(
                    profile=key,
                    family=profiles[key]["family"],
                    edition=profiles[key]["edition"],
                    beats=profiles[key]["beats"],
                    section=profiles[key]["section"],
                    matched_files=matches,
                    list_matches=lists,
                    template_matches=templates,
                )
            )
    ranked.sort(
        key=lambda p: (p["matched_files"], p["list_matches"], p["template_matches"]),
        reverse=True,
    )
    core = [p for p in ranked if p["section"] == "core"]
    selection = core or ranked
    best = selection[0] if selection else None
    tied = [
        p
        for p in selection
        if best
        and (p["matched_files"], p["list_matches"], p["template_matches"])
        == (best["matched_files"], best["list_matches"], best["template_matches"])
    ]
    details = []
    for name, hashes in observed:
        matching = [key for key, values in known.items() if values & hashes]
        details.append(dict(wav=name, profiles=matching, recognized=bool(matching)))
    recognized = sum(p["recognized"] for p in details)
    warning = "" if ranked else "등록된 영어 CVVC 리스트와 일치하지 않습니다."
    if ranked and len(tied) > 1:
        warning = "공통 항목만 있어 LITE/FULL 또는 박 수를 확정할 수 없습니다."
    if ranked and wavs and recognized < len(wavs):
        warning += (
            " " if warning else ""
        ) + "일부 WAV는 등록된 리스트와 일치하지 않습니다."
    families = sorted({p["family"] for p in ranked})
    return dict(
        selected_mode="en_cvvc",
        recognition_only=False,
        family="/".join(families) if ranked else None,
        profile=tied[0]["profile"] if len(tied) == 1 else None,
        candidates=[p["profile"] for p in tied],
        components=ranked,
        files=len(wavs),
        recognized_files=recognized,
        list_matches=sum(
            any(values & hashes for hashes in known.values()) for values in list_groups
        ),
        file_details=details,
        warning=warning,
        summary=(("/".join(families)) + " 영어 CVVC" if ranked else "영어 CVVC 미확인")
        + f" · WAV {recognized}/{len(wavs)}개 공식 리스트 일치",
    )


VERSION = 2
VOWELS = set(
    "@ { A E I i O U u V aI eI OI aU oU @r @l 3 a o e 1 {~ E~ I~ Ar Er Ir Or Al il Ol ul mm nn } Q VI VU aU~ 3r ar or Ur aIr aUr {l al El el Il Ul aIl aUl NN".split()
)
MAP = {p: [p] for p in "p b t d k g f v s z m n l r w".split()}
MAP.update(
    {
        k: v.split()
        for k, v in {
            "@": "ax",
            "{": "ae",
            "A": "aa",
            "E": "eh",
            "I": "ih",
            "i": "iy",
            "O": "ao",
            "U": "uh",
            "u": "uw",
            "V": "ah",
            "aI": "ay",
            "eI": "ey",
            "OI": "oy",
            "aU": "aw",
            "oU": "ow",
            "@r": "er",
            "3": "er",
            "@l": "ax l",
            "a": "aa",
            "o": "ao",
            "e": "eh",
            "1": "ih",
            "{~": "ae",
            "E~": "eh",
            "I~": "ih",
            "Ar": "aa r",
            "Er": "eh r",
            "Ir": "ih r",
            "Or": "ao r",
            "Al": "aa l",
            "il": "iy l",
            "Ol": "ao l",
            "ul": "uw l",
            "mm": "m",
            "nn": "n",
            "NN": "ng",
            "}": "uw",
            "Q": "aa",
            "VI": "ay",
            "VU": "aw",
            "aU~": "aw",
            "3r": "er",
            "ar": "aa r",
            "or": "ao r",
            "Ur": "uh r",
            "aIr": "ay r",
            "aUr": "aw r",
            "{l": "ae l",
            "al": "aa l",
            "El": "eh l",
            "el": "eh l",
            "Il": "ih l",
            "Ul": "uh l",
            "aIl": "ay l",
            "aUl": "aw l",
            "h": "hh",
            "N": "ng",
            "j": "y",
            "tS": "ch",
            "dZ": "jh",
            "T": "th",
            "D": "dh",
            "S": "sh",
            "Z": "zh",
            "ts": "t s",
            "dz": "d z",
            "'": "q",
            "4": "dx",
            "ph": "p",
            "th": "t",
            "kh": "k",
            "C": "hh",
            "5": "l",
            "4~": "dx",
            "x": "k",
            "W": "w",
            "hh": "SP",
        }.items()
    }
)
DIRECT = set(
    "@ { A E I i O U u V aI eI OI aU oU @r 3 p b t d k g f v s z m n l r w h N j tS dZ T D S Z ts dz".split()
) | {"'", "4"}
DELTA = {
    "o+i+": "OI",
    "ai+": "aI",
    "ei+": "eI",
    "au+": "aU",
    "ou+": "oU",
    "i+": "I",
    "e+": "E",
    "a+": "A",
    "o+": "O",
    "v+": "V",
    "u+": "U",
    "t+": "T",
    "d+": "D",
    "s+": "S",
    "z+": "Z",
    "n+": "N",
    "ts+": "tS",
    "dz+": "dZ",
    "{+": "{",
    "e": "E",
}


def parse_sequence(sequence, family="DELTA", section="core"):
    """Parse notation before translation: never lowercase X-SAMPA or guess words."""
    delta = family == "DELTA"
    aliases = {k: k for k in MAP}
    if delta:
        aliases.update(DELTA)
    aliases["ju"] = "ju"
    alphabet = sorted(aliases, key=lambda s: (-len(s), s))
    units = []
    warnings = []
    pos = 0
    while pos < len(sequence):
        if sequence[pos] in "_- ":
            end = pos + 1
            while end < len(sequence) and sequence[end] in "_- ":
                end += 1
            sep = sequence[pos:end]
            if (
                not delta
                and ("__" in sep or section == "cvc" and "_" in sep)
                and units
                and units[-1]["kind"] not in ("pause", "breath")
            ):
                units.append(dict(symbol="SP", model=["SP"], kind="pause"))
            pos = end
            continue
        # j+u is two original symbols; only its model vowel is overridden to uh.
        if sequence.startswith("ju", pos) and not sequence.startswith("ju+", pos):
            units.extend(
                [
                    dict(symbol="j", model=["y"], kind="consonant"),
                    dict(symbol="u", model=["uh"], kind="vowel"),
                ]
            )
            pos += 2
            continue
        raw = next(
            (s for s in alphabet if s != "ju" and sequence.startswith(s, pos)), None
        )
        if raw is None:
            raise ValueError(
                "DELTA/Salem 미지원 표기: " + sequence[pos:] + " (" + sequence + ")"
            )
        symbol = aliases[raw]
        model = MAP[symbol]
        kind = (
            "breath" if symbol == "hh" else "vowel" if symbol in VOWELS else "consonant"
        )
        units.append(dict(symbol=symbol, model=model, kind=kind))
        if symbol not in DIRECT:
            warnings.append(
                symbol
                + " → "
                + " ".join(model)
                + " 경계 추정용 근사"
                + (" (숨을 SP로 추정)" if symbol == "hh" else "")
            )
        pos += len(raw)
    while units and units[-1]["kind"] == "pause":
        units.pop()
    if not units:
        raise ValueError("음소 표기가 없습니다.")
    return units, list(dict.fromkeys(warnings))


class CvvcResolver:
    def __init__(self, folder):
        from arpasing_core import wav_files

        self.folder = Path(folder).resolve()
        self.files = wav_files(folder)
        self.profiles = catalog()["profiles"]
        self.lookup = {}
        for key, p in self.profiles.items():
            for h in p["fingerprints"]:
                self.lookup.setdefault(h, []).append(key)
        scores = {}
        for p in self.files:
            for _, ids in self.matches(p.stem):
                for family in {self.profiles[k]["family"] for k in ids}:
                    scores[family] = scores.get(family, 0) + 1
        self.default_family = (
            max(scores, key=scores.get)
            if scores
            and len([v for v in scores.values() if v == max(scores.values())]) == 1
            else None
        )

    def matches(self, stem):
        base = re.sub(r"(?:[_ -]?[A-G][#b]?[0-9])$", "", stem)
        parts = base.split("_")
        names = {stem, base}
        names.update(
            "_".join(parts[i:j])
            for i in range(len(parts))
            for j in range(i + 1, len(parts) + 1)
        )
        for name in sorted(names, key=len, reverse=True):
            ids = self.lookup.get(fingerprint(name))
            if ids:
                yield name, ids

    def metadata(self, path):
        path = Path(path).resolve()
        relative = path.relative_to(self.folder).as_posix()
        matches = list(self.matches(path.stem))
        profiles = []
        if matches:
            name, profiles = matches[0]
            families = {self.profiles[k]["family"] for k in profiles}
            if len(families) > 1:
                raise ValueError("DELTA/Salem 표기가 모호합니다: " + path.name)
            family = next(iter(families))
            section = self.profiles[profiles[0]]["section"]
        else:
            name = re.sub(r"(?:[_ -]?[A-G][#b]?[0-9])$", "", path.stem)
            family = (
                "DELTA"
                if re.search(r"(?<=[a-z{}])\+", canonical(name))
                else self.default_family
            )
            if family is None:
                raise ValueError(
                    "DELTA 또는 Salem 리스트를 확정할 수 없습니다: " + path.name
                )
            section = "core"
        sequence = canonical(name)
        units, notes = parse_sequence(sequence, family, section)
        phones = ["SP"]
        mapped = []
        for unit in units:
            indices = list(range(len(phones), len(phones) + len(unit["model"])))
            phones.extend(unit["model"])
            mapped.append(dict(unit, indices=indices))
        if phones[-1] != "SP":
            phones.append("SP")
        return dict(
            wav=relative,
            phones=phones,
            cvvc_units=mapped,
            format="en_cvvc",
            cvvc_version=VERSION,
            cvvc_family=family,
            cvvc_profiles=profiles,
            input_source="official-list" if profiles else "filename",
            # Compatibility for the common inference/cache engine, not alias generation.
            arpasing_units=[
                dict(phone=u["symbol"], indices=u["indices"]) for u in mapped
            ],
            label_warnings=notes,
            breath_proxy=any(u["kind"] == "breath" for u in mapped),
        )


def create_oto(record):
    from vcv_core import make_entry

    spans = record["intervals"]
    duration = record["duration"]
    rows = []
    units = [
        dict(u, start=spans[u["indices"][0]][0], end=spans[u["indices"][-1]][1])
        for u in record["cvvc_units"]
    ]

    def add(alias, off, over, pre, cut, lead, kind, fixed=None):
        row = make_entry(
            record["wav"],
            alias,
            off,
            over,
            pre,
            cut - lead if fixed is None else fixed,
            cut,
            duration,
            [],
            fixed_lead=lead,
            allow_negative_overlap=True,
        )
        row.update(entry_kind=kind, source_index=len(rows))
        rows.append(row)

    def fraction(u, f):
        return u["start"] + (u["end"] - u["start"]) * f

    for i, u in enumerate(units):
        if u["kind"] in ("pause", "breath"):
            continue
        previous = units[i - 1] if i else None
        following = units[i + 1] if i + 1 < len(units) else None
        if u["kind"] == "vowel":
            # Consecutive consonants are one CV onset, with suffix CVs for template compatibility.
            start = i
            while start and units[start - 1]["kind"] == "consonant":
                start -= 1
            cut = fraction(u, 2 / 3)
            if start == i:
                if previous is None or previous["kind"] in ("pause", "breath"):
                    add(
                        "- " + u["symbol"],
                        u["start"] - 0.3,
                        u["start"],
                        u["start"],
                        cut,
                        0.07,
                        "start",
                    )
                add(u["symbol"], u["start"], u["start"], u["start"], cut, 0.07, "v")
                if previous and previous["kind"] == "vowel":
                    add(
                        previous["symbol"] + " " + u["symbol"],
                        fraction(previous, 2 / 3),
                        previous["end"],
                        u["start"],
                        cut,
                        0.04,
                        "vv",
                    )
            else:
                first = units[start]
                alias = "".join(x["symbol"] for x in units[start : i + 1])
                if start == 0 or units[start - 1]["kind"] in ("pause", "breath"):
                    add(
                        "- " + alias,
                        first["start"] - 0.3,
                        first["start"],
                        u["start"],
                        cut,
                        0.07,
                        "start",
                    )
                for j in range(start, i):
                    off = units[j]["start"] + (u["start"] - units[j]["start"]) / 3
                    add(
                        "".join(x["symbol"] for x in units[j : i + 1]),
                        off,
                        (off + u["start"]) / 2,
                        u["start"],
                        cut,
                        0.07,
                        "cv",
                    )
            if following and following["kind"] == "vowel":
                continue
            # Include all recorded coda clusters as VC aliases, preserving original notation.
            j = i + 1
            while j < len(units) and units[j]["kind"] == "consonant":
                c = units[j]
                off = fraction(u, 3 / 4)
                pre = units[i + 1]["start"]
                end = fraction(c, 0.5)
                alias = (
                    u["symbol"]
                    + " "
                    + "".join(x["symbol"] for x in units[i + 1 : j + 1])
                )
                add(alias, off, off + (pre - off) / 4, pre, end, 0.015, "vc")
                if j + 1 == len(units) or units[j + 1]["kind"] in ("pause", "breath"):
                    add(
                        alias + "-",
                        off,
                        off + (pre - off) / 4,
                        pre,
                        end,
                        0.015,
                        "vc",
                    )
                j += 1
        if following and following["kind"] == "consonant" and u["kind"] == "consonant":
            off = fraction(u, 0.8)
            pre = following["start"]
            add(
                u["symbol"] + " " + following["symbol"],
                off,
                off + (pre - off) * 2 / 3,
                pre,
                fraction(following, 0.5),
                0.015,
                "cc",
            )
        if following is None or following["kind"] in ("pause", "breath"):
            pre = following["start"] if following else spans[-1][0]
            off = fraction(u, 2 / 3)
            over = off + (pre - off) * 0.75
            if u["kind"] == "vowel":
                fixed = pre + 0.5
                cut = fixed + 0.2
                lead = 0.2
            else:
                pause_end = following["end"] if following else spans[-1][1]
                fixed = pre + (pause_end - pre) / 3
                cut = fixed + 0.02
                lead = 0.02
            add(
                u["symbol"]
                + (" hh" if following and following["kind"] == "breath" else " -"),
                off,
                over,
                pre,
                cut,
                lead,
                "tail",
                fixed,
            )
            if u["kind"] == "consonant":
                add(u["symbol"], off, over, pre, cut, lead, "tail", fixed)
    return rows


def match_template(template, generated, durations, records, key_function=None):
    from copy import deepcopy
    from arpasing_core import match_template as match

    # Normalize whitespace only: I/i, T/t, 1 etc are meaningful original symbols.
    @lru_cache(maxsize=8192)
    def key(value):
        parts = []
        for part in value.strip().split():
            if part == "-":
                parts.append(part)
                continue
            ending = part.endswith("-")
            base = part[:-1] if ending else part
            try:
                units, _ = parse_sequence(base, "DELTA")
                parts.append(
                    "".join(u["symbol"] for u in units) + ("-" if ending else "")
                )
            except ValueError:
                parts.append(part)
        return re.sub(r"\s*-\s*", "-", " ".join(parts))

    if key_function is not None:
        key = key_function
    grouped = {}
    for g in generated:
        name = g["wav"].replace("\\", "/").casefold()
        grouped.setdefault(name, {}).setdefault(key(g["alias"]), []).append(g)
    rows = match(template, generated, durations, records, key_function=key)
    for r in rows:
        if r.get("unmapped_template"):
            candidates = grouped.get(r["wav"].replace("\\", "/").casefold(), {})
            alias = r["alias"]
            found = []
            for left in range(len(alias)):
                for right in range(left + 1, len(alias) + 1):
                    prefix, suffix = alias[:left], alias[right:]
                    if prefix and not (
                        prefix.endswith(("_", " ", "-"))
                        or any(ord(c) > 127 for c in prefix)
                    ):
                        continue
                    if suffix and not (
                        suffix.startswith(("_", " ", "#"))
                        or re.fullmatch(r"[A-G][#b]?[0-9]", suffix)
                    ):
                        continue
                    sound = key(alias[left:right])
                    found.extend((right - left, g) for g in candidates.get(sound, []))
            if found:
                longest = max(n for n, g in found)
                target = (r["values"][0] + r["values"][3]) / 1000
                replacement = deepcopy(
                    min(
                        (g for n, g in found if n == longest),
                        key=lambda g: abs(g["absolute"][2] - target),
                    )
                )
                replacement.update(wav=r["wav"], alias=r["alias"], preserve_alias=True)
                r.clear()
                r.update(replacement)
        if r.get("unmapped_template"):
            r["warnings"] = [
                "DELTA/Salem 에일리어스 대응 불가: 기존 값 유지, 경계 이동 시 연동"
            ]
    return rows


from arpasing_core import EnglishEngine as _EnglishEngine


class EnglishCvvcEngine(_EnglishEngine):
    def __init__(self, folder, progress=lambda _: None):
        super().__init__(folder, progress)
        self.resolver = CvvcResolver(folder)
        self.oto_factory = create_oto

    def analyze(self, path, cache_dir, mode="en_cvvc"):
        return super().analyze(path, cache_dir, mode)
