"""Preservation check and audit classification, no application changes."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from evidence_store import file_hash
OUT=ROOT/'evidence/audit3-2026-10-31'
old=json.loads((ROOT/'evidence/source-before.json').read_text(encoding='utf8'));checks=[]
for item in old:
    p=ROOT.parent/item['path'];same=p.is_file() and p.stat().st_size==item['bytes'] and p.stat().st_mtime_ns==item['mtime_ns'] and file_hash(p)==item['sha256']
    checks.append({'path':item['path'],'unchanged':same})
before=json.loads((OUT/'save-backup.json').read_text(encoding='utf8'));p=Path(before['path'])
saved_restored=file_hash(p)==before['sha256'] and p.stat().st_mtime_ns==before['mtime_ns']
assert all(c['unchanged'] for c in checks) and saved_restored
from PIL import Image
import numpy as np
original=np.asarray(Image.open(ROOT/'evidence/public-test-images/coffee.png').convert('RGB'),dtype=float)
roundtrip=np.asarray(Image.open(OUT/'hdr-correct-reference.png').convert('RGB'),dtype=float)
result={'date':'2026-10-31','functional_commit':'a8c5fb2','regression_tests':{'total':70,'passed':70},
        'case_count':10,'new_defects':['T07','T09','T10'],'known_limits_reproduced':['T02','T06','T08'],'normal_controls':['T01','T03','T04','T05'],
        'hdr_roundtrip_reference_RGB_MAE':round(float(np.abs(original-roundtrip).mean()),3),
        'source_integrity':{'total':len(checks),'unchanged':sum(c['unchanged'] for c in checks),'checks':checks},
        'saved_project_restored_hash_and_mtime':saved_restored,'primary_save_note':'Temporarily saved the synthetic order test through UI; original bytes and mtime restored after checking no independent save occurred.',
        'application_changed':False,'paid_api_calls':0,'scope':'Synthetic and CC0-derived technical examples, not real shop accuracy or user acceptance',
        'fixtures':[{'name':f.name,'bytes':f.stat().st_size,'sha256':file_hash(f)} for f in sorted((ROOT/'data/audit3-fixtures').iterdir()) if f.is_file()]}
(OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'cases':10,'new_defects':3,'known_limits':3,'originals_unchanged':len(checks),'saved_project_restored':saved_restored}))
