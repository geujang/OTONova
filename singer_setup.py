"""Stage-three singer form and background voicebank ZIP export."""

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QScrollArea,
    QFileDialog,
    QMessageBox,
)

import ui_settings as ui
from singer_settings import (
    FIELDS,
    load_settings,
    save_settings,
    export_zip,
    metadata_snapshot,
)

PHONEMIZERS = [
    "JapaneseVCVPhonemizer",
    "JapaneseCVVCPhonemizer",
    "JapanesePresampPhonemizer",
    "KoreanCVPhonemizer",
    "KoreanCVCPhonemizer",
    "KoreanVCVPhonemizer",
    "KoreanCVVCPhonemizer",
    "KoreanCBNNPhonemizer",
    "ArpasingPhonemizer",
    "EnglishCpVPhonemizer",
    "EnglishVCCVPhonemizer",
]


class ZipWorker(QThread):
    progress = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, folder, destination, data, report):
        super().__init__()
        self.folder, self.destination = folder, destination
        self.data, self.report = deepcopy(data), deepcopy(report)

    def run(self):
        try:
            result = export_zip(
                self.folder,
                self.destination,
                self.data,
                self.report,
                self.progress.emit,
                self.isInterruptionRequested,
            )
            self.completed.emit(str(result))
        except Exception as exc:
            self.failed.emit(str(exc))


