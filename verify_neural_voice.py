"""Actual local narration and video checks; never writes the user's saved project."""
import copy,hashlib,json,shutil,sys,time,urllib.error,urllib.request
from pathlib import Path
from audio import prepare_voice,duration,run,FFMPEG
from qwen_voice import PROFILE_ID,PROFILE,status
from media import DATA,probe

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'evidence/voice-2026-11-02';OUT.mkdir(parents=True,exist_ok=True)
DELIVERY=ROOT/'交付/开源活泼女声';DELIVERY.mkdir(parents=True,exist_ok=True)
PORT=int(sys.argv[sys.argv.index('--port')+1]) if '--port' in sys.argv else 4180
def save(name,obj):(OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
def api(path,obj=None):
    request=urllib.request.Request(f'http://127.0.0.1:{PORT}'+path,
        data=None if obj is None else json.dumps(obj,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=900) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as exc:return exc.code,json.load(exc)
def main():
    samples=[('01-活泼女声试听','欢迎来到街角咖啡！手冲咖啡，陪你开启元气满满的一天。'),
             ('02-价格日期试听','单杯19元，每人限购一杯。活动时间：2026年11月2日至11月8日。'),
             ('03-地址条件试听','地址是学院路99号，A1室。参与前，请核对活动条件。')]
    records=[]
    for name,text in samples:
        begun=time.perf_counter();wav,seconds,cues=prepare_voice(text);elapsed=time.perf_counter()-begun
        target=DELIVERY/(name+'.wav');shutil.copyfile(wav,target)
        assert 0<seconds<40 and cues and max(c['end'] for c in cues)<=seconds+.0001
        assert all(0<=c['start']<c['end'] for c in cues)
        begun=time.perf_counter();again=prepare_voice(text);cached=time.perf_counter()-begun
        assert again[0]==wav and again[1:]==(seconds,cues)
        records.append({'name':name,'text':text,'seconds':seconds,'generation_seconds':round(elapsed,3),
                        'cached_seconds':round(cached,4),'cues':cues,'audio':str(target),'human_listening':'pending'})
        save('samples.json',{'voice':PROFILE,'samples':records});print(name,records[-1]['seconds'],records[-1]['generation_seconds'],flush=True)
    if '--samples-only' in sys.argv:return
    code,health=api('/api/health');assert code==200 and health['voice']['profile_id']==PROFILE_ID,health
    saved=DATA/'saved-project.json';before=(hashlib.sha256(saved.read_bytes()).hexdigest(),saved.stat().st_mtime_ns)
    project=json.loads((ROOT/'evidence/fixes5-2026-11-01/non-adjacent-session.json').read_text(encoding='utf8'))
    old=project.pop('saved_edit')['plan'];code,response=api('/api/validate',{'project':project,'plan':old})
    assert code==400 and '配音已更换' in response['error'],response
    # Keep this synthetic fixture in its already explicit Nov 2026 promotion window.
    code,plan=api('/api/plan',{'project':project,'method':'chronological'});assert code==200 and plan['renderable'],plan
    assert plan['voice_profile']==PROFILE_ID
    code,validated=api('/api/validate',{'project':project,'plan':plan});assert code==200,validated
    code,pending=api('/api/render',{'project':project,'plan':plan});assert code==202,pending
    deadline=time.monotonic()+900
    while time.monotonic()<deadline:
        code,item=api('/api/jobs/'+pending['job_id']);assert code==200,item
        if item['status']=='done':result=item['result'];break
        if item['status']=='error':raise AssertionError(item['message'])
        time.sleep(1)
    else:raise TimeoutError('video job timed out')
    assert result['metrics']['voice']['profile_id']==PROFILE_ID
    assert result['metrics']['metadata']['audio'] and result['metrics']['metadata']['duration']<=45.1
    for timing in result['metrics']['timings']:
        assert timing['voice_speed']<=1.18
        assert max(c['end'] for c in timing['captions'])<=timing['end']-timing['start']+.02
    final=DATA/result['video'].split('/')[2]
    shutil.copyfile(final/'result.mp4',DELIVERY/'Vivian女声-模拟技术样片.mp4')
    shutil.copyfile(final/'report.json',DELIVERY/'运行报告.json')
    code,session=api('/api/export-project',{'project':project,'plan':plan,'method':'chronological'});assert code==200,session
    (DELIVERY/'模拟样片-可恢复项目.json').write_text(json.dumps(session,ensure_ascii=False,indent=2),encoding='utf8')
    assert before==(hashlib.sha256(saved.read_bytes()).hexdigest(),saved.stat().st_mtime_ns)
    save('render.json',result);save('plan.json',plan);save('session.json',session)
    save('results.json',{'date':'2026-11-02','voice':PROFILE,'samples':records,'old_plan_rejected':True,
                         'current_plan_valid':True,'actual_render_complete':True,'saved_project_unchanged':True,
                         'video':result['video'],'metadata':result['metrics']['metadata'],'human_listening':'pending'})
    print('VIDEO',result['video'],flush=True)

if __name__=='__main__':main()
