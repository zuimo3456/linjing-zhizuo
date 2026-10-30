import copy,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from planner import make_plan as _make_plan,validate_plan,PlanError,caption_for,GOALS,CTA
from vision_adapter import parse_labels

def sample():
    p={'goal':'visit','synthetic':True,'name':'test','facts':[
        {'id':'f1','kind':'shop','value':'测试店','confirmed':True,'source':'模拟'},
        {'id':'f2','kind':'product','value':'测试商品','confirmed':True,'source':'模拟'},
        {'id':'f3','kind':'address','value':'测试地址','confirmed':True,'source':'模拟'},
        {'id':'f4','kind':'offer','value':'第二杯半价，限同款','confirmed':True,'source':'模拟'},
        {'id':'f5','kind':'validity','value':'2099年10月23日至30日','confirmed':True,'source':'模拟'}],
        'shots':[{'id':f's{i}','media_id':'a'*32,'source_sha256':'b'*64,'start':0.,'end':6.,'quality':.8,'tags':[tag],'confirmed':True,
                  'product_binding':{'fact_id':'f2','value':'测试商品','confirmed':True}}
                 for i,tag in enumerate(['interior','product','storefront','process'])]}
    from evidence_store import identity
    for shot in p['shots']:shot['product_binding']['evidence_id']=identity(shot)
    return p

def make_plan(project,method='evidence'):
    # These structural tests use explicitly simulated 1s narration. Actual TTS is separately integrated.
    lengths={}
    for role in GOALS[project['goal']]['roles']:
        text=caption_for(role,project['facts'],project['goal'])[0]
        lengths[text]=1.;lengths[text+CTA[project['goal']]]=1.
    return _make_plan(project,method,lengths)

class Constraints(unittest.TestCase):
    def setUp(self): self.p=sample();self.plan=make_plan(self.p)
    def reject(self,mutate):
        mutate(self.plan)
        with self.assertRaises(PlanError):validate_plan(self.p,self.plan)
    def test_visit_order(self):self.assertEqual([s['shot_id'] for s in self.plan['segments']],['s2','s1','s0'])
    def test_attract_order(self):
        self.p['goal']='attract';p=make_plan(self.p);self.assertEqual([s['shot_id'] for s in p['segments']],['s1','s3','s0']);self.assertTrue(validate_plan(self.p,p))
    def test_promo_requirements(self):
        self.p['goal']='promo';p=make_plan(self.p);self.assertEqual(p['segments'][0]['fact_ids'],['f1','f2','f4','f5']);self.assertTrue(validate_plan(self.p,p))
    def test_chronological_baseline(self):self.assertEqual([s['shot_id'] for s in make_plan(self.p,'chronological')['segments']],['s0','s1','s2'])
    def test_valid_plan(self):self.assertTrue(validate_plan(self.p,self.plan))
    def test_versatile_shot_not_greedily_consumed(self):
        self.p['shots'][1]['tags']=['storefront','product'];self.p['shots'][1]['quality']=.99
        p=make_plan(self.p)
        self.assertTrue(p['renderable']);self.assertEqual([s['shot_id'] for s in p['segments']],['s2','s1','s0'])
    def test_unknown_shot(self):self.reject(lambda p:p['segments'][0].update(shot_id='fake'))
    def test_unknown_fact(self):self.reject(lambda p:p['segments'][0].update(fact_ids=['fake']))
    def test_hallucinated_price(self):self.reject(lambda p:p['segments'][1].update(text='今天只要9.9元。'))
    def test_suffix_hallucination(self):self.reject(lambda p:p['segments'][0].update(text=p['segments'][0]['text']+'全市第一。'))
    def test_unsupported_role(self):self.reject(lambda p:p['segments'][0].update(role='product'))
    def test_negative_start(self):self.reject(lambda p:p['segments'][0].update(start=-1))
    def test_end_beyond_source(self):self.reject(lambda p:p['segments'][0].update(end=99))
    def test_nan_time(self):self.reject(lambda p:p['segments'][0].update(start=float('nan')))
    def test_infinite_time(self):self.reject(lambda p:p['segments'][0].update(end=float('inf')))
    def test_duplicate_shot(self):self.reject(lambda p:p['segments'].append(copy.deepcopy(p['segments'][0])))
    def test_unconfirmed_source(self):
        self.p['shots'][2]['confirmed']=False
        with self.assertRaises(PlanError):validate_plan(self.p,self.plan)
    def test_low_quality(self):
        self.p['shots'][2]['quality']=.1;self.assertFalse(make_plan(self.p)['renderable'])
    def test_missing_interior(self):
        self.p['shots'][0]['tags']=['other'];p=make_plan(self.p);self.assertFalse(p['renderable']);self.assertIn('环境',''.join(p['missing']))
    def test_missing_address(self):
        self.p['facts'][2]['confirmed']=False;self.assertFalse(make_plan(self.p)['renderable'])
    def test_conflicting_fact(self):
        self.p['facts'].append({'id':'f6','kind':'address','value':'不同地址','confirmed':True,'source':'模拟'})
        with self.assertRaises(PlanError):make_plan(self.p)
    def test_no_source_attestation(self):
        self.p['facts'][0]['source']=''
        with self.assertRaises(PlanError):make_plan(self.p)
    def test_goal_tamper(self):self.reject(lambda p:p.update(goal='promo'))
    def test_synthetic_marker_tamper(self):self.reject(lambda p:p.update(synthetic=False))
    def test_unconfirmed_fact_not_used(self):
        self.p['facts'][0]['confirmed']=False;p=make_plan(self.p);self.assertNotIn('f1',p['segments'][1]['fact_ids'])
    def test_short_clip(self):
        self.p['shots'][2]['end']=.3;self.assertFalse(make_plan(self.p)['renderable'])
    def test_labels_remain_candidates(self):
        obj={'labels':[{'shot_id':'s0','tags':['product'],'confidence':.8,'description':'杯子'}]}
        self.assertFalse(parse_labels(obj,{'s0'})[0]['confirmed'])
    def test_labels_unknown_id(self):
        with self.assertRaises(ValueError):parse_labels({'labels':[{'shot_id':'fake','tags':['product'],'confidence':.8}]},{'s0'})
    def test_labels_invalid_confidence(self):
        with self.assertRaises(ValueError):parse_labels({'labels':[{'shot_id':'s0','tags':['product'],'confidence':float('nan')}]},{'s0'})
    def test_labels_invalid_tag(self):
        with self.assertRaises(ValueError):parse_labels({'labels':[{'shot_id':'s0','tags':['identity_of_person'],'confidence':.8}]},{'s0'})

if __name__=='__main__':unittest.main(verbosity=2)
