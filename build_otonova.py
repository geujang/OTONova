"""Build OtoNova on the validated v30 runtime without recompressing models."""

from pathlib import Path
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "release/OTONova-Windows-V2.0"


def main():
    if TARGET.exists():
        raise RuntimeError("Use a fresh distribution folder")
    shutil.copytree(
        ROOT / "release/OTONova-Windows-V1.5",
        TARGET,
        ignore=shutil.ignore_patterns(
            "*.log",
            "gui-preview.png",
            "__pycache__",
            "*.pyc",
            "WFL-Oto.exe",
            "OtoNova.exe",
        ),
    )
    for name in (
        "vcv_gui.py",
        "gui_workers.py",
        "gui_dialogs.py",
        "singer_settings.py",
        "singer_setup.py",
        "feedback_client.py",
        "external_files.py",
        "project_store.py",
        "audio_cache.py",
        "platform_support.py",
        "ui_settings.py",
        "vcv_core.py",
        "audio_view.py",
        "audio_playback.py",
        "formats.py",
        "format_detection.py",
        "english_cvvc.py",
        "english_vccv.py",
        "korean_core.py",
        "korean_formats.py",
        "korean_combined.py",
        "arpasing_core.py",
        "app_bootstrap.py",
        "README.md",
    ):
        shutil.copy2(ROOT / name, TARGET / name)
    shutil.copytree(ROOT / "assets", TARGET / "assets", dirs_exist_ok=True)
    shutil.copy2(ROOT / "CREDITS.md", TARGET / "CREDITS.md")
    for name in (
        "CODE_CLEANUP.md",
        "MODEL_COMPRESSION.md",
        "SUPPORTED_FORMATS.md",
        "THIRD_PARTY_NOTICES.md",
        "RELEASE_NOTES.md",
        "DEVELOPMENT.md",
        "USER_GUIDE.md",
    ):
        shutil.copy2(ROOT / name, TARGET / name)
    shutil.copy2(ROOT / "PROJECTS.md", TARGET / "PROJECTS.md")
    compiler = "C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    subprocess.run(
        [
            compiler,
            "/nologo",
            "/codepage:65001",
            "/target:winexe",
            "/platform:x64",
            "/reference:System.Windows.Forms.dll",
            "/win32icon:" + str(ROOT / "assets/otonova.ico"),
            "/out:" + str(TARGET / "OTONova.exe"),
            str(ROOT / "tools/distribution_launcher.cs"),
        ],
        check=True,
    )
    from tools.set_executable_icon import replace_icon

    replace_icon(TARGET / "runtime/pythonw.exe", ROOT / "assets/otonova.ico")
    (TARGET / "validation.json").write_text(
        json.dumps(
            dict(
                version="2.0",
                product="OTONova",
                inherited_validated_runtime=36,
                english_cvvc="DELTA + Salem alignment and oto",
                english_vccv="PaintedCz CORE 10 sections",
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    print(TARGET, flush=True)


if __name__ == "__main__":
    main()
