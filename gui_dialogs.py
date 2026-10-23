"""Voicebank format selection, independent of project and alignment state."""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QComboBox, QDialogButtonBox
import ui_settings as ui
from formats import PUBLIC_FORMATS


def select_voicebank_format(parent=None):
    """Return the confirmed public format, or None when cancelled."""
    dialog = QDialog(parent)
    ui.set_title(dialog, "음원 형식 선택")
    layout = QVBoxLayout(dialog)
    layout.addWidget(ui.label("언어와 녹음 리스트 형식을 선택하세요."))
    layout.addWidget(ui.label("언어권"))
    language_combo = QComboBox()
    language_combo.setObjectName("voicebank_language")
    language_combo.addItem(ui.translate("언어권을 선택하세요"), None)
    for code, label in [("ko", "한국어"), ("ja", "일본어"), ("en", "영어")]:
        language_combo.addItem(ui.translate(label), code)
    layout.addWidget(language_combo)
    layout.addWidget(ui.label("형식"))
    combo = QComboBox()
    combo.setObjectName("voicebank_format")
    combo.setMinimumWidth(440)
    combo.addItem(ui.translate("언어권을 먼저 선택하세요"), None)
    combo.setEnabled(False)
    layout.addWidget(combo)
    info = ui.label(
        "세부 녹음 방식은 파일명·녹음 리스트·기존 에일리어스로 자동 인식합니다.\n기존 oto.ini가 있으면 그 에일리어스 목록을 유지합니다."
    )
    info.setWordWrap(True)
    layout.addWidget(info)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.button(QDialogButtonBox.Ok).setText(ui.translate("확인"))
    buttons.button(QDialogButtonBox.Cancel).setText(ui.translate("취소"))
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    ok = buttons.button(QDialogButtonBox.Ok)
    ok.setEnabled(False)

    def update_formats():
        code = language_combo.currentData()
        combo.clear()
        combo.addItem(ui.translate("형식을 선택하세요"), None)
        if code:
            for key, (label, language, kind) in PUBLIC_FORMATS.items():
                if language == code:
                    combo.addItem(ui.translate(label), key)
        combo.setEnabled(bool(code))
        ok.setEnabled(False)

    language_combo.currentIndexChanged.connect(update_formats)
    combo.currentIndexChanged.connect(
        lambda: ok.setEnabled(combo.currentData() is not None)
    )
    if dialog.exec() != QDialog.Accepted:
        return None
    return combo.currentData()
