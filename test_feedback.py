import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile,json,unittest
from pathlib import Path
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from feedback_client import FeedbackDialog,payload,endpoint_from_config
APP=QApplication.instance() or QApplication([])

class FeedbackTests(unittest.TestCase):
    def test_payload_has_only_explicit_text_and_version(self):
        data=payload('hello','name','bug')
        self.assertEqual(set(data),{'message','contact','category','version','request_id'})
        self.assertEqual(len(data['request_id']),24)
        for text in ['', 'a'*1501, '😀'*751]:
            with self.assertRaises(ValueError):payload(text)

    def test_insecure_or_missing_endpoint_is_not_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'assets').mkdir()
            for endpoint,expected in [('', ''),('http://example.com/feedback',''),('https://example.workers.dev/feedback','https://example.workers.dev/feedback')]:
                (root/'assets/feedback-config.json').write_text(json.dumps({'endpoint':endpoint}))
                self.assertEqual(endpoint_from_config(root),expected)

    def test_unconfigured_dialog_saves_draft_but_does_not_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings=QSettings(str(Path(tmp)/'test.ini'),QSettings.IniFormat)
            dialog=FeedbackDialog('',settings=settings)
            self.assertFalse(dialog.send.isEnabled())
            dialog.message.setPlainText('feedback draft');dialog.reject()
            reopened=FeedbackDialog('',settings=settings)
            self.assertEqual(reopened.message.toPlainText(),'feedback draft');reopened.reject()

    def test_failure_preserves_text_and_success_clears_it(self):
        from PySide6.QtNetwork import QNetworkRequest
        class Reply:
            def __init__(self,status,data):self.status=status;self.data=data
            def attribute(self,_):return self.status
            def readAll(self):return json.dumps(self.data).encode()
            def deleteLater(self):pass
        with tempfile.TemporaryDirectory() as tmp:
            settings=QSettings(str(Path(tmp)/'test.ini'),QSettings.IniFormat)
            dialog=FeedbackDialog('https://example.workers.dev/feedback',settings=settings)
            dialog.message.setPlainText('keep this');dialog.last_payload=payload('keep this')
            dialog.reply=Reply(429,{'error':'rate_limited'});dialog.finished_sending()
            self.assertEqual(dialog.message.toPlainText(),'keep this')
            dialog.reply=Reply(200,{'ok':True,'request_id':dialog.last_payload['request_id']});dialog.finished_sending()
            self.assertEqual(dialog.message.toPlainText(),'');self.assertFalse(settings.contains('draft'));dialog.reject()

if __name__=='__main__':unittest.main()
