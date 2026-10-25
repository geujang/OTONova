import sys
import os
import json
from copy import deepcopy
import ui_settings as ui
from PySide6.QtCore import QSettings
from pathlib import Path

if getattr(sys, "frozen", False):
    # Numba resolves the frozen code's relative source path when constructing its cache.
    os.chdir(sys._MEIPASS)
from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer
from PySide6.QtGui import (
    QColor,
    QShortcut,
    QKeySequence,
    QIcon,
    QPixmap,
    QDesktopServices,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QMenu,
    QMenuBar,
    QLineEdit,
    QFileDialog,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QScrollBar,
    QPlainTextEdit,
    QMessageBox,
    QHeaderView,
    QDialog,
    QTextBrowser,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QComboBox,
    QSpinBox,
    QStackedWidget,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from vcv_core import (
    RESOURCE_ROOT,
    DEFAULT_FOLDER,
    run_folder,
    install_oto,
    move_boundary,
    edit_oto_marker,
    recalculate_file,
    persist_report,
    save_record,
    atomic_write,
    output_dir,
    RULES_VERSION,
    read_existing_oto,
)
from audio_view import AudioEditor as Waveform, SPECTRUM_PALETTES
from formats import FORMATS, PUBLIC_FORMATS, public_mode, is_korean
from format_detection import resolve_mode
from project_store import PROJECT_NAME, save_project, open_project
from feedback_client import FeedbackDialog, endpoint_from_config
from singer_setup import SingerSettingsPanel

from gui_workers import FileScanner, ExternalReload, FolderLoader
from gui_dialogs import select_voicebank_format


class Worker(QThread):
    progress = Signal(str)
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, folder, mode="vcv", only_files=None, base_report=None):
        super().__init__()
        self.folder = folder
        self.only_files = only_files
        self.base_report = base_report
        self.mode = mode

    def run(self):
        try:
            self.completed.emit(
                run_folder(
                    self.folder,
                    self.progress.emit,
                    self.isInterruptionRequested,
                    self.mode,
                    only_files=self.only_files,
                    base_report=self.base_report,
                )
            )
        except Exception as exc:
            self.failed.emit(str(exc))


