import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_invariants import sample
from planner import clean_project,make_plan,caption_for,CTA,GOALS,validate_plan,PlanError
from text_rules import direction_problem,quarantine_text,display_text,DIRECTION_CONTROLS
from grouped_planner import grouped_fallback
from media import probe,write_ass
from evidence_store import identity
from session_store import restore_session
import review_store

class FifthAuditFixes(unittest.TestCase):
    def test_raw_direction_controls_never_enter_planning(self):
        for c in '\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069':
            p=sample();p['facts'][3]['value']='单杯'+c+'19元'
            with self.subTest(code=ord(c)),self.assertRaisesRegex(PlanError,'隐藏方向'):clean_project(p)

    def test_quarantine_preserves_raw_revokes_confirmation_and_shows_codes(self):
        p=sample();p['facts'][3]['value']='单杯\u202e19\u202c元';out=quarantine_text(p);f=out['facts'][3]
        self.assertEqual(f['original_value'],p['facts'][3]['value']);self.assertFalse(f['confirmed'])
        self.assertEqual(f['value'],'单杯[U+202E]19[U+202C]元');self.assertIsNone(direction_problem(f['value']))
        clean_project(out)

    def test_pending_marker_cannot_be_confirmed_by_json(self):
        p=sample();p['facts'][3]['value']='\u202e19\u202c元';out=quarantine_text(p);out['facts'][3]['confirmed']=True
        with self.assertRaisesRegex(PlanError,'重新填写'):clean_project(out)

    def test_user_can_choose_91_after_retyping_without_silent_19_conversion(self):
        p=sample();p['facts'][3]['value']='单杯\u202e19\u202c元';out=quarantine_text(p);f=out['facts'][3];f.update(value='单杯91元',confirmed=True)
        checked=clean_project(out);self.assertEqual(checked['facts'][3]['value'],'单杯91元');self.assertNotIn('text_issue',checked['facts'][3])
        self.assertIn('\u202e',checked['facts'][3]['original_value'])

    def test_long_raw_value_can_be_recovered_with_visible_markers(self):
        p=sample();p['facts'][3]['value']='价'*98+'\u202e'+'元';out=quarantine_text(p)
        self.assertGreater(len(out['facts'][3]['value']),100);clean_project(out)

    def test_ordinary_international_letters_not_rejected(self):
        p=sample();p['facts'][3]['value']='قهوة Cafe 19元';clean_project(p);self.assertIsNone(direction_problem(p['facts'][3]['value']))

    def test_direct_subtitle_path_also_rejects_direction_overrides(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'隐藏方向'):write_ass(Path(folder)/'x.ass','\u202e19\u202c元',3,False)

    def test_restore_opens_draft_instead_of_locking_out_unsafe_legacy_project(self):
        p=sample();p['facts'][3]['value']='\u202e19\u202c元'
        with patch('session_store.reconcile',side_effect=copy.deepcopy):out=restore_session(p)
        self.assertFalse(out['facts'][3]['confirmed']);self.assertIn('[U+202E]',out['facts'][3]['value']);self.assertTrue(out['warnings'])

    def test_probe_keeps_video_origin_and_duration_separate_from_container(self):
        obj={'format':{'duration':'8','start_time':'0'},'streams':[{'codec_type':'video','width':720,'height':1280,'start_time':'2','duration':'6'},{'codec_type':'audio'}]}
        with patch('media.run',return_value=json.dumps(obj)):meta=probe(Path('test.mp4'))
        self.assertEqual(meta['duration'],8);self.assertEqual(meta['video_duration'],6);self.assertEqual(meta['video_offset'],2)

    def test_absolute_shared_timestamp_shift_has_no_relative_offset(self):
        obj={'format':{'duration':'13','start_time':'7'},'streams':[{'codec_type':'video','width':720,'height':1280,'start_time':'7','duration_ts':150,'time_base':'1/25'}]}
        with patch('media.run',return_value=json.dumps(obj)):meta=probe(Path('test.mp4'))
        self.assertEqual(meta['video_duration'],6);self.assertEqual(meta['video_offset'],0)

    def interrupted(self):
        p=sample();p['goal']='promo';products=[]
        for i,seconds in enumerate((8,1,8)):
            s=copy.deepcopy(p['shots'][1]);s.update(id=f'product-{i}',end=seconds);s['product_binding']['evidence_id']=identity(s);products.append(s)
        p['shots']=[s for s in p['shots'] if 'storefront' in s['tags']]+products;lengths={}
        for role in GOALS[p['goal']]['roles']:
            text=caption_for(role,p['facts'],p['goal'])[0];lengths[text]=12.6 if role=='product' else 2.5;lengths[text+CTA[p['goal']]]=15.2 if role=='product' else 5.2
        return p,lengths

    def test_non_adjacent_long_clips_are_found_without_removing_short_source(self):
        p,lengths=self.interrupted();out=grouped_fallback(p,make_plan(p,'chronological',lengths),lengths,'chronological')
        self.assertTrue(out['renderable']);validate_plan(p,out);group=out['segments'][-1]
        self.assertEqual([c['shot_id'] for c in group['clips']],['product-0','product-2']);self.assertEqual(len(p['shots']),4)

    def test_non_adjacent_search_does_not_waive_confirmation(self):
        p,lengths=self.interrupted();p['shots'][-1]['confirmed']=False
        out=grouped_fallback(p,make_plan(p,'chronological',lengths),lengths,'chronological');self.assertFalse(out['renderable'])

    def test_search_budget_failure_does_not_claim_material_is_insufficient(self):
        p,lengths=self.interrupted()
        with patch('grouped_planner.MAX_COMBINATION_ATTEMPTS',1):out=grouped_fallback(p,make_plan(p,'chronological',lengths),lengths,'chronological')
        self.assertFalse(out['renderable']);self.assertIn('不能据此认定',''.join(out['missing']))

    def test_prior_semantic_veto_survives_analysis_upgrade_without_reusing_candidate(self):
        p=sample();s=p['shots'][1];s['analysis_version']=6
        with tempfile.TemporaryDirectory() as folder,patch.object(review_store,'DATA',Path(folder)):
            review_store.store_review(s,{'semantic_issue':'已有混入风险'})
            s['analysis_version']=7
            self.assertIsNone(review_store.load_review(s));self.assertEqual(review_store.semantic_issue(s),'已有混入风险')
            s['end']=5;self.assertIsNone(review_store.semantic_issue(s))

if __name__=='__main__':unittest.main()
