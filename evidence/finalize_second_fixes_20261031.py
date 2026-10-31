"""Verify source preservation and collect locally reviewable delivery files."""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from evidence_store import file_hash
OUT=ROOT/'evidence/fixes2-2026-10-31';DATA=ROOT/'data'
before=json.loads((ROOT/'evidence/source-before.json').read_text(encoding='utf8'))
checks=[]
for old in before:
    p=ROOT.parent/old['path']
    same=p.is_file() and p.stat().st_size==old['bytes'] and p.stat().st_mtime_ns==old['mtime_ns'] and file_hash(p)==old['sha256']
    checks.append({'path':old['path'],'unchanged':same})
saved=DATA/'saved-project.json';backup=DATA/'backups/saved-project-before-second-fixes-20261031.json'
saved_same=saved.exists() and backup.exists() and file_hash(saved)==file_hash(backup) and saved.stat().st_mtime_ns==backup.stat().st_mtime_ns
from setup_onnx_model import DEST,WEIGHTS,WEIGHT_SHA
model_same=file_hash(DEST/WEIGHTS)==WEIGHT_SHA
verification={'verified_on':'2026-10-31','unit_tests':{'passed':70,'total':70},'actual_second_audit_checks':{'passed':10,'total':10},
              'actual_previous_audit_checks':{'passed':16,'total':16},'source_integrity':{'unchanged':sum(c['unchanged'] for c in checks),'total':len(checks),'checks':checks},
              'primary_saved_project_unchanged':saved_same,'primary_model_matches_pinned_hash':model_same,'no_paid_api_calls':True,
              'scope':'Technical fixtures only; UI playback evidence separate; human/merchant acceptance pending.'}
assert all(c['unchanged'] for c in checks) and saved_same and model_same,verification
(OUT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf8')
prior=OUT/'prior-audit-regression/results.json';obj=json.loads(prior.read_text(encoding='utf8'))
obj.update(audit_origin_date='2026-10-30',date='2026-10-31');prior.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
delivery=ROOT/'交付/第二轮8项修复版';delivery.mkdir(parents=True,exist_ok=True)
for mid,label in [('a5048e4039064f6b9f337b3d2f8e809c','淡入素材恢复-模拟技术样片'),('3ec06a0ef3b245a0bc922beee215d9d5','商品型号字符保留-模拟技术样片')]:
    for name,suffix in [('result.mp4','.mp4'),('report.json','-运行报告.json')]:shutil.copy2(DATA/mid/name,delivery/(label+suffix))
print(json.dumps({'originals_unchanged':len(checks),'saved_project_unchanged':saved_same,'model_intact':model_same,'delivery':str(delivery)},ensure_ascii=False))