class Window(QMainWindow):
    def __init__(self, settings=None):
        super().__init__()
        self.preferences = (
            settings if settings is not None else QSettings("OtoNova", "OtoNova")
        )
        ui.language = str(self.preferences.value("language", ui.system_language()))
        if ui.language not in ui.LANGUAGES:
            ui.language = "en"
        ui.theme = str(self.preferences.value("theme", "dark"))
        if ui.theme not in ("dark", "light"):
            ui.theme = "dark"
        ui.set_title(self, "OTONova V2.0 · 일본어 / 한국어 / 영어 자동 원설기")
        self.setWindowIcon(QIcon(str(RESOURCE_ROOT / "assets/otonova.ico")))
        self.resize(1320, 1000)
        ui.spectrum_palette = str(self.preferences.value("spectrum_palette", "fire"))
        if ui.spectrum_palette not in SPECTRUM_PALETTES:
            ui.spectrum_palette = "fire"
        ui.spectrum_max_hz = ui.normalize_spectrum_hz(
            self.preferences.value("spectrum_max_hz", 10000)
        )
        self.worker = None
        self.report = None
        self.current_record = None
        self.histories = {}
        self.pending_before = None
        self.edit_backup_done = False
        self.file_rows = {}
        self.row_warning_flags = {}
        self.stage = 1
        self.mode = "vcv"
        self.mode_chosen = False
        self.project_path = None
        self.project_records = {}
        self.inventory = {}
        self.asset_worker = None
        self._watch_folder = None
        self._file_baseline = None
        self._file_revision = 0
        self._accepted_oto = {}
        self.file_scanner = None
        self.reload_worker = None
        self._external_dialog = False
        self.pending_external_wavs = set()
        self.file_timer = QTimer(self)
        self.file_timer.setInterval(1500)
        self.file_timer.timeout.connect(self.check_external_files)
        self.file_timer.start()
        self.network = QNetworkAccessManager(self)
        self.top_menus = QMenuBar(self)
        self.top_menus.setNativeMenuBar(False)
        self.menuBar().setCornerWidget(self.top_menus, Qt.TopRightCorner)
        self.work_menu = self.top_menus.addMenu(ui.translate("작업"))
        self.settings_menu = self.top_menus.addMenu(ui.translate("설정"))
        self.settings_button = self.settings_menu.addAction(
            ui.translate("설정"), self.show_settings
        )
        help_menu = self.top_menus.addMenu(ui.translate("도움말"))
        self.help_menu = help_menu
        self.update_action = help_menu.addAction(
            ui.translate("업데이트 확인"), self.check_updates
        )
        self.github_action = help_menu.addAction(
            ui.translate("GitHub 링크"),
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/geujang/OTONova")
            ),
        )
        self.about_action = help_menu.addAction(
            ui.translate("버전 정보"), self.show_version
        )
        self.feedback_action = help_menu.addAction(
            ui.translate("피드백"), self.show_feedback
        )
        help_menu.addSeparator()
        self.credits_action = help_menu.addAction(
            ui.translate("크레딧"), self.show_credits
        )
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        title = ui.label("OTONova V2.0")
        title.setStyleSheet("font-size:24px;font-weight:700;padding:10px")
        title_bar = QHBoxLayout()
        logo = ui.label()
        logo.setPixmap(
            QPixmap(str(RESOURCE_ROOT / "assets/otonova-logo.png")).scaled(
                48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )
        title_bar.addWidget(logo)
        title_bar.addWidget(title, 1)
        layout.addLayout(title_bar)
        layout.addWidget(
            ui.label("파일명 / 인덱스 인식 → 모델 음소 정렬 → 지정 규칙으로 원설 생성")
        )
        bar = QHBoxLayout()
        self.folder = QLineEdit(str(DEFAULT_FOLDER))
        self.folder.setReadOnly(True)
        browse = ui.button("음원 폴더")
        self.browse_button = browse
        browse.clicked.connect(self.browse)
        bar.addWidget(self.folder, 1)
        bar.addWidget(browse)

        def work_action(text, callback):
            action = self.work_menu.addAction(ui.translate(text), callback)
            ui.set_text(action, text)
            return action

        self.open_project_button = work_action("프로젝트 열기", self.browse_project)
        self.save_project_button = work_action("프로젝트 저장", self.save_project_as)
        self.work_menu.addSeparator()
        self.generate = work_action("자동원설", self.start)
        self.stop = work_action(
            "중지", lambda: self.worker.requestInterruption() if self.worker else None
        )
        self.stop.setEnabled(False)
        self.work_menu.addSeparator()
        self.save = work_action("oto.ini 저장 (기존 파일 백업)", self.save_oto)
        self.save.setEnabled(False)
        layout.addLayout(bar)
        self.status = ui.label("준비")
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        layout.addWidget(self.progress)
        stages = QHBoxLayout()
        self.stage_buttons = []
        for number, text in [
            (1, "1단계 · 음소 경계"),
            (2, "2단계 · 원설 조정"),
            (3, "3단계 · 가수 설정"),
        ]:
            button = ui.button(text)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, n=number: self.set_stage(n))
            stages.addWidget(button)
            self.stage_buttons.append(button)
        layout.addLayout(stages)
        self.splitter = QSplitter(Qt.Horizontal)
        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(editor)
        self.splitter.addWidget(side)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([850, 470])
        self.workspace_stack = QStackedWidget()
        self.workspace_stack.addWidget(self.splitter)
        self.singer_setup = SingerSettingsPanel(self)
        self.workspace_stack.addWidget(self.singer_setup)
        self.singer_save_timer = QTimer(self)
        self.singer_save_timer.setSingleShot(True)
        self.singer_save_timer.setInterval(500)
        self.singer_save_timer.timeout.connect(self.save_singer_draft)
        self.singer_setup.changed.connect(lambda: self.singer_save_timer.start())
        layout.addWidget(self.workspace_stack, 1)
        self.wave = Waveform()
        self.wave.segmentRequested.connect(self.play_segment)
        self.wave.editStarted.connect(self.begin_edit)
        self.wave.boundaryMoved.connect(self.edit_boundary)
        self.wave.otoMoved.connect(self.edit_oto)
        self.wave.editFinished.connect(self.finish_edit)
        self.wave.boundarySelected.connect(self.show_boundary)
        editor_layout.addWidget(self.wave, 1)
        self.scroll = QScrollBar(Qt.Horizontal)
        self.scroll.valueChanged.connect(
            lambda value: self.wave.set_view(value / 1000, self.wave.length)
        )
        self.wave.viewChanged.connect(self.update_scroll)
        editor_layout.addWidget(self.scroll)
        audio_bar = QHBoxLayout()
        self.play = ui.button("선택한 WAV 듣기")
        self.play.clicked.connect(self.play_audio)
        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        audio_bar.addWidget(self.play)
        self.review = ui.button("검토 항목만 보기")
        self.review.setCheckable(True)
        self.review.toggled.connect(self.filter_rows)
        audio_bar.addWidget(self.review)
        for label, factor in [("확대 +", 1.5), ("축소 -", 1 / 1.5)]:
            button = ui.button(label)
            button.clicked.connect(lambda checked=False, f=factor: self.wave.zoom(f))
            audio_bar.addWidget(button)
        reset = ui.button("전체 보기")
        reset.clicked.connect(self.wave.reset_view)
        audio_bar.addWidget(reset)
        self.undo = ui.button("경계 되돌리기 (Ctrl+Z)")
        self.undo.setEnabled(False)
        self.undo.clicked.connect(self.undo_edit)
        audio_bar.addWidget(self.undo)
        self.undo_shortcut = QShortcut(QKeySequence.Undo, self)
        self.undo_shortcut.activated.connect(self.undo_edit)
        audio_bar.addStretch()
        editor_layout.addLayout(audio_bar)
        self.boundary_info = ui.label(
            "파스텔 분홍색 점선 음소 경계를 드래그하세요 · 즉시 재계산 · 놓으면 경계와 oto.ini 자동 저장"
        )
        self.boundary_info.setWordWrap(True)
        editor_layout.addWidget(self.boundary_info)
        side_layout.addWidget(ui.label("파일 · 현재 단계의 경고"))
        self.files = QListWidget()
        self.files.setContextMenuPolicy(Qt.CustomContextMenu)
        self.files.customContextMenuRequested.connect(self.file_context_menu)
        self.files.currentItemChanged.connect(self.select_file)
        side_layout.addWidget(self.files, 1)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                ui.translate(x)
                for x in [
                    "WAV",
                    "에일리어스",
                    "오프셋",
                    "고정",
                    "컷오프",
                    "선행",
                    "오버랩",
                    "검토",
                ]
            ]
        )
        self.table.setColumnHidden(0, True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for column, width in enumerate([0, 90, 75, 75, 80, 75, 75]):
            self.table.setColumnWidth(column, width)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.selected)
        side_layout.addWidget(self.table, 2)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        layout.addWidget(self.log)
        self.apply_preferences()
        self.set_stage(1)
        self.load_report()
        self.refresh_files()
        for button in self.stage_buttons:
            button.setEnabled(True)

    def apply_preferences(self):
        ui.apply_font()
        self.setStyleSheet(ui.stylesheet())
        ui.refresh()
        self.work_menu.setTitle(ui.translate("작업"))
        self.settings_menu.setTitle(ui.translate("설정"))
        self.settings_button.setText(ui.translate("설정"))
        self.credits_action.setText(ui.translate("크레딧"))
        self.help_menu.setTitle(ui.translate("도움말"))
        self.singer_setup.refresh_language()
        for action, text in [
            (self.update_action, "업데이트 확인"),
            (self.github_action, "GitHub 링크"),
            (self.about_action, "버전 정보"),
            (self.feedback_action, "피드백"),
        ]:
            action.setText(ui.translate(text))
        if hasattr(self, "table"):
            self.table.setHorizontalHeaderLabels(
                [
                    ui.translate(x)
                    for x in [
                        "WAV",
                        "에일리어스",
                        "오프셋",
                        "고정",
                        "컷오프",
                        "선행",
                        "오버랩",
                        "검토",
                    ]
                ]
            )
            for row in range(self.table.rowCount()):
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item.setForeground(
                            QColor(
                                ui.colors()["warning"]
                                if col == 7 and item.text()
                                else ui.colors()["text"]
                            )
                        )
        if hasattr(self, "wave"):
            self.wave._background_key = None
            self.wave.update_spectrum_palette()
            self.wave.setToolTip(
                ui.translate(
                    "음소 경계선 드래그: 실시간 원설 · 휠: 확대/축소 · 아래 스크롤바: 이동"
                )
                + "\n"
                + ui.translate("우클릭: 라벨 사이 구간 재생")
                + "\n"
                + ui.translate("파형 빈 곳을 위아래로 드래그: 진폭 표시 확대·축소")
            )
            self.wave.update()
        self.refresh_files()

    def show_settings(self):
        dialog = QDialog(self)
        ui.set_title(dialog, "설정")
        layout = QVBoxLayout(dialog)
        layout.addWidget(ui.label("표시 언어"))
        languages = QComboBox()
        for key, name in ui.LANGUAGES.items():
            languages.addItem(name, key)
        languages.setCurrentIndex(languages.findData(ui.language))
        layout.addWidget(languages)
        layout.addWidget(ui.label("화면 모드"))
        themes = QComboBox()
        for key, name in [("dark", "다크"), ("light", "라이트")]:
            themes.addItem(ui.translate(name), key)
        themes.setCurrentIndex(themes.findData(ui.theme))
        layout.addWidget(themes)
        layout.addWidget(ui.label("스펙트로그램 색상"))
        palettes = QComboBox()
        for key, (name, colors) in SPECTRUM_PALETTES.items():
            palettes.addItem(ui.translate(name), key)
        palettes.setCurrentIndex(palettes.findData(ui.spectrum_palette))
        layout.addWidget(palettes)
        layout.addWidget(ui.label("스펙트로그램 최대 주파수"))
        maximum_hz = QSpinBox()
        maximum_hz.setObjectName("spectrum_max_hz")
        maximum_hz.setRange(100, 96000)
        maximum_hz.setSingleStep(1000)
        maximum_hz.setSuffix(" Hz")
        maximum_hz.setValue(ui.spectrum_max_hz)
        layout.addWidget(maximum_hz)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(ui.translate("확인"))
        buttons.button(QDialogButtonBox.Cancel).setText(ui.translate("취소"))
        buttons.button(QDialogButtonBox.Ok).setText(ui.translate("확인"))
        buttons.button(QDialogButtonBox.Cancel).setText(ui.translate("취소"))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return
        self.set_preferences(
            languages.currentData(),
            themes.currentData(),
            palettes.currentData(),
            maximum_hz.value(),
        )

    def set_preferences(
        self, language, theme, spectrum_palette=None, spectrum_max_hz=None
    ):
        if language not in ui.LANGUAGES or theme not in ("dark", "light"):
            raise ValueError("Invalid preferences")
        if spectrum_palette is not None:
            if spectrum_palette not in SPECTRUM_PALETTES:
                raise ValueError("Invalid spectrogram palette")
            ui.spectrum_palette = spectrum_palette
            self.preferences.setValue("spectrum_palette", spectrum_palette)
        if spectrum_max_hz is not None:
            ui.spectrum_max_hz = ui.normalize_spectrum_hz(spectrum_max_hz)
            self.preferences.setValue("spectrum_max_hz", ui.spectrum_max_hz)
        ui.language = language
        ui.theme = theme
        self.preferences.setValue("language", language)
        self.preferences.setValue("theme", theme)
        self.preferences.sync()
        self.apply_preferences()

    def show_credits(self):
        dialog = QDialog(self)
        ui.set_title(dialog, "모델 크레딧")
        dialog.resize(640, 700)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.document().setDefaultStyleSheet(
            "a { color: " + ui.colors()["accent"] + "; }"
        )
        browser.setMarkdown(
            (RESOURCE_ROOT / "assets/CREDITS.md").read_text(encoding="utf-8")
        )
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText(ui.translate("닫기"))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, ui.translate("음원 폴더"), self.folder.text()
        )
        if folder:
            try:
                self.open_folder(folder)
            except Exception as exc:
                QMessageBox.warning(self, "프로젝트 열기", str(exc))

    def show_version(self):
        QMessageBox.about(
            self,
            ui.translate("버전 정보"),
            "OTONova V2.0\nKURO\nWFL 기반 UTAU 자동 원설기\nhttps://github.com/geujang/OTONova",
        )

    def show_feedback(self):
        FeedbackDialog(endpoint_from_config(RESOURCE_ROOT), self).exec()

    def check_updates(self):
        self.update_action.setEnabled(False)
        request = QNetworkRequest(
            QUrl("https://api.github.com/repos/geujang/OTONova/releases/latest")
        )
        request.setRawHeader(b"User-Agent", b"OTONova/2.0")
        request.setTransferTimeout(10000)
        reply = self.network.get(request)
        reply.finished.connect(lambda: self.update_reply(reply))

    def update_reply(self, reply):
        self.update_action.setEnabled(True)
        try:
            if reply.error() != QNetworkReply.NoError:
                raise ValueError(reply.errorString())
            data = json.loads(bytes(reply.readAll()))
            import re

            version = tuple(int(n) for n in re.findall(r"\d+", data["tag_name"])[:3])
            version = version + (0,) * (3 - len(version))
            if version > (2, 0, 0):
                answer = QMessageBox.question(
                    self,
                    ui.translate("업데이트 확인"),
                    ui.translate("새 버전이 있습니다. 다운로드 페이지를 열까요?")
                    + "\n"
                    + data["tag_name"],
                )
                if answer == QMessageBox.Yes:
                    QDesktopServices.openUrl(
                        QUrl("https://github.com/geujang/OTONova/releases/latest")
                    )
            else:
                QMessageBox.information(
                    self,
                    ui.translate("업데이트 확인"),
                    ui.translate(
                        "현재 버전은 V2.0입니다. 더 새로운 공개 릴리스가 없습니다."
                    ),
                )
        except Exception as exc:
            QMessageBox.warning(
                self,
                ui.translate("업데이트 확인"),
                ui.translate("업데이트 정보를 확인할 수 없습니다.") + "\n" + str(exc),
            )
        finally:
            reply.deleteLater()

    def start_file_watch(self):
        from external_files import snapshot

        self._watch_folder = self.folder.text()
        self._file_revision += 1
        self._file_baseline = {
            name: {"kind": "wav", "signature": item["signature"]}
            for name, item in self.inventory.items()
        }
        self._accepted_oto = snapshot(self._watch_folder, "oto")
        self._file_baseline.update(self._accepted_oto)
        self.pending_external_wavs = set()
        self.update_approved_signatures()

    def update_approved_signatures(self):
        folder = Path(self.folder.text())
        self.wave.approved_signatures = {
            str((folder / name).resolve()): item["signature"]
            for name, item in self.inventory.items()
        }

    def check_external_files(self):
        if (
            self.singer_setup.export_worker
            and self.singer_setup.export_worker.isRunning()
        ):
            return
        if not self._watch_folder or self._external_dialog:
            return
        if QApplication.activeModalWidget() is not None:
            return
        if any(
            w and w.isRunning()
            for w in [self.worker, self.file_scanner, self.reload_worker]
        ):
            return
        folder = self._watch_folder
        revision = self._file_revision
        self.file_scanner = FileScanner(folder)
        self.file_scanner.completed.connect(
            lambda state, f=folder, r=revision: self.external_snapshot(f, r, state)
        )
        self.file_scanner.start()

    def external_snapshot(self, folder, revision, state):
        if (
            self.singer_setup.export_worker
            and self.singer_setup.export_worker.isRunning()
        ):
            return
        if folder != self._watch_folder or revision != self._file_revision:
            return
        if self.worker and self.worker.isRunning():
            return
        if QApplication.activeModalWidget() is not None:
            return
        if self._file_baseline is None:
            self._file_baseline = state
            return
        from external_files import changes

        changed = changes(self._file_baseline, state)
        self._file_baseline = (
            state  # Cancel acknowledges this change, avoiding repeated dialogs.
        )
        if not changed["wav"] and not changed["oto"]:
            return
        self._stop_assets()
        self._external_dialog = True
        try:
            self.pending_external_wavs.update(changed["wav"])
            wavs = (
                changed["wav"]
                if changed["wav"]
                and self.confirm_external_reload("wav", changed["wav"])
                else []
            )
            oto = bool(
                changed["oto"] and self.confirm_external_reload("oto", changed["oto"])
            )
            if wavs or oto:
                self.generate.setEnabled(False)
                self.browse_button.setEnabled(False)
                self.open_project_button.setEnabled(False)
                self.save.setEnabled(False)
                self.reload_worker = ExternalReload(folder, wavs, oto)
                self.reload_worker.completed.connect(self.external_reloaded)
                self.reload_worker.start()
        finally:
            self._external_dialog = False

    def confirm_external_reload(self, kind, names):
        question = (
            "WAV 파일을 재로드 하고 시각음성자료를 다시 재 렌더링 할까요?"
            if kind == "wav"
            else "OTO 파일을 재 인식 할까요?"
        )
        box = QMessageBox(
            QMessageBox.Question,
            ui.translate("외부 파일 변경"),
            ui.translate(question),
            QMessageBox.Ok | QMessageBox.Cancel,
            self,
        )
        box.setInformativeText(
            "\n".join(names[:8])
            + ("\n… " + str(len(names)) + "개" if len(names) > 8 else "")
        )
        box.setDefaultButton(QMessageBox.Cancel)
        box.button(QMessageBox.Ok).setText(
            ui.translate("다시 로드" if kind == "wav" else "재인식")
        )
        box.button(QMessageBox.Cancel).setText(ui.translate("취소"))
        return box.exec() == QMessageBox.Ok

    def external_reloaded(self, result):
        selected = str(self.wave.path.resolve()) if self.wave.path else None
        stage = self.stage
        for name, item in result["wavs"].items():
            self.pending_external_wavs.discard(name)
            self.project_records.pop(name, None)
            if item is None:
                self.inventory.pop(name, None)
            else:
                self.inventory[name] = item
            if self.current_record and self.current_record["wav"] == name:
                self.current_record = None
            if self.report:
                for row in self.report["entries"]:
                    if row["wav"] == name:
                        row["warnings"] = list(
                            dict.fromkeys(
                                row.get("warnings", []) + ["WAV 변경: 경계 재확인 필요"]
                            )
                        )
        self.update_approved_signatures()
        if result["report"] is not None:
            from external_files import snapshot

            self._accepted_oto = snapshot(self.folder.text(), "oto")
            result["report"]["mode"] = self.mode
            self.wave.clear()
            self.done(result["report"])
            self.set_stage(stage)
        else:
            self.refresh_files()
            changed_paths = {
                str((Path(self.folder.text()) / n).resolve()) for n in result["wavs"]
            }
            if selected in changed_paths:
                self.wave.clear()
                row = (
                    self.report["entries"][self.table.currentRow()]
                    if self.report and self.table.currentRow() >= 0
                    else None
                )
                if Path(selected).exists():
                    self.wave.load(selected, [], row)
        self.idle()
        self.set_stage(stage)
        if self.project_path:
            self.save_project_snapshot()
        for error in result["errors"]:
            self.update_progress(error)

    def acknowledge_oto_writes(self):
        if self._file_baseline is None:
            return
        from external_files import snapshot

        self._file_revision += 1
        self._file_baseline = {
            name: item
            for name, item in self._file_baseline.items()
            if item["kind"] != "oto"
        }
        self._accepted_oto = snapshot(self.folder.text(), "oto")
        self._file_baseline.update(self._accepted_oto)
        if self.project_path:
            self.save_project_snapshot()

    def _stop_assets(self):
        if self.asset_worker and self.asset_worker.isRunning():
            self.asset_worker.requestInterruption()
            self.asset_worker.wait()

    def open_folder(self, folder):
        if self.worker and self.worker.isRunning():
            return
        self._stop_assets()
        self.project_path = Path(folder) / PROJECT_NAME
        if self.project_path.exists():
            self.restore_project(self.project_path)
            return
        self.folder.setText(str(folder))
        self.bind_singer_folder(folder, force=True)
        self.mode_chosen = False
        self.project_records = {}
        self.inventory = {}
        self.wave.async_loading = True
        self.wave.cache_folder = Path(folder) / ".otonova-cache"
        self.report = None
        self.file_rows = {}
        self.wave.clear()
        self.files.clear()
        self.table.setRowCount(0)
        self.generate.setEnabled(False)
        self.asset_worker = FolderLoader(folder)
        self.asset_worker.indexed.connect(
            lambda i, r, s, f=str(folder): (
                self.folder_indexed(i, r, s) if self.folder.text() == f else None
            )
        )
        self.asset_worker.progress.connect(self.update_progress)
        self.asset_worker.failed.connect(self.failed)
        self.asset_worker.finished.connect(
            lambda: self.generate.setEnabled(
                not (self.worker and self.worker.isRunning())
            )
        )
        self.asset_worker.start()

    def folder_indexed(self, inventory, report, records):
        self.inventory = inventory
        self.project_records = records
        self.start_file_watch()
        self.done(report)
        self.set_stage(
            2 if report.get("uses_existing_oto") and report["entries"] else 1
        )
        self.generate.setEnabled(True)
        if self.project_path:
            self.save_project_snapshot()
        if records:
            self.update_progress(
                f"기존 라벨 캐시 {len(records)}개 복원 · 경계 재추정 없음"
            )

    def browse_project(self):
        if self.worker and self.worker.isRunning():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "프로젝트 열기", self.folder.text(), "OTONova project (*.otonova)"
        )
        if path:
            try:
                self.restore_project(path)
            except Exception as exc:
                QMessageBox.warning(self, "프로젝트 열기", str(exc))

    def restore_project(self, path):
        self._stop_assets()
        data = open_project(path)
        self.project_path = Path(path)
        self.folder.setText(data["folder"])
        self.bind_singer_folder(data["folder"], data.get("singer_settings"), force=True)
        self.project_records = data["records"]
        self.inventory = data["inventory"]
        self.start_file_watch()
        if data.get("file_snapshot") is not None:
            self._file_baseline = data["file_snapshot"]
            self._accepted_oto = {
                name: item
                for name, item in data["file_snapshot"].items()
                if item["kind"] == "oto"
            }
        self.pending_external_wavs.update(data["changed_files"])
        self.mode = data["report"]["mode"]
        self.selected_mode = public_mode(self.mode)
        self.mode_chosen = True
        self.wave.async_loading = True
        self.wave.cache_folder = Path(data["folder"]) / ".otonova-cache"
        self.wave.clear()
        restored_stage = data.get("stage", 1)
        self.stage = restored_stage if restored_stage in (1, 2, 3) else 1
        self.done(data["report"])
        self.set_stage(self.stage)
        for i in range(self.files.count()):
            if self.files.item(i).data(Qt.UserRole) == data.get("selected"):
                self.files.setCurrentRow(i)
                break
        self.asset_worker = FolderLoader(data["folder"], scan=False)
        self.asset_worker.progress.connect(self.update_progress)
        self.asset_worker.start()
        self.update_progress(
            "프로젝트 복원 완료 · 경계 재추정 없음"
            + (
                " · WAV 변경 " + str(len(data["changed_files"])) + "개"
                if data["changed_files"]
                else ""
            )
        )

    def save_project_snapshot(self):
        if not self.report:
            return
        folder = Path(self.folder.text())
        if self.current_record:
            self.project_records[self.current_record["wav"]] = deepcopy(
                self.current_record
            )
        # Include all labels, so the project survives removal of the original cache.
        if not self.inventory:
            from project_store import signature
            from arpasing_core import wav_files

            self.inventory = {
                p.relative_to(folder).as_posix(): {"signature": signature(p)}
                for p in wav_files(folder)
            }
        target = self.project_path or folder / PROJECT_NAME
        accepted = {
            name: {"kind": "wav", "signature": item["signature"]}
            for name, item in self.inventory.items()
        }
        accepted.update(self._accepted_oto)
        save_project(
            target,
            folder,
            self.report,
            self.project_records,
            self.inventory,
            self.stage,
            (self.current_record or {}).get("wav"),
            accepted,
            singer_settings=self.singer_setup.snapshot(),
        )
        self.project_path = target

    def save_project_as(self):
        if not self.report:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "프로젝트 저장",
            str(self.project_path or Path(self.folder.text()) / PROJECT_NAME),
            "OTONova project (*.otonova)",
        )
        if path:
            previous = self.project_path
            try:
                self.project_path = Path(path).with_suffix(".otonova")
                self.save_project_snapshot()
            except Exception as exc:
                self.project_path = previous
                QMessageBox.warning(self, "프로젝트 저장", str(exc))

    def set_mode(self, mode):
        if mode not in FORMATS:
            raise ValueError(mode)
        self.selected_mode = public_mode(mode)
        template, _ = read_existing_oto(Path(self.folder.text()) / "oto.ini")
        if self.selected_mode == "en_vccv":
            from english_vccv import read_templates

            template, _ = read_templates(self.folder.text())
        self.mode, self.detection = resolve_mode(
            self.folder.text(), self.selected_mode, template
        )
        self.wave.empty_message = "원설 행 선택 → 음소 경계 드래그 → 즉시 재계산"
        self.mode_chosen = True
        self.set_stage(1)
        ui.set_text(self.generate, "자동원설")
        if not self.project_path:
            self.load_report()
        self.refresh_files()
        for button in self.stage_buttons:
            button.setEnabled(True)
        if self.detection:
            message = self.detection.get("summary", "녹음 리스트 자동 인식 완료")
            if self.detection["warning"]:
                message += " · " + self.detection["warning"]
            ui.set_text(self.status, message)
            ui.append_log(self.log, message)
            if self.mode == "en_cvvc":
                for row in self.detection["components"]:
                    ui.append_log(
                        self.log,
                        f"{row['family']} · {row['profile']} · {row['section']} · WAV {row['matched_files']} / TXT {row['list_matches']}",
                    )

    def choose_mode(self):
        mode = select_voicebank_format(self)
        if mode is None:
            return False
        self.set_mode(mode)
        return True

    def load_report(self):
        self.report = None
        self.current_record = None
        self.histories = {}
        self.pending_before = None
        self.edit_backup_done = False
        self.table.setRowCount(0)
        self.files.clear()
        self.save.setEnabled(False)
        self.wave.clear()
        path = output_dir(self.folder.text(), self.mode) / "report.json"
        if path.exists():
            report = json.loads(path.read_text(encoding="utf-8"))
            template, _ = read_existing_oto(Path(self.folder.text()) / "oto.ini")
            if self.mode == "en_vccv":
                from english_vccv import read_templates

                template, _ = read_templates(self.folder.text())
            changed_template = template is not None and [
                (r["wav"], r["alias"]) for r in template
            ] != [(r["wav"], r["alias"]) for r in report["entries"]]
            if (
                any("source_index" not in r for r in report["entries"])
                or report.get("rules_version", 1) < RULES_VERSION
                or changed_template
            ):
                ui.set_text(
                    self.status,
                    "음소 처리 규칙이 변경되었습니다. 생성을 눌러 다시 추정해주세요.",
                )
                return
            # Another format may have corrected the shared labels since this report.
            grouped = {}
            english_resolver = None
            if self.mode == "en_arpasing":
                from arpasing_core import ArpasingResolver

                english_resolver = ArpasingResolver(self.folder.text())
            elif self.mode == "en_cvvc":
                from english_cvvc import CvvcResolver

                english_resolver = CvvcResolver(self.folder.text())
            elif self.mode == "en_vccv":
                from english_vccv import VccvResolver

                english_resolver = VccvResolver(self.folder.text())
            for i, row in enumerate(report["entries"]):
                grouped.setdefault(row["wav"], []).append(i)
            for wav, indices in grouped.items():
                label = (
                    Path(self.folder.text())
                    / "auto-vcv/labels"
                    / Path(wav).with_suffix(".json")
                )
                if label.exists():
                    automatic = [
                        i for i in indices if not report["entries"][i].get("manual_oto")
                    ]
                    record = json.loads(label.read_text(encoding="utf-8"))
                    if english_resolver:
                        try:
                            metadata = english_resolver.metadata(
                                Path(self.folder.text()) / wav
                            )
                        except ValueError as exc:
                            ui.set_text(self.status, str(exc))
                            return
                        units_key = (
                            "vccv_units"
                            if self.mode == "en_vccv"
                            else (
                                "cvvc_units"
                                if self.mode == "en_cvvc"
                                else "arpasing_units"
                            )
                        )
                        version_key = (
                            "vccv_version" if self.mode == "en_vccv" else "cvvc_version"
                        )
                        if (
                            metadata["phones"] != record["phones"]
                            or metadata[units_key] != record.get(units_key)
                            or self.mode in ("en_cvvc", "en_vccv")
                            and metadata[version_key] != record.get(version_key)
                        ):
                            ui.set_text(
                                self.status,
                                "영어 음소 매핑이 변경되었습니다. 다시 생성해주세요.",
                            )
                            return
                        record.update(metadata)
                    if is_korean(self.mode) and self.mode != "ko_cvvc":
                        from korean_formats import make_record_metadata

                        metadata = make_record_metadata(Path(wav).stem, self.mode)
                        if metadata["phones"] != record["phones"]:
                            ui.set_text(
                                self.status,
                                "형식의 음소열이 변경되었습니다. 생성을 눌러 다시 추정해주세요.",
                            )
                            return
                        record.update(metadata)
                    if automatic:
                        recalculate_file(report, record, automatic)
            persist_report(self.folder.text(), report)
            self.done(report)
        else:
            ui.set_text(
                self.status,
                "준비 · " + FORMATS[self.mode][0] + " 원설 생성을 눌러주세요",
            )

    def file_context_menu(self, position):
        item = self.files.itemAt(position)
        if item is None:
            return
        self.files.setCurrentItem(item)
        menu = QMenu(self)
        action = menu.addAction(ui.translate("자동원설"))
        action.setEnabled(
            not any(
                w and w.isRunning()
                for w in [self.worker, self.asset_worker, self.reload_worker]
            )
        )
        action.triggered.connect(
            lambda: self.start(only_files=[item.data(Qt.UserRole)])
        )
        menu.exec(self.files.viewport().mapToGlobal(position))

    def start(self, checked=False, only_files=None):
        from arpasing_core import wav_files

        previous = deepcopy(self.report) if only_files else None
        if not self.choose_mode():
            return
        self._stop_assets()
        if only_files is None and not (
            wav_files(self.folder.text())
            if getattr(self, "selected_mode", self.mode)
            in ("en_arpasing", "en_cvvc", "en_vccv")
            else list(Path(self.folder.text()).glob("*.wav"))
        ):
            QMessageBox.warning(
                self,
                ui.translate("음원 없음"),
                ui.translate("선택한 폴더에 WAV가 없습니다."),
            )
            return
        self.set_stage(1)
        self.generate.setEnabled(False)
        self.folder.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.open_project_button.setEnabled(False)
        self.save_project_button.setEnabled(False)
        self.save.setEnabled(False)
        self.stop.setEnabled(True)
        self.table.setEnabled(False)
        self.wave.editable = False
        self.undo.setEnabled(False)
        self.progress.setRange(0, 0)
        self.worker = Worker(
            self.folder.text(),
            getattr(self, "selected_mode", self.mode),
            only_files,
            previous,
        )
        self.worker.progress.connect(self.update_progress)
        self.worker.completed.connect(self.generated_done)
        self.worker.failed.connect(self.failed)
        self.worker.start()

    def generated_done(self, report):
        folder = Path(self.folder.text())
        from project_store import signature
        from arpasing_core import wav_files

        self.inventory = {
            p.relative_to(folder).as_posix(): {"signature": signature(p)}
            for p in wav_files(folder)
        }
        self.update_approved_signatures()
        if not report.get("processed_files"):
            self.project_records = {}
        for wav in dict.fromkeys(
            report.get("processed_files") or [row["wav"] for row in report["entries"]]
        ):
            label = folder / "auto-vcv/labels" / Path(wav).with_suffix(".json")
            if label.exists():
                self.project_records[wav] = json.loads(
                    label.read_text(encoding="utf-8")
                )
        self.project_path = self.project_path or folder / PROJECT_NAME
        self.done(report)
        if report.get("processed_files"):
            for i in range(self.files.count()):
                if self.files.item(i).data(Qt.UserRole) == report["processed_files"][0]:
                    self.files.setCurrentRow(i)
                    break

    def update_progress(self, text):
        ui.set_text(self.status, text)
        ui.append_log(self.log, text)

    def idle(self):
        self.generate.setEnabled(True)
        self.folder.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.open_project_button.setEnabled(True)
        self.save_project_button.setEnabled(True)
        self.stop.setEnabled(False)
        self.table.setEnabled(True)
        self.wave.editable = True
        self.progress.setRange(0, 1)
        self.progress.setValue(1)

    @staticmethod
    def row_display_values(row):
        """Use the same numeric precision for initial display and live edits."""
        return (
            [row["wav"], row["alias"]]
            + [f"{v:.3f}" for v in row["values"]]
            + [" / ".join(row["warnings"])]
        )

    def save_singer_draft(self):
        try:
            self.save_project_snapshot()
        except Exception as exc:
            self.update_progress("프로젝트 저장 실패: " + str(exc))

    def bind_singer_folder(self, folder, draft=None, force=False):
        try:
            self.singer_setup.bind_folder(folder, draft, force)
        except Exception as exc:
            self.singer_setup.folder = None
            self.singer_setup.setEnabled(False)
            self.singer_setup.folder_label.setText(str(exc))
            self.update_progress(str(exc))

    def done(self, report):
        self.bind_singer_folder(self.folder.text())
        self.idle()
        self.mode = report["mode"]
        self.report = report
        self.file_rows = {}
        self.row_warning_flags = {}
        for index, row in enumerate(report["entries"]):
            self.file_rows.setdefault(row["wav"], []).append(index)
            self.row_warning_flags[index] = bool(row["warnings"])
        self.current_record = None
        self.save.setEnabled(self.stage == 2 and bool(report["entries"]))
        self.table.blockSignals(True)
        self.table.setRowCount(len(report["entries"]))
        for i, row in enumerate(report["entries"]):
            values = self.row_display_values(row)
            for j, value in enumerate(values):
                item = QTableWidgetItem(value)
                if j == 7:
                    ui.set_text(item, value)
                if row["warnings"]:
                    item.setForeground(QColor(ui.colors()["warning"]))
                self.table.setItem(i, j, item)
        self.table.blockSignals(False)
        ui.set_text(self.status, self.summary())
        if report.get("detection", {}) and report["detection"].get("warning"):
            ui.set_text(
                self.status, self.summary() + " · " + report["detection"]["warning"]
            )
            ui.append_log(self.log, report["detection"]["warning"])
        for failure in report["failures"]:
            ui.append_log(self.log, str(failure))
        self.refresh_files()
        self.filter_rows()
        if report["entries"]:
            self.table.selectRow(0)
            self.selected()
        elif self.files.count():
            self.files.setCurrentRow(0)
        if self.project_path:
            try:
                self.save_project_snapshot()
            except Exception as exc:
                self.update_progress("프로젝트 저장 실패: " + str(exc))

    def summary(self):
        report = self.report
        return f"{FORMATS[self.mode][0]} · {report['successful_files']}/{report['files']} WAV · {len(report['entries'])}개 원설 · 중복 {report.get('duplicates_removed',0)}개 제거 · 실패 {len(report['failures'])}개"

    def set_stage(self, stage):
        if self.worker and self.worker.isRunning():
            return
        if stage not in (1, 2, 3):
            return
        if stage == 3:
            try:
                self.singer_setup.refresh_from_disk()
            except Exception as exc:
                self.update_progress(str(exc))
        self.stage = stage
        self.workspace_stack.setCurrentIndex(1 if stage == 3 else 0)
        self.undo_shortcut.setEnabled(stage != 3)
        self.wave.set_stage(1 if stage == 1 else 2)
        for n, b in enumerate(self.stage_buttons, 1):
            b.setChecked(n == stage)
        self.table.setVisible(stage == 2)
        self.save.setEnabled(
            stage == 2 and bool(self.report and self.report["entries"])
        )
        ui.set_text(
            self.boundary_info,
            (
                "음소 경계만 드래그하여 수정합니다. 원설 라벨은 2단계에서 표시됩니다."
                if stage == 1
                else "음소 경계는 잠깁니다. 원설 선을 드래그하거나 파형 위에서 왼쪽부터 1~5 키를 눌러 커서 위치로 이동하세요. 키를 누른 채 이동할 수도 있습니다."
            ),
        )
        self.refresh_files()
        self.filter_rows()

    def label_warnings(self, wav):
        path = (
            Path(self.folder.text())
            / "auto-vcv/labels"
            / Path(wav).with_suffix(".json")
        )
        if self.project_path and wav not in self.project_records:
            return ["추정된 음소 경계 없음"]
        if not path.exists() and wav not in self.project_records:
            return ["추정된 음소 경계 없음"]
        try:
            record = self.project_records.get(wav) or json.loads(
                path.read_text(encoding="utf-8")
            )
        except (ValueError, OSError):
            return ["음소 경계 파일을 읽을 수 없음"]
        spans = record.get("intervals", [])
        warnings = list(record.get("label_warnings", []))
        if not spans:
            warnings.append("음소 경계 없음")
        if any(e <= a for a, e, _ in spans):
            warnings.append("음소 구간 길이가 0 이하")
        if any(0 < e - a < 0.015 for a, e, _ in spans):
            warnings.append("15ms 미만 음소: 경계 확인 필요")
        if any(
            abs(spans[i - 1][1] - spans[i][0]) > 0.001 for i in range(1, len(spans))
        ):
            warnings.append("음소 경계 사이에 빈 구간 또는 겹침")
        if record.get("breath_proxy"):
            warnings.append("한숨을 SP로 정렬한 경계: 확인 필요")
        return list(dict.fromkeys(warnings))

    def refresh_files(self):
        if not hasattr(self, "files"):
            return
        current = self.files.currentItem()
        selected = (
            current.data(Qt.UserRole)
            if current
            else (self.current_record or {}).get("wav")
        )
        self.files.blockSignals(True)
        self.files.clear()
        if (
            self.mode in ("en_cvvc", "en_vccv")
            and self.report is None
            and getattr(self, "detection", None)
        ):
            for row in self.detection["file_details"]:
                item = QListWidgetItem(
                    row["wav"]
                    + (" · 리스트 일치" if row["recognized"] else " · 미등록")
                )
                item.setToolTip(
                    "\n".join(row["profiles"]) or "일치하는 공식 리스트 항목 없음"
                )
                self.files.addItem(item)
            self.files.blockSignals(False)
            return
        if self.report:
            failures = {r["wav"]: r["error"] for r in self.report.get("failures", [])}
            names = list(
                dict.fromkeys(
                    list(self.inventory) + list(self.file_rows) + list(failures)
                )
            )
            for wav in names:
                if self.stage == 1:
                    warnings = (
                        [failures[wav]] if wav in failures else self.label_warnings(wav)
                    )
                else:
                    warnings = list(
                        dict.fromkeys(
                            w
                            for i in self.file_rows.get(wav, [])
                            for w in self.report["entries"][i]["warnings"]
                        )
                    )
                    if wav in failures:
                        warnings = ["원설 생성 불가: " + failures[wav]]
                item = QListWidgetItem(
                    wav
                    + ("  ⚠ " + ui.translate(" / ".join(warnings)) if warnings else "")
                )
                item.setData(Qt.UserRole, wav)
                item.setData(Qt.UserRole + 1, bool(warnings))
                item.setToolTip(wav + "\n" + ui.translate("\n".join(warnings)))
                if warnings:
                    item.setForeground(QColor(ui.colors()["warning"]))
                self.files.addItem(item)
                if wav == selected:
                    self.files.setCurrentItem(item)
        self.files.blockSignals(False)

    def select_file(self, item, previous=None):
        if not item or not self.report:
            return
        wav = item.data(Qt.UserRole)
        indices = self.file_rows.get(wav, [])
        if indices:
            self.table.selectRow(indices[0])
            self.selected()
        else:
            self.current_record = None
            self.wave.clear()
            path = Path(self.folder.text()) / wav
            if path.exists():
                record = self.project_records.get(wav)
                if record:
                    self.current_record = deepcopy(record)
                    self.wave.load(path, record["intervals"], None)
                    self.undo.setEnabled(bool(self.histories.get(wav)))
                else:
                    self.wave.load(path, [], None)

    def filter_rows(self):
        if not self.report:
            return
        label_warnings = (
            {wav: self.label_warnings(wav) for wav in self.file_rows}
            if self.stage == 1
            else {}
        )
        for i, row in enumerate(self.report["entries"]):
            warnings = (
                row["warnings"]
                if self.stage == 2
                else label_warnings.get(row["wav"], [])
            )
            self.table.setRowHidden(i, self.review.isChecked() and not warnings)
        for i in range(self.files.count()):
            item = self.files.item(i)
            item.setHidden(self.review.isChecked() and not item.data(Qt.UserRole + 1))

    def failed(self, text):
        self.idle()
        self.update_progress(text)

    def selected(self):
        if not self.report or self.table.currentRow() < 0:
            return
        row = self.report["entries"][self.table.currentRow()]
        if (
            row["wav"] in self.pending_external_wavs
            and row["wav"] not in self.inventory
        ):
            self.current_record = None
            self.wave.clear()
            self.update_progress("새 WAV의 다시 로드를 취소하여 표시하지 않습니다.")
            return
        folder = Path(self.folder.text())
        if self.current_record and self.current_record["wav"] == row["wav"]:
            record = self.current_record
        else:
            label = folder / "auto-vcv/labels" / Path(row["wav"]).with_suffix(".json")
            saved = self.project_records.get(row["wav"])
            if saved is not None:
                record = deepcopy(saved)
            elif self.project_path:
                self.current_record = None
                (
                    self.wave.load(folder / row["wav"], [], row)
                    if (folder / row["wav"]).is_file()
                    else self.wave.clear()
                )
                return
            elif not label.exists() or not (folder / row["wav"]).is_file():
                self.current_record = None
                self.wave.clear()
                self.undo.setEnabled(False)
                ui.set_text(
                    self.boundary_info,
                    "해당 WAV의 경계가 없어 기존 원설 값을 유지합니다.",
                )
                return
            else:
                record = json.loads(label.read_text(encoding="utf-8"))
        if not self.project_path and is_korean(self.mode) and self.mode != "ko_cvvc":
            from korean_formats import make_record_metadata

            record.update(make_record_metadata(Path(row["wav"]).stem, self.mode))
        self.current_record = record
        self.files.blockSignals(True)
        for i in range(self.files.count()):
            if self.files.item(i).data(Qt.UserRole) == row["wav"]:
                self.files.setCurrentRow(i)
                break
        self.files.blockSignals(False)
        self.wave.load(folder / row["wav"], record["intervals"], row)
        self.undo.setEnabled(bool(self.histories.get(row["wav"])))

    def update_scroll(self, start, length):
        self.scroll.blockSignals(True)
        self.scroll.setRange(0, max(0, round((self.wave.duration - length) * 1000)))
        self.scroll.setPageStep(max(1, round(length * 1000)))
        self.scroll.setSingleStep(20)
        self.scroll.setValue(round(start * 1000))
        self.scroll.blockSignals(False)

    def show_boundary(self, index, seconds):
        if not self.current_record:
            return
        spans = self.current_record["intervals"]
        ui.set_text(
            self.boundary_info,
            f"{spans[index-1][2]} → {spans[index][2]} · {seconds:.3f}초 · 드래그 즉시 재계산 / 놓으면 자동 저장",
        )

    def begin_edit(self):
        if self.current_record:
            self.pending_before = {
                "stage": self.stage,
                "intervals": deepcopy(self.current_record["intervals"]),
                "rows": deepcopy(
                    [
                        self.report["entries"][i]
                        for i in self.file_rows.get(self.current_record["wav"], [])
                    ]
                ),
            }

    def edit_boundary(self, index, seconds):
        if self.stage != 1 or not self.current_record:
            return
        seconds = move_boundary(self.current_record, index, seconds)
        self.refresh_edited_file()
        self.show_boundary(index, seconds)

    def edit_oto(self, index, seconds):
        if self.stage != 2 or not self.current_record or self.table.currentRow() < 0:
            return
        row = self.report["entries"][self.table.currentRow()]
        edit_oto_marker(row, index, seconds, self.current_record["duration"])
        self.refresh_edited_file(recalculate=False)

    def refresh_edited_file(self, recalculate=True):
        changed = (
            recalculate_file(
                self.report,
                self.current_record,
                self.file_rows.get(self.current_record["wav"]),
            )
            if recalculate
            else self.file_rows.get(self.current_record["wav"], [])
        )
        self.table.blockSignals(True)
        for i in changed:
            row = self.report["entries"][i]
            warning_changed = self.row_warning_flags.get(i) != bool(row["warnings"])
            self.row_warning_flags[i] = bool(row["warnings"])
            values = self.row_display_values(row)
            for j, value in enumerate(values):
                item = self.table.item(i, j)
                if item.text() != value:
                    ui.set_text(item, value) if j == 7 else item.setText(value)
                if warning_changed:
                    item.setForeground(
                        QColor(
                            ui.colors()["warning"]
                            if row["warnings"]
                            else ui.colors()["text"]
                        )
                    )
        self.table.blockSignals(False)
        selected = self.table.currentRow()
        if selected >= 0:
            self.wave.row = self.report["entries"][selected]
        self.wave.spans = self.current_record["intervals"]
        self.wave.update()

    def finish_edit(self):
        if not self.current_record or self.pending_before is None:
            return
        current_rows = [
            self.report["entries"][i]
            for i in self.file_rows.get(self.current_record["wav"], [])
        ]
        if (
            self.pending_before["intervals"] != self.current_record["intervals"]
            or self.pending_before["rows"] != current_rows
        ):
            self.histories.setdefault(self.current_record["wav"], []).append(
                self.pending_before
            )
            self.save_edits()
        self.pending_before = None
        self.refresh_files()
        self.filter_rows()
        self.undo.setEnabled(bool(self.histories.get(self.current_record["wav"])))

    def save_edits(self):
        try:
            folder = Path(self.folder.text())
            save_record(folder, self.current_record)
            persist_report(folder, self.report)
            self.save_project_snapshot()
            if self.stage == 1:
                ui.set_text(self.status, self.summary() + " · 음소 경계 저장 완료")
                return
            if not self.edit_backup_done:
                install_oto(folder, self.mode)
                self.edit_backup_done = True
            elif self.mode == "en_vccv" and not (folder / "oto.ini").exists():
                from english_vccv import install_nested_oto

                install_nested_oto(folder, backup=False, wav=self.current_record["wav"])
            else:
                atomic_write(
                    folder / "oto.ini",
                    (output_dir(folder, self.mode) / "oto.preview.ini").read_bytes(),
                )
            self.acknowledge_oto_writes()
            ui.set_text(
                self.status, self.summary() + " · 수정 경계와 oto.ini 저장 완료"
            )
        except Exception as exc:
            self.update_progress(f"수정 저장 실패: {exc}")

    def undo_edit(self):
        if not self.current_record or (self.worker and self.worker.isRunning()):
            return
        history = self.histories.get(self.current_record["wav"], [])
        if history:
            snapshot = history.pop()
            self.current_record["intervals"] = snapshot["intervals"]
            for i, row in zip(
                self.file_rows.get(self.current_record["wav"], []), snapshot["rows"]
            ):
                self.report["entries"][i] = row
            self.refresh_edited_file(recalculate=False)
            self.refresh_files()
            self.filter_rows()
            self.save_edits()
            self.undo.setEnabled(bool(history))

    def play_segment(self, begin, end):
        if self.wave.path is None:
            return
        if self.playback_needs_reload():
            return
        from audio_playback import set_wav_segment_source

        previous = getattr(self, "playback_buffer", None)
        self.player.stop()
        try:
            self.playback_buffer = set_wav_segment_source(
                self.player, self.wave.path, begin, end, self
            )
        except Exception as exc:
            self.failed(str(exc))
            return
        if previous is not None:
            previous.deleteLater()
        self.player.play()

    def play_audio(self):
        if self.wave.path is None:
            return
        if self.playback_needs_reload():
            return
        from audio_playback import set_wav_source

        previous = getattr(self, "playback_buffer", None)
        self.player.stop()
        try:
            self.playback_buffer = set_wav_source(self.player, self.wave.path, self)
        except Exception as exc:
            self.failed(str(exc))
            return
        if previous is not None:
            previous.deleteLater()
        self.player.play()

    def playback_needs_reload(self):
        if self.wave.path is None:
            return False
        name = (
            self.wave.path.resolve()
            .relative_to(Path(self.folder.text()).resolve())
            .as_posix()
        )
        if name not in self.pending_external_wavs:
            return False
        self.update_progress(
            "WAV 변경 후 다시 로드를 취소했습니다. 파일을 다시 열거나 다음 변경 때 다시 로드를 선택해주세요."
        )
        return True

    def save_oto(self):
        if self.stage != 2:
            return
        try:
            if self.current_record:
                save_record(self.folder.text(), self.current_record)
            if self.report:
                persist_report(self.folder.text(), self.report)
            target = install_oto(self.folder.text(), self.mode)
            self.acknowledge_oto_writes()
            self.update_progress(f"저장 완료: {target}")
        except Exception as exc:
            self.failed(str(exc))

    def closeEvent(self, event):
        if (
            self.singer_setup.export_worker
            and self.singer_setup.export_worker.isRunning()
        ):
            self.update_progress(ui.translate("ZIP 내보내기 중…"))
            event.ignore()
            return
        self.singer_save_timer.stop()
        if self.reload_worker and self.reload_worker.isRunning():
            self.update_progress(
                "자료를 다시 로드하는 중입니다. 완료 후 창을 닫아주세요."
            )
            event.ignore()
            return
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            ui.set_text(
                self.status, "현재 WAV 분석이 끝나면 중지됩니다. 그 후 창을 닫아주세요."
            )
            event.ignore()
        else:
            self.file_timer.stop()
            self._watch_folder = None
            if self.file_scanner:
                self.file_scanner.wait()
            self._stop_assets()
            for job in list(self.wave._load_jobs):
                job.wait()
            if self.project_path:
                try:
                    self.save_project_snapshot()
                except Exception as exc:
                    self.update_progress("프로젝트 저장 실패: " + str(exc))
                    event.ignore()
                    return
            event.accept()


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        wav = Path(sys.argv[sys.argv.index("--self-test") + 1])
        out = wav.parent / "auto-vcv/packaged-self-test"
        mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "vcv"
        mode, _ = resolve_mode(wav.parent, mode)
        from vcv_core import create_alignment_engine

        engine = create_alignment_engine(wav.parent, mode)
        try:
            rows, record = engine.analyze(wav, out, mode)
        finally:
            engine.close()
        (out / "result.json").write_text(
            json.dumps(
                {"entries": rows, "intervals": record["intervals"]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        sys.exit(0)
    app = QApplication(sys.argv)
    app.setApplicationName("OTONova")
    app.setApplicationDisplayName("OTONova V2.0")
    app.setWindowIcon(QIcon(str(RESOURCE_ROOT / "assets/otonova.ico")))
    ui.apply_font()
    window = Window()
    project_argument = next(
        (
            Path(arg)
            for arg in sys.argv[1:]
            if arg.lower().endswith(".otonova") and Path(arg).is_file()
        ),
        None,
    )
    if project_argument:
        window.restore_project(project_argument)
    if "--mode" in sys.argv:
        window.set_mode(sys.argv[sys.argv.index("--mode") + 1])
    window.show()
    from platform_support import set_windows_taskbar_icon

    set_windows_taskbar_icon(window, RESOURCE_ROOT / "assets/otonova.ico")
    if "--ui-check" in sys.argv:
        from PySide6.QtCore import QTimer
        from platform_support import log_path

        preview = log_path("gui-preview.png")

        def capture_preview():
            success = window.grab().save(str(preview))
            app.exit(0 if success else 1)

        QTimer.singleShot(1200, capture_preview)
    sys.exit(app.exec())
