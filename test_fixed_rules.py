"""Fixed-marker fallback runs after normal timing rules."""
import unittest
from copy import deepcopy
from vcv_core import make_entry,create_oto,parse_name,move_boundary,recalculate_file

class FixedFallbackTests(unittest.TestCase):
    def test_short_pattern_uses_midpoint_after_its_normal_rule(self):
        for lead in [.015,.02,.04,.07,.2]:
            with self.subTest(lead=lead):
                pre=1.;cut=pre+lead/2
                row=make_entry('a.wav','a',.5,.6,pre,cut-lead,cut,2,[],fixed_lead=lead)
                self.assertAlmostEqual(row['absolute'][3],(pre+cut)/2)
                self.assertAlmostEqual(row['values'][1],((pre+cut)/2-.5)*1000)
                self.assertEqual(row['absolute'][2],pre)
                self.assertEqual(row['absolute'][4],cut)

    def test_vowel_only_offset_equal_to_pre_does_not_mask_fallback(self):
        row=make_entry('a.wav','a',1,1,1,.97,1.04,2,[],fixed_lead=.07)
        self.assertAlmostEqual(row['absolute'][3],1.02)

    def test_valid_fixed_marker_is_unchanged(self):
        row=make_entry('a.wav','a',.5,.6,1,1.43,1.5,2,[],fixed_lead=.07)
        self.assertAlmostEqual(row['absolute'][3],1.43)

    def test_equal_fixed_and_pre_is_unchanged(self):
        row=make_entry('a.wav','a',.5,.6,1,1,1.5,2,[],fixed_lead=.5)
        self.assertEqual(row['absolute'][3],1)

    def test_wav_end_clamping_is_followed_by_midpoint_fallback(self):
        row=make_entry('a.wav','a',.5,.6,.99,1.2,1.4,1,[],fixed_lead=.07)
        self.assertAlmostEqual(row['absolute'][3],.995)
        self.assertEqual(row['absolute'][4],1)

    def test_live_boundary_recalculation_uses_same_fallback(self):
        spans=[[0,.3,'pau'],[.3,.5,'k'],[.5,.56,'a'],[.56,1,'pau']]
        record=dict(wav='か.wav',duration=1,intervals=deepcopy(spans))
        rows=create_oto('か.wav',parse_name('か'),spans,1,'cvvc')
        report=dict(mode='cvvc',entries=rows)
        for row in rows:
            if row['alias'] in ['- か','か']:
                self.assertAlmostEqual(row['absolute'][3],(row['absolute'][2]+row['absolute'][4])/2)
        move_boundary(record,2,.51);recalculate_file(report,record)
        for row in report['entries']:
            if row['alias'] in ['- か','か']:
                self.assertAlmostEqual(row['absolute'][3],(row['absolute'][2]+row['absolute'][4])/2)

if __name__=='__main__':unittest.main()