class SingerSettingsPanel(QWidget):
    changed = Signal()

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.folder = None
        self.base = {}
        self.loading = True
        self.dirty = False
        self.disk_snapshot = {}
        self.export_worker = None
        layout = QVBoxLayout(self)
        self.folder_label = ui.label("음원 폴더를 먼저 선택해주세요.")
        self.folder_label.setWordWrap(True)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_label, 1)
        self.reload_button = ui.button("기존 파일 다시 읽기")
        self.reload_button.clicked.connect(self.reload_files)
        folder_row.addWidget(self.reload_button)
        layout.addLayout(folder_row)
        area = QScrollArea()
        area.setWidgetResizable(True)
        body = QWidget()
        inner = QVBoxLayout(body)
        form = QFormLayout()
        self.inputs = {}
        labels = {
            "name": "가수 이름",
            "author": "제작자",
            "voice": "음성 제공자",
            "version": "음원 버전",
            "web": "웹사이트",
            "image": "아이콘 이미지",
            "sample": "샘플 WAV",
            "portrait": "초상화 이미지",
        }
        for key in FIELDS:
            if key == "default_phonemizer":
                continue
            edit = QLineEdit()
            edit.setObjectName("singer_" + key)
            edit.textChanged.connect(self.notify)
            self.inputs[key] = edit
            if key in ("image", "sample", "portrait"):
                row = QWidget()
                horizontal = QHBoxLayout(row)
                horizontal.setContentsMargins(0, 0, 0, 0)
                horizontal.addWidget(edit)
                browse = ui.button("파일 선택")
                browse.clicked.connect(lambda checked=False, k=key: self.choose_file(k))
                horizontal.addWidget(browse)
                form.addRow(ui.label(labels[key]), row)
            else:
                form.addRow(ui.label(labels[key]), edit)
        self.phonemizer = QComboBox()
        self.phonemizer.setEditable(True)
        self.phonemizer.addItem("")
        self.phonemizer.addItems(
            ["OpenUtau.Plugin.Builtin." + name for name in PHONEMIZERS]
        )
        self.phonemizer.currentTextChanged.connect(self.notify)
        form.addRow(ui.label("기본 포너마이저"), self.phonemizer)
        self.encoding = QComboBox()
        for label, key in [
            ("UTF-8", "utf-8"),
            ("Shift-JIS / CP932", "shift_jis"),
            ("Korean / CP949", "cp949"),
        ]:
            self.encoding.addItem(label, key)
        self.encoding.currentIndexChanged.connect(self.notify)
        form.addRow(ui.label("텍스트 인코딩"), self.encoding)
        self.opacity = QDoubleSpinBox()
        self.opacity.setRange(0, 1)
        self.opacity.setSingleStep(0.05)
        self.opacity.valueChanged.connect(self.notify)
        form.addRow(ui.label("초상화 불투명도"), self.opacity)
        self.portrait_height = QSpinBox()
        self.portrait_height.setRange(0, 20000)
        self.portrait_height.setSuffix(" px")
        self.portrait_height.valueChanged.connect(self.notify)
        form.addRow(ui.label("초상화 높이 (0: 자동)"), self.portrait_height)
        inner.addLayout(form)
        inner.addWidget(ui.label("서브뱅크 · 색상 / 접두사 / 접미사 / 음역"))
        self.banks = QTableWidget(0, 4)
        self.banks.setMinimumHeight(145)
        self.banks.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.banks.itemChanged.connect(self.notify)
        inner.addWidget(self.banks)
        bank_buttons = QHBoxLayout()
        add = ui.button("서브뱅크 추가")
        add.clicked.connect(lambda: self.add_bank())
        remove = ui.button("선택 행 삭제")
        remove.clicked.connect(self.remove_bank)
        bank_buttons.addWidget(add)
        bank_buttons.addWidget(remove)
        bank_buttons.addStretch()
        inner.addLayout(bank_buttons)
        self.add_readme = ui.button("readme.txt 추가")
        self.add_readme.clicked.connect(lambda: self.set_readme_enabled(True))
        inner.addWidget(self.add_readme)
        self.readme_panel = QWidget()
        readme_layout = QVBoxLayout(self.readme_panel)
        readme_layout.setContentsMargins(0, 0, 0, 0)
        heading = QHBoxLayout()
        heading.addWidget(ui.label("readme.txt"), 1)
        delete = ui.button("×")
        delete.setFixedWidth(36)
        delete.setToolTip(ui.translate("README 삭제"))
        delete.clicked.connect(lambda: self.set_readme_enabled(False))
        heading.addWidget(delete)
        readme_layout.addLayout(heading)
        self.readme = QPlainTextEdit()
        self.readme.setMinimumHeight(180)
        self.readme.textChanged.connect(self.notify)
        readme_layout.addWidget(self.readme)
        inner.addWidget(self.readme_panel)
        inner.addStretch()
        area.setWidget(body)
        layout.addWidget(area, 1)
        actions = QHBoxLayout()
        self.save_button = ui.button("가수 설정 파일 저장")
        self.save_button.clicked.connect(self.save_files)
        self.export_button = ui.button("ZIP으로 내보내기")
        self.export_button.clicked.connect(self.export)
        actions.addWidget(self.save_button)
        actions.addWidget(self.export_button)
        layout.addLayout(actions)
        self.readme_enabled = False
        self.set_readme_enabled(False)
        self.refresh_language()
        self.loading = False
        self.setEnabled(False)

    def refresh_language(self):
        self.banks.setHorizontalHeaderLabels(
            [ui.translate(x) for x in ["색상", "접두사", "접미사", "음역"]]
        )

    def notify(self, *args):
        if not self.loading:
            self.dirty = True
            self.changed.emit()

    def bind_folder(self, folder, draft=None, force=False):
        folder = Path(folder).resolve()
        if folder == self.folder and draft is None and not force:
            return
        dirty = False
        if draft is not None:
            dirty = draft.get("_draft_dirty")
            if dirty is None:
                dirty = bool(
                    draft.get("_yaml")
                    or draft.get("readme_enabled")
                    or draft.get("subbanks")
                    or draft.get("portrait_opacity", 0.67) != 0.67
                    or draft.get("portrait_height", 0) != 0
                    or draft.get("text_file_encoding") != draft.get("_source_encoding")
                    or draft.get("readme")
                    or draft.get("name", folder.name) != folder.name
                    or any(draft.get(key) for key in FIELDS if key != "name")
                )
        data = deepcopy(draft) if dirty else load_settings(folder)
        self.folder = folder
        self.loading = True
        self.base = deepcopy(data)
        try:
            self.folder_label.setText(str(folder))
            for key, edit in self.inputs.items():
                edit.setText(str(data.get(key, "")))
            self.phonemizer.setCurrentText(str(data.get("default_phonemizer", "")))
            encoding = data.get("text_file_encoding", "utf-8")
            index = self.encoding.findData(encoding)
            if index < 0:
                self.encoding.addItem(encoding, encoding)
                index = self.encoding.count() - 1
            self.encoding.setCurrentIndex(index)
            self.opacity.setValue(float(data.get("portrait_opacity", 0.67)))
            self.portrait_height.setValue(int(data.get("portrait_height", 0)))
            self.banks.setRowCount(0)
            for bank in data.get("subbanks", []):
                self.add_bank(bank)
            self.readme.setPlainText(data.get("readme", ""))
            self.set_readme_enabled(bool(data.get("readme_enabled")))
            self.setEnabled(True)
        finally:
            self.loading = False
        self.dirty = bool(dirty)
        self.disk_snapshot = deepcopy(
            data.get("_metadata_snapshot", metadata_snapshot(folder))
        )

    def refresh_from_disk(self):
        if (
            self.folder is not None
            and not self.dirty
            and metadata_snapshot(self.folder) != self.disk_snapshot
        ):
            self.bind_folder(self.folder, force=True)
            self.changed.emit()

    def reload_files(self):
        if self.folder is None:
            return
        if (
            self.dirty
            and QMessageBox.question(
                self,
                ui.translate("가수 설정"),
                ui.translate("입력 중인 내용을 버리고 기존 파일을 다시 읽을까요?"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        try:
            self.bind_folder(self.folder, force=True)
            self.changed.emit()
        except Exception as exc:
            QMessageBox.warning(self, ui.translate("가수 설정"), str(exc))

    def snapshot(self):
        if self.folder is None:
            return None
        data = deepcopy(self.base)
        data["_draft_dirty"] = self.dirty
        data["_metadata_snapshot"] = deepcopy(self.disk_snapshot)
        data.update({key: edit.text() for key, edit in self.inputs.items()})
        data.update(
            default_phonemizer=self.phonemizer.currentText(),
            text_file_encoding=self.encoding.currentData(),
            portrait_opacity=self.opacity.value(),
            portrait_height=self.portrait_height.value(),
            readme_enabled=self.readme_enabled,
            readme=self.readme.toPlainText(),
            subbanks=[],
        )
        for row in range(self.banks.rowCount()):
            values = [
                self.banks.item(row, col).text() if self.banks.item(row, col) else ""
                for col in range(4)
            ]
            data["subbanks"].append(
                dict(
                    color=values[0],
                    prefix=values[1],
                    suffix=values[2],
                    tone_ranges=[v.strip() for v in values[3].split(",") if v.strip()],
                )
            )
        return data

    def add_bank(self, bank=None):
        bank = bank or {}
        row = self.banks.rowCount()
        self.banks.insertRow(row)
        for col, value in enumerate(
            [
                bank.get("color", ""),
                bank.get("prefix", ""),
                bank.get("suffix", ""),
                ", ".join(bank.get("tone_ranges", [])),
            ]
        ):
            self.banks.setItem(row, col, QTableWidgetItem(value))
        self.notify()

    def remove_bank(self):
        if self.banks.currentRow() >= 0:
            self.banks.removeRow(self.banks.currentRow())
            self.notify()

    def set_readme_enabled(self, enabled):
        self.readme_enabled = enabled
        self.readme_panel.setVisible(enabled)
        self.add_readme.setVisible(not enabled)
        self.notify()

    def choose_file(self, key):
        path, _ = QFileDialog.getOpenFileName(
            self,
            ui.translate("파일 선택"),
            str(self.folder),
            (
                "WAV (*.wav *.WAV)"
                if key == "sample"
                else "Images (*.png *.bmp *.jpg *.jpeg *.webp *.gif)"
            ),
        )
        if path:
            source = Path(path).resolve()
            self.inputs[key].setText(
                source.relative_to(self.folder).as_posix()
                if source.is_relative_to(self.folder)
                else str(source)
            )

    def save_files(self):
        try:
            save_settings(self.folder, self.snapshot())
            data = load_settings(self.folder)
            self.bind_folder(self.folder, data, force=True)
            self.owner.acknowledge_oto_writes()
            self.owner.save_project_snapshot()
            self.owner.update_progress(ui.translate("가수 설정 저장 완료"))
        except Exception as exc:
            QMessageBox.warning(self, ui.translate("가수 설정"), str(exc))

    def export_failed(self, error):
        self.owner.setEnabled(True)
        QMessageBox.warning(self.owner, ui.translate("ZIP으로 내보내기"), error)

    def export(self):
        if self.folder is None or (
            self.export_worker and self.export_worker.isRunning()
        ):
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            ui.translate("ZIP으로 내보내기"),
            str(self.folder.parent / (self.folder.name + ".zip")),
            "ZIP (*.zip)",
        )
        if not path:
            return
        if Path(path).suffix.casefold() != ".zip":
            path += ".zip"
            if (
                Path(path).exists()
                and QMessageBox.question(
                    self,
                    ui.translate("ZIP으로 내보내기"),
                    ui.translate("기존 ZIP을 덮어쓰시겠습니까?"),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                != QMessageBox.Yes
            ):
                return
        self.owner.save_singer_draft()
        self.export_worker = ZipWorker(
            self.folder, path, self.snapshot(), self.owner.report
        )
        self.export_worker.progress.connect(self.owner.update_progress)
        self.export_worker.completed.connect(
            lambda name: self.owner.update_progress(
                ui.translate("ZIP 내보내기 완료") + ": " + name
            )
        )
        self.export_worker.failed.connect(self.export_failed)
        self.export_worker.finished.connect(lambda: self.owner.setEnabled(True))
        self.owner.setEnabled(False)
        self.owner.update_progress(ui.translate("ZIP 내보내기 중…"))
        self.export_worker.start()
