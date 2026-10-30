import copy,unittest
from datetime import date
from test_invariants import sample,make_plan
from planner import make_plan as plan_with_timings,caption_for,CTA,GOALS
from validity import parse_period,period_problem
from evidence_store import identity,attest,valid_attestation

class AuditFixes(unittest.TestCase):
    def test_browser_integer_serialization_preserves_attestation(self):
        s=sample()['shots'][1];s['attestation']=attest(s)
        s['start']=int(s['start']);s['end']=int(s['end'])
        self.assertTrue(valid_attestation(s))

    def test_changed_source_invalidates_product_binding(self):
        p=sample();p['shots'][1]['media_id']='c'*32
        self.assertFalse(make_plan(p)['renderable'])

    def test_changed_range_invalidates_attestation(self):
        s=sample()['shots'][1];s['attestation']=attest(s)
        self.assertTrue(valid_attestation(s));s['end']=5
        self.assertFalse(valid_attestation(s))

    def test_changed_file_hash_invalidates_attestation(self):
        s=sample()['shots'][1];s['attestation']=attest(s);s['source_sha256']='c'*64
        self.assertFalse(valid_attestation(s))

    def test_purpose_relabel_invalidates_signature(self):
        s=sample()['shots'][1];s['attestation']=attest(s);s['tags']=['storefront']
        self.assertFalse(valid_attestation(s))

    def test_expired_promo_not_renderable(self):
        p=sample();p['goal']='promo';p['facts'][-1]['value']='2020年1月1日至2日'
        result=make_plan(p);self.assertFalse(result['renderable']);self.assertIn('结束',''.join(result['missing']))

    def test_reverse_dates_rejected(self):
        self.assertIn('早于',period_problem('2099年5月10日至2099年5月1日',date(2026,10,30)))

    def test_unknown_dates_require_clear_input(self):
        self.assertIn('无法识别',period_problem('长期有效',date(2026,10,30)))

    def test_expiry_today_is_inclusive(self):
        self.assertIsNone(period_problem('2026年10月23日至30日',date(2026,10,30)))

    def test_iso_date_range(self):
        self.assertEqual(parse_period('2099-05-01至2099-05-07'),(date(2099,5,1),date(2099,5,7)))

    def test_unmeasured_plan_is_not_ready(self):
        self.assertFalse(plan_with_timings(sample())['renderable'])

    def test_timing_selects_longer_feasible_product(self):
        p=sample();short=p['shots'][1];short.update(end=1.,quality=.99)
        from evidence_store import identity
        short['product_binding']['evidence_id']=identity(short)
        long=copy.deepcopy(short);long.update(id='long',end=8.,quality=.6)
        long['product_binding']['evidence_id']=identity(long);p['shots'].append(long)
        lengths={}
        for role in GOALS[p['goal']]['roles']:
            text=caption_for(role,p['facts'],p['goal'])[0];lengths[text]=2.9;lengths[text+CTA[p['goal']]]=3.8
        result=plan_with_timings(p,speech_lengths=lengths)
        self.assertTrue(result['renderable'])
        self.assertEqual(next(s['shot_id'] for s in result['segments'] if s['role']=='product'),'long')

    def test_chronological_last_caption_must_fit(self):
        p=sample();text=caption_for('storefront',p['facts'],p['goal'])[0]
        lengths={}
        for role in GOALS[p['goal']]['roles']:
            t=caption_for(role,p['facts'],p['goal'])[0];lengths[t]=1.;lengths[t+CTA[p['goal']]]=1.
        lengths[text+CTA[p['goal']]]=10.
        self.assertFalse(plan_with_timings(p,'chronological',lengths)['renderable'])

    def test_quality_issues_block_even_when_score_forged(self):
        p=sample();p['shots'][1].update(quality=.99,quality_issues=['纯色'])
        self.assertFalse(make_plan(p)['renderable'])

if __name__=='__main__':unittest.main(verbosity=2)
