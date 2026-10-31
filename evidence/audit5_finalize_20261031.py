"""Preserve exploratory audit 5 evidence and verify original file integrity."""
from pathlib import Path
import json,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from media import DATA,FFMPEG,run
from evidence_store import file_hash
from setup_onnx_model import DEST,WEIGHTS,WEIGHT_SHA
OUT=ROOT/'evidence/audit5-2026-10-31'
records=json.loads((OUT/'results.json').read_text(encoding='utf8'))['cases'];assert len(records)==8 and not any(c['result'].get('harness_exception') for c in records)
browser=json.loads((OUT/'browser-checks.json').read_text(encoding='utf8'))
assert browser['direction']['planCanRender'] and browser['ordinary']=='单杯19元'
assert browser['delayed']['confirmed'] is False and browser['group']['renderDisabled']
delayed=json.loads((OUT/'delayed-asset.json').read_text(encoding='utf8'))
f=next(f for f in delayed['shots'][0]['frames'] if f['time']==3)
shutil.copy2(DATA/delayed['id']/f['url'].rsplit('/',1)[1],OUT/'delayed-evidence-time3.jpg')
run([FFMPEG,'-y','-v','error','-ss','3','-i',DATA/'audit5-fixtures/counter-video-delay2.mp4','-frames:v','1',OUT/'delayed-source-time3.jpg'])
checks=[]
for item in json.loads((ROOT/'evidence/source-before.json').read_text(encoding='utf8')):
    path=ROOT.parent/item['path'];checks.append({'path':item['path'],'unchanged':path.is_file() and path.stat().st_size==item['bytes'] and path.stat().st_mtime_ns==item['mtime_ns'] and file_hash(path)==item['sha256']})
old=json.loads((ROOT/'evidence/fixes3-2026-10-31/ui-save-before.json').read_text(encoding='utf8'));saved=Path(old['path'])
saved_ok=file_hash(saved)==old['sha256'] and saved.stat().st_mtime_ns==old['mtime_ns'];model_ok=file_hash(DEST/WEIGHTS)==WEIGHT_SHA
assert all(x['unchanged'] for x in checks) and saved_ok and model_ok
result={'baseline':'1f4d1ed','actual_backend_scenario_groups':len(records),'browser_scenario_groups':3,
        'successful_technical_videos':sum(bool(c['result'].get('video') or c['result'].get('valid_video')) for c in records),
        'new_findings':3,'unit_tests_not_repeated':True,'original_files':checks,'primary_saved_project_unchanged':saved_ok,'model_sha_verified':model_ok,
        'scope':'No application edits, no cloud calls, simulated fixtures; human listening and merchant accuracy not measured.'}
(OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'groups':8,'new_findings':3,'originals_unchanged':len(checks),'saved_unchanged':saved_ok,'model_intact':model_ok},ensure_ascii=False))
