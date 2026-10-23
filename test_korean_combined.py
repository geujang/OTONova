import tempfile,unittest,math
from pathlib import Path
from korean_combined import catalog,metadata,create_oto,make_alias
from korean_core import KNOWN,AUXILIARY
from format_detection import resolve_mode
from vcv_core import recalculate_file,move_boundary

def record(stem,mode):
    data=metadata(stem,mode)
    data.update(wav=stem+'.wav',language='ko',duration=float(len(data['phones'])),
                intervals=[[float(i),float(i+1),p] for i,p in enumerate(data['phones'])])
    return data

class CombinedTests(unittest.TestCase):
    def test_all_supplied_recordings_align_with_available_model_phones(self):
        source=Path(__file__).resolve().parent/'build/korean-new'
        if not source.is_dir():self.skipTest('Full source-list audit requires the privately supplied original lists')
        counts={}
        for mode in catalog():
            recordings={}
            for path in (source/mode[3:]).rglob('*.ini'):
                if path.name=='oto_full.ini':continue
                for line in path.read_text(encoding='utf-8-sig').splitlines():
                    if '.wav=' not in line:continue
                    stem,right=line.split('.wav=',1);alias=right.rsplit(',',5)[0]
                    aliases=recordings.setdefault(stem,[])
                    if alias not in aliases:aliases.append(alias)
            count=0
            for stem,aliases in recordings.items():
                with self.subTest(mode=mode,stem=stem):
                    r=record(stem,mode)
                    self.assertFalse(set(r['phones'])-(KNOWN|set(AUXILIARY)))
                    rows=create_oto(r,mode)
                    self.assertEqual([row['alias'] for row in rows],aliases)
                    self.assertFalse(any(row['entry_kind']=='unresolved' for row in rows))
                    self.assertTrue(all(math.isfinite(v) for row in rows for v in row['values']))
                    count+=len(rows)
            counts[mode]=count
        self.assertEqual(counts,{'ko_coc':521,'ko_cbnn':3390,'ko_cmpx':1041})

    def test_digits_prefixes_and_coc_hyphens_are_not_spoken(self):
        r=record("cvc+'ma2N'ma2N_'pa2N",'ko_cbnn')
        self.assertEqual(r['phones'],['SP','m','a','N','m','a','N','SP','p','a','N','SP'])
        self.assertEqual(r['phone_tags'][2],'2')
        r=record('ga-gi-gu','ko_coc')
        self.assertEqual(r['phones'],['SP','g','a','g','i','g','u','SP'])
        self.assertEqual(metadata('prefix_ga-gi-gu-ge-go-geu-geo-geo_A4','ko_coc')['reclist_stem'],'ga-gi-gu-ge-go-geu-geo-geo')

    def test_timing_rules_and_live_updates(self):
        stem="cv+'ma'ma_'pa_'ra_'ba";r=record(stem,'ko_cbnn')
        initial=make_alias('- ma',r)
        self.assertAlmostEqual(initial['absolute'][0],.7)
        self.assertAlmostEqual(initial['absolute'][4]-initial['absolute'][3],.07)
        cv=make_alias('ma',r)
        self.assertAlmostEqual(cv['absolute'][0],3+1/3)
        vc=make_alias('a m',r)
        self.assertAlmostEqual(vc['absolute'][4]-vc['absolute'][3],.015)
        cluster=record("cv+'mya'mya_'pya_'rya_'bya",'ko_cbnn')
        self.assertEqual(make_alias('a my',cluster)['entry_kind'],'vc')
        report={'mode':'ko_cbnn','entries':[initial]}
        before=initial['absolute'][2];move_boundary(r,2,2.2);recalculate_file(report,r)
        self.assertNotEqual(report['entries'][0]['absolute'][2],before)
        self.assertEqual(report['entries'][0]['alias'],'- ma')

    def test_detect_explicit_and_cvvc_auto(self):
        for mode in catalog():
            stem={'ko_coc':'a-i-u-e-o-eu-eo','ko_cbnn':"cv+'ma'ma_'pa_'ra_'ba",'ko_cmpx':"-c+n'n'na_m'm'ma"}[mode]
            with tempfile.TemporaryDirectory() as tmp:
                Path(tmp,stem+'.wav').touch()
                self.assertEqual(resolve_mode(tmp,mode),(mode,None))
                self.assertEqual(resolve_mode(tmp,'ko_auto_cvvc')[0],mode)

    def test_existing_aliases_only_and_unmatched_are_not_guessed(self):
        from korean_formats import match_template
        r=record("cv+'ma'ma_'pa_'ra_'ba",'ko_cbnn')
        template=[dict(wav=r['wav'],alias=a,values=[0,0,0,0,0]) for a in ['ma','- ma','unknown']]
        result=match_template(template,create_oto(r,'ko_cbnn'),{r['wav']:r['duration']},{r['wav']:r},'ko_cbnn')
        self.assertEqual([row['alias'] for row in result],['ma','- ma','unknown'])
        self.assertTrue(result[-1]['unmapped_template'])

if __name__=='__main__':unittest.main()
