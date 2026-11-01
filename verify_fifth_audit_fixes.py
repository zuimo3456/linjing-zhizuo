"""Audit-5 fixes: actual local API/media checks; historical evidence is read only."""
from pathlib import Path
import copy,json,sys,time,urllib.parse,wave
import numpy as np
from PIL import Image
from verify_fourth_audit_fixes import api,done
from media import ROOT,DATA,FFMPEG,run,probe
from demo import create_demo

OUT=ROOT/'evidence/fixes5-2026-11-01';OUT.mkdir(exist_ok=True)
FIX=DATA/'fixes5-fixtures';FIX.mkdir(exist_ok=True)
ONLY=sys.argv[sys.argv.index('--only')+1] if '--only' in sys.argv else None
records=json.loads((OUT/'results.json').read_text(encoding='utf8'))['cases'] if ONLY and (OUT/'results.json').exists() else []
def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def load(name):return json.loads((ROOT/name).read_text(encoding='utf8'))
def case(name,fn):
    if ONLY and name!=ONLY:return
    records[:]=[r for r in records if r['id']!=name]
    begun=time.perf_counter()
    try:r=fn();passed=True
    except Exception as e:r={'exception':type(e).__name__,'message':str(e)};passed=False
    records.append({'id':name,'passed':passed,'seconds':round(time.perf_counter()-begun,3),'result':r})
    save('results.json',{'date':'2026-11-01','scope':'Original/authorized technical fixtures; human listening and merchant acceptance pending.','passed':sum(r['passed'] for r in records),'total':len(records),'cases':records})
    print(name,passed,json.dumps(r,ensure_ascii=False)[:850],flush=True)
def upload(path):return done(api('/api/upload?name='+urllib.parse.quote(path.name),raw=path.read_bytes()))
def confirm_all(p):
    for shot in list(p['shots']):
        if shot.get('quality_issues') or shot.get('semantic_issue') or shot.get('unavailable') or shot['tags']==['other']:continue
        index=next(i for i,s in enumerate(p['shots']) if s['id']==shot['id'])
        for mode in (['purpose','product'] if 'product' in shot['tags'] else ['purpose']):
            code,out=api('/api/confirm-shot',{'project':p,'shot_id':shot['id'],'mode':mode,'checked':True});assert code==200,out;p['shots'][index]=out['shot']
    return p
def refreshed(p):
    code,out=api('/api/reconcile',{'project':p});assert code==200,out
    out.pop('saved_edit',None);return confirm_all(out)
def with_asset(a,role,goal='visit'):
    p=copy.deepcopy(base);p['goal']=goal;p['shots']=[s for s in p['shots'] if role not in s['tags']]+copy.deepcopy(a['shots'])
    for s in p['shots']:
        if s['media_id']==a['id']:s['tags']=[role]
    return confirm_all(p)
def plan(p,method='evidence'):
    code,pl=api('/api/plan',{'project':p,'method':method});assert code==200,pl
    return pl
def render(p,pl):return done(api('/api/render',{'project':p,'plan':pl}))
def export(name,p,pl,method='evidence'):
    code,out=api('/api/export-project',{'project':p,'plan':pl,'method':method});assert code==200,out;save(name,out)
def frame(path,at,name):run([FFMPEG,'-y','-v','error','-ss',at,'-i',path,'-frames:v','1',OUT/name])
def banner_distance(a,b):
    with Image.open(a) as im:x=np.asarray(im.convert('L').resize((202,360)),dtype=float)[272:301,8:194]
    with Image.open(b) as im:y=np.asarray(im.convert('L').resize((202,360)),dtype=float)[272:301,8:194]
    return float(np.abs(x-y).mean())

