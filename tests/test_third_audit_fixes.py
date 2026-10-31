import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from test_invariants import sample,make_plan
from planner import caption_for,CTA,GOALS,clean_project,validate_plan,PlanError,segment_seconds
from evidence_store import identity,confirm
from grouped_planner import grouped_fallback
from media import write_ass,analyze
from session_store import prepare_session,restore_session,context_id
from local_vision import semantic_risk
import review_store

class ThirdAuditFixes(unittest.TestCase):
    def test_control_separators_preserve_all_words(self):
        p=sample();p['facts'][1]['value']='手冲\r\nA1\t咖啡'
        text,_=caption_for('product',p['facts'],p['goal'])
        self.assertIn('手冲 A1 咖啡',text);self.assertEqual(p['facts'][1]['value'],'手冲\r\nA1\t咖啡')

    def test_unsupported_controls_rejected_before_confirmation(self):
        p=sample();p['facts'][1]['value']='咖啡\x00A1'
        with self.assertRaisesRegex(PlanError,'控制字符'):clean_project(p)

    def test_ass_carriage_return_does_not_drop_name_tail(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'a.ass';write_ass(path,'手冲\rA1咖啡',2,False)
            body=path.read_text(encoding='utf-8-sig')
            self.assertIn('手冲 A1咖啡',body);self.assertEqual(body.count('Dialogue:'),1)

    def grouped(self):
        p=sample();s=p['shots'][1];s['end']=2;s['product_binding']['evidence_id']=identity(s)
        second=copy.deepcopy(s);second['id']='short-2';second['product_binding']['evidence_id']=identity(second);p['shots'].append(second)
        lengths={}
        for role in GOALS[p['goal']]['roles']:
            text=caption_for(role,p['facts'],p['goal'])[0];lengths[text]=2.9;lengths[text+CTA[p['goal']]]=3.5
        initial=make_plan(p);result=grouped_fallback(p,initial,lengths,'evidence');return p,result,lengths

    def test_two_short_clips_carry_one_caption(self):
        p,plan,_=self.grouped();self.assertTrue(validate_plan(p,plan));s=next(s for s in plan['segments'] if s['role']=='product')
        self.assertEqual(len(s['clips']),2);self.assertEqual(segment_seconds(s),4)
        self.assertEqual(sum('带你看看' in s['text'] for s in plan['segments']),1)

    def test_group_cannot_hide_unconfirmed_second_source(self):
        p,plan,_=self.grouped();p['shots'][-1]['confirmed']=False
        with self.assertRaises(PlanError):validate_plan(p,plan)

    def test_grouped_chronological_baseline_keeps_source_order_and_last_cta(self):
        p,_,lengths=self.grouped();products=[s for s in p['shots'] if 'product' in s['tags']]
        p['shots']=[s for s in p['shots'] if 'product' not in s['tags']]+products
        result=grouped_fallback(p,make_plan(p),lengths,'chronological')
        self.assertTrue(validate_plan(p,result));self.assertEqual(result['segments'][-1]['role'],'product')
        self.assertEqual(len(result['segments'][-1]['clips']),2);self.assertTrue(result['segments'][-1]['text'].endswith(CTA[p['goal']]))

    def test_group_cannot_repeat_same_shot(self):
        p,plan,_=self.grouped();s=next(s for s in plan['segments'] if s.get('clips'));s['clips'][1]=copy.deepcopy(s['clips'][0])
        with self.assertRaises(PlanError):validate_plan(p,plan)

    def test_group_cannot_exceed_second_source(self):
        p,plan,_=self.grouped();next(s for s in plan['segments'] if s.get('clips'))['clips'][1]['end']=9
        with self.assertRaises(PlanError):validate_plan(p,plan)

    def test_group_product_binding_checked_for_each_source(self):
        p,plan,_=self.grouped();p['shots'][-1]['product_binding']['value']='另一商品'
        with self.assertRaises(PlanError):validate_plan(p,plan)

    def test_short_groups_do_not_waive_missing_confirmation(self):
        p,original,lengths=self.grouped();p['shots'][1]['confirmed']=False;p['shots'][-1]['confirmed']=False
        result=grouped_fallback(p,{'renderable':False},lengths,'evidence');self.assertFalse(result['renderable'])

    def test_session_keeps_custom_order_and_revalidates(self):
        p=sample();plan=make_plan(p);plan['segments'][0],plan['segments'][1]=plan['segments'][1],plan['segments'][0]
        with patch('session_store.reconcile',side_effect=copy.deepcopy),patch('session_store.preflight',side_effect=lambda p,pl:(p,pl)) as check:
            packed=prepare_session(p,plan,'chronological');out=restore_session(packed)
        self.assertEqual(out['saved_edit']['plan']['segments'],plan['segments']);self.assertEqual(check.call_count,2)
        self.assertEqual(out['saved_edit']['method'],'chronological')

    def test_changed_fact_invalidates_saved_plan_without_losing_facts(self):
        p=sample();plan=make_plan(p)
        with patch('session_store.reconcile',side_effect=copy.deepcopy),patch('session_store.preflight',side_effect=lambda p,pl:(p,pl)):
            packed=prepare_session(p,plan);packed['facts'][1]['value']='新商品';out=restore_session(packed)
        self.assertNotIn('saved_edit',out);self.assertEqual(out['facts'][1]['value'],'新商品');self.assertTrue(out['warnings'])

    def test_old_source_change_invalidates_saved_plan(self):
        p=sample()
        with patch('session_store.reconcile',side_effect=copy.deepcopy),patch('session_store.preflight',side_effect=lambda p,pl:(p,pl)):
            packed=prepare_session(p,make_plan(p));packed['shots'][0]['source_sha256']='c'*64;out=restore_session(packed)
        self.assertNotIn('saved_edit',out)

    def test_browser_number_roundtrip_does_not_invalidate_session(self):
        p=sample();q=copy.deepcopy(p)
        for s in q['shots']:s['start']=int(s['start']);s['end']=int(s['end'])
        self.assertEqual(context_id(p),context_id(q))

    def test_legacy_project_without_plan_restores_normally(self):
        p=sample()
        with patch('session_store.reconcile',side_effect=copy.deepcopy):self.assertEqual(restore_session(p),p)

    def test_visual_change_toward_unsupported_class_marks_time(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a.png';b=Path(d)/'b.png';Image.new('RGB',(32,32),'black').save(a);Image.new('RGB',(32,32),'white').save(b)
            risk=semantic_risk([a,a,b],[{'time':0},{'time':1},{'time':2.5}],[[1,9,1,1,1,1],[1,9,1,1,1,1],[1,1,1,1,9,1]])
            self.assertIn('2.50',risk)

    def test_small_model_jitter_on_same_image_not_hard_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a.png';Image.new('RGB',(32,32),'white').save(a)
            self.assertIsNone(semantic_risk([a,a,a],[{'time':0},{'time':1},{'time':2}],[[1,9,1,1,1,1],[1,9,1,1,1,1],[1,1,1,1,9,1]]))

    def test_client_cannot_clear_server_risk_with_json_flag(self):
        p=sample();s=p['shots'][1];s['analysis_version']=6
        with tempfile.TemporaryDirectory() as d,patch.object(review_store,'DATA',Path(d)):
            review_store.store_review(s,{'semantic_issue':'混入内容风险'})
            s['semantic_issue']=None
            with patch('evidence_store.canonical',return_value=(s,s['source_sha256'])):
                with self.assertRaisesRegex(ValueError,'混入'):confirm(p,s['id'],'purpose',True)

    def test_hdr_rejected_before_lossy_review_generation(self):
        with patch('media.probe',return_value={'duration':8,'color_transfer':'smpte2084'}),patch('media.run') as run:
            with self.assertRaisesRegex(ValueError,'HDR'):analyze(Path('unused'),'a'*32,'hdr.mp4')
            run.assert_not_called()

if __name__=='__main__':unittest.main()
