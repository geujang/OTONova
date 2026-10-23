"""COC/CBNN/CMPX spelling and alias recipes, sharing the CVVC timing rules."""

from functools import lru_cache
from pathlib import Path
import gzip, json, re, sys, unicodedata

MODES = {"ko_coc", "ko_cbnn", "ko_cmpx"}
VOWELS = {
    "a",
    "i",
    "u",
    "e",
    "o",
    "eu",
    "eo",
    "ae",
    "oe",
    "uy",
    "ui",
    "eui",
    "er",
    "ER",
}
CODA = {"n": "N", "m": "M", "ng": "NG", "l": "L", "k": "K", "t": "T", "p": "P"}
TOKENS = sorted(
    VOWELS
    | set(CODA)
    | set(CODA.values())
    | set("gbdrsjhfvzcyw")
    | {
        "gg",
        "dd",
        "bb",
        "kk",
        "tt",
        "pp",
        "jj",
        "ss",
        "ch",
        "th",
        "rr",
        "RR",
        "R",
        "H",
        "GS",
        "Rb",
        "B",
        "E",
        "Y",
        "W",
        "EU",
        "br",
    },
    key=lambda x: (-len(x), x),
)


@lru_cache(maxsize=1)
def catalog():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return json.loads(
        gzip.decompress((root / "assets/korean-combined-catalog.json.gz").read_bytes())
    )


def resolve_stem(stem, mode):
    from format_detection import stem_variants, fingerprint

    known = catalog()[mode]["recordings"]
    for value in stem_variants(unicodedata.normalize("NFC", stem)):
        if fingerprint(value) in known:
            return value
    return unicodedata.normalize("NFC", stem)


def units(text):
    text = text.replace("Long", "").replace("~", "E")
    output = []
    pos = 0
    while pos < len(text):
        if text[pos].isdigit():
            if not output:
                raise ValueError("모음 없는 숫자 접미사: " + text)
            output[-1][1] += text[pos]
            pos += 1
            continue
        breath = re.match(r"(?:dynbr|slowbr|fastbr|br)\d+", text[pos:])
        token = (
            breath[0]
            if breath
            else next(
                (
                    p
                    for p in TOKENS
                    if text.startswith(p, pos)
                    and not (p == "er" and text.startswith("err", pos))
                ),
                None,
            )
        )
        if token is None:
            raise ValueError("지원하지 않는 조합형 표기: " + text[pos:])
        output.append([token, ""])
        pos += len(token)
    return output


def metadata(stem, mode, lookup=True, collapse=True):
    from korean_core import PHONE_SUBSTITUTIONS

    original = resolve_stem(stem, mode) if lookup else stem
    if original.casefold() == "breath":
        return dict(
            phones=["SP", "AP", "SP"],
            source_phones=["SP", "br", "SP"],
            phone_roles=["pause", "breath", "pause"],
            phone_tags=["", "", ""],
            phone_groups=[-1, 0, 1],
            onset_indices=[],
            format=mode,
            reclist_stem=original,
            label_warnings=[
                "breath: 여러 br 별칭은 같은 호흡 구간을 공유하므로 청음 확인 필요"
            ],
        )
    text = original.split("+", 1)[-1] if "+" in original else original
    # COC hyphens separate sung morae; CBNN/CMPX underscores indicate rests.
    chunks = re.split(r"([_])|['\-\s]+", text)
    phones = ["SP"]
    source = ["SP"]
    roles = ["pause"]
    tags = [""]
    groups = [-1]
    warnings = []

    def append(p, s, role, tag, group):
        phones.append(p)
        source.append(s)
        roles.append(role)
        tags.append(tag)
        groups.append(group)

    group = 0
    for chunk in chunks:
        if not chunk:
            continue
        if chunk == "_":
            if phones[-1] != "SP":
                append("SP", "SP", "pause", "", group)
            group += 1
            continue
        parsed = (
            units(chunk[:-2]) + [["er", ""]]
            if chunk.endswith("er") and len(chunk) > 2
            else units(chunk)
        )
        for i, (symbol, tag) in enumerate(parsed):
            after = parsed[i + 1][0] if i + 1 < len(parsed) else ""
            before = parsed[i - 1][0] if i else ""
            role = "onset"
            mapped = PHONE_SUBSTITUTIONS.get(
                symbol,
                {
                    "Y": "y",
                    "W": "w",
                    "EU": "eu",
                    "gg": "kk",
                    "dd": "tt",
                    "bb": "pp",
                }.get(symbol, symbol),
            )
            if symbol == "EU":
                role = "vowel"
            if symbol in VOWELS:
                expansion = {
                    "ae": ["e"],
                    "oe": ["w", "e"],
                    "uy": ["w", "i"],
                    "ui": ["eu", "i"],
                    "eui": ["eu", "i"],
                    "ER": ["er"],
                }.get(symbol, [symbol])
                for n, p in enumerate(expansion):
                    r = (
                        "vowel"
                        if n == len(expansion) - 1
                        else ("vowel" if p == "eu" else "onset")
                    )
                    if n and expansion[0] == "eu":
                        r = "vowel_continuation"
                    if symbol in ["er", "ER"] and before in VOWELS:
                        r = "coda"
                    append(p, symbol if n == len(expansion) - 1 else p, r, tag, group)
                continue
            if symbol in ["y", "w", "Y", "W"] and not after:
                mapped = "i" if symbol.lower() == "y" else "u"
                role = "vowel"
                symbol = symbol.upper()
            elif symbol in CODA.values() or (
                symbol in CODA and before in VOWELS and after not in VOWELS | {"y", "w"}
            ):
                mapped = CODA.get(symbol, symbol)
                role = "coda"
            elif symbol == "ng":
                mapped = "NG"
            if symbol in ["R", "Rb", "B"] or "br" in symbol:
                mapped = "AP"
                role = "breath"
            if symbol == "H":
                mapped = "axh"
                role = "breath"
            if symbol == "GS":
                mapped = "cl"
                role = "fry"
            if symbol == "E":
                mapped = "vf"
                role = "fry"
            if symbol == "RR":
                mapped = "r"
                warnings.append("RR: 한국어 r로 경계 추정, 원래 에일리어스 유지")
            if symbol == "c":
                mapped = "s"
            if before in VOWELS and symbol == "er":
                role = "coda"
            if symbol in ["f", "v", "z", "rr", "th"]:
                warnings.append(
                    symbol
                    + " → "
                    + mapped
                    + ": 기존 모델 치환 사용, 원래 에일리어스 유지"
                )
            append(mapped, symbol, role, tag, group)
        group += 1
    if phones[-1] != "SP":
        append("SP", "SP", "pause", "", group)
    from korean_core import collapse_onset_glides

    return (collapse_onset_glides if collapse else lambda data: data)(
        dict(
            phones=phones,
            source_phones=source,
            phone_roles=roles,
            phone_tags=tags,
            phone_groups=groups,
            onset_indices=[i for i, r in enumerate(roles) if r == "onset"],
            format=mode,
            reclist_stem=original,
            label_warnings=list(dict.fromkeys(warnings)),
        )
    )