if __name__=='__main__':
    base=create_demo()
    def price_block():
        raw=load('evidence/audit5-2026-10-31/direction-control-project.json')
        code,error=api('/api/plan',{'project':raw});assert code==400 and '隐藏方向' in error['error']
        code,p=api('/api/reconcile',{'project':raw});assert code==200,p
        f=next(f for f in p['facts'] if f['kind']=='offer');assert not f['confirmed'] and f['original_value']=='单杯\u202e19\u202c元' and '[U+202E]' in f['value']
        forged=copy.deepcopy(p);next(f for f in forged['facts'] if f['kind']=='offer')['confirmed']=True
        bad,err=api('/api/plan',{'project':forged});assert bad==400 and '重新填写' in err['error']
        save('quarantined-price-project.json',p)
        return {'raw_input_http':400,'message':error['error'],'imported_draft':f,'forged_confirmation_http':bad}
    case('price_quarantine',price_block)
    def price_retype():
        p=load('evidence/fixes5-2026-11-01/quarantined-price-project.json');f=next(f for f in p['facts'] if f['kind']=='offer');f.update(value='单杯91元',confirmed=True)
        p=refreshed(p);pl=plan(p);assert pl['renderable'] and '单杯91元' in pl['segments'][0]['text'],pl
        r=render(p,pl);cue=next(c for c in r['metrics']['timings'][0]['captions'] if '91' in c['text'])
        frame(DATA/r['video'].split('/')[2]/'result.mp4',(cue['start']+cue['end'])/2,'price91-fixed.jpg');export('price91-session.json',p,pl)
        return {'copy':pl['segments'][0]['text'],'raw_preserved':f['original_value'],'video':r['video']}
    case('price_retyped_confirmed',price_retype)
    def delayed():
        a=upload(DATA/'audit5-fixtures/counter-video-delay2.mp4');save('delayed-asset.json',a);s=a['shots'][0]
        assert (s['start'],s['end'],s['review_start'],s['review_end'])==(2,8,0,6) and not s['quality_issues'] and not a['coverage']['truncated'],a
        f=next(f for f in s['frames'] if f['time']==3);image=DATA/a['id']/f['url'].rsplit('/',1)[1]
        import shutil
        shutil.copy2(image,OUT/'evidence-source-time3.jpg')
        frame(DATA/a['id']/'source.mp4',3,'original-time3.jpg');frame(DATA/a['id']/'source.mp4',5,'original-time5-negative.jpg');frame(DATA/a['id']/'review.mp4',1,'review-time1.jpg')
        correct=banner_distance(image,OUT/'original-time3.jpg');wrong=banner_distance(image,OUT/'original-time5-negative.jpg')
        assert correct<wrong,{'correct':correct,'wrong':wrong}
        p=with_asset(a,'process','attract');pl=plan(p);assert pl['renderable'],pl;r=render(p,pl)
        t=next(t for t in r['metrics']['timings'] if t['text']=='这是制作过程。');assert abs(t['end']-t['start']-6)<.001
        frame(DATA/r['video'].split('/')[2]/'result.mp4',t['start']+.3,'output-counter-start.jpg');frame(DATA/r['video'].split('/')[2]/'result.mp4',t['start']+5.3,'output-counter-end.jpg')
        export('delayed-counter-session.json',p,pl);save('delayed-render.json',r)
        return {'range':[s['start'],s['end']],'review_range':[s['review_start'],s['review_end']],'frames':len(s['frames']),'mapping':a['review_mapping'],'distance_to_correct_time':correct,'distance_to_wrong_time':wrong,'video':r['video'],'metadata':r['metrics']['metadata']}
    case('timeline_delayed_video',delayed)
    def absolute_offset():
        target=FIX/'counter-all-shifted7.mp4'
        if not target.exists():run([FFMPEG,'-y','-v','error','-i',DATA/'audit5-fixtures/counter-plain.mp4','-c','copy','-output_ts_offset','7',target])
        a=upload(target);save('shared-offset-asset.json',a);assert a['meta']['video_offset']==0 and a['meta']['video_duration']==6,a['meta']
        assert not a['shots'][0]['quality_issues'] and a['shots'][0]['start']==0
        p=with_asset(a,'process','attract');pl=plan(p);r=render(p,pl);t=next(t for t in r['metrics']['timings'] if t['text']=='这是制作过程。')
        frame(DATA/r['video'].split('/')[2]/'result.mp4',t['start']+.3,'shared-offset-output-start.jpg');frame(DATA/r['video'].split('/')[2]/'result.mp4',t['start']+5.3,'shared-offset-output-end.jpg')
        return {'metadata':a['meta'],'video':r['video']}
    case('timeline_shared_absolute_shift',absolute_offset)
    def late_audio():
        target=FIX/'counter-audio-late2.mp4'
        if not target.exists():run([FFMPEG,'-y','-v','error','-i',DATA/'audit5-fixtures/counter-plain.mp4','-itsoffset','2','-f','lavfi','-i','sine=frequency=300:duration=4','-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-t','6',target])
        a=upload(target);assert not a['shots'][0]['quality_issues'];wav=FIX/'late-audio-review.wav'
        run([FFMPEG,'-y','-v','error','-i',DATA/a['id']/'review.mp4','-vn','-ar','16000','-ac','1','-c:a','pcm_s16le',wav])
        with wave.open(str(wav),'rb') as source:x=np.frombuffer(source.readframes(source.getnframes()),dtype='<i2').astype(float)
        first=float(np.sqrt(np.mean(x[:24000]**2)));later=float(np.sqrt(np.mean(x[48000:64000]**2)))
        assert first<2 and later>1000,{'first':first,'later':later}
        return {'metadata':a['meta'],'early_audio_rms':first,'later_audio_rms':later,'review':a['review_url']}
    case('timeline_late_audio_preserved',late_audio)
    def skipped_middle():
        p=refreshed(load('evidence/audit5-2026-10-31/interrupted-project.json'));pl=plan(p,'chronological');assert pl['renderable'],pl
        group=pl['segments'][-1];assert len(group['clips'])==2 and sum(c['end']-c['start'] for c in group['clips'])==16
        short=next(s['id'] for s in p['shots'] if s['end']-s['start']==1);assert short not in [c['shot_id'] for c in group['clips']]
        r=render(p,pl);export('non-adjacent-session.json',p,pl,'chronological');save('non-adjacent-render.json',r)
        return {'group':group,'search':pl['assignment'],'video':r['video'],'metadata':r['metrics']['metadata']}
    case('non_adjacent_combo',skipped_middle)
    def rejection_guards():
        p=refreshed(load('evidence/audit5-2026-10-31/long-offer-project.json'));pl=plan(p);assert not pl['renderable'] and '17.3秒' in ''.join(pl['missing']) and '16.0秒' in ''.join(pl['missing'])
        risky=load('evidence/fixes3-2026-10-31/semantic-risk-project.json');code,risky=api('/api/reconcile',{'project':risky});assert code==200
        s=next(s for s in risky['shots'] if s.get('semantic_issue'));s.pop('semantic_issue',None)
        code,err=api('/api/confirm-shot',{'project':risky,'shot_id':s['id'],'mode':'purpose','checked':True});assert code==400 and '风险' in err['error']
        risk_id=s['id'];analyzed=done(api('/api/local-analyze',{'project':risky}))
        reviewed=next(item for item in analyzed['shots'] if item['id']==risk_id)
        assert reviewed.get('analysis_version')==7 and reviewed.get('semantic_issue') and analyzed['vision_analysis']['remote_requests']==0
        save('old-risk-after-upgrade.json',risky)
        p=load('evidence/fixes5-2026-11-01/non-adjacent-session.json');p.pop('saved_edit',None)
        next(s for s in reversed(p['shots']) if 'product' in s['tags'])['confirmed']=False
        assert not plan(p,'chronological')['renderable']
        return {'long_conditions_still_rejected':True,'unconfirmed_required_source_still_rejected':True,'known_source_risk_still_blocked':code,'message':err['error']}
    case('existing_rejections',rejection_guards)
    def legacy():
        old=load('evidence/fixes4-2026-10-31/eight-session.json');code,p=api('/api/reconcile',{'project':old});assert code==200
        assert 'saved_edit' not in p and all(s['analysis_version']==7 and not s['confirmed'] for s in p['shots'])
        assert p['facts']==old['facts'];save('legacy-upgraded-project.json',p)
        return {'facts_preserved':True,'old_confirmations_revoked':True,'old_plan_invalidated':True,'warnings':p['warnings']}
    case('legacy_upgrade',legacy)
    def compatibility():
        a=upload(DATA/'audit3-fixtures/A3_vfr.mp4');p=with_asset(a,'product');pl=plan(p);assert pl['renderable'];r=render(p,pl)
        code,j=api('/api/upload?name=HDR_PQ.mp4',raw=(DATA/'audit3-fixtures/A3_HDR_PQ.mp4').read_bytes());assert code==202
        for _ in range(500):
            _,job=api('/api/jobs/'+j['job_id'])
            if job['status'] in ('done','error'):break
            time.sleep(.1)
        assert job['status']=='error' and 'HDR' in job['message'] and 'SDR' in job['message']
        return {'VFR_video':r['video'],'VFR_metadata':a['meta'],'HDR_still_rejected':job['message']}
    case('format_regression',compatibility)
    if not all(c['passed'] for c in records):raise SystemExit(1)
