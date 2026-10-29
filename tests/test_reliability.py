"""Critical failures: wrong products, contradictory frames, bad output, timing."""
import copy,math,tempfile,unittest
from pathlib import Path
from planner import make_plan,validate_plan,PlanError
from test_invariants import sample
from local_vision import decide,frame_paths
from audio import phrases
from media import write_ass

class Reliability(unittest.TestCase):
    def test_missing_product_binding_cannot_render(self):
        p=sample();p['shots'][1].pop('product_binding')
        self.assertFalse(make_plan(p)['renderable'])

    def test_renaming_product_invalidates_old_binding(self):
        p=sample();plan=make_plan(p);p['facts'][1]['value']='另一种商品'
        self.assertFalse(make_plan(p)['renderable'])
        with self.assertRaises(PlanError):validate_plan(p,plan)

    def test_forged_product_fact_reference_rejected(self):
        p=sample();p['shots'][1]['product_binding']['fact_id']='f1'
        self.assertFalse(make_plan(p)['renderable'])

    def test_product_confirmation_is_separate_from_label(self):
        p=sample();p['shots'][1]['product_binding']['confirmed']=False
        self.assertFalse(make_plan(p)['renderable'])

    def test_compatible_product_binding_allows_plan(self):
        p=sample();self.assertTrue(validate_plan(p,make_plan(p)))

    def test_disagreeing_frames_abstain(self):
        rows=[[30,10,5,2,1,0],[0,1,2,30,0,0],[30,10,5,2,1,0]]
        result=decide(rows,.8)
        self.assertTrue(result['abstained']);self.assertEqual(result['tags'],['other'])

    def test_near_tied_scores_abstain(self):
        self.assertTrue(decide([[30,29,5,2,1,0]]*3,.8)['abstained'])

    def test_unrelated_frames_abstain(self):
        self.assertTrue(decide([[0,1,2,3,4,30]]*3,.8)['abstained'])

    def test_people_not_auto_selected_as_product(self):
        self.assertTrue(decide([[0,1,2,3,30,4]]*3,.8)['abstained'])

    def test_low_quality_cannot_override_with_high_model_score(self):
        self.assertTrue(decide([[30,1,2,3,4,5]]*3,.1)['abstained'])

    def test_single_frame_requires_review(self):
        self.assertTrue(decide([[30,1,2,3,4,5]],.8)['abstained'])

    def test_stable_candidate_still_unconfirmed(self):
        r=decide([[30,1,2,3,4,5]]*3,.8)
        self.assertEqual(r['tags'],['storefront']);self.assertFalse(r['confirmed'])

    def test_model_nan_rejected(self):
        with self.assertRaises(ValueError):decide([[math.nan,1,2,3,4,5]]*3,.8)

    def test_model_wrong_dimensions_rejected(self):
        with self.assertRaises(ValueError):decide([[1,2,3]]*3,.8)

    def test_frame_path_traversal_rejected(self):
        with self.assertRaises(ValueError):frame_paths({'media_id':'../secret'})

    def test_subtitle_does_not_execute_ass_markup(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'test.ass'
            write_ass(p,'不用',3,False,[{'start':.3,'end':1.4,'text':'{\\pos(1,1)}测试'}])
            body=p.read_text(encoding='utf-8-sig')
            self.assertNotIn('{\\pos',body);self.assertIn('0:00:00.30,0:00:01.40',body)

    def test_phrases_bound_subtitle_length(self):
        text='这是一个很长的测试句子，'+('测试'*30)+'。第二句。'
        chunks=phrases(text)
        self.assertEqual(''.join(chunks),text)
        self.assertTrue(all(len(x)<=26 for x in chunks))

if __name__=='__main__':unittest.main(verbosity=2)