def transcribe(stem, mode):
    data = metadata(stem, mode)
    return data["phones"], data["source_phones"], data["phone_roles"]


def alias_recipe(alias, record):
    if record.get("glide_source"):
        shadow = dict(record)
        shadow.update(record["glide_source"])
        shadow.pop("glide_source", None)
        result = _alias_recipe(alias, shadow)
        if result:
            kind, indices, note = result
            return (
                kind,
                list(dict.fromkeys(record["glide_to_label"][i] for i in indices)),
                note,
            )
        return None
    return _alias_recipe(alias, record)


def _alias_recipe(alias, record):
    """Find recorded phones for an alias, keeping suffix numbers out of alignment."""
    clean = alias.strip().lstrip("_")
    initial = clean.startswith("- ")
    if initial:
        clean = clean[2:]
    parts = clean.split()
    tail = len(parts) > 1 and parts[-1] in ["-", "R", "H", "~", "*", "GS", "Rb", "B"]
    body = " ".join(parts[:-1]) if tail else clean
    query = metadata(
        body.replace(" ", "'"), record["format"], lookup=False, collapse=False
    )
    wanted = query["phones"][1:-1]
    tagged = query["phone_tags"][1:-1]

    # Uppercase aliases describe a held semivowel; lowercase coda/onset share sound.
    def equal(a, b):
        if (
            a == b
            or (a in CODA.values() and b == a.lower())
            or (b in CODA.values() and a == b.lower())
        ):
            return True
        if (a, b) in [("y", "i"), ("w", "u")]:
            return True
        if record["format"] in ["ko_coc", "ko_cmpx"] and (a, b) in [
            ("kk", "K"),
            ("tt", "T"),
            ("pp", "P"),
        ]:
            return True
        return False

    actual = record["phones"]
    roles = record["phone_roles"]
    matches = []
    for i in range(1, len(actual) - len(wanted)):
        indices = list(range(i, i + len(wanted)))
        if not all(equal(actual[j], p) for j, p in zip(indices, wanted)):
            continue
        if any(
            tag and tag != record["phone_tags"][j] for j, tag in zip(indices, tagged)
        ):
            continue
        score = sum(
            record["source_phones"][j] == p
            for j, p in zip(indices, query["source_phones"][1:-1])
        )
        start = roles[i - 1] in ["pause", "breath", "fry"]
        if initial:
            score += 10 if start else -10
        elif not tail and len(parts) == 1:
            score += 2 if not start else 0
        if tail:
            score += 3 if roles[indices[-1] + 1] in ["pause", "breath", "fry"] else 0
        matches.append((score, -i, indices))
    note = None
    if not matches and len(parts) == 2 and parts[0] == parts[1]:
        # Self-VV aliases intentionally reuse a held vowel.
        shortened = alias_recipe(parts[0], record)
        if shortened:
            return (*shortened[:2], "동일 모음 VV: 녹음된 지속 모음 구간 사용")
    if not matches:
        if record.get("reclist_stem", "").casefold() == "breath" and alias in [
            "h",
            "h -",
        ]:
            return (
                "tail" if alias.endswith(" -") else "cv",
                [1],
                "호흡 녹음의 h 별칭: 청음 확인 필요",
            )
        return None
    indices = max(matches)[2]
    if tail:
        kind = "tail"
    elif initial:
        kind = "start"
    elif len(parts) == 2:
        right_query = metadata(parts[1], record["format"], lookup=False, collapse=False)
        vowel_right = all(
            r in ["vowel", "vowel_continuation"] or p in ["y", "w"]
            for p, r in zip(
                right_query["phones"][1:-1], right_query["phone_roles"][1:-1]
            )
        )
        kind = (
            (
                "vv"
                if query["phone_roles"][1] in ["vowel", "vowel_continuation"]
                else "cv"
            )
            if vowel_right
            else "vc"
        )
    elif query["phone_roles"][-2] == "coda" and any(
        roles[j] == "vowel" for j in indices
    ):
        kind = "vc"
    elif any(roles[j] in ["vowel", "vowel_continuation"] for j in indices):
        kind = "cv"
    else:
        kind = "consonant"
    return kind, indices, note


