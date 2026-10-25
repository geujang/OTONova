import unittest
import json
import math
from pathlib import Path
from copy import deepcopy
from vcv_core import parse_name,create_oto,ROOT,deduplicate,move_boundary,recalculate_file,read_existing_oto,apply_oto_template
BANK=next((p for p in ROOT.iterdir() if p.is_dir() and (p/'ああいあうえあ.wav').is_file()),ROOT/'Natural')

class RulesTests(unittest.TestCase):
    def test_existing_alias_common_affixes_and_live_update(self):
        spans=[[0,1,'pau'],[1,2,'k'],[2,3,'a'],[3,4,'sh'],[4,5,'i'],[5,6,'pau']]
        generated=create_oto('かし.wav',parse_name('かし'),spans,6,'vcv_cvvc')
        for prefix,suffix in [('', 'A4'),('強_', ''),('強_', '_softA4')]:
            originals=[dict(r,alias=prefix+r['alias']+suffix) for r in generated]
            kept=apply_oto_template(originals,generated,{'かし.wav':6})
            self.assertTrue(all(not r.get('unmapped_template') for r in kept))
            self.assertEqual([r['alias'] for r in kept],[r['alias'] for r in originals])
            self.assertEqual([r['values'] for r in kept],[r['values'] for r in generated])
            record={'wav':'かし.wav','duration':6,'intervals':deepcopy(spans)}
            move_boundary(record,4,4.2)
            recalculate_file({'mode':'vcv_cvvc','entries':kept},record)
            self.assertEqual([r['alias'] for r in kept],[r['alias'] for r in originals])
        # Common phonetic text alone must not be mistaken for decoration.
        plain=[r for r in generated if r['alias'].startswith('a ')]
        kept=apply_oto_template(plain,generated,{'かし.wav':6})
        self.assertTrue(all('alias_prefix' not in r for r in kept))
    def test_combined_mode_keeps_vcv_and_adds_cv_vc_live(self):
        tokens=parse_name('かし')
        spans=[[0,1,'pau'],[1,2,'k'],[2,3.5,'a'],[3.5,4.1,'sh'],[4.1,5.6,'i'],[5.6,7,'pau']]
        vcv=create_oto('かし.wav',tokens,spans,7)
        combined=create_oto('かし.wav',tokens,spans,7,'vcv_cvvc')
        self.assertEqual([r['alias'] for r in combined],['- か','a し','i -','か','し','a sh'])
        for original,row in zip(vcv,combined):self.assertEqual(original['values'],row['values'])
        self.assertEqual(len({r['source_index'] for r in combined}),len(combined))
        before={r['alias']:r['values'][:] for r in combined}
        record={'wav':'かし.wav','duration':7,'intervals':deepcopy(spans)}
        move_boundary(record,4,4.3)
        report={'mode':'vcv_cvvc','entries':combined}
        recalculate_file(report,record)
        for alias in ['a し','し','a sh']:
            self.assertNotEqual(next(r['values'] for r in combined if r['alias']==alias),before[alias])
    def test_w_consonant_proxy_keeps_oto_alias(self):
        for alias,base in [('kw','k'),('gw','g'),('nw','n'),('sw','s'),('bw','b'),('pw','p'),('mw','m'),('rw','r')]:
            tokens=parse_name('あ'+alias)
            self.assertEqual(tokens[-1]['phones'],[base])
            rows=create_oto('あ'+alias+'.wav',tokens,
                [[0,1,'pau'],[1,2,'a'],[2,2.5,base],[2.5,3.5,'pau']],3.5,'cvvc')
            self.assertIn('a '+alias,[r['alias'] for r in rows])
            tail=next(r for r in rows if r['alias']==alias+' -')
            self.assertEqual(tail['absolute'][2],2.5)
            standalone=next(r for r in rows if r['alias']==alias)
            self.assertEqual(standalone['absolute'][2],2.5)
            report={'mode':'cvvc','entries':[standalone,tail]}
            record={'wav':'あ'+alias+'.wav','duration':3.5,'intervals':deepcopy(
                [[0,1,'pau'],[1,2,'a'],[2,2.5,base],[2.5,3.5,'pau']])}
            move_boundary(record,3,2.7)
            recalculate_file(report,record)
            self.assertTrue(all(row['absolute'][2]==2.7 for row in report['entries']))
        for kana,base in [('くぁ','k'),('ぐぁ','g'),('ぬぁ','n'),('ぶぁ','b')]:
            token=parse_name(kana)[0]
            self.assertEqual(token['phones'],[base,'a'])
            self.assertEqual(token['alias_phones'],[base,'w','a'])
        spans=[[0,1,'pau'],[1,2,'N'],[2,2.5,'n'],[2.5,3,'u'],[3,4,'pau']]
        rows=create_oto('んぬ.wav',parse_name('んぬ'),spans,4,'cvvc')
        kept=apply_oto_template([{'wav':'んぬ.wav','alias':'n nw','values':[1500,300,-800,500,100]}],
                                rows,{'んぬ.wav':4})
        self.assertEqual(kept[0]['alias'],'n nw')
        self.assertFalse(kept[0].get('unmapped_template',False))
    def test_unmapped_alias_moves_with_boundaries_without_renaming(self):
        spans=[[0,1,'pau'],[1,2,'a'],[2,3,'pau']]
        record={'wav':'あ.wav','duration':3,'intervals':deepcopy(spans)}
        original={'wav':'あ.wav','alias':'custom','values':[1200,300,-600,200,100]}
        entries=apply_oto_template([original],[],{'あ.wav':3},{'あ.wav':record})
        self.assertEqual(entries[0]['values'],original['values'])
        report={'mode':'cvvc','entries':entries}
        move_boundary(record,2,2.5)
        self.assertEqual(recalculate_file(report,record),[0])
        row=report['entries'][0]
        self.assertEqual(row['alias'],'custom')
        for actual,want in zip(row['absolute'],[1.3,1.45,1.6,1.75,2.2]):
            self.assertAlmostEqual(actual,want)
        serialized=json.loads(json.dumps(report))
        move_boundary(record,2,2)
        recalculate_file(serialized,record)
        for actual,want in zip(serialized['entries'][0]['values'],original['values']):
            self.assertAlmostEqual(actual,want)

    def test_breath_kanji_and_lowercase_consonants(self):
        self.assertEqual(parse_name('あ息'),parse_name('あR'))
        for stem,phone in [('k -','k'),('d','d'),('b -','b'),('g','g')]:
            self.assertEqual(parse_name(stem)[0]['phones'],[phone])
        self.assertEqual(parse_name('あsh')[1]['phones'],['sh'])

    def test_terminal_consonant_vc_and_original_alias_preservation(self):
        spans=[[0,1,'pau'],[1,2,'a'],[2,2.4,'k'],[2.4,3,'pau']]
        rows=create_oto('あk.wav',parse_name('あk'),spans,3,'cvvc')
        vc=next(r for r in rows if r['alias']=='a k')
        self.assertAlmostEqual(vc['absolute'][2],2)
        self.assertAlmostEqual(vc['absolute'][4],2.2)
        self.assertAlmostEqual(vc['absolute'][4]-vc['absolute'][3],.015)
        original={'wav':'あk.wav','alias':'k -','values':[1900,200,-700,100,50]}
        result=apply_oto_template([original],rows,{'あk.wav':3},
            {'あk.wav':{'phones':['pau','a','k','pau']}})
        self.assertTrue(result[0]['consonant_only'])
        for actual,expected in zip(result[0]['absolute'],[2+0.4*2/3,2+0.4*5/6,2.4,2.6,2.62]):
            self.assertAlmostEqual(actual,expected)
        report={'mode':'cvvc','entries':result}
        record={'wav':'あk.wav','duration':3,'intervals':deepcopy(spans)}
        move_boundary(record,3,2.5)
        recalculate_file(report,record)
        self.assertAlmostEqual(report['entries'][0]['absolute'][3],2.5+.5/3)
        self.assertAlmostEqual(report['entries'][0]['absolute'][4]-report['entries'][0]['absolute'][3],.02)
        self.assertGreater(report['entries'][0]['values'][3],0)
        self.assertGreater(report['entries'][0]['values'][4],0)
        # Original consonant aliases also work on kana-named recordings.
        derived=apply_oto_template([dict(original,alias='k')],[],{'あk.wav':3},
            {'あk.wav':dict(record,phones=['pau','a','k','pau'])})
        self.assertEqual(derived[0]['alias'],'k')
        recalculate_file({'mode':'vcv','entries':derived},record)
        breath=create_oto('あ息.wav',parse_name('あ息'),
            [[0,1,'pau'],[1,2,'a'],[2,3,'pau']],3,'cvvc')
        template=[{'wav':'あ息.wav','alias':'a 息','values':[0,0,-1000,0,0]}]
        kept=apply_oto_template(template,breath,{'あ息.wav':3})
        self.assertFalse(kept[0].get('unmapped_template',False))
        self.assertEqual(kept[0]['alias'],'a 息')

    def test_existing_template_missing_wav_and_invalid_ini_are_preserved(self):
        import tempfile
        template=[{'wav':'missing.wav','alias':'独自名','values':[100,50,-500,80,40]}]
        rows=apply_oto_template(template,[],{})
        self.assertEqual(rows[0]['alias'],'独自名')
        self.assertEqual(rows[0]['values'],template[0]['values'])
        self.assertTrue(rows[0]['unmapped_template'])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'oto.ini'
            original=b'bad line without oto fields\n'
            path.write_bytes(original)
            with self.assertRaises(ValueError):read_existing_oto(path)
            self.assertEqual(path.read_bytes(),original)

    def test_cvvc_exact_rules_and_aliases(self):
        spans=[[0,1,'pau'],[1,2,'k'],[2,3.5,'a'],[3.5,4.1,'sh'],
               [4.1,5.6,'i'],[5.6,7,'pau']]
        rows=create_oto('カシ.wav',parse_name('カシ'),spans,7,'cvvc')
        self.assertEqual([r['alias'] for r in rows],['- か','か','し','a sh','i -'])
        expected=[[.7,1,2,2.93,3],[1+1/3,5/3,2,2.93,3],
                  [3.7,3.9,4.1,5.03,5.1],[3.125,3.21875,3.5,3.785,3.8],
                  [5.1,5.475,5.6,6.1,6.3]]
        for row,absolute in zip(rows,expected):
            for actual,want in zip(row['absolute'],absolute):
                self.assertAlmostEqual(actual,want)
        self.assertAlmostEqual(rows[0]['values'][4],300)

    def test_cvvc_compound_onset_and_breath(self):
        spans=[[0,1,'pau'],[1,2,'a'],[2,2.6,'k'],
               [2.6,4,'a'],[4,5,'pau']]
        rows=create_oto('あクァR.wav',parse_name('あクァR'),spans,5,'cvvc')
        self.assertEqual([r['alias'] for r in rows],['- あ','あ','くぁ','a kw','a R'])
        vc=rows[3]
        self.assertAlmostEqual(vc['absolute'][2],2)
        self.assertAlmostEqual(vc['absolute'][4],2.3)
        self.assertTrue(rows[-1]['warnings'])

    def test_cvvc_start_consonant_screenshot_regression(self):
        spans=[[0,1,'pau'],[1,1.1,'k'],[1.1,1.38,'i'],[1.38,2.5,'pau']]
        row=create_oto('き.wav',parse_name('き'),spans,2.5,'cvvc')[0]
        self.assertEqual(row['alias'],'- き')
        for actual,expected in zip(row['values'],[700,516.6666667,-586.6666667,400,300]):
            self.assertAlmostEqual(actual,expected,places=4)
        self.assertGreater(row['values'][1],row['values'][3])

    def test_cvvc_start_vowel_has_300ms_leading_offset(self):
        rows=create_oto('あ.wav',parse_name('あ'),
            [[0,1,'pau'],[1,2,'a'],[2,3,'pau']],3,'cvvc')
        self.assertAlmostEqual(rows[0]['absolute'][0],.7)
        self.assertAlmostEqual(rows[0]['values'][3],300)
        self.assertAlmostEqual(rows[0]['values'][4],300)
        self.assertLess(rows[0]['values'][2],0)
        self.assertAlmostEqual(rows[0]['absolute'][4]-rows[0]['absolute'][3],.07)
        short=create_oto('あ.wav',parse_name('あ'),
            [[0,.1,'pau'],[.1,.5,'a'],[.5,1.5,'pau']],1.5,'cvvc')[0]
        self.assertEqual(short['absolute'][0],0)
        self.assertAlmostEqual(short['values'][4],100)
        self.assertLess(short['values'][2],0)

    def test_cvvc_vv_uses_vcv_rules_and_live_recalculation(self):
        record={'wav':'あい.wav','duration':5,'intervals':[
            [0,1,'pau'],[1,2.5,'a'],[2.5,4,'i'],[4,5,'pau']]}
        rows=create_oto(record['wav'],parse_name('あい'),record['intervals'],5,'cvvc')
        self.assertEqual([r['alias'] for r in rows],['- あ','あ','い','a い','i -'])
        vv=rows[3]
        self.assertAlmostEqual(rows[1]['absolute'][4]-rows[1]['absolute'][3],.07)
        self.assertEqual(vv['absolute'],[2,2.5,2.5,3.46,3.5])
        vcv=create_oto(record['wav'],parse_name('あい'),record['intervals'],5)
        self.assertEqual(vv['values'],vcv[1]['values'])
        report={'mode':'cvvc','entries':rows}
        move_boundary(record,2,2.8)
        recalculate_file(report,record)
        self.assertAlmostEqual(report['entries'][3]['absolute'][1],2.8)
        self.assertAlmostEqual(report['entries'][3]['absolute'][2],2.8)
        self.assertAlmostEqual(report['entries'][3]['absolute'][4]-report['entries'][3]['absolute'][3],.04)

    def test_actual_cvvc_bank(self):
        folder=BANK
        # The user may edit with an older GUI while tests run. Evaluate the current
        # rules from the saved boundary cache without overwriting their report.
        files=sorted(folder.glob('*.wav'),key=lambda p:(p.stem.endswith('R'),p.name))
        self.assertEqual(len(files),198)
        raw=[]
        for wav in files:
            record=json.loads((folder/'auto-vcv/labels'/wav.with_suffix('.json').name).read_text(encoding='utf-8'))
            raw.extend(create_oto(wav.name,parse_name(wav.stem),record['intervals'],record['duration'],'cvvc'))
        entries,removed=deduplicate(raw)
        self.assertEqual(len(entries),512)
        self.assertEqual(removed,2262)
        aliases=[r['alias'] for r in entries]
        self.assertEqual(len(aliases),len(set(aliases)))
        self.assertIn('a k',aliases)
        self.assertIn('a sh',aliases)
        self.assertIn('a ky',aliases)
        self.assertIn('a い',aliases)
        for row in entries:
            if row['alias'].startswith('- '):
                self.assertLess(row['absolute'][0],row['absolute'][1])
                self.assertLess(row['values'][2],0)
                self.assertGreaterEqual(row['absolute'][3],row['absolute'][2])
            self.assertTrue(all(math.isfinite(v) for v in row['values']))
            record=json.loads((folder/'auto-vcv/labels'/Path(row['wav']).with_suffix('.json')).read_text(encoding='utf-8'))
            expected=create_oto(row['wav'],parse_name(Path(row['wav']).stem),
                record['intervals'],record['duration'],'cvvc')[row['source_index']]
            for value,want in zip(row['values'],expected['values']):
                self.assertAlmostEqual(value,want)

    def test_cvvc_shared_boundary_recalculates_without_restoring_duplicates(self):
        record={'wav':'あかか.wav','duration':6,'intervals':[
            [0,1,'pau'],[1,2,'a'],[2,2.6,'k'],[2.6,3.6,'a'],
            [3.6,4.2,'k'],[4.2,5.2,'a'],[5.2,6,'pau']]}
        raw=create_oto(record['wav'],parse_name('あかか'),record['intervals'],6,'cvvc')
        rows,removed=deduplicate(raw)
        self.assertEqual(removed,2)
        report={'mode':'cvvc','entries':rows}
        move_boundary(record,2,2.1)
        recalculate_file(report,record)
        vc=next(r for r in report['entries'] if r['alias']=='a k')
        self.assertAlmostEqual(vc['absolute'][0],1.825)
        self.assertAlmostEqual(vc['absolute'][1],1.89375)
        self.assertAlmostEqual(vc['absolute'][2],2.1)
        self.assertAlmostEqual(vc['absolute'][4],2.35)
        self.assertAlmostEqual(vc['absolute'][4]-vc['absolute'][3],.015)
        self.assertEqual(len(rows),len(report['entries']))

    def test_exact_rules(self):
        tokens=parse_name('あか')
        spans=[[0,1,'pau'],[1,1.9,'a'],[1.9,2.1,'k'],[2.1,3,'a'],[3,4,'pau']]
        rows=create_oto('test.wav',tokens,spans,4)
        expected=[[.7,1,1,1.56,1.6],[1.6,1.9,2.1,2.66,2.7],
                  [2.7,2.925,3,3.66,3.7]]
        self.assertEqual([r['alias'] for r in rows],['- あ','a か','a -'])
        for row,absolute in zip(rows,expected):
            for actual,want in zip(row['absolute'],absolute):
                self.assertAlmostEqual(actual,want)
        self.assertAlmostEqual(rows[1]['values'][2],-1100)

    def test_katakana_and_yoon(self):
        self.assertEqual(parse_name('キャキク'),parse_name('きゃきく'))
        self.assertEqual(parse_name('きゃ')[0]['phones'],['ky','a'])
        self.assertEqual(parse_name('き')[0]['phones'],['k','i'])

    def test_breath_keeps_R(self):
        rows=create_oto('あR.wav',parse_name('あR'),
                        [[0,1,'pau'],[1,2,'a'],[2,4,'pau']],4)
        self.assertEqual([r['alias'] for r in rows],['- あ','a R'])
        self.assertTrue(rows[-1]['warnings'])

    def test_clipping_is_reported(self):
        rows=create_oto('あ.wav',parse_name('あ'),
                        [[0,.1,'pau'],[.1,.2,'a'],[.2,.3,'pau']],.3)
        self.assertEqual(rows[0]['absolute'][0],0)
        self.assertAlmostEqual(rows[-1]['absolute'][-1],.3)
        self.assertTrue(rows[0]['warnings'])

    def test_shared_boundary_and_live_rules(self):
        record={'wav':'あか.wav','duration':4,
                'intervals':[[0,1,'pau'],[1,1.9,'a'],[1.9,2.1,'k'],[2.1,3,'a'],[3,4,'pau']]}
        original=deepcopy(record['intervals'])
        rows=create_oto(record['wav'],parse_name('あか'),record['intervals'],4)
        report={'entries':rows}
        move_boundary(record,2,2.0)
        self.assertEqual(record['intervals'][1][1],record['intervals'][2][0])
        self.assertEqual(record['model_intervals'],original)
        self.assertEqual(recalculate_file(report,record),[0,1,2])
        self.assertAlmostEqual(report['entries'][1]['absolute'][0],1+2/3)
        self.assertAlmostEqual(report['entries'][1]['absolute'][1],2)
        self.assertAlmostEqual(report['entries'][1]['absolute'][3],2.66)
        self.assertAlmostEqual(move_boundary(record,2,100),2.099)
        self.assertAlmostEqual(move_boundary(record,2,-100),1.001)

    def test_dedup_and_recalculation_do_not_restore_duplicates(self):
        record={'wav':'あああ.wav','duration':5,
                'intervals':[[0,1,'pau'],[1,2,'a'],[2,3,'a'],[3,4,'a'],[4,5,'pau']]}
        raw=create_oto(record['wav'],parse_name('あああ'),record['intervals'],5)
        rows,removed=deduplicate(raw+deepcopy(raw))
        self.assertEqual(removed,5)
        self.assertEqual([r['source_index'] for r in rows],[0,1,3])
        report={'entries':rows}
        move_boundary(record,2,2.2)
        recalculate_file(report,record)
        self.assertEqual(len(report['entries']),3)
        self.assertEqual([r['alias'] for r in report['entries']],['- あ','a あ','a -'])

    def test_actual_bank_output(self):
        folder=BANK
        files=sorted(folder.glob('*.wav'),key=lambda p:(p.stem.endswith('R'),p.name))
        self.assertEqual(len(files),198)
        raw=[]
        for wav in files:
            record=json.loads((folder/'auto-vcv/labels'/wav.with_suffix('.json').name).read_text(encoding='utf-8'))
            raw.extend(create_oto(wav.name,parse_name(wav.stem),record['intervals'],record['duration']))
        entries,removed=deduplicate(raw)
        self.assertEqual(len(entries),1027)
        self.assertEqual(removed,459)
        aliases=[r['alias'] for r in entries]
        self.assertEqual(len(aliases),len(set(aliases)))
        for row in entries:
            self.assertTrue((folder/row['wav']).exists())
            self.assertTrue(all(math.isfinite(v) for v in row['values']))
            offset,fixed,cutoff,pre,overlap=row['values']
            self.assertGreaterEqual(offset,0)
            self.assertGreaterEqual(fixed,0)
            self.assertLess(cutoff,0)
            self.assertGreaterEqual(pre,overlap)
            duration=json.loads((folder/'auto-vcv/labels'/Path(row['wav']).with_suffix('.json')).read_text(encoding='utf-8'))['duration']
            self.assertLessEqual(offset-cutoff,duration*1000+.001)
            self.assertAlmostEqual(-cutoff-fixed,40,places=3)

if __name__=='__main__':unittest.main()
