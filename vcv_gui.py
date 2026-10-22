import sys
import os
import json
from copy import deepcopy
import ui_settings as ui
from PySide6.QtCore import QSettings
from pathlib import Path
if getattr(sys,'frozen',False):
    # Numba resolves the frozen code's relative source path when constructing its cache.
    os.chdir(sys._MEIPASS)
import numpy as np
import soundfile as sf
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QColor, QFont, QFontDatabase, QShortcut, QKeySequence, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QPushButton,QLineEdit,QFileDialog,QLabel,QProgressBar,QTableWidget,QTableWidgetItem,
    QScrollBar,QPlainTextEdit,QMessageBox,QHeaderView,QDialog,QTextBrowser,QDialogButtonBox,QListWidget,QListWidgetItem,QSplitter,QComboBox)
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput
from vcv_core import (ROOT,RESOURCE_ROOT,DEFAULT_FOLDER,run_folder,install_oto,move_boundary,
                      edit_oto_marker,recalculate_file,persist_report,save_record,atomic_write,output_dir,RULES_VERSION,read_existing_oto)
from audio_view import AudioEditor as Waveform, SPECTRUM_PALETTES
from formats import FORMATS,PUBLIC_FORMATS,public_mode,is_korean
from format_detection import resolve_mode

class Worker(QThread):
    progress = Signal(str)
    completed = Signal(dict)
    failed = Signal(str)
    def __init__(self,folder,mode='vcv'):
        super().__init__()
        self.folder=folder
        self.mode=mode
    def run(self):
        try:
            self.completed.emit(run_folder(self.folder,self.progress.emit,self.isInterruptionRequested,self.mode))
        except Exception as exc:
            self.failed.emit(str(exc))