def make_alias(alias, record):
    from vcv_core import make_entry, two_thirds

    recipe = alias_recipe(alias, record)
    if recipe is None:
        return None
    kind, indices, note = recipe
    spans = record["intervals"]
    roles = record["phone_roles"]
    duration = record["duration"]
    first, last = indices[0], indices[-1]
    off = spans[first][0]
    pre = off
    if kind == "tail":
        right = min(last + 1, len(spans) - 1)
        pre = spans[right][0]
        off = two_thirds(spans[last])
        overlap = off + (pre - off) * 0.75
        cut = min(duration, pre + 0.7)
        lead = 0.2
    elif kind in ["vc", "vv"]:
        right = next(
            (j for j in indices[1:] if roles[j] not in ["vowel_continuation"]), last
        )
        pre = spans[right][0]
        if kind == "vv":
            off = two_thirds(spans[first])
            overlap = spans[first][1]
            cut = two_thirds(spans[last])
            lead = 0.04
        else:
            off = spans[first][0] + (spans[first][1] - spans[first][0]) * 0.8
            overlap = off + (pre - off) * 2 / 3
            cut = pre + (spans[last][1] - pre) / 2
            lead = 0.015
    elif kind == "consonant":
        # Consonant-only and ending consonants use the final pause as preutterance.
        pause = next((s for s in reversed(spans) if s[2] == "SP"), spans[-1])
        pre = pause[0]
        off = two_thirds(spans[first])
        overlap = (off + pre) / 2
        fixed = pause[0] + (pause[1] - pause[0]) / 3
        cut = fixed + 0.02
        lead = 0.02
    else:
        vowel = next(
            (j for j in indices if roles[j] in ["vowel", "vowel_continuation"]), None
        )
        pre = spans[vowel][0] if vowel is not None else spans[first][0]
        cut = two_thirds(spans[last])
        lead = 0.07
        if kind == "start":
            off = spans[first][0] - 0.3
            overlap = spans[first][0]
        else:
            off = spans[first][0] + (pre - spans[first][0]) / 3
            overlap = (off + pre) / 2
    row = make_entry(
        record["wav"],
        alias,
        off,
        overlap,
        pre,
        cut - lead,
        cut,
        duration,
        [note] if note else [],
        fixed_lead=lead,
        allow_negative_overlap=True,
    )
    row.update(
        entry_kind=kind, phone_indices=indices, combined_alias=alias, source_index=-1
    )
    return row


def create_oto(record, mode):
    from format_detection import fingerprint

    aliases = catalog()[mode]["recordings"].get(
        fingerprint(record.get("reclist_stem", "")), []
    )
    if not aliases:
        # An existing custom oto is handled below; unknown filenames still get CVVC rows.
        from korean_formats import create_oto as common

        shadow = dict(record, format="ko_cvvc_malcha")
        return common(shadow, "ko_cvvc_malcha")
    rows = []
    for alias in aliases:
        row = make_alias(alias, record)
        if row is None:
            # Never silently substitute an unrelated sound for a supplied alias.
            from vcv_core import make_entry

            row = make_entry(
                record["wav"],
                alias,
                0,
                0,
                0,
                0,
                record["duration"],
                record["duration"],
                ["리스트 에일리어스의 음소 대응 없음: 경계·발음 확인 필요"],
            )
            row.update(entry_kind="unresolved", combined_alias=alias, phone_indices=[])
        row["source_index"] = len(rows)
        rows.append(row)
    return rows
