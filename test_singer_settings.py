"""Validate actual OpenUtau metadata, optional README, project drafts and ZIPs."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from copy import deepcopy
import tempfile
import time
import unittest
import zipfile

import numpy as np
import soundfile as sf
import yaml
from PySide6.QtWidgets import QApplication

from singer_settings import load_settings, metadata_files, save_settings, export_zip
from project_store import PROJECT_NAME, open_project
from vcv_gui import Window

APP = QApplication.instance() or QApplication([])


def settle(window):
    until = time.monotonic() + 10
    while (
        (window.asset_worker and window.asset_worker.isRunning())
        or window.wave._load_jobs
    ) and time.monotonic() < until:
        APP.processEvents()
        time.sleep(0.01)
    APP.processEvents()


class SingerSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "Voicebank"
        self.root.mkdir()
        sf.write(self.root / "a.wav", np.zeros(16000), 16000)
        (self.root / "oto.ini").write_bytes(
            "a.wav=か,0,100,-900,50,20\n".encode("cp932")
        )
        self.data = load_settings(self.root)
        self.data.update(
            name="테스트 가수", author="제작자", text_file_encoding="utf-8"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_existing_utf16_txt_readme_and_legacy_yaml_name(self):
        (self.root / "CHARACTER.TXT").write_text(
            "名前=기존 가수\nAuthor=TXT author\nVoice by=CV name\n", encoding="utf-16"
        )
        (self.root / "CHARACTET.YAML").write_text(
            "name: ''\nauthor: YAML author\ntext_file_encoding: shift_jis\nportrait_opacity: 0.5\nsubbanks:\n- color: Power\n  prefix: ''\n  suffix: C4\n  tone_ranges: [C1-B7]\n",
            encoding="utf-8",
        )
        (self.root / "README.TXT").write_text("기존 사용 안내", encoding="utf-16")
        data = load_settings(self.root)
        self.assertEqual(data["name"], "기존 가수")
        self.assertEqual(data["author"], "YAML author")
        self.assertEqual(data["voice"], "CV name")
        self.assertEqual(data["readme"], "기존 사용 안내")
        self.assertTrue(data["readme_enabled"])
        self.assertEqual(data["subbanks"][0]["suffix"], "C4")
        self.assertEqual(data["portrait_opacity"], 0.5)

    def test_stage_entry_refreshes_existing_files_without_overwriting_edits(self):
        from unittest.mock import patch
        from PySide6.QtCore import QSettings

        settings = QSettings(
            str(Path(self.tmp.name) / "reload-ui.ini"), QSettings.IniFormat
        )
        window = Window(settings)
        try:
            window.open_folder(self.root)
            settle(window)
            (self.root / "character.txt").write_text(
                "name=Existing singer\nauthor=Existing author\n", encoding="utf-8"
            )
            (self.root / "readme.txt").write_text("Existing README", encoding="utf-8")
            window.set_stage(3)
            panel = window.singer_setup
            self.assertEqual(panel.inputs["name"].text(), "Existing singer")
            self.assertEqual(panel.inputs["author"].text(), "Existing author")
            self.assertTrue(panel.readme_enabled)
            self.assertEqual(panel.readme.toPlainText(), "Existing README")
            panel.inputs["name"].setText("Unsaved edit")
            (self.root / "character.txt").write_text(
                "name=Updated on disk\n", encoding="utf-8"
            )
            window.set_stage(1)
            window.set_stage(3)
            self.assertEqual(panel.inputs["name"].text(), "Unsaved edit")
            from PySide6.QtWidgets import QMessageBox

            with patch(
                "singer_setup.QMessageBox.question", return_value=QMessageBox.No
            ):
                panel.reload_button.click()
            self.assertEqual(panel.inputs["name"].text(), "Unsaved edit")
            with patch(
                "singer_setup.QMessageBox.question", return_value=QMessageBox.Yes
            ):
                panel.reload_button.click()
            self.assertEqual(panel.inputs["name"].text(), "Updated on disk")
            self.assertFalse(panel.dirty)
        finally:
            settle(window)
            window.close()
            APP.processEvents()

    def test_empty_legacy_project_singer_draft_does_not_hide_existing_files(self):
        import json
        from PySide6.QtCore import QSettings

        settings = QSettings(
            str(Path(self.tmp.name) / "legacy-ui.ini"), QSettings.IniFormat
        )
        window = Window(settings)
        try:
            window.open_folder(self.root)
            settle(window)
            window.save_project_snapshot()
            path = self.root / PROJECT_NAME
            saved = json.loads(path.read_text(encoding="utf-8"))
            saved["singer_settings"].pop("_draft_dirty", None)
            path.write_text(json.dumps(saved), encoding="utf-8")
            (self.root / "character.txt").write_text(
                "name=Loaded from existing file\n", encoding="utf-8"
            )
            window.restore_project(path)
            settle(window)
            window.set_stage(3)
            self.assertEqual(
                window.singer_setup.inputs["name"].text(), "Loaded from existing file"
            )
        finally:
            settle(window)
            window.close()
            APP.processEvents()

    def test_metadata_uses_official_fields_and_preserves_extra_yaml(self):
        self.data["_yaml"] = {
            "localized_names": {"ja-JP": "名前"},
            "use_filename_as_alias": False,
        }
        self.data.update(
            default_phonemizer="OpenUtau.Plugin.Builtin.JapaneseVCVPhonemizer",
            subbanks=[
                dict(color="power", prefix="", suffix="C4", tone_ranges=["C1-B3", "C4"])
            ],
        )
        files = metadata_files(self.root, self.data)
        self.assertEqual(set(files), {"character.txt", "character.yaml"})
        self.assertIn("name=테스트 가수", files["character.txt"].decode("utf-8-sig"))
        config = yaml.safe_load(files["character.yaml"])
        self.assertEqual(config["singer_type"], "utau")
        self.assertEqual(config["localized_names"], {"ja-JP": "名前"})
        self.assertEqual(config["subbanks"][0]["tone_ranges"], ["C1-B3", "C4"])
        self.assertEqual(config["text_file_encoding"], "utf-8")
        self.assertNotIn("charactet.yaml", files)

    def test_zip_contains_audio_latest_oto_assets_and_optional_readme(self):
        outside = Path(self.tmp.name) / "portrait.png"
        outside.write_bytes(b"test portrait")
        self.data.update(portrait=str(outside), readme_enabled=True, readme="사용 안내")
        for folder in [".otonova-cache", "auto-vcv", ".git"]:
            (self.root / folder).mkdir()
            (self.root / folder / "private.txt").write_text("not for release")
        (self.root / PROJECT_NAME).write_text("private project")
        (self.root / "oto.backup.old.ini").write_text("old")
        wav = (self.root / "a.wav").read_bytes()
        original_oto = (self.root / "oto.ini").read_bytes()
        report = {
            "entries": [dict(wav="a.wav", alias="新しい", values=[10, 20, -800, 30, 5])]
        }
        output = self.root / "result.zip"
        export_zip(self.root, output, self.data, report)
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            config = yaml.safe_load(archive.read("Voicebank/character.yaml"))
            self.assertEqual(archive.read("Voicebank/a.wav"), wav)
            self.assertEqual(
                archive.read("Voicebank/readme.txt").decode("utf-8-sig"), "사용 안내"
            )
            self.assertIn(
                "a.wav=新しい,10.000,20.000,-800.000,30.000,5.000",
                archive.read("Voicebank/oto.ini").decode("utf-8-sig"),
            )
            self.assertEqual(
                archive.read("Voicebank/" + config["portrait"]), b"test portrait"
            )
            self.assertFalse(
                any(
                    "auto-vcv" in n
                    or ".otonova" in n
                    or ".git" in n
                    or "backup" in n
                    or n.endswith(".zip")
                    for n in names
                )
            )
        self.assertEqual((self.root / "oto.ini").read_bytes(), original_oto)
        self.data["readme_enabled"] = False
        export_zip(self.root, output, self.data, report)
        with zipfile.ZipFile(output) as archive:
            self.assertNotIn("Voicebank/readme.txt", archive.namelist())

    def test_zip_excludes_loose_alignment_caches_but_keeps_real_dictionary(self):
        import json

        for directory in ["cache", "Labels", "logits", "AUTO-WFL-JA"]:
            path = self.root / directory
            path.mkdir()
            (path / "private.txt").write_text("cache")
        files = ["audio.npz", "features.npy", "boundaries.lab", "old.pyc"]
        for name in files:
            (self.root / name).write_bytes(b"cache")
        (self.root / "loose-labels.json").write_text(
            json.dumps(dict(wav="a.wav", intervals=[[0, 1, "a"]], phones=["a"]))
        )
        (self.root / "old-report.json").write_text(
            json.dumps(dict(rules_version=1, entries=[]))
        )
        (self.root / "dictionary.json").write_text(
            json.dumps({"words": {"word": ["w", "er", "d"]}})
        )
        (self.root / "a.wav.frq").write_bytes(b"UTAU frequency data")
        output = Path(self.tmp.name) / "clean.zip"
        export_zip(self.root, output, self.data)
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            self.assertIn("Voicebank/dictionary.json", names)
            self.assertIn("Voicebank/a.wav.frq", names)
            self.assertFalse(
                any(
                    name.endswith(
                        (
                            ".npz",
                            ".npy",
                            ".lab",
                            ".pyc",
                            "loose-labels.json",
                            "old-report.json",
                        )
                    )
                    or "/cache/" in name
                    or "/Labels/" in name
                    or "/logits/" in name
                    or "/AUTO-" in name
                    for name in names
                )
            )
        self.assertTrue(all((self.root / name).exists() for name in files))
        self.assertTrue((self.root / "loose-labels.json").exists())

    def test_cancel_preserves_existing_zip_and_removes_temporary_output(self):
        output = Path(self.tmp.name) / "export.zip"
        output.write_bytes(b"previous ZIP")
        with self.assertRaises(RuntimeError):
            export_zip(self.root, output, self.data, cancelled=lambda: True)
        self.assertEqual(output.read_bytes(), b"previous ZIP")
        self.assertFalse(list(output.parent.glob(".otonova-export-*")))

    def test_save_and_remove_readme_back_up_previous_files(self):
        self.data.update(readme_enabled=True, readme="first README")
        save_settings(self.root, self.data)
        loaded = load_settings(self.root)
        self.assertEqual(loaded["name"], "테스트 가수")
        self.assertEqual(loaded["readme"], "first README")
        self.assertIn("か", (self.root / "oto.ini").read_text(encoding="utf-8-sig"))
        loaded["readme_enabled"] = False
        save_settings(self.root, loaded)
        self.assertFalse((self.root / "readme.txt").exists())
        self.assertTrue(list(self.root.glob("readme.txt.backup.*")))

    def test_nested_oto_replaces_known_wav_without_losing_unprocessed_aliases(self):
        pitch = self.root / "C4"
        pitch.mkdir()
        sf.write(pitch / "a.wav", np.zeros(8000), 8000)
        (self.root / "oto.ini").write_text(
            "a.wav=keep,0,1,-2,3,4\nC4/a.wav=old,0,1,-2,3,4\n", encoding="utf-8"
        )
        self.data["_source_encoding"] = "utf-8"
        output = Path(self.tmp.name) / "nested.zip"
        export_zip(
            self.root,
            output,
            self.data,
            {"entries": [dict(wav="C4/a.wav", alias="new", values=[1, 2, -3, 4, 5])]},
        )
        with zipfile.ZipFile(output) as archive:
            self.assertIn("keep", archive.read("Voicebank/oto.ini").decode("utf-8-sig"))
            self.assertNotIn(
                "old", archive.read("Voicebank/oto.ini").decode("utf-8-sig")
            )
            self.assertIn(
                "a.wav=new", archive.read("Voicebank/C4/oto.ini").decode("utf-8-sig")
            )

    def test_export_action_creates_zip_in_background_and_reenables_window(self):
        from unittest.mock import patch
        from PySide6.QtCore import QSettings

        settings = QSettings(str(Path(self.tmp.name) / "ui.ini"), QSettings.IniFormat)
        window = Window(settings)
        try:
            window.open_folder(self.root)
            settle(window)
            window.set_stage(3)
            panel = window.singer_setup
            panel.add_readme.click()
            panel.readme.setPlainText("README from the UI")
            output = Path(self.tmp.name) / "ui-export.zip"
            with patch(
                "singer_setup.QFileDialog.getSaveFileName",
                return_value=(str(output), "ZIP (*.zip)"),
            ):
                panel.export_button.click()
            deadline = time.monotonic() + 10
            while panel.export_worker.isRunning() and time.monotonic() < deadline:
                APP.processEvents()
                time.sleep(0.01)
            APP.processEvents()
            self.assertTrue(window.isEnabled())
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(
                    archive.read("Voicebank/readme.txt").decode("utf-8-sig"),
                    "README from the UI",
                )
        finally:
            settle(window)
            window.close()
            APP.processEvents()

    def test_declared_oto_charset_is_respected_when_converting(self):
        (self.root / "oto.ini").write_bytes(
            "#Charset: utf-8\na.wav=한국어,0,100,-900,50,20\n".encode("utf-8")
        )
        self.data["_source_encoding"] = "cp932"
        output = Path(self.tmp.name) / "charset.zip"
        export_zip(self.root, output, self.data)
        with zipfile.ZipFile(output) as archive:
            text = archive.read("Voicebank/oto.ini").decode("utf-8-sig")
            self.assertIn("한국어", text)
            self.assertNotIn("#Charset:", text)

    def test_stage_three_and_optional_readme_draft_survive_project_restore(self):
        window = Window()
        try:
            window.open_folder(self.root)
            settle(window)
            window.set_stage(3)
            self.assertEqual(window.workspace_stack.currentIndex(), 1)
            panel = window.singer_setup
            panel.inputs["name"].setText("저장된 이름")
            panel.set_readme_enabled(True)
            panel.readme.setPlainText("미완성 설명")
            panel.add_bank(
                dict(color="normal", prefix="", suffix="C4", tone_ranges=["C1-B7"])
            )
            window.save_project_snapshot()
            saved = open_project(self.root / PROJECT_NAME)
            self.assertEqual(saved["stage"], 3)
            self.assertEqual(saved["singer_settings"]["name"], "저장된 이름")
            panel.set_readme_enabled(False)
            self.assertFalse(panel.snapshot()["readme_enabled"])
            window.restore_project(self.root / PROJECT_NAME)
            settle(window)
            self.assertEqual(window.stage, 3)
            self.assertTrue(window.singer_setup.readme_enabled)
            self.assertEqual(window.singer_setup.readme.toPlainText(), "미완성 설명")
            self.assertEqual(window.singer_setup.banks.rowCount(), 1)
            window.set_stage(1)
            self.assertEqual(window.workspace_stack.currentIndex(), 0)
            window.set_stage(2)
            self.assertFalse(window.table.isHidden())
        finally:
            settle(window)
            window.close()
            APP.processEvents()


if __name__ == "__main__":
    unittest.main()
