"""Explicit, draft-preserving feedback UI; no bot credentials in the application."""

from pathlib import Path
import json, re, uuid
from urllib.parse import urlsplit
import ui_settings as ui
from PySide6.QtCore import QSettings, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPlainTextEdit,
    QLineEdit,
    QComboBox,
    QPushButton,
    QHBoxLayout,
)


def endpoint_from_config(root):
    try:
        value = json.loads(
            (Path(root) / "assets/feedback-config.json").read_text(encoding="utf-8")
        ).get("endpoint", "")
    except (OSError, ValueError):
        return ""
    if not isinstance(value, str):
        return ""
    parsed = urlsplit(value)
    return (
        value
        if parsed.scheme == "https"
        and parsed.hostname
        and not parsed.username
        and not parsed.password
        else ""
    )


def payload(message, contact="", category="other", request_id=None):
    message = message.strip()
    contact = contact.strip()
    if not message or len(message.encode("utf-16-le")) // 2 > 1500:
        raise ValueError("내용은 1~1,500자까지 입력해주세요.")
    if len(contact.encode("utf-16-le")) // 2 > 100:
        raise ValueError("연락처는 100자 이하로 입력해주세요.")
    if category not in ("bug", "suggestion", "other"):
        raise ValueError("잘못된 피드백 종류입니다.")
    request_id = request_id or uuid.uuid4().hex[:24]
    if not re.fullmatch("[a-f0-9]{24}", request_id):
        raise ValueError("잘못된 전송 식별자입니다.")
    return dict(
        message=message,
        contact=contact,
        category=category,
        version="2.0",
        request_id=request_id,
    )


class FeedbackDialog(QDialog):
    def __init__(self, endpoint, parent=None, settings=None):
        super().__init__(parent)
        self.endpoint = endpoint
        self.settings = (
            settings if settings is not None else QSettings("OTONova", "Feedback")
        )
        self.reply = None
        self.manager = QNetworkAccessManager(self)
        self.last_payload = None
        self.setWindowTitle(ui.translate("피드백"))
        self.resize(520, 430)
        layout = QVBoxLayout(self)
        notice = QLabel(
            ui.translate(
                "작성 내용·선택한 연락처·분류·앱 버전을 Discord 피드백 포럼에 게시합니다. 채널을 볼 수 있는 서버 멤버에게 공개됩니다. 음원·OTO·로그는 전송하지 않습니다."
            )
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.category = QComboBox()
        for key, label in [
            ("bug", "오류 제보"),
            ("suggestion", "기능 제안"),
            ("other", "기타"),
        ]:
            self.category.addItem(ui.translate(label), key)
        layout.addWidget(self.category)
        self.contact = QLineEdit()
        self.contact.setPlaceholderText(ui.translate("답변 받을 연락처 (선택)"))
        self.contact.setMaxLength(100)
        layout.addWidget(self.contact)
        self.message = QPlainTextEdit()
        self.message.setPlaceholderText(ui.translate("피드백 내용 (최대 1,500자)"))
        layout.addWidget(self.message)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.send = QPushButton(ui.translate("전송"))
        self.send.clicked.connect(self.submit)
        self.close_button = QPushButton(ui.translate("닫기"))
        self.close_button.clicked.connect(self.reject)
        buttons.addWidget(self.send)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        try:
            draft = json.loads(str(self.settings.value("draft", "{}")))
            self.message.setPlainText(draft.get("message", ""))
            self.contact.setText(draft.get("contact", ""))
            self.category.setCurrentIndex(
                max(0, self.category.findData(draft.get("category", "other")))
            )
            pending = draft.get("pending")
            self.last_payload = (
                pending
                if isinstance(pending, dict)
                and re.fullmatch("[a-f0-9]{24}", str(pending.get("request_id", "")))
                else None
            )
        except (TypeError, ValueError):
            pass
        self.message.textChanged.connect(self.save_draft)
        self.contact.textChanged.connect(self.save_draft)
        self.category.currentIndexChanged.connect(self.save_draft)
        if not endpoint:
            self.send.setEnabled(False)
            self.status.setText(
                ui.translate(
                    "피드백 서버 연결 준비 중입니다. 작성한 내용은 이 PC에 보관됩니다."
                )
            )

    def save_draft(self):
        self.settings.setValue(
            "draft",
            json.dumps(
                dict(
                    message=self.message.toPlainText(),
                    contact=self.contact.text(),
                    category=self.category.currentData(),
                    pending=self.last_payload,
                ),
                ensure_ascii=False,
            ),
        )
        self.settings.sync()

    def submit(self):
        if self.reply is not None or not self.endpoint:
            return
        try:
            current = payload(
                self.message.toPlainText(),
                self.contact.text(),
                self.category.currentData(),
            )
            if self.last_payload and all(
                current[k] == self.last_payload.get(k)
                for k in ["message", "contact", "category", "version"]
            ):
                current["request_id"] = self.last_payload["request_id"]
        except ValueError as exc:
            self.status.setText(ui.translate(str(exc)))
            return
        self.last_payload = current
        self.save_draft()
        request = QNetworkRequest(QUrl(self.endpoint))
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
        request.setRawHeader(b"User-Agent", b"OTONova/2.0")
        request.setTransferTimeout(20000)
        self.send.setEnabled(False)
        self.message.setReadOnly(True)
        self.contact.setReadOnly(True)
        self.category.setEnabled(False)
        self.status.setText(ui.translate("전송 중…"))
        self.reply = self.manager.post(
            request, json.dumps(current, ensure_ascii=False).encode("utf-8")
        )
        self.reply.finished.connect(self.finished_sending)

    def finished_sending(self):
        reply = self.reply
        self.reply = None
        try:
            status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            try:
                data = json.loads(bytes(reply.readAll()))
            except (ValueError, TypeError):
                data = {}
            if (
                status == 200
                and data.get("ok") is True
                and data.get("request_id") == self.last_payload["request_id"]
            ):
                self.last_payload = None
                self.message.clear()
                self.contact.clear()
                self.settings.remove("draft")
                self.settings.sync()
                self.status.setText(ui.translate("Discord 피드백 포럼에 게시했습니다."))
            else:
                text = (
                    "전송이 제한되었습니다. 잠시 후 다시 보내주세요."
                    if status == 429
                    else "전송하지 못했습니다. 내용은 보관되어 있으니 다시 시도해주세요."
                )
                self.status.setText(ui.translate(text))
                self.save_draft()
        finally:
            reply.deleteLater()
            self.send.setEnabled(bool(self.endpoint))
            self.message.setReadOnly(False)
            self.contact.setReadOnly(False)
            self.category.setEnabled(True)

    def reject(self):
        self.save_draft()
        if self.reply is not None:
            self.reply.abort()
        super().reject()
