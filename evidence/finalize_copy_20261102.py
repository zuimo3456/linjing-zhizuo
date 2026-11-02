"""Preservation and delivery checks for specific-product copy."""
import json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from setup_qwen_voice import file_hash
OUT=ROOT/'evidence/copy-2026-11-02';DELIVERY=ROOT/'交付/具体商品文案'
def load(path):return json.loads(Path(path).read_text(encoding='utf8'))
rows=[]
for row in load(ROOT/'evidence/source-before.json'):
    path=ROOT.parent/row['path'];rows.append({'path':row['path'],'unchanged':path.stat().st_size==row['bytes']
        and path.stat().st_mtime_ns==row['mtime_ns'] and file_hash(path)==row['sha256']})
prior=load(ROOT/'evidence/fixes3-2026-10-31/ui-save-before.json');saved=Path(prior['path'])
saved_ok=file_hash(saved)==prior['sha256'] and saved.stat().st_mtime_ns==prior['mtime_ns']
project=load(OUT/'coconut-project.json');sources={s['media_id']:s['source_sha256'] for s in project['shots']}
source_ok=all(file_hash(ROOT/'data'/mid/'source.mp4')==sha for mid,sha in sources.items())
browser=load(OUT/'browser-checks.json');assert browser['playback_end']['ended'] and browser['playback_end']['error'] is None
assert len(rows)==49 and all(r['unchanged'] for r in rows) and saved_ok and source_ok
verification={'date':'2026-11-02','unit_checks_at_validation':146,'new_copy_unit_cases':13,'javascript_syntax':'pass',
 'original_files':rows,'primary_saved_project_unchanged':saved_ok,'source_videos_verified':len(sources),'source_videos_unchanged':source_ok,
 'actual_api_cases':['two_specific_coffee_plans','bakery_copy_without_footage_rejected','mismatched_traits_400','renamed_import_recovery','invented_claim_400','Vivian_mp4'],
 'actual_browser_flow':'pass','json_browser_download':'pass','mp4_browser_download':'not_verified_this_round','human_listening':'pending',
 'runtime':'4191 isolated preview; concurrent duration edits preserved; no shared-index commit this round'}
(OUT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf8')
folder=ROOT/'data'/browser['ui_generated_video'].split('/')[2]
for source,target in [('result.mp4','生椰拿铁-模拟文案样片.mp4'),('report.json','运行报告.json')]:shutil.copyfile(folder/source,DELIVERY/target)
project['saved_edit']={'version':1,'method':'evidence','plan':load(folder/'report.json')['plan']}
from session_store import prepare_session
session=prepare_session(project,project['saved_edit']['plan'])
(DELIVERY/'可恢复模拟项目.json').write_text(json.dumps(session,ensure_ascii=False,indent=2),encoding='utf8')
shutil.copyfile(ROOT/'docs/具体商品文案与事实约束_2026-11-02.md',DELIVERY/'使用与验证说明.md')
print(json.dumps({'originals_unchanged':49,'saved_unchanged':saved_ok,'source_videos_unchanged':len(sources),'browser_video':browser['ui_generated_video']},ensure_ascii=False))
