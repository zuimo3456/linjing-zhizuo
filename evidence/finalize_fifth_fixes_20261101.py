"""Final preservation checks and delivery assembly for the three audit-5 fixes."""
from pathlib import Path
import json,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from evidence_store import file_hash
from setup_onnx_model import DEST,WEIGHTS,WEIGHT_SHA
from media import DATA,FFMPEG,run
OUT=ROOT/'evidence/fixes5-2026-11-01'
r=json.loads((OUT/'results.json').read_text(encoding='utf8'));assert r['passed']==r['total']==9
b=json.loads((OUT/'browser-checks.json').read_text(encoding='utf8'))
assert not b['importedPrice']['confirmed'] and '[U+202E]' in b['importedPrice']['value']
assert not b['pastedPrice']['confirmed'] and '[U+202E]' in b['pastedPrice']['value']
assert b['correctedPrice']['checked'] and b['correctedPrice']['value']=='单杯91元' and b['correctedPrice']['warningHidden']
assert b['timeline']['review'].endswith('#t=0,6') and b['timeline']['checked']
assert b['combo']['names'].count('one-second-product.mp4')==1 and '共16.0秒' in b['combo']['plan'] and not b['combo']['renderDisabled']
assert b['playbackStart']['paused'] is False and b['playbackEnd']['ended'] and b['playbackEnd']['readyState']==4 and b['playbackEnd']['error'] is None
assert b['reviewStart']['paused'] is False and b['reviewEnd']['currentTime']==6 and b['reviewEnd']['readyState']==4 and b['reviewEnd']['error'] is None
checks=[]
for item in json.loads((ROOT/'evidence/source-before.json').read_text(encoding='utf8')):
    p=ROOT.parent/item['path'];checks.append({'path':item['path'],'unchanged':p.is_file() and p.stat().st_size==item['bytes'] and p.stat().st_mtime_ns==item['mtime_ns'] and file_hash(p)==item['sha256']})
prior=json.loads((ROOT/'evidence/fixes3-2026-10-31/ui-save-before.json').read_text(encoding='utf8'));p=Path(prior['path'])
saved_ok=file_hash(p)==prior['sha256'] and p.stat().st_mtime_ns==prior['mtime_ns'];model_ok=file_hash(DEST/WEIGHTS)==WEIGHT_SHA
sources={}
for path in (ROOT/'evidence/audit5-2026-10-31').glob('*project.json'):
    for s in json.loads(path.read_text(encoding='utf8')).get('shots',[]):
        if s.get('source_sha256'):sources[s['media_id']]=s['source_sha256']
source_ok=all(file_hash(DATA/mid/'source.mp4')==sha for mid,sha in sources.items())
assert all(c['unchanged'] for c in checks) and saved_ok and model_ok and source_ok
verification={'date':'2026-11-01','unit_tests':{'passed':111,'total':111},'actual_scenario_groups':{'passed':9,'total':9},
              'browser_flows':['unsafe_price_recovery_paste_retype_and_render','mapped_review_window_and_video_playback','non_adjacent_planning_and_complete_playback'],
              'original_files':checks,'prior_audit_source_files_unchanged':len(sources),'primary_saved_project_unchanged':saved_ok,'pinned_model_hash_verified':model_ok,
              'analysis_version':7,'service_version':'local-ai-prototype-7','scope':'Simulated/authorized technical fixtures; not merchant or human listening acceptance.'}
(OUT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf8')
price=DATA/b['correctedPrice']['video'].split('/')[2];report=json.loads((price/'report.json').read_text(encoding='utf8'))
cue=next(c for t in report['timings'] for c in t['captions'] if '91' in c['text']);start=report['timings'][0]['start']+(cue['start']+cue['end'])/2
run([FFMPEG,'-y','-v','error','-ss',start,'-i',price/'result.mp4','-frames:v','1',OUT/'ui-generated-price91.jpg'])
delivery=ROOT/'交付/第五轮三项修复版';delivery.mkdir(exist_ok=True,parents=True);final=DATA/b['finalVideo'].split('/')[2]
for a,name in [('result.mp4','跳过短镜头-模拟技术样片.mp4'),('report.json','剪辑与运行报告.json'),('project.json','素材与事实.json')]:shutil.copy2(final/a,delivery/name)
shutil.copy2(OUT/'non-adjacent-session.json',delivery/'可恢复剪辑方案-项目.json')
shutil.copy2(price/'result.mp4',delivery/'重新确认91元-模拟技术样片.mp4')
shutil.copy2(OUT/'price91-session.json',delivery/'价格重新确认-项目.json')
print(json.dumps({'originals_unchanged':len(checks),'source_files_unchanged':len(sources),'saved_unchanged':saved_ok,'model_intact':model_ok,'delivery':str(delivery)},ensure_ascii=False))
