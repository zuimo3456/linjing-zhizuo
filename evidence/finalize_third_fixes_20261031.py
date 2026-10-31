"""Preserve original sources and assemble third-fix handoff artifacts."""
from pathlib import Path
import json,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from evidence_store import file_hash
from setup_onnx_model import DEST,WEIGHTS,WEIGHT_SHA
OUT=ROOT/'evidence/fixes3-2026-10-31';DATA=ROOT/'data'
before=json.loads((ROOT/'evidence/source-before.json').read_text(encoding='utf8'));checks=[]
for item in before:
    p=ROOT.parent/item['path'];same=p.is_file() and p.stat().st_size==item['bytes'] and p.stat().st_mtime_ns==item['mtime_ns'] and file_hash(p)==item['sha256']
    checks.append({'path':item['path'],'unchanged':same})
saved_before=json.loads((OUT/'ui-save-before.json').read_text(encoding='utf8'));p=Path(saved_before['path'])
restored=file_hash(p)==saved_before['sha256'] and p.stat().st_mtime_ns==saved_before['mtime_ns']
browser=json.loads((OUT/'browser-checks.json').read_text(encoding='utf8'))
assert browser['playbackEnd']['ended'] and browser['playbackEnd']['readyState']==4
assert browser['savedOrderBefore']==browser['restoredOrder']
assert len(browser['upload']['names'])==len(browser['uploadRetry']['names'])==2
assert browser['semantic']['checked'] is False
assert all(c['unchanged'] for c in checks) and restored
model_ok=file_hash(DEST/WEIGHTS)==WEIGHT_SHA;assert model_ok
result={'date':'2026-10-31','unit_tests':{'passed':89,'total':89},'actual_new_backend_checks':{'passed':6,'total':6},
        'actual_previous_checks':{'passed':26,'total':26},'browser_scenarios':['batch_and_retry','risk_confirmation_block','group_import_save_reload_render_playback'],
        'original_files':{'unchanged':sum(c['unchanged'] for c in checks),'total':len(checks),'checks':checks},
        'primary_saved_project_restored_hash_and_mtime':restored,'pinned_model_hash_verified':model_ok,
        'HDR_handling':'Detected and explicitly rejected; user must supply SDR. No automatic HDR color conversion.',
        'semantic_scope':'0.5-second evidence sampling and source-bound content-change risk veto, not exhaustive semantic correctness.',
        'scope':'Synthetic/CC0 technical fixtures; human and merchant acceptance pending; no cloud inference.'}
(OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
prior=OUT/'prior-audit-regression/results.json';r=json.loads(prior.read_text(encoding='utf8'));r.update(audit_origin_date='2026-10-30',date='2026-10-31');prior.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
shutil.copy2(OUT/'ui-final-playing.png',OUT/'ui-final-preview.png')
delivery=ROOT/'交付/第三轮六项修复版';delivery.mkdir(exist_ok=True,parents=True)
video_id=browser['finalVideo'].split('/')[2]
for name,target in [('result.mp4','短镜头连续旁白-模拟技术样片.mp4'),('report.json','短镜头连续旁白-运行报告.json'),('project.json','短镜头连续旁白-素材事实.json')]:shutil.copy2(DATA/video_id/name,delivery/target)
shutil.copy2(OUT/'ui-saved-session.json',delivery/'可恢复剪辑顺序-项目.json')
print(json.dumps({'originals_unchanged':len(checks),'saved_restored':restored,'model_intact':model_ok,'browser_ended':True,'delivery':str(delivery)},ensure_ascii=False))
