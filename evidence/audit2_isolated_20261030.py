"""Exercise unmodified server copies; never write the primary saved project/model."""
from pathlib import Path
import json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
CLONE=ROOT/'data/audit2-isolated/app';CLONE.mkdir(parents=True,exist_ok=True)
for src in ROOT.glob('*.py'):shutil.copy2(src,CLONE/src.name)
for folder in ('data','evidence','.models/chinese-clip-onnx/onnx'):(CLONE/folder).mkdir(parents=True,exist_ok=True)
(CLONE/'.models/chinese-clip-onnx/onnx/model_quantized.onnx').write_bytes(b'x')
(CLONE/'evidence/local-model-lock.json').write_text('{}',encoding='utf8')
worker=r'''
import concurrent.futures,collections,json,threading,urllib.request,urllib.error
from pathlib import Path
import server
srv=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
threading.Thread(target=srv.serve_forever,daemon=True).start()
url='http://127.0.0.1:'+str(srv.server_port)
def call(path,obj=None):
    data=None if obj is None else json.dumps(obj,ensure_ascii=False).encode('utf8')
    try:
        with urllib.request.urlopen(urllib.request.Request(url+path,data=data,headers={'Content-Type':'application/json'}),timeout=30) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
project={'goal':'visit','name':'隔离副本并发保存测试','facts':[],'shots':[
    {'id':'isolated-'+str(i),'media_id':format(i+1,'032x'),'start':0,'end':6,'quality':.5,'tags':['other'],'confirmed':False,'name':'中文并发测试'*10}
    for i in range(1000)]}
seed=call('/api/save',{'project':project})
barrier=threading.Barrier(5)
def writer():
    barrier.wait();return [call('/api/save',{'project':project}) for _ in range(25)]
def reader():
    barrier.wait();return [call('/api/saved') for _ in range(100)]
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    fs=[pool.submit(writer)]+[pool.submit(reader) for _ in range(4)]
    rows=[f.result() for f in fs]
errors=[{'http':code,'response':obj} for batch in rows for code,obj in batch if code!=200]
health=call('/api/health')
from local_vision import Engine
try:Engine();engine='unexpected_success'
except Exception as e:engine=str(e)
result={'isolation':'unmodified root Python sources copied to data/audit2-isolated/app; ephemeral loopback port; primary saved project and model untouched',
        'B11':{'seed_http':seed[0],'writes':25,'reads':400,'http_counts':dict(collections.Counter(str(code) for batch in rows for code,_ in batch)),
               'error_count':len(errors),'representative_errors':errors[:4],'saved_bytes':(server.DATA/'saved-project.json').stat().st_size},
        'B12':{'health_local_vision':health[1]['local_vision'],'engine_load_result':engine}}
print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
srv.shutdown();srv.server_close();server.pool.shutdown()
'''
result=subprocess.run([sys.executable,'-X','utf8','-c',worker],cwd=CLONE,capture_output=True,text=True,encoding='utf8',timeout=120)
out=ROOT/'evidence/audit2-2026-10-30/isolated-results.json'
if result.returncode:raise RuntimeError(result.stderr[-3000:])
obj=json.loads(result.stdout);out.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
print(result.stdout)
