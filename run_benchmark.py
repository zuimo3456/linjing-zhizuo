"""Constraint regression, explicitly not a merchant/semantic benchmark."""
import json,sys,unittest
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests'))
import test_invariants
class Recorder(unittest.TextTestResult):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.records=[]
    def addSuccess(self,test):super().addSuccess(test);self.records.append({'name':test._testMethodName,'passed':True})
    def addFailure(self,test,err):super().addFailure(test,err);self.records.append({'name':test._testMethodName,'passed':False})
    def addError(self,test,err):super().addError(test,err);self.records.append({'name':test._testMethodName,'passed':False})
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2,resultclass=Recorder).run(unittest.defaultTestLoader.discover(str(ROOT/'tests')))
    doc={'created_at':datetime.now(timezone.utc).isoformat(),'scope':'人工设计的合成约束回归测试，不能外推到真实模型或商户效果',
         'total':result.testsRun,'passed':sum(x['passed'] for x in result.records),'cases':result.records,
         'real_merchants':0,'real_videos':0,'model_comparison':'not_run'}
    (ROOT/'evidence/constraint-results.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
