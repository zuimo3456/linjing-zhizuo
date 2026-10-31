"""Actual regression for all six third-audit findings. UI checks are separate."""
from pathlib import Path
import copy,json,shutil,sys,time,urllib.parse
import verify_second_audit_fixes as h
from media import ROOT,DATA,FFMPEG,run,ANALYSIS_VERSION
from demo import create_demo
OUT=ROOT/'evidence/fixes3-2026-10-31';OUT.mkdir(exist_ok=True);h.OUT=OUT
ONLY=sys.argv[sys.argv.index('--only')+1] if '--only' in sys.argv else None
records=json.loads((OUT/'results.json').read_text(encoding='utf8'))['cases'] if ONLY and (OUT/'results.json').exists() else []
def save():
    (OUT/'results.json').write_text(json.dumps({'date':'2026-10-31','scope':'Actual local API/model/video checks, not merchant accuracy. HDR is explicitly rejected, not tone-mapped.','passed':sum(c['passed'] for c in records),'total':len(records),'cases':records},ensure_ascii=False,indent=2),encoding='utf8')
def case(cid,fn):
    if ONLY and cid!=ONLY:return
    records[:]=[r for r in records if r['id']!=cid];begun=time.perf_counter()
    try:r=fn();passed=True
    except Exception as e:r={'error':type(e).__name__,'message':str(e)};passed=False
    records.append({'id':cid,'passed':passed,'elapsed_seconds':round(time.perf_counter()-begun,3),'result':r});save();print(cid,passed,json.dumps(r,ensure_ascii=False)[:950],flush=True)
