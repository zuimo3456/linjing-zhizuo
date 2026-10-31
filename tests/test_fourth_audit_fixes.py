import copy,tempfile,unittest
from pathlib import Path
from test_invariants import sample
from planner import make_plan,caption_for,CTA,GOALS,validate_plan,segment_seconds,clean_project,PlanError
from evidence_store import identity
from grouped_planner import grouped_fallback
from media import write_ass

class FourthAuditFixes(unittest.TestCase):
    def project(self,seconds):
        p=sample();product=p['shots'][1];product['end']=seconds
        product['product_binding']['evidence_id']=identity(product)
        other=copy.deepcopy(product);other['id']='second-product';other['product_binding']['evidence_id']=identity(other)
        p['shots'].append(other)
        lengths={}
        for role in GOALS[p['goal']]['roles']:
            text=caption_for(role,p['facts'],p['goal'])[0];lengths[text]=1;lengths[text+CTA[p['goal']]]=2
        return p,lengths

    def test_eight_second_sources_are_grouped_like_nearby_durations(self):
        for seconds in (7.96,8,10):
            with self.subTest(seconds=seconds):
                p,lengths=self.project(seconds);text=caption_for('product',p['facts'],p['goal'])[0];lengths[text]=12.56
                plan=grouped_fallback(p,make_plan(p,'evidence',lengths),lengths,'evidence')
                self.assertTrue(plan['renderable']);self.assertTrue(validate_plan(p,plan))
                group=next(s for s in plan['segments'] if s['role']=='product')
                self.assertEqual(len(group['clips']),2);self.assertAlmostEqual(segment_seconds(group),2*min(8,seconds))

    def test_eight_second_group_still_requires_second_confirmation(self):
        p,lengths=self.project(8);lengths[caption_for('product',p['facts'],p['goal'])[0]]=12.56;p['shots'][-1]['confirmed']=False
        plan=grouped_fallback(p,make_plan(p,'evidence',lengths),lengths,'evidence')
        self.assertFalse(plan['renderable'])

    def test_group_limit_not_relaxed_for_long_narration(self):
        p,lengths=self.project(8);lengths[caption_for('product',p['facts'],p['goal'])[0]]=20
        plan=grouped_fallback(p,make_plan(p,'evidence',lengths),lengths,'evidence')
        self.assertFalse(plan['renderable']);diag=next(d for d in plan['timing_diagnostics'] if d['role']=='product')
        self.assertEqual(diag['available_seconds'],16);self.assertGreater(diag['minimum_seconds'],16)

    def test_last_chronological_group_diagnostic_includes_cta(self):
        p,lengths=self.project(2);products=[s for s in p['shots'] if 'product' in s['tags']]
        p['shots']=[s for s in p['shots'] if 'product' not in s['tags']]+products
        text=caption_for('product',p['facts'],p['goal'])[0];lengths[text]=2.887188;lengths[text+CTA[p['goal']]]=5.544750
        plan=grouped_fallback(p,make_plan(p,'chronological',lengths),lengths,'chronological')
        self.assertFalse(plan['renderable']);diag=next(d for d in plan['timing_diagnostics'] if d['role']=='product')
        self.assertTrue(diag['includes_cta']);self.assertTrue(diag['text'].endswith(CTA[p['goal']]))
        self.assertAlmostEqual(diag['minimum_seconds'],4.779);self.assertEqual(diag['available_seconds'],4)
        self.assertIn('包含结尾引导语',''.join(plan['missing']));self.assertIn('2个可组合片段合计4.0秒',''.join(plan['missing']))
        self.assertNotIn('至少需要2.5秒',''.join(plan['missing']))

    def test_nonfinal_role_diagnostic_does_not_add_cta(self):
        p,lengths=self.project(2);text=caption_for('product',p['facts'],p['goal'])[0];lengths[text]=7
        plan=grouped_fallback(p,make_plan(p,'evidence',lengths),lengths,'evidence')
        diag=next(d for d in plan['timing_diagnostics'] if d['role']=='product')
        self.assertFalse(diag['includes_cta']);self.assertEqual(diag['text'],text)

    def test_unicode_layout_separators_preserve_raw_fact_and_visible_words(self):
        p=sample();raw='示例路18号\u2028\u202999室';p['facts'][2]['value']=raw
        clean_project(p);text,_=caption_for('storefront',p['facts'],p['goal'])
        self.assertEqual(text,'门店地址：示例路18号 99室。');self.assertEqual(p['facts'][2]['value'],raw)

    def test_ass_normalizes_unicode_line_and_paragraph_separators(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'captions.ass';write_ass(path,'示例路18号\u2028\u202999室',3,False)
            text=path.read_text(encoding='utf-8-sig')
            self.assertNotIn('\u2028',text);self.assertNotIn('\u2029',text)
            self.assertIn('示例路18号 99室',text);self.assertEqual(text.count('Dialogue:'),1)

    def test_layout_normalization_does_not_allow_other_control_characters(self):
        p=sample();p['facts'][2]['value']='18号\u2028\x0099室'
        with self.assertRaisesRegex(PlanError,'控制字符'):clean_project(p)

if __name__=='__main__':unittest.main()
