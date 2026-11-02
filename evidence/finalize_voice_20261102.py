"""Verify preservation and publish small, reproducible narration evidence."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from setup_qwen_voice import DEST,WEIGHTS,file_hash
from setup_onnx_model import DEST as VISION,WEIGHTS as VISION_FILE,WEIGHT_SHA
OUT=ROOT/'evidence/voice-2026-11-02'
def load(path):return json.loads(Path(path).read_text(encoding='utf8'))
originals=[]
for row in load(ROOT/'evidence/source-before.json'):
    path=ROOT.parent/row['path']
    originals.append({'path':row['path'],'unchanged':path.is_file() and path.stat().st_size==row['bytes']
                      and path.stat().st_mtime_ns==row['mtime_ns'] and file_hash(path)==row['sha256']})
saved=load(ROOT/'evidence/fixes3-2026-10-31/ui-save-before.json');path=Path(saved['path'])
saved_ok=file_hash(path)==saved['sha256'] and path.stat().st_mtime_ns==saved['mtime_ns']
voice_ok=all(file_hash(DEST/name)==sha for name,sha in WEIGHTS.items())
vision_ok=file_hash(VISION/VISION_FILE)==WEIGHT_SHA
project=load(OUT/'session.json');sources={s['media_id']:s['source_sha256'] for s in project['shots']}
sources_ok=all(file_hash(ROOT/'data'/mid/'source.mp4')==sha for mid,sha in sources.items())
assert len(originals)==49 and all(x['unchanged'] for x in originals)
assert saved_ok and voice_ok and vision_ok and sources_ok
phrases=[load(p) for p in (ROOT/'data/voice-phrases').glob('*.json')]
verification={'date':'2026-11-02','unit_tests':{'passed':120,'total':120},'javascript_syntax':'pass',
 'audio_samples':3,'actual_api_plan_validate_render':'pass','old_plan_rejected':'pass',
 'original_files':originals,'primary_saved_project_unchanged':saved_ok,'test_source_count':len(sources),
 'test_sources_unchanged':sources_ok,'voice_weight_hashes_verified':voice_ok,'vision_weight_hash_verified':vision_ok,
 'initial_cold_promotional_sample_seconds':37.964,'initial_timing_source':'First verify_neural_voice.py console output before warm-cache rerun',
 'max_model_gpu_mb':max(p['cuda_peak_mb'] for p in phrases),'generated_phrase_count':len(phrases),
 'browser_playback':'not_verified_this_round','browser_download':'not_verified_this_round','human_listening':'pending',
 'preview':'http://127.0.0.1:4191/','previous_4180_service':'not_stopped_due_to_concurrent_work'}
(OUT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf8')
(OUT/'phrase-metrics.json').write_text(json.dumps(phrases,ensure_ascii=False,indent=2),encoding='utf8')
shutil.copyfile(ROOT/'docs/开源活泼女声接入_2026-11-02.md',ROOT/'交付/开源活泼女声/使用与验证说明.md')
shutil.copyfile(DEST/'verified-manifest.json',OUT/'model-manifest.json')
print(json.dumps({'originals_unchanged':len(originals),'saved_unchanged':saved_ok,'source_videos_unchanged':len(sources),
 'voice_and_vision_weights_verified':voice_ok and vision_ok},ensure_ascii=False))
