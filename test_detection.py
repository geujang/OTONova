import tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
from formats import PUBLIC_FORMATS,public_mode
from format_detection import resolve_mode,fingerprint

class DetectionTests(unittest.TestCase):
    def test_public_choices(self):
        self.assertEqual(len(PUBLIC_FORMATS),13)
        self.assertFalse(any('식' in v[0].replace('리스트 인식','') for v in PUBLIC_FORMATS.values()))
        self.assertEqual(public_mode('ko_cvc_binbin'),'ko_auto_cvc')

    def test_files_suffixes_and_aliases(self):
        signatures={
            'ko_cvvc_malcha':{'stems':[fingerprint('ga_na')],'aliases':[fingerprint('a kcl')]},
            'ko_cvvc_tabi':{'stems':[fingerprint('ga_na')],'aliases':[fingerprint('N g')]}}
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'prefix_ga_na_A4.wav').touch()
            with patch('format_detection.json.loads',return_value=signatures):
                profile,detail=resolve_mode(tmp,'ko_auto_cvvc',[{'alias':'N g'}])
            self.assertEqual(profile,'ko_cvvc_tabi')
            self.assertEqual(detail['matched_files'],1)
            self.assertFalse(detail['warning'])

    def test_unknown_and_ambiguous_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'unknown.wav').touch()
            profile,detail=resolve_mode(tmp,'ko_auto_cvc')
            self.assertEqual(profile,'ko_cvc_zetty');self.assertTrue(detail['warning'])
            signatures={p:{'stems':[fingerprint('unknown')],'aliases':[]} for p in ['ko_cvc_zetty','ko_cvc_binbin']}
            with patch('format_detection.json.loads',return_value=signatures):
                self.assertTrue(resolve_mode(tmp,'ko_auto_cvc')[1]['warning'])

    def test_supplied_reclist_and_japanese(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'reclist.txt').write_text("_ga'na",encoding='utf-8')
            signatures={'ko_vcv_diko':{'stems':[fingerprint("ga'na")],'aliases':[]}}
            with patch('format_detection.json.loads',return_value=signatures):
                self.assertEqual(resolve_mode(tmp,'ko_auto_vcv')[1]['list_matches'],1)
            self.assertEqual(resolve_mode(tmp,'vcv'),('vcv',None))

    def test_generation_uses_detected_profile(self):
        from vcv_core import run_folder
        calls=[]
        class Engine:
            def __init__(self,*args):pass
            def analyze(self,path,out,mode):
                calls.append(mode);return [],{'duration':1,'wav':path.name,'intervals':[]}
            def close(self):pass
        signatures={'ko_cvvc_tabi':{'stems':[fingerprint('ga_na')],'aliases':[]}}
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'ga_na.wav').touch()
            with patch('format_detection.json.loads',return_value=signatures),patch('korean_core.KoreanEngine',Engine):
                report=run_folder(tmp,mode='ko_auto_cvvc')
            self.assertEqual(calls,['ko_cvvc_tabi'])
            self.assertEqual(report['mode'],'ko_cvvc_tabi')
            self.assertEqual(report['detection']['selected_mode'],'ko_auto_cvvc')

if __name__=='__main__':unittest.main()