class Window(QMainWindow):
    def __init__(self, settings=None):
        super().__init__()
        self.preferences=settings if settings is not None else QSettings('OtoNova','OtoNova')
        ui.language=str(self.preferences.value('language','ko'))
        if ui.language not in ui.LANGUAGES:ui.language='ko'
        ui.theme=str(self.preferences.value('theme','dark'))
        if ui.theme not in ('dark','light'):ui.theme='dark'
        ui.set_title(self, 'OTONova V1.0 · 일본어 / 한국어 / 영어 자동 원설기')
        self.setWindowIcon(QIcon(str(RESOURCE_ROOT/'assets/otonova.ico')))
        self.resize(1320,1000)
        ui.spectrum_palette=str(self.preferences.value('spectrum_palette','classic'))
        if ui.spectrum_palette not in SPECTRUM_PALETTES:ui.spectrum_palette='classic'
        self.worker=None
        self.report=None
        self.current_record=None
        self.histories={}
        self.pending_before=None
        self.edit_backup_done=False
        self.file_rows={}
        self.row_warning_flags={}
        self.stage=1
        self.mode='vcv'
        self.mode_chosen=False
        central=QWidget()
        self.setCentralWidget(central)
        layout=QVBoxLayout(central)
        title=ui.label('OTONova V1.0')
        title.setStyleSheet('font-size:24px;font-weight:700;padding:10px')
        title_bar=QHBoxLayout()
        logo=ui.label()
        logo.setPixmap(QPixmap(str(RESOURCE_ROOT/'assets/otonova-logo.png')).scaled(48,48,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        title_bar.addWidget(logo)
        title_bar.addWidget(title,1)
        self.settings_button=ui.button('설정')
        self.settings_button.clicked.connect(self.show_settings)
        title_bar.addWidget(self.settings_button)
        self.credits_button=ui.button('크레딧')
        self.credits_button.clicked.connect(self.show_credits)
        title_bar.addWidget(self.credits_button)
        layout.addLayout(title_bar)
        layout.addWidget(ui.label('파일명 / 인덱스 인식 → 모델 음소 정렬 → 지정 규칙으로 원설 생성'))
        bar=QHBoxLayout()
        self.folder=QLineEdit(str(DEFAULT_FOLDER))
        self.folder.setReadOnly(True)
        browse=ui.button('음원 폴더')
        self.browse_button=browse
        browse.clicked.connect(self.browse)
        bar.addWidget(self.folder,1)
        bar.addWidget(browse)
        self.mode_button=ui.button('형식: 연속음 (VCV)')
        self.mode_button.clicked.connect(self.choose_mode)
        bar.addWidget(self.mode_button)
        self.generate=ui.button('VCV 원설 생성')
        self.generate.clicked.connect(self.start)
        bar.addWidget(self.generate)
        self.stop=ui.button('중지')
        self.stop.setEnabled(False)
        self.stop.clicked.connect(lambda:self.worker.requestInterruption())
        bar.addWidget(self.stop)
        self.save=ui.button('oto.ini 저장 (기존 파일 백업)')
        self.save.setEnabled(False)
        self.save.clicked.connect(self.save_oto)
        bar.addWidget(self.save)
        layout.addLayout(bar)
        self.status=ui.label('준비')
        layout.addWidget(self.status)
        self.progress=QProgressBar()
        self.progress.setRange(0,1)
        layout.addWidget(self.progress)
        stages=QHBoxLayout()
        self.stage_buttons=[]
        for number,text in [(1,'1단계 · 음소 경계'),(2,'2단계 · 원설 조정')]:
            button=ui.button(text);button.setCheckable(True)
            button.clicked.connect(lambda checked=False,n=number:self.set_stage(n))
            stages.addWidget(button);self.stage_buttons.append(button)
        layout.addLayout(stages)
        self.splitter=QSplitter(Qt.Horizontal)
        editor=QWidget();editor_layout=QVBoxLayout(editor);editor_layout.setContentsMargins(0,0,0,0)
        side=QWidget();side_layout=QVBoxLayout(side);side_layout.setContentsMargins(0,0,0,0)
        self.splitter.addWidget(editor);self.splitter.addWidget(side)
        self.splitter.setStretchFactor(0,3);self.splitter.setStretchFactor(1,2)
        self.splitter.setSizes([850,470]);layout.addWidget(self.splitter,1)
        self.wave=Waveform()
        self.wave.segmentRequested.connect(self.play_segment)
        self.wave.editStarted.connect(self.begin_edit)
        self.wave.boundaryMoved.connect(self.edit_boundary)
        self.wave.otoMoved.connect(self.edit_oto)
        self.wave.editFinished.connect(self.finish_edit)
        self.wave.boundarySelected.connect(self.show_boundary)
        editor_layout.addWidget(self.wave,1)
        self.scroll=QScrollBar(Qt.Horizontal)
        self.scroll.valueChanged.connect(lambda value:self.wave.set_view(value/1000,self.wave.length))
        self.wave.viewChanged.connect(self.update_scroll)
        editor_layout.addWidget(self.scroll)
        audio_bar=QHBoxLayout()
        self.play=ui.button('선택한 WAV 듣기')
        self.play.clicked.connect(self.play_audio)
        self.player=QMediaPlayer()
        self.audio=QAudioOutput()
        self.player.setAudioOutput(self.audio)
        audio_bar.addWidget(self.play)
        self.review=ui.button('검토 항목만 보기')
        self.review.setCheckable(True)
        self.review.toggled.connect(self.filter_rows)
        audio_bar.addWidget(self.review)
        for label,factor in [('확대 +',1.5),('축소 -',1/1.5)]:
            button=ui.button(label)
            button.clicked.connect(lambda checked=False,f=factor:self.wave.zoom(f))
            audio_bar.addWidget(button)
        reset=ui.button('전체 보기')
        reset.clicked.connect(self.wave.reset_view)
        audio_bar.addWidget(reset)
        self.undo=ui.button('경계 되돌리기 (Ctrl+Z)')
        self.undo.setEnabled(False)
        self.undo.clicked.connect(self.undo_edit)
        audio_bar.addWidget(self.undo)
        self.undo_shortcut=QShortcut(QKeySequence.Undo,self)
        self.undo_shortcut.activated.connect(self.undo_edit)
        audio_bar.addStretch()
        editor_layout.addLayout(audio_bar)
        self.boundary_info=ui.label('보라색 점선 음소 경계를 드래그하세요 · 즉시 재계산 · 놓으면 경계와 oto.ini 자동 저장')
        self.boundary_info.setWordWrap(True)
        editor_layout.addWidget(self.boundary_info)
        side_layout.addWidget(ui.label('파일 · 현재 단계의 경고'))
        self.files=QListWidget()
        self.files.currentItemChanged.connect(self.select_file)
        side_layout.addWidget(self.files,1)
        self.table=QTableWidget(0,8)
        self.table.setHorizontalHeaderLabels([ui.translate(x) for x in ['WAV','에일리어스','오프셋','고정','컷오프','선행','오버랩','검토']])
        self.table.setColumnHidden(0,True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for column,width in enumerate([0,90,75,75,80,75,75]):
            self.table.setColumnWidth(column,width)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.selected)
        side_layout.addWidget(self.table,2)
        self.log=QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        layout.addWidget(self.log)
        self.apply_preferences()
        self.set_stage(1)
        self.load_report()
        self.refresh_files()
        for button in self.stage_buttons:button.setEnabled(True)
    def apply_preferences(self):
        ui.apply_font()
        self.setStyleSheet(ui.stylesheet())
        ui.refresh()
        if hasattr(self,'table'):
            self.table.setHorizontalHeaderLabels([ui.translate(x) for x in ['WAV','에일리어스','오프셋','고정','컷오프','선행','오버랩','검토']])
            for row in range(self.table.rowCount()):
                for col in range(self.table.columnCount()):
                    item=self.table.item(row,col)
                    if item:item.setForeground(QColor(ui.colors()['warning'] if col==7 and item.text() else ui.colors()['text']))
        if hasattr(self,'wave'):
            self.wave._background_key=None
            self.wave.update_spectrum_palette()
            self.wave.setToolTip(ui.translate('음소 경계선 드래그: 실시간 원설 · 휠: 확대/축소 · 아래 스크롤바: 이동')+'\n'+ui.translate('우클릭: 라벨 사이 구간 재생'))
            self.wave.update()
        self.refresh_files()

    def show_settings(self):
        dialog=QDialog(self)
        ui.set_title(dialog,'설정')
        layout=QVBoxLayout(dialog)
        layout.addWidget(ui.label('표시 언어'))
        languages=QComboBox()
        for key,name in ui.LANGUAGES.items():languages.addItem(name,key)
        languages.setCurrentIndex(languages.findData(ui.language))
        layout.addWidget(languages)
        layout.addWidget(ui.label('화면 모드'))
        themes=QComboBox()
        for key,name in [('dark','다크'),('light','라이트')]:themes.addItem(ui.translate(name),key)
        themes.setCurrentIndex(themes.findData(ui.theme))
        layout.addWidget(themes)
        layout.addWidget(ui.label('스펙트로그램 색상'))
        palettes=QComboBox()
        for key,(name,colors) in SPECTRUM_PALETTES.items():palettes.addItem(ui.translate(name),key)
        palettes.setCurrentIndex(palettes.findData(ui.spectrum_palette))
        layout.addWidget(palettes)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(ui.translate('확인'))
        buttons.button(QDialogButtonBox.Cancel).setText(ui.translate('취소'))
        buttons.button(QDialogButtonBox.Ok).setText(ui.translate('확인'))
        buttons.button(QDialogButtonBox.Cancel).setText(ui.translate('취소'))
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec()!=QDialog.Accepted:return
        self.set_preferences(languages.currentData(),themes.currentData(),palettes.currentData())

    def set_preferences(self, language, theme, spectrum_palette=None):
        if language not in ui.LANGUAGES or theme not in ('dark','light'):raise ValueError('Invalid preferences')
        if spectrum_palette is not None:
            if spectrum_palette not in SPECTRUM_PALETTES:raise ValueError('Invalid spectrogram palette')
            ui.spectrum_palette=spectrum_palette
            self.preferences.setValue('spectrum_palette',spectrum_palette)
        ui.language=language;ui.theme=theme
        self.preferences.setValue('language',language);self.preferences.setValue('theme',theme);self.preferences.sync()
        self.apply_preferences()

    def show_credits(self):
        dialog=QDialog(self)
        ui.set_title(dialog, '모델 크레딧')
        dialog.resize(640,700)
        layout=QVBoxLayout(dialog)
        browser=QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.document().setDefaultStyleSheet('a { color: '+ui.colors()['accent']+'; }')
        browser.setMarkdown((RESOURCE_ROOT/'assets/CREDITS.md').read_text(encoding='utf-8'))
        layout.addWidget(browser)
        buttons=QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText(ui.translate('닫기'))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
    def browse(self):
        folder=QFileDialog.getExistingDirectory(self,ui.translate('음원 폴더'),self.folder.text())
        if folder:
            self.folder.setText(folder)
            self.mode_chosen=False
            self.choose_mode()
    def set_mode(self,mode):
        if mode not in FORMATS:raise ValueError(mode)
        self.selected_mode=public_mode(mode)
        template,_=read_existing_oto(Path(self.folder.text())/'oto.ini')
        if self.selected_mode=='en_vccv':
            from english_vccv import read_templates
            template,_=read_templates(self.folder.text())
        self.mode,self.detection=resolve_mode(self.folder.text(),self.selected_mode,template)
        self.wave.empty_message='원설 행 선택 → 음소 경계 드래그 → 즉시 재계산'
        self.mode_chosen=True
        self.set_stage(1)
        title=PUBLIC_FORMATS[self.selected_mode][0]
        ui.set_text(self.mode_button, '형식: '+title)
        ui.set_text(self.generate, '음소 경계 추정 / 원설 생성')
        self.load_report()
        self.refresh_files()
        for button in self.stage_buttons:button.setEnabled(True)
        if self.detection:
            message=self.detection.get('summary','녹음 리스트 자동 인식 완료')
            if self.detection['warning']:message+=' · '+self.detection['warning']
            ui.set_text(self.status, message)
            ui.append_log(self.log, message)
            if self.mode=='en_cvvc':
                for row in self.detection['components']:
                    ui.append_log(self.log, f"{row['family']} · {row['profile']} · {row['section']} · WAV {row['matched_files']} / TXT {row['list_matches']}")
    def choose_mode(self):
        dialog=QDialog(self);ui.set_title(dialog, '음원 형식 선택')
        layout=QVBoxLayout(dialog)
        layout.addWidget(ui.label('언어와 녹음 리스트 형식을 선택하세요.'))
        combo=QComboBox();combo.setMinimumWidth(440)
        for key,(label,language,kind) in PUBLIC_FORMATS.items():combo.addItem(ui.translate(label),key)
        combo.setCurrentIndex(combo.findData(public_mode(self.mode)));layout.addWidget(combo)
        info=ui.label('세부 녹음 방식은 파일명·녹음 리스트·기존 에일리어스로 자동 인식합니다.\n기존 oto.ini가 있으면 그 에일리어스 목록을 유지합니다.')
        info.setWordWrap(True);layout.addWidget(info)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(ui.translate('확인'))
        buttons.button(QDialogButtonBox.Cancel).setText(ui.translate('취소'))
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()!=QDialog.Accepted:return False
        self.set_mode(combo.currentData());return True
    def load_report(self):
        self.report=None
        self.current_record=None
        self.histories={}
        self.pending_before=None
        self.edit_backup_done=False
        self.table.setRowCount(0)
        self.files.clear()
        self.save.setEnabled(False)
        self.wave.clear()
        path=output_dir(self.folder.text(),self.mode)/'report.json'
        if path.exists():
            report=json.loads(path.read_text(encoding='utf-8'))
            template,_=read_existing_oto(Path(self.folder.text())/'oto.ini')
            if self.mode=='en_vccv':
                from english_vccv import read_templates
                template,_=read_templates(self.folder.text())
            changed_template=(template is not None and
                [(r['wav'],r['alias']) for r in template]!=[(r['wav'],r['alias']) for r in report['entries']])
            if (any('source_index' not in r for r in report['entries']) or
                report.get('rules_version',1)<RULES_VERSION or changed_template):
                ui.set_text(self.status, '음소 처리 규칙이 변경되었습니다. 생성을 눌러 다시 추정해주세요.')
                return
            # Another format may have corrected the shared labels since this report.
            grouped={}
            english_resolver=None
            if self.mode=='en_arpasing':
                from arpasing_core import ArpasingResolver
                english_resolver=ArpasingResolver(self.folder.text())
            elif self.mode=='en_cvvc':
                from english_cvvc import CvvcResolver
                english_resolver=CvvcResolver(self.folder.text())
            elif self.mode=='en_vccv':
                from english_vccv import VccvResolver
                english_resolver=VccvResolver(self.folder.text())
            for i,row in enumerate(report['entries']):grouped.setdefault(row['wav'],[]).append(i)
            for wav,indices in grouped.items():
                label=Path(self.folder.text())/'auto-vcv/labels'/Path(wav).with_suffix('.json')
                if label.exists():
                    automatic=[i for i in indices if not report['entries'][i].get('manual_oto')]
                    record=json.loads(label.read_text(encoding='utf-8'))
                    if english_resolver:
                        try:metadata=english_resolver.metadata(Path(self.folder.text())/wav)
                        except ValueError as exc:
                            ui.set_text(self.status, str(exc));return
                        units_key='vccv_units' if self.mode=='en_vccv' else 'cvvc_units' if self.mode=='en_cvvc' else 'arpasing_units'
                        version_key='vccv_version' if self.mode=='en_vccv' else 'cvvc_version'
                        if metadata['phones']!=record['phones'] or metadata[units_key]!=record.get(units_key) or self.mode in ('en_cvvc','en_vccv') and metadata[version_key]!=record.get(version_key):
                            ui.set_text(self.status, '영어 음소 매핑이 변경되었습니다. 다시 생성해주세요.');return
                        record.update(metadata)
                    if is_korean(self.mode) and self.mode!='ko_cvvc':
                        from korean_formats import make_record_metadata
                        metadata=make_record_metadata(Path(wav).stem,self.mode)
                        if metadata['phones']!=record['phones']:
                            ui.set_text(self.status, '형식의 음소열이 변경되었습니다. 생성을 눌러 다시 추정해주세요.');return
                        record.update(metadata)
                    if automatic:recalculate_file(report,record,automatic)
            persist_report(self.folder.text(),report)
            self.done(report)
        else:ui.set_text(self.status, '준비 · '+FORMATS[self.mode][0]+' 원설 생성을 눌러주세요')
    def start(self):
        from arpasing_core import wav_files
        if not self.mode_chosen and not self.choose_mode():return
        if not (wav_files(self.folder.text()) if getattr(self,'selected_mode',self.mode) in ('en_arpasing','en_cvvc','en_vccv') else list(Path(self.folder.text()).glob('*.wav'))):
            QMessageBox.warning(self,ui.translate('음원 없음'),ui.translate('선택한 폴더에 WAV가 없습니다.'))
            return
        self.set_mode(getattr(self,'selected_mode',public_mode(self.mode)))
        self.set_stage(1)
        self.generate.setEnabled(False)
        self.folder.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.mode_button.setEnabled(False)
        self.save.setEnabled(False)
        self.stop.setEnabled(True)
        self.table.setEnabled(False)
        self.wave.editable=False
        self.undo.setEnabled(False)
        self.progress.setRange(0,0)
        self.worker=Worker(self.folder.text(),getattr(self,'selected_mode',self.mode))
        self.worker.progress.connect(self.update_progress)
        self.worker.completed.connect(self.done)
        self.worker.failed.connect(self.failed)
        self.worker.start()
    def update_progress(self,text):
        ui.set_text(self.status, text)
        ui.append_log(self.log, text)
    def idle(self):
        self.generate.setEnabled(True)
        self.folder.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.mode_button.setEnabled(True)
        self.stop.setEnabled(False)
        self.table.setEnabled(True)
        self.wave.editable=True
        self.progress.setRange(0,1)
        self.progress.setValue(1)
    def done(self,report):
        self.idle()
        self.mode=report['mode']
        self.report=report
        self.file_rows={}
        self.row_warning_flags={}
        for index,row in enumerate(report['entries']):
            self.file_rows.setdefault(row['wav'],[]).append(index)
            self.row_warning_flags[index]=bool(row['warnings'])
        self.current_record=None
        self.save.setEnabled(self.stage==2 and bool(report['entries']))
        self.table.blockSignals(True)
        self.table.setRowCount(len(report['entries']))
        for i,row in enumerate(report['entries']):
            values=[row['wav'],row['alias']]+[f'{v:.3f}' for v in row['values']]+[' / '.join(row['warnings'])]
            for j,value in enumerate(values):
                item=QTableWidgetItem(value)
                if j==7:ui.set_text(item,value)
                if row['warnings']: item.setForeground(QColor(ui.colors()['warning']))
                self.table.setItem(i,j,item)
        self.table.blockSignals(False)
        ui.set_text(self.status, self.summary())
        if report.get('detection',{} ) and report['detection'].get('warning'):
            ui.set_text(self.status, self.summary()+' · '+report['detection']['warning'])
            ui.append_log(self.log, report['detection']['warning'])
        for failure in report['failures']: ui.append_log(self.log, str(failure))
        self.refresh_files()
        self.filter_rows()
        if report['entries']:
            self.table.selectRow(0)
            self.selected()
        elif self.files.count():self.files.setCurrentRow(0)
    def summary(self):
        report=self.report
        return f"{FORMATS[self.mode][0]} · {report['successful_files']}/{report['files']} WAV · {len(report['entries'])}개 원설 · 중복 {report.get('duplicates_removed',0)}개 제거 · 실패 {len(report['failures'])}개"
    def set_stage(self,stage):
        if self.worker and self.worker.isRunning():return
        self.stage=stage;self.wave.set_stage(stage)
        for n,b in enumerate(self.stage_buttons,1):b.setChecked(n==stage)
        self.table.setVisible(stage==2)
        self.save.setEnabled(stage==2 and bool(self.report and self.report['entries']))
        ui.set_text(self.boundary_info, '음소 경계만 드래그하여 수정합니다. 원설 라벨은 2단계에서 표시됩니다.' if stage==1 else '음소 경계는 잠깁니다. 원설 선을 드래그하거나 파형 위에서 왼쪽부터 1~5 키를 눌러 커서 위치로 이동하세요. 키를 누른 채 이동할 수도 있습니다.')
        self.refresh_files()
        self.filter_rows()

    def label_warnings(self,wav):
        path=Path(self.folder.text())/'auto-vcv/labels'/Path(wav).with_suffix('.json')
        if not path.exists():return ['추정된 음소 경계 없음']
        try:record=json.loads(path.read_text(encoding='utf-8'))
        except (ValueError,OSError):return ['음소 경계 파일을 읽을 수 없음']
        spans=record.get('intervals',[]);warnings=list(record.get('label_warnings',[]))
        if not spans:warnings.append('음소 경계 없음')
        if any(e<=a for a,e,_ in spans):warnings.append('음소 구간 길이가 0 이하')
        if any(0<e-a<.015 for a,e,_ in spans):warnings.append('15ms 미만 음소: 경계 확인 필요')
        if any(abs(spans[i-1][1]-spans[i][0])>.001 for i in range(1,len(spans))):warnings.append('음소 경계 사이에 빈 구간 또는 겹침')
        if record.get('breath_proxy'):warnings.append('한숨을 SP로 정렬한 경계: 확인 필요')
        return list(dict.fromkeys(warnings))

    def refresh_files(self):
        if not hasattr(self,'files'):return
        current=self.files.currentItem()
        selected=current.data(Qt.UserRole) if current else (self.current_record or {}).get('wav')
        self.files.blockSignals(True);self.files.clear()
        if self.mode in ('en_cvvc','en_vccv') and self.report is None and getattr(self,'detection',None):
            for row in self.detection['file_details']:
                item=QListWidgetItem(row['wav']+(' · 리스트 일치' if row['recognized'] else ' · 미등록'))
                item.setToolTip('\n'.join(row['profiles']) or '일치하는 공식 리스트 항목 없음')
                self.files.addItem(item)
            self.files.blockSignals(False)
            return
        if self.report:
            failures={r['wav']:r['error'] for r in self.report.get('failures',[])}
            names=list(dict.fromkeys(list(self.file_rows)+list(failures)))
            for wav in names:
                if self.stage==1:
                    warnings=[failures[wav]] if wav in failures else self.label_warnings(wav)
                else:
                    warnings=list(dict.fromkeys(w for i in self.file_rows.get(wav,[]) for w in self.report['entries'][i]['warnings']))
                    if wav in failures:warnings=['원설 생성 불가: '+failures[wav]]
                item=QListWidgetItem(wav+('  ⚠ '+ ui.translate(' / '.join(warnings)) if warnings else ''))
                item.setData(Qt.UserRole,wav);item.setData(Qt.UserRole+1,bool(warnings));item.setToolTip(wav+'\n'+ui.translate('\n'.join(warnings)))
                if warnings:item.setForeground(QColor(ui.colors()['warning']))
                self.files.addItem(item)
                if wav==selected:self.files.setCurrentItem(item)
        self.files.blockSignals(False)

    def select_file(self,item,previous=None):
        if not item or not self.report:return
        wav=item.data(Qt.UserRole);indices=self.file_rows.get(wav,[])
        if indices:self.table.selectRow(indices[0]);self.selected()
        else:
            self.current_record=None;self.wave.clear()
            path=Path(self.folder.text())/wav
            if path.exists():self.wave.load(path,[],None)

    def filter_rows(self):
        if not self.report:return
        label_warnings={wav:self.label_warnings(wav) for wav in self.file_rows} if self.stage==1 else {}
        for i,row in enumerate(self.report['entries']):
            warnings=row['warnings'] if self.stage==2 else label_warnings.get(row['wav'],[])
            self.table.setRowHidden(i,self.review.isChecked() and not warnings)
        for i in range(self.files.count()):
            item=self.files.item(i);item.setHidden(self.review.isChecked() and not item.data(Qt.UserRole+1))
    def failed(self,text):
        self.idle()
        self.update_progress(text)
    def selected(self):
        if not self.report or self.table.currentRow()<0:return
        row=self.report['entries'][self.table.currentRow()]
        folder=Path(self.folder.text())
        if self.current_record and self.current_record['wav']==row['wav']:
            record=self.current_record
        else:
            label=folder/'auto-vcv/labels'/Path(row['wav']).with_suffix('.json')
            if not label.exists() or not (folder/row['wav']).is_file():
                self.current_record=None
                self.wave.clear()
                self.undo.setEnabled(False)
                ui.set_text(self.boundary_info, '해당 WAV의 경계가 없어 기존 원설 값을 유지합니다.')
                return
            record=json.loads(label.read_text(encoding='utf-8'))
        if is_korean(self.mode) and self.mode!='ko_cvvc':
            from korean_formats import make_record_metadata
            record.update(make_record_metadata(Path(row['wav']).stem,self.mode))
        self.current_record=record
        self.files.blockSignals(True)
        for i in range(self.files.count()):
            if self.files.item(i).data(Qt.UserRole)==row['wav']:self.files.setCurrentRow(i);break
        self.files.blockSignals(False)
        self.wave.load(folder/row['wav'],record['intervals'],row)
        self.undo.setEnabled(bool(self.histories.get(row['wav'])))
    def update_scroll(self,start,length):
        self.scroll.blockSignals(True)
        self.scroll.setRange(0,max(0,round((self.wave.duration-length)*1000)))
        self.scroll.setPageStep(max(1,round(length*1000)))
        self.scroll.setSingleStep(20)
        self.scroll.setValue(round(start*1000))
        self.scroll.blockSignals(False)
    def show_boundary(self,index,seconds):
        if not self.current_record:return
        spans=self.current_record['intervals']
        ui.set_text(self.boundary_info, f"{spans[index-1][2]} → {spans[index][2]} · {seconds:.3f}초 · 드래그 즉시 재계산 / 놓으면 자동 저장")
    def begin_edit(self):
        if self.current_record:
            self.pending_before={'stage':self.stage,'intervals':deepcopy(self.current_record['intervals']),'rows':deepcopy([self.report['entries'][i] for i in self.file_rows[self.current_record['wav']]])}
    def edit_boundary(self,index,seconds):
        if self.stage!=1 or not self.current_record:return
        seconds=move_boundary(self.current_record,index,seconds)
        self.refresh_edited_file()
        self.show_boundary(index,seconds)
    def edit_oto(self,index,seconds):
        if self.stage!=2 or not self.current_record or self.table.currentRow()<0:return
        row=self.report['entries'][self.table.currentRow()]
        edit_oto_marker(row,index,seconds,self.current_record['duration'])
        self.refresh_edited_file(recalculate=False)

    def refresh_edited_file(self,recalculate=True):
        changed=(recalculate_file(self.report,self.current_record,self.file_rows.get(self.current_record['wav'])) if recalculate else self.file_rows.get(self.current_record['wav'],[]))
        self.table.blockSignals(True)
        for i in changed:
            row=self.report['entries'][i]
            warning_changed=self.row_warning_flags.get(i)!=bool(row['warnings'])
            self.row_warning_flags[i]=bool(row['warnings'])
            values=[row['wav'],row['alias']]+[f'{v:.3f}' for v in row['values']]+[' / '.join(row['warnings'])]
            for j,value in enumerate(values):
                item=self.table.item(i,j)
                if item.text()!=value:
                    ui.set_text(item,value) if j==7 else item.setText(value)
                if warning_changed:
                    item.setForeground(QColor(ui.colors()['warning'] if row['warnings'] else ui.colors()['text']))
        self.table.blockSignals(False)
        selected=self.table.currentRow()
        if selected>=0:self.wave.row=self.report['entries'][selected]
        self.wave.spans=self.current_record['intervals']
        self.wave.update()
    def finish_edit(self):
        if not self.current_record or self.pending_before is None:return
        current_rows=[self.report['entries'][i] for i in self.file_rows[self.current_record['wav']]]
        if self.pending_before['intervals']!=self.current_record['intervals'] or self.pending_before['rows']!=current_rows:
            self.histories.setdefault(self.current_record['wav'],[]).append(self.pending_before)
            self.save_edits()
        self.pending_before=None
        self.refresh_files();self.filter_rows()
        self.undo.setEnabled(bool(self.histories.get(self.current_record['wav'])))
    def save_edits(self):
        try:
            folder=Path(self.folder.text())
            save_record(folder,self.current_record)
            persist_report(folder,self.report)
            if self.stage==1:
                ui.set_text(self.status, self.summary()+' · 음소 경계 저장 완료')
                return
            if not self.edit_backup_done:
                install_oto(folder,self.mode)
                self.edit_backup_done=True
            elif self.mode=='en_vccv' and not (folder/'oto.ini').exists():
                from english_vccv import install_nested_oto
                install_nested_oto(folder,backup=False,wav=self.current_record['wav'])
            else:
                atomic_write(folder/'oto.ini',(output_dir(folder,self.mode)/'oto.preview.ini').read_bytes())
            ui.set_text(self.status, self.summary()+' · 수정 경계와 oto.ini 저장 완료')
        except Exception as exc:
            self.update_progress(f'수정 저장 실패: {exc}')
    def undo_edit(self):
        if not self.current_record or (self.worker and self.worker.isRunning()):return
        history=self.histories.get(self.current_record['wav'],[])
        if history:
            snapshot=history.pop()
            self.current_record['intervals']=snapshot['intervals']
            for i,row in zip(self.file_rows[self.current_record['wav']],snapshot['rows']):self.report['entries'][i]=row
            self.refresh_edited_file(recalculate=False)
            self.refresh_files();self.filter_rows()
            self.save_edits()
            self.undo.setEnabled(bool(history))
    def play_segment(self, begin, end):
        if self.wave.path is None:return
        from audio_playback import set_wav_segment_source
        previous=getattr(self,'playback_buffer',None)
        self.player.stop()
        try:self.playback_buffer=set_wav_segment_source(self.player,self.wave.path,begin,end,self)
        except Exception as exc:self.failed(str(exc));return
        if previous is not None:previous.deleteLater()
        self.player.play()

    def play_audio(self):
        if not self.report or self.table.currentRow()<0:return
        row=self.report['entries'][self.table.currentRow()]
        from audio_playback import set_wav_source
        previous=getattr(self,'playback_buffer',None)
        self.player.stop()
        try:self.playback_buffer=set_wav_source(self.player,Path(self.folder.text())/row['wav'],self)
        except Exception as exc:self.failed(str(exc));return
        if previous is not None:previous.deleteLater()
        self.player.play()
    def save_oto(self):
        if self.stage!=2:return
        try:
            if self.current_record:save_record(self.folder.text(),self.current_record)
            if self.report:persist_report(self.folder.text(),self.report)
            target=install_oto(self.folder.text(),self.mode)
            self.update_progress(f'저장 완료: {target}')
        except Exception as exc:self.failed(str(exc))
    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            ui.set_text(self.status, '현재 WAV 분석이 끝나면 중지됩니다. 그 후 창을 닫아주세요.')
            event.ignore()
        else:event.accept()

if __name__=='__main__':
    if '--self-test' in sys.argv:
        from vcv_core import Engine
        wav=Path(sys.argv[sys.argv.index('--self-test')+1])
        out=wav.parent/'auto-vcv/packaged-self-test'
        mode=sys.argv[sys.argv.index('--mode')+1] if '--mode' in sys.argv else 'vcv'
        mode,_=resolve_mode(wav.parent,mode)
        if mode=='en_vccv':
            from english_vccv import EnglishVccvEngine
            engine=EnglishVccvEngine(wav.parent)
        elif mode=='en_cvvc':
            from english_cvvc import EnglishCvvcEngine
            engine=EnglishCvvcEngine(wav.parent)
        elif mode=='en_arpasing':
            from arpasing_core import EnglishEngine
            engine=EnglishEngine(wav.parent)
        elif is_korean(mode):
            from korean_core import KoreanEngine
            engine=KoreanEngine()
        else:engine=Engine()
        try:rows,record=engine.analyze(wav,out,mode)
        finally:engine.close()
        (out/'result.json').write_text(json.dumps({'entries':rows,'intervals':record['intervals']},ensure_ascii=False,indent=2),encoding='utf-8')
        sys.exit(0)
    app=QApplication(sys.argv)
    app.setApplicationName('OTONova')
    app.setApplicationDisplayName('OTONova V1.0')
    app.setWindowIcon(QIcon(str(RESOURCE_ROOT/'assets/otonova.ico')))
    ui.apply_font()
    window=Window()
    if '--mode' in sys.argv:
        window.set_mode(sys.argv[sys.argv.index('--mode')+1])
    window.show()
    if '--ui-check' in sys.argv:
        from PySide6.QtCore import QTimer
        preview=DEFAULT_FOLDER.parent/'gui-preview.png'
        QTimer.singleShot(1200,lambda:window.grab().save(str(preview)))
        QTimer.singleShot(1500,app.quit)
    sys.exit(app.exec())
