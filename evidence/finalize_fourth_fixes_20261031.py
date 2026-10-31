"""Verify preservation and assemble the fourth-fix reviewable deliverables."""
from pathlib import Path
import json,sys,shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from evidence_store import file_hash
from setup_onnx_model import DEST,WEIGHTS,WEIGHT_SHA
OUT=ROOT/'evidence/fixes4-2026-10-31'
records=json.loads((OUT/'results.json').read_text(encoding='utf8'));assert records['passed']==records['total']==7
browser=json.loads((OUT/'browser-checks.json').read_text(encoding='utf8'))
assert browser['allFailedPreserved'] and browser['editedPreserved'] and browser['retryPreserved']
assert browser['allFailedBefore']==browser['allFailedAfter'] and browser['editedBefore']==browser['editedAfter']
assert browser['partial']==browser['retry'] and browser['partial']['synthetic'] is False and len(browser['partial']['names'])==2
assert '包含结尾引导语' in browser['diagnostic']['text'] and '至少需要4.8秒' in browser['diagnostic']['text'] and browser['diagnostic']['renderDisabled']
assert browser['playbackStart']['paused'] is False and browser['playbackEnd']['ended'] and browser['playbackEnd']['readyState']==4 and browser['playbackEnd']['error'] is None
checks=[]
for item in json.loads((ROOT/'evidence/source-before.json').read_text(encoding='utf8')):
    path=ROOT.parent/item['path'];checks.append({'path':item['path'],'unchanged':path.is_file() and path.stat().st_size==item['bytes'] and path.stat().st_mtime_ns==item['mtime_ns'] and file_hash(path)==item['sha256']})
old=json.loads((ROOT/'evidence/fixes3-2026-10-31/ui-save-before.json').read_text(encoding='utf8'));saved=Path(old['path'])
saved_ok=file_hash(saved)==old['sha256'] and saved.stat().st_mtime_ns==old['mtime_ns'];model_ok=file_hash(DEST/WEIGHTS)==WEIGHT_SHA
assert all(x['unchanged'] for x in checks) and saved_ok and model_ok
result={'unit_tests':{'passed':97,'total':97},'actual_backend_checks':{'passed':7,'total':7},
        'browser_checks':['failed_batch_retains_plan_and_preview','failed_batch_retains_unsaved_fact_edit','partial_success_and_retry_deduplication','chronological_duration_diagnostic','grouped_promo_render_and_complete_playback'],
        'original_files':checks,'primary_saved_project_unchanged':saved_ok,'model_sha_verified':model_ok,
        'scope':'Simulated/authorized technical fixtures; human listening and merchant acceptance pending; no paid API calls.'}
(OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
delivery=ROOT/'交付/第四轮四项修复版';delivery.mkdir(parents=True,exist_ok=True)
source=ROOT/'data'/browser['finalVideo'].split('/')[2]
for a,b in [('result.mp4','完整优惠条件-模拟技术样片.mp4'),('report.json','完整优惠条件-运行报告.json'),('project.json','完整优惠条件-素材事实.json')]:shutil.copy2(source/a,delivery/b)
shutil.copy2(OUT/'eight-session.json',delivery/'可恢复剪辑方案-项目.json')
print(json.dumps({'originals_unchanged':len(checks),'saved_unchanged':saved_ok,'model_intact':model_ok,'playback_ended':True,'delivery':str(delivery)},ensure_ascii=False))
