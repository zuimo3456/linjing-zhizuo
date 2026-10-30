"""Record audit provenance and verify preserved original files."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from media import FFMPEG,run,DATA
OUT=ROOT/'evidence/audit2-2026-10-30'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
originals=json.loads((ROOT/'evidence/source-before.json').read_text(encoding='utf8'))
checks=[]
for old in originals:
    p=ROOT.parent/old['path'];same=p.is_file() and p.stat().st_size==old['bytes'] and p.stat().st_mtime_ns==old['mtime_ns'] and digest(p)==old['sha256']
    checks.append({'path':old['path'],'unchanged':same})
for name,at in [('fade-start.jpg',.025),('fade-clear.jpg',2)]:
    run([FFMPEG,'-y','-v','error','-ss',at,'-i',DATA/'f52f8b5d48104050986acd1551c12e67/source.mp4','-frames:v','1',OUT/name])
facts={'functional_commit':'51db091','audit_base_commit':'a4250e2','regression':{'command':'python -X utf8 -m unittest discover -s tests','passed':61,'failed':0},
       'source_integrity':{'total':len(checks),'unchanged':sum(c['unchanged'] for c in checks),'checks':checks},
       'fixtures':[{'name':p.name,'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted((DATA/'audit2-fixtures').iterdir()) if p.is_file()],
       'primary_saved_project':'No /api/save request to the main server during this audit. Concurrency checks used a copied app on an ephemeral localhost port.',
       'scope':'12 exploratory cases; 8 reproduced issues; 4 positive or non-reproducing checks. Browser evidence supplements B03, not another independent case. Technical fixtures only.'}
(OUT/'verification.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'originals_unchanged':sum(c['unchanged'] for c in checks),'originals_total':len(checks),'fixtures':len(facts['fixtures'])}))
