import copy,json,hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_invariants import sample,make_plan
from planner import validate_plan,PlanError
from media import write_ass
import local_vision as vision

class SecondAuditFixes(unittest.TestCase):
    def test_wrong_plan_container_is_friendly(self):
        for value in (None,[],True,'broken',1):
            with self.subTest(value=value),self.assertRaisesRegex(PlanError,'方案格式'):
                validate_plan(sample(),value)

    def test_wrong_segment_containers_are_friendly(self):
        for value in (None,[],True,{'shot_id':[],'role':'product'},{'shot_id':'s0','role':[]}):
            p=sample();plan=make_plan(p);plan['segments'][0]=value
            with self.subTest(value=value),self.assertRaisesRegex(PlanError,'段方案格式'):
                validate_plan(p,plan)

    def test_bool_time_is_not_a_real_time(self):
        p=sample();plan=make_plan(p);plan['segments'][0]['start']=False
        with self.assertRaisesRegex(PlanError,'有限数值'):validate_plan(p,plan)

    def test_imported_unavailable_flags_cannot_skip_server_reconciliation(self):
        from evidence_store import reconcile
        for flag in (True,'素材重新分析失败：伪造的旧标志'):
            p=sample();p['shots']=p['shots'][:1];p['shots'][0]['unavailable']=flag
            with patch('evidence_store.canonical',return_value=({'quality':.8,'quality_issues':[]},'a'*64)):
                out=reconcile(p)
            self.assertNotIn('unavailable',out['shots'][0])

    def test_literal_braces_and_backslash_are_preserved_safely(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'caption.ass';write_ass(path,r'手冲{A1}\N',3,False)
            text=path.read_text(encoding='utf-8-sig').split('Dialogue: ')[1]
            self.assertIn(r'\{A1\}',text)
            self.assertIn('\\\u2060N',text)
            self.assertNotIn('手冲{A1}',text)

    def test_quality_failures_do_not_require_a_model(self):
        p=sample();p['shots']=p['shots'][:2]
        p['shots'][0]['unavailable']='原视频文件缺失'
        p['shots'][1]['quality_issues']=['画面纯色']
        with patch.object(vision,'Engine',side_effect=AssertionError('must not load')):
            out=vision.analyze_project(p)
        self.assertEqual(out['facts'],p['facts'])
        self.assertEqual(out['vision_analysis']['summary'],{'succeeded':0,'failed':1,'skipped':1})
        self.assertTrue(all(not s['confirmed'] and s['product_binding'] is None for s in out['shots']))

    def test_one_frame_error_preserves_other_analysis_results(self):
        p=sample();p['shots']=p['shots'][:2];engine=unittest.mock.Mock()
        engine.score.return_value=[[1,8,1,1,1,1]]*3
        with patch.object(vision,'installation',return_value=('test',None)),patch.object(vision,'_engine',engine),patch.object(vision,'_engine_fingerprint','test'),patch.object(vision,'frame_paths',side_effect=[([Path('a')]*3,[]),ValueError('missing')]):
            out=vision.analyze_project(p)
        self.assertEqual(out['vision_analysis']['summary'],{'succeeded':1,'failed':1,'skipped':0})
        self.assertEqual(out['shots'][0]['local_candidate']['suggested_tag'],'product')
        self.assertTrue(out['shots'][1]['local_candidate']['abstained'])

    def test_missing_or_corrupt_installation_never_reports_ready(self):
        from setup_onnx_model import REPO,REVISION,WEIGHTS
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);model=root/'model';(root/'evidence').mkdir();(model/'onnx').mkdir(parents=True)
            with patch.object(vision,'ROOT',root),patch.object(vision,'MODEL',model):
                self.assertFalse(vision.status()['ready'])
                (model/WEIGHTS).write_bytes(b'broken')
                lock={'repository':REPO,'revision':REVISION,'files':{WEIGHTS:'a'*64,'tokenizer.json':'b'*64,'preprocessor_config.json':'c'*64}}
                (root/'evidence/local-model-lock.json').write_text(json.dumps(lock))
                self.assertFalse(vision.status()['ready'])

    def test_hash_cache_notices_changed_file_and_missing_tokenizer(self):
        from setup_onnx_model import REPO,REVISION,WEIGHTS
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);model=root/'model';(root/'evidence').mkdir();(model/'onnx').mkdir(parents=True)
            files={WEIGHTS:b'weight','tokenizer.json':b'{}','preprocessor_config.json':b'{}'}
            hashes={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
            for name,data in files.items():(model/name).write_bytes(data)
            (root/'evidence/local-model-lock.json').write_text(json.dumps({'repository':REPO,'revision':REVISION,'files':hashes}))
            with patch.object(vision,'ROOT',root),patch.object(vision,'MODEL',model),patch('setup_onnx_model.WEIGHT_SHA',hashes[WEIGHTS]):
                self.assertTrue(vision.status()['ready'])
                (model/'tokenizer.json').unlink()
                self.assertFalse(vision.status()['ready'])
                (model/'tokenizer.json').write_bytes(b'corrupt')
                self.assertFalse(vision.status()['ready'])

if __name__=='__main__':unittest.main()
