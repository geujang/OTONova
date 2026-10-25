"""Romaji filenames must share kana alignment and keep existing OTO aliases."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import unittest

from vcv_core import Engine, parse_name, create_oto, apply_oto_template


class JapaneseRomajiTests(unittest.TestCase):
    def test_common_morae_and_continuous_or_separated_names(self):
        pairs = [
            ("a_a_i_a_u_e_a", "ああいあうえあ"),
            ("aaiauea", "ああいあうえあ"),
            ("aka", "あか"),
            ("a_ka", "あか"),
            ("KA_KI_KU", "かきく"),
            ("shi_chi_tsu_fu_ji", "しちつふじ"),
            ("kya_kyu_kyo_she_che_je", "きゃきゅきょしぇちぇじぇ"),
            ("kwa_thi_dhi", "くぁてぃでぃ"),
            ("si_ti_tu_hu_zi_tya", "しちつふじちゃ"),
            ("akka", "あっか"),
            ("konnichiwa", "こんにちわ"),
            ("an", "あん"),
            ("anna", "あんな"),
            ("n'a", "んあ"),
            ("aN", "あん"),
            ("ann", "あん"),
            ("xa_xtsu", "ぁっ"),
            ("aaR", "ああR"),
            ("あkaシ", "あかし"),
        ]
        for roman, kana in pairs:
            with self.subTest(roman=roman):
                self.assertEqual(parse_name(roman), parse_name(kana))

    def test_consonant_only_and_breath_conventions_are_preserved(self):
        for name, phone in [
            ("k -", "k"),
            ("n", "n"),
            ("d", "d"),
            ("kw", "k"),
            ("nw", "n"),
            ("ty", "t"),
        ]:
            self.assertEqual(parse_name(name)[0]["phones"], [phone])
        self.assertTrue(parse_name("R")[0]["breath"])

    def test_romaji_existing_aliases_and_affixes_keep_exact_timing(self):
        spans = [
            [0, 1, "pau"],
            [1, 2, "k"],
            [2, 3, "a"],
            [3, 4, "sh"],
            [4, 5, "i"],
            [5, 6, "pau"],
        ]
        rows = create_oto("kashi.wav", parse_name("kashi"), spans, 6, "vcv_cvvc")
        roman = {"- か": "- ka", "a し": "a shi", "か": "ka", "し": "shi"}
        for prefix, suffix in [("", ""), ("強_", "A4")]:
            template = [
                dict(row, alias=prefix + roman.get(row["alias"], row["alias"]) + suffix)
                for row in rows
            ]
            result = apply_oto_template(template, rows, {"kashi.wav": 6})
            self.assertEqual(
                [r["alias"] for r in result], [r["alias"] for r in template]
            )
            self.assertEqual([r["values"] for r in result], [r["values"] for r in rows])
            self.assertFalse(any(r.get("unmapped_template") for r in result))

    def test_all_japanese_modes_analyze_romaji_and_reuse_boundaries(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Japanese").mkdir()
            (root / "Japanese/last.ckpt").touch()
            audio = root / "kashi.wav"
            audio.write_bytes(b"fake WAV for mocked inference")
            backend = Mock()
            phones = ["SP", "k", "a", "sh", "i", "SP"]
            backend.request.return_value = dict(
                duration=3,
                intervals=[[i * 0.5, (i + 1) * 0.5, p] for i, p in enumerate(phones)],
            )
            engine = Engine.__new__(Engine)
            engine.backend = backend
            with patch("vcv_core.WORKSPACE", root):
                for mode in ["ja_cv", "vcv", "cvvc", "vcv_cvvc"]:
                    rows, record = engine.analyze(audio, root / "labels", mode)
                    self.assertTrue(rows)
                    self.assertEqual(
                        record["phones"], ["pau", "k", "a", "sh", "i", "pau"]
                    )
                    self.assertTrue(any("か" in row["alias"] for row in rows))
            self.assertEqual(backend.request.call_count, 1)
            self.assertEqual(backend.request.call_args.args[1], phones)


if __name__ == "__main__":
    unittest.main()
