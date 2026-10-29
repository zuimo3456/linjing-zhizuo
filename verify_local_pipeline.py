"""Opt-in actual local-model/audio/render checks, using declared technical fixtures."""
import json,shutil,tempfile,uuid
from pathlib import Path
from datetime import datetime,timezone
from demo import create_demo
from planner import make_plan,validate_plan
from local_vision import analyze_project
from audio import synthesize
from media import render,DATA,ROOT,probe

def main():
    project=create_demo(print)
    analyzed=analyze_project(project,print)
    assert all(not s['confirmed'] for s in analyzed['shots'])
    assert not make_plan(analyzed)['renderable']
    # Synthetic drawing ground truth, explicitly restored by test code after AI abstention.
    truth={s['id']:s for s in project['shots']}
    for shot in analyzed['shots']:
        shot.update(tags=truth[shot['id']]['tags'],confirmed=True,label_source='synthetic_ground_truth_after_model')
        shot['product_binding']=truth[shot['id']].get('product_binding')
    outputs={}
    for goal in ('visit','attract'):
        analyzed['goal']=goal;plan=make_plan(analyzed);validate_plan(analyzed,plan)
        result=render(analyzed,plan,uuid.uuid4().hex,print)
        timings=result['metrics']['timings']
        assert all(t['held_frame_seconds']==0 and 1<=t['voice_speed']<=1.18 for t in timings)
        assert all(0<=c['start']<c['end']<=t['end']-t['start']+.02 for t in timings for c in t['captions'])
        outputs[goal]=result
    with tempfile.TemporaryDirectory(prefix='linjing-refusal-') as folder:
        try:synthesize('这段完整的优惠条件不能随意删减，需要足够长的画面。',Path(folder),'too-long',1)
        except ValueError as e:
            assert '不使用长停帧' in str(e);refusal=str(e)
        else:raise AssertionError('Overlong narration was not rejected')
    result={'created_at':datetime.now(timezone.utc).isoformat(),'scope':'实际本地推理和音画合成技术检查；插画，不是真实商户',
            'model_result':analyzed['vision_analysis'],'all_model_results_unconfirmed':True,
            'model_abstentions':sum(s['local_candidate']['abstained'] for s in analyzed['shots']),
            'manual_ground_truth_restoration':True,'overlong_refusal':refusal,'outputs':outputs}
    (ROOT/'evidence/local-pipeline-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    delivery=ROOT/'交付/本地AI技术验证';delivery.mkdir(parents=True,exist_ok=True)
    for goal,item in outputs.items():
        jid=item['video'].split('/')[2]
        shutil.copy2(DATA/jid/'result.mp4',delivery/f'{goal}-模拟技术样片.mp4')
        shutil.copy2(DATA/jid/'report.json',delivery/f'{goal}-报告.json')
    print(json.dumps({'goals':list(outputs),'overlong_refused':True,'delivery':str(delivery)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
