"""Background file inventory, external reload and display-cache preparation.

These workers only prepare data. GUI state is applied on the main Qt thread.
"""

from pathlib import Path
from PySide6.QtCore import QThread, Signal
from project_store import scan_folder


class FileScanner(QThread):
    completed = Signal(object)

    def __init__(self, folder):
        super().__init__()
        self.folder = folder

    def run(self):
        from external_files import snapshot

        try:
            self.completed.emit(snapshot(self.folder))
        except OSError:
            pass


class ExternalReload(QThread):
    completed = Signal(object)

    def __init__(self, folder, wavs, oto):
        super().__init__()
        self.folder = Path(folder)
        self.wavs = wavs
        self.oto = oto

    def run(self):
        from audio_cache import get
        from project_store import signature

        result = {"wavs": {}, "errors": [], "report": None}
        for name in self.wavs:
            try:
                path = self.folder / name
                if not path.exists():
                    result["wavs"][name] = None
                    continue
                before = signature(path)
                data = get(path, self.folder / ".otonova-cache", before)
                if signature(path) != before:
                    raise ValueError(
                        "다시 로드 중 WAV가 변경되었습니다. 다시 확인해주세요."
                    )
                result["wavs"][name] = {
                    "signature": before,
                    "duration": len(data["samples"]) / int(data["sample_rate"]),
                }
            except Exception as exc:
                result["errors"].append(name + ": " + str(exc))
        if self.oto:
            try:
                _, result["report"], _ = scan_folder(
                    self.folder, prefer_report=False, include_records=False
                )
            except Exception as exc:
                result["errors"].append(str(exc))
        self.completed.emit(result)


class FolderLoader(QThread):
    indexed = Signal(object, object, object)
    progress = Signal(str)
    failed = Signal(str)

    def __init__(self, folder, scan=True):
        super().__init__()
        self.folder = Path(folder)
        self.scan = scan

    def run(self):
        try:
            if self.scan:
                inventory, report, records = scan_folder(self.folder)
                self.indexed.emit(inventory, report, records)
                names = list(inventory)
            else:
                names = [
                    p.relative_to(self.folder).as_posix()
                    for p in self.folder.rglob("*")
                    if p.is_file() and p.suffix.lower() == ".wav"
                ]
            from audio_cache import get

            for i, name in enumerate(names):
                if self.isInterruptionRequested():
                    return
                try:
                    get(self.folder / name, self.folder / ".otonova-cache")
                except Exception as exc:
                    self.progress.emit(name + ": " + str(exc))
                    continue
                self.progress.emit(f"표시 데이터 준비 {i+1}/{len(names)} · {name}")
        except Exception as exc:
            self.failed.emit(str(exc))
