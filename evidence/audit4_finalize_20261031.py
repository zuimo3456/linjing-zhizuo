"""Export audit artifacts; assert original files and primary saved project are intact."""
from pathlib import Path
import json,sys,urllib.request
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from media import DATA,FFMPEG,run
from evidence_store import file_hash
def api(path,obj):
    request=urllib.request.Request('http://127.0.0.1:4180'+path,data=json.dumps(obj,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=120) as response:return response.status,json.load(response)
OUT=ROOT/'evidence/audit4-2026-10-31'
r=json.loads((OUT/'results.json').read_text(encoding='utf8'))
for c in r['cases']:
    if not isinstance(c['result'],dict):continue
    render=c['result'].get('render') or {}
    if render.get('status')=='done':
        res=render['result'];source=DATA/res['video'].split('/')[2]/'result.mp4'
        run([FFMPEG,'-y','-v','error','-ss','0.8','-i',source,'-frames:v','1',OUT/(c['id']+'-output.jpg')])
        print(c['id'],'render done',res['video'],res['metrics']['metadata']['duration'])
        if c['id']=='C02':
            p=json.loads((OUT/'under-eight-project.json').read_text(encoding='utf8'));pl=c['result']['plan']
            code,packed=api('/api/export-project',{'project':p,'plan':pl,'method':'evidence'});assert code==200,packed
            (OUT/'under-eight-session.json').write_text(json.dumps(packed,ensure_ascii=False,indent=2),encoding='utf8')
checks=[]
for item in json.loads((ROOT/'evidence/source-before.json').read_text(encoding='utf8')):
    path=ROOT.parent/item['path'];checks.append({'path':item['path'],'unchanged':path.is_file() and path.stat().st_size==item['bytes'] and path.stat().st_mtime_ns==item['mtime_ns'] and file_hash(path)==item['sha256']})
old=json.loads((ROOT/'evidence/fixes3-2026-10-31/ui-save-before.json').read_text(encoding='utf8'));saved=Path(old['path'])
saved_ok=file_hash(saved)==old['sha256'] and saved.stat().st_mtime_ns==old['mtime_ns']
assert all(x['unchanged'] for x in checks) and saved_ok
(OUT/'integrity.json').write_text(json.dumps({'baseline':'d02f4aa','original_files':checks,'primary_saved_project_unchanged':saved_ok,'scope':'Read-only audit of application code; test-generated local artifacts only.'},ensure_ascii=False,indent=2),encoding='utf8')
print('Original files:',len(checks),'unchanged. Primary saved project unchanged:',saved_ok)
