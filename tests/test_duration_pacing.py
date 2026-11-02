import copy,unittest
from unittest.mock import patch
from test_invariants import sample
from planner import make_plan,caption_for,GOALS,CTA,validate_plan,segment_seconds,PlanError
from evidence_store import identity
from grouped_planner import grouped_fallback
from pacing import POLICY,valid_duration_plan,narration_offset
from pipeline import build_plan,preflight
from qwen_voice import PROFILE_ID

class DurationPacing(unittest.TestCase):
    def prepare(self,seconds=8):
        p=sample();p['goal']='attract'
        for s in p['shots']:
            s['end']=seconds;s['product_binding']['evidence_id']=identity(s)
        lengths={}
        for role in GOALS[p['goal']]['roles']:
            text=caption_for(role,p['facts'],p['goal'])[0];lengths[text]=1.;lengths[text+CTA[p['goal']]]=2.
        return p,lengths

    def plan(self,p,lengths,method='evidence'):
        return grouped_fallback(p,make_plan(p,method,lengths),lengths,method,POLICY)

    def test_short_narration_keeps_twenty_four_seconds_of_real_footage(self):
        p,l=self.prepare();plan=self.plan(p,l)
        self.assertTrue(plan['renderable']);self.assertEqual(valid_duration_plan(plan),24)
        self.assertTrue(validate_plan(p,plan));self.assertEqual(plan['estimated_seconds'],24)

    def test_multiple_short_sources_fill_duration_without_duplicate_or_repeated_copy(self):
        p,l=self.prepare(2)
        for role in ('product','process','interior'):
            template=next(s for s in p['shots'] if role in s['tags'])
            for i in range(2):
                s=copy.deepcopy(template);s['id']+=f'-extra{i}';s['product_binding']['evidence_id']=identity(s);p['shots'].append(s)
        plan=self.plan(p,l);self.assertTrue(validate_plan(p,plan));self.assertEqual(valid_duration_plan(plan),18)
        selected=[c['shot_id'] for s in plan['segments'] for c in s.get('clips',[s])]
        self.assertEqual(len(selected),len(set(selected)));self.assertLessEqual(len(selected),10)
        self.assertEqual(sum('带你看看' in s['text'] for s in plan['segments']),1)

    def test_under_fifteen_is_explained_not_exported(self):
        p,l=self.prepare(4);plan=self.plan(p,l)
        self.assertFalse(plan['renderable']);self.assertIn('12.0秒',' '.join(plan['missing']))

    def test_unconfirmed_footage_does_not_count_toward_duration(self):
        p,l=self.prepare(4)
        for original in list(p['shots']):
            s=copy.deepcopy(original);s['id']+='-unconfirmed';s['end']=8;s['confirmed']=False;p['shots'].append(s)
        self.assertFalse(self.plan(p,l)['renderable'])

    def test_missing_role_not_replaced_with_extra_product(self):
        p,l=self.prepare();p['shots']=[s for s in p['shots'] if 'process' not in s['tags']]
        plan=self.plan(p,l);self.assertFalse(plan['renderable']);self.assertIn('制作',' '.join(plan['missing']))

    def test_upper_bound_search_selects_shorter_bundle(self):
        p,l=self.prepare()
        for original in list(p['shots']):
            s=copy.deepcopy(original);s['id']+='-extra';s['product_binding']['evidence_id']=identity(s);p['shots'].append(s)
        plan=self.plan(p,l);self.assertTrue(validate_plan(p,plan));self.assertLessEqual(valid_duration_plan(plan),29.8)

    def test_current_voice_old_duration_plan_refused_before_tts(self):
        p,l=self.prepare();old=make_plan(p,'evidence',l);old['voice_profile']=PROFILE_ID
        with patch('pipeline.prepare_voice') as speak:
            with self.assertRaisesRegex(PlanError,'时长规则'):preflight(p,old)
        speak.assert_not_called()

    def test_preflight_and_renderer_contract_keep_same_selected_duration(self):
        p,l=self.prepare();plan=self.plan(p,l);plan['voice_profile']=PROFILE_ID
        with patch('pipeline.reconcile',side_effect=copy.deepcopy),patch('pipeline.verify_selected'),patch('pipeline.prepare_voice',return_value=(None,1.,[])):
            _,checked=preflight(p,plan)
        self.assertEqual(checked['estimated_seconds'],24)

    def test_tampered_duration_policy_and_short_plan_refused(self):
        p,l=self.prepare();plan=self.plan(p,l);plan['pacing']['min_seconds']=1
        with self.assertRaises(PlanError):validate_plan(p,plan)
        plan=self.plan(p,l)
        for s in plan['segments']:s['end']=s['start']+2
        with self.assertRaisesRegex(PlanError,'15–30'):validate_plan(p,plan)

    def test_chronological_order_and_full_cta_preserved(self):
        p,l=self.prepare();plan=self.plan(p,l,'chronological');self.assertTrue(validate_plan(p,plan))
        self.assertEqual([s['role'] for s in plan['segments']],['interior','product','process'])
        self.assertTrue(plan['segments'][-1]['text'].endswith(CTA[p['goal']]))

    def test_malformed_new_duration_plan_has_actionable_error(self):
        with self.assertRaises(PlanError):valid_duration_plan({'pacing':copy.deepcopy(POLICY),'segments':[{'start':'oops','end':4}]})

    def test_short_environment_can_move_before_product_closing(self):
        p,l=self.prepare(6)
        text=caption_for('interior',p['facts'],p['goal'])[0]+CTA[p['goal']];l[text]=10.
        plan=self.plan(p,l);self.assertTrue(validate_plan(p,plan))
        self.assertEqual(plan['segments'][-1]['role'],'product');self.assertEqual(valid_duration_plan(plan),18)

    def test_narration_breathing_room_balanced_without_speed_change(self):
        offset=narration_offset(3.6,13)
        self.assertAlmostEqual(offset,4.66);self.assertAlmostEqual(13-(offset+3.6),4.74)
        self.assertEqual(narration_offset(3.,2.9),0.)

if __name__=='__main__':unittest.main()