def upload(path):return h.done(h.api('/api/upload?name='+urllib.parse.quote(path.name),raw=path.read_bytes()))
def snapshot(r,at,name):run([FFMPEG,'-y','-v','error','-ss',at,'-i',DATA/r['video'].split('/')[2]/'result.mp4','-frames:v','1',OUT/name])
def save_project(name,p):(OUT/name).write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':
    saved=DATA/'saved-project.json';backup=DATA/'backups/saved-project-before-third-fixes-20261031.json';backup.parent.mkdir(exist_ok=True)
    if saved.exists() and not backup.exists():shutil.copy2(saved,backup)
    h.base=base=create_demo()
    def text():
        p=copy.deepcopy(base);next(f for f in p['facts'] if f['kind']=='product')['value']='手冲\rA1咖啡'
        s=next(s for s in p['shots'] if 'product' in s['tags']);h.confirm(p,s,'product');pl,r=h.render(p)
        text=next(s['text'] for s in pl['segments'] if s['role']=='product');assert '手冲 A1咖啡' in text and '\r' not in text
        from media import write_ass
        path=OUT/'carriage-return-fixed.ass';write_ass(path,text,5,False)
        assert 'A1' in path.read_text(encoding='utf-8-sig');h.product_frame(r,'carriage-return-fixed.jpg');save_project('text-project.json',p)
        return {'copy':text,'video':r['video'],'raw_fact_preserved':next(f['value'] for f in p['facts'] if f['kind']=='product')}
    case('T07_text',text)
    def session():
        p=copy.deepcopy(base);pl=h.plan(p);pl['segments'][0],pl['segments'][1]=pl['segments'][1],pl['segments'][0]
        code,checked=h.api('/api/validate',{'project':p,'plan':pl});assert code==200,checked;pl=checked['plan']
        code,packed=h.api('/api/export-project',{'project':p,'plan':pl,'method':'evidence'});assert code==200,packed
        code,out=h.api('/api/reconcile',{'project':packed});assert code==200 and out['saved_edit']['plan']['segments']==pl['segments'],out
        save_project('custom-order-session.json',packed)
        tampered=copy.deepcopy(packed);next(f for f in tampered['facts'] if f['kind']=='product')['value']='变更商品'
        code,invalid=h.api('/api/reconcile',{'project':tampered});assert code==200 and 'saved_edit' not in invalid and invalid['warnings']
        return {'order':[s['role'] for s in pl['segments']],'roundtrip_preserved':True,'changed_product_invalidates_plan':True,'warnings':invalid['warnings']}
    case('T10_session',session)
    def semantic():
        asset=upload(DATA/'audit3-fixtures/A3_dissolve_cat.mp4');p=h.with_asset(asset,'product');old_plan=h.plan(p)
        analyzed=h.done(h.api('/api/local-analyze',{'project':p}));s=next(s for s in analyzed['shots'] if s['media_id']==asset['id'])
        assert s['local_candidate']['abstained'] and s.get('semantic_issue'),s.get('local_candidate')
        attempted=copy.deepcopy(p);bad=next(s for s in attempted['shots'] if s['media_id']==asset['id']);bad['semantic_issue']=None;bad.pop('local_candidate',None)
        code,blocked=h.api('/api/confirm-shot',{'project':attempted,'shot_id':bad['id'],'mode':'purpose','checked':True});assert code==400,blocked
        stale=h.api('/api/render',{'project':p,'plan':old_plan});assert stale[0]==400,stale
        clean=upload(DATA/'audit3-fixtures/A3_01_plain.mp4');p['shots'].extend(copy.deepcopy(clean['shots']))
        for item in list(p['shots']):
            if item['media_id']==clean['id']:h.confirm(p,item,'product')
        pl,r=h.render(p);selected={c['shot_id'] for seg in pl['segments'] for c in seg.get('clips',[seg])};assert bad['id'] not in selected
        save_project('semantic-risk-project.json',analyzed);save_project('semantic-fallback-project.json',p)
        h.product_frame(r,'semantic-clean-fallback.jpg')
        return {'risk':s['semantic_issue'],'frames':len(s['frames']),'sample_times':[f['time'] for f in s['frames']],
                'candidate':s['local_candidate'],'confirmation_http':code,'stale_render_http':stale[0],'clean_alternative_video':r['video']}
    case('T02_semantic',semantic)
    def hdr():
        code,initial=h.api('/api/upload?name=A3_HDR_PQ.mp4',raw=(DATA/'audit3-fixtures/A3_HDR_PQ.mp4').read_bytes());assert code==202
        for _ in range(500):
            _,job=h.api('/api/jobs/'+initial['job_id'])
            if job['status'] in ('done','error'):break
            time.sleep(.1)
        assert job['status']=='error' and 'HDR' in job['message'] and 'SDR' in job['message'],job
        historical=json.loads((ROOT/'evidence/audit3-2026-10-31/results.json').read_text(encoding='utf8'))
        hdr_id=next(c['result']['asset']['id'] for c in historical['cases'] if c['id']=='T08')
        legacy=json.loads((DATA/hdr_id/'asset.json').read_text(encoding='utf8'));p=copy.deepcopy(base)
        p['shots']=[s for s in p['shots'] if 'product' not in s['tags']]+legacy['shots']
        status,restored=h.api('/api/reconcile',{'project':p});assert status==200
        legacy_issue=next(s['unavailable'] for s in restored['shots'] if s['media_id']==hdr_id);assert 'HDR' in legacy_issue and 'SDR' in legacy_issue
        normal=upload(DATA/'audit3-fixtures/A3_01_plain.mp4');pl,r=h.render(h.with_asset(normal,'product'))
        return {'HDR_rejected':True,'message':job['message'],'legacy_HDR_message':legacy_issue,'SDR_positive_video':r['video'],'automatic_tone_mapping':False}
    case('T08_HDR',hdr)
    def shorts():
        first=upload(DATA/'audit3-fixtures/A3_two_seconds.mp4')
        second_path=DATA/'audit3-fixtures/THIRD_FIX_short_B.mp4'
        if not second_path.exists():run([FFMPEG,'-y','-v','error','-i',DATA/'audit3-fixtures/A3_two_seconds.mp4','-vf','hflip','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',second_path])
        second=upload(second_path);p=h.with_asset(first,'product');p['shots'].extend(copy.deepcopy(second['shots']))
        for item in list(p['shots']):
            if item['media_id']==second['id']:h.confirm(p,item,'product')
        pl,r=h.render(p);group=next(s for s in pl['segments'] if s['role']=='product');assert len(group.get('clips',[]))==2,pl
        timing=next(t for t in r['metrics']['timings'] if '带你看看' in t['text']);assert len(timing['visual_clips'])==2
        assert abs(timing['end']-timing['start']-4)<.001;assert sum('带你看看' in t['text'] for t in r['metrics']['timings'])==1
        snapshot(r,timing['start']+.5,'short-group-A.jpg');snapshot(r,timing['start']+2.5,'short-group-B.jpg');save_project('short-group-project.json',p)
        packed=h.api('/api/export-project',{'project':p,'plan':pl,'method':'evidence'});assert packed[0]==200;save_project('short-group-session.json',packed[1])
        broken=copy.deepcopy(p);next(s for s in broken['shots'] if s['id']==group['clips'][1]['shot_id'])['confirmed']=False
        invalid=h.api('/api/render',{'project':broken,'plan':pl});assert invalid[0]==400
        duplicate=copy.deepcopy(pl);g=next(s for s in duplicate['segments'] if s['role']=='product');g['clips'][1]=copy.deepcopy(g['clips'][0])
        repeat=h.api('/api/validate',{'project':p,'plan':duplicate});assert repeat[0]==400
        return {'group':group,'timing':timing,'video':r['video'],'metadata':r['metrics']['metadata'],'second_unconfirmed_http':invalid[0],'repeated_clip_http':repeat[0]}
    case('T06_short_group',shorts)
    def fade():
        asset=upload(DATA/'audit2-fixtures/AUDIT2_fade.mp4');p=h.with_asset(asset,'product')
        analyzed=h.done(h.api('/api/local-analyze',{'project':p}));good=[s for s in analyzed['shots'] if s['media_id']==asset['id'] and not s['quality_issues']]
        assert good and all(not s.get('semantic_issue') for s in good),good
        for item in list(analyzed['shots']):
            if not item['quality_issues']:h.confirm(analyzed,item,next(iter(item['tags'])))
        pl,r=h.render(analyzed)
        return {'recovered_good_ranges':[[s['start'],s['end']] for s in good],'not_falsely_semantic_blocked':True,'video':r['video']}
    case('normal_fade_and_AI',fade)
    if not all(c['passed'] for c in records):sys.exit(1)
