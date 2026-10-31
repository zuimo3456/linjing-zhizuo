"""Actual API/media regression for audit defects. Browser races are verified separately."""
from pathlib import Path
import copy,json,time,uuid,urllib.request,urllib.error,sys
from demo import create_demo
from media import DATA,ROOT,FFMPEG,run,analyze,ANALYSIS_VERSION

OUT=ROOT/(sys.argv[sys.argv.index('--out')+1] if '--out' in sys.argv else 'evidence/fixes-2026-10-30');OUT.mkdir(parents=True,exist_ok=True)
ONLY=sys.argv[sys.argv.index('--only')+1] if '--only' in sys.argv else None
records=json.loads((OUT/'results.json').read_text(encoding='utf8'))['cases'] if ONLY and (OUT/'results.json').exists() else []
def save():
    (OUT/'results.json').write_text(json.dumps({'date':'2026-10-30','scope':'Technical fixtures, not merchant efficacy','cases':records},ensure_ascii=False,indent=2),encoding='utf8')
def api(path,obj=None,raw=None):
    data=raw if raw is not None else (json.dumps(obj,ensure_ascii=False).encode('utf8') if obj is not None else None)
    req=urllib.request.Request('http://127.0.0.1:4180'+path,data=data,headers={'Content-Type':'application/octet-stream' if raw is not None else 'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=90) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
def job(initial):
    code,obj=initial
    assert code==202,(code,obj)
    for _ in range(800):
        _,j=api('/api/jobs/'+obj['job_id'])
        if j['status'] in ('done','error'):return j
        time.sleep(.1)
    raise AssertionError('Job timeout')
def check(cid,fn):
    if ONLY and cid!=ONLY:return
    records[:]=[r for r in records if r['id']!=cid]
    try:
        result=fn();records.append({'id':cid,'passed':True,'evidence':result});print(cid,'PASS',str(result)[:500],flush=True)
    except Exception as e:
        records.append({'id':cid,'passed':False,'error':str(e)});print(cid,'FAIL',str(e),flush=True)
    save()
def plan(p):
    code,value=api('/api/plan',{'project':p});assert code==200,value;return value
def render(p,pl):
    done=job(api('/api/render',{'project':p,'plan':pl}));assert done['status']=='done',done
    return done['result']
def refreshed(mid):
    folder=DATA/mid;cache=folder/'asset.json';old=json.loads(cache.read_text(encoding='utf8'))
    if old.get('analysis_version')==ANALYSIS_VERSION:return old
    result=analyze(folder/'source.mp4',mid,old['name']);cache.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result
def fixture(name,args):
    for meta in DATA.glob('*/asset.json'):
        item=json.loads(meta.read_text(encoding='utf8'))
        if item.get('name')==name:return refreshed(item['id'])
    mid=uuid.uuid4().hex;folder=DATA/mid;folder.mkdir()
    run([FFMPEG,'-y','-v','error',*args,'-c:v','libx264','-preset','ultrafast','-threads','2','-pix_fmt','yuv420p',folder/'source.mp4'])
    item=analyze(folder/'source.mp4',mid,name);(folder/'asset.json').write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf8');return item
def add_confirmed(p,asset,role,index=0):
    s=copy.deepcopy(asset['shots'][index]);s.update(tags=[role],confirmed=False)
    p['shots'].append(s);pos=len(p['shots'])-1
    for mode in (['purpose','product'] if role=='product' else ['purpose']):
        code,res=api('/api/confirm-shot',{'project':p,'shot_id':s['id'],'mode':mode,'checked':True})
        assert code==200,res;p['shots'][pos]=res['shot']
    return p['shots'][pos]

if __name__=='__main__':
    base=create_demo();old=json.loads((ROOT/'evidence/audit-2026-10-30/results.json').read_text(encoding='utf8'))
    oldby={c['id']:c['result'] for c in old['cases']}
    def normal():
        pl=plan(base);assert pl['renderable'],pl['missing'];r=render(base,pl)
        (OUT/'normal-report.json').write_text(json.dumps(r['metrics'],ensure_ascii=False,indent=2),encoding='utf8')
        return {'video':r['video'],'duration':r['metrics']['metadata']['duration']}
    check('normal_valid_signed_render',normal)
    def binding():
        p=copy.deepcopy(base);catmid=oldby['C16']['segments'][1]['shot_id']
        saved=json.loads((ROOT/'evidence/audit-2026-10-30/source-rebound-project.json').read_text(encoding='utf8'))
        next(s for s in p['shots'] if 'product' in s['tags'])['media_id']=next(s for s in saved['shots'] if 'product' in s['tags'])['media_id']
        pl=plan(p);assert not pl['renderable'];code,res=api('/api/render',{'project':p,'plan':plan(base)})
        assert code==400;return {'plan_ready':False,'render_status':code,'message':res['error']}
    check('D01_source_rebind_blocked',binding)
    def dates():
        messages=[]
        for text in ('2020年1月1日至2日','2099年5月10日至2099年5月1日','长期有效'):
            p=copy.deepcopy(base);p['goal']='promo';next(f for f in p['facts'] if f['kind']=='validity')['value']=text
            pl=plan(p);assert not pl['renderable'];messages.append(pl['missing'])
        return messages
    check('D02_expired_reverse_unknown_dates',dates)
    def timing():
        p=copy.deepcopy(base);product=next(s for s in p['shots'] if 'product' in s['tags'])
        png=DATA/product['media_id']/'illustration.png';p['shots'].remove(product)
        short=fixture('FIX_1秒清晰商品',['-loop','1','-i',str(png),'-t','1','-r','25'])
        long=fixture('FIX_8秒可辨商品',['-loop','1','-i',str(png),'-vf','gblur=sigma=4','-t','8','-r','25'])
        ss=add_confirmed(p,short,'product');ls=add_confirmed(p,long,'product')
        assert ss['quality']>ls['quality'],(ss['quality'],ls['quality'])
        pl=plan(p);assert pl['renderable'],pl['missing'];chosen=next(s for s in pl['segments'] if s['role']=='product')
        assert chosen['shot_id']==ls['id'];r=render(p,pl)
        return {'short_quality':ss['quality'],'long_quality':ls['quality'],'selected':chosen,'video':r['video']}
    check('D05_feasible_long_candidate_selected',timing)
    def coverage():
        asset=refreshed(oldby['C21']['media_id'])
        assert len(asset['shots'])>=30;assert abs(asset['coverage']['analyzed_end']-45)<.1
        assert not asset['coverage']['truncated'];return {'shots':len(asset['shots']),'coverage':asset['coverage']}
    check('D06_all_thirty_scenes_covered',coverage)
    def flash():
        asset=refreshed(oldby['C22']['media_id'])
        suspect=[s for s in asset['shots'] if s['start']<2.7 and s['end']>2.5]
        assert suspect and any(s.get('quality_issues') for s in suspect)
        from local_vision import analyze_project
        p=copy.deepcopy(base);p['shots']=[s for s in p['shots'] if 'product' not in s['tags']]+asset['shots']
        result=analyze_project(p,print)
        marked=[s for s in result['shots'] if s['id'] in {x['id'] for x in suspect}]
        assert all(s['local_candidate']['abstained'] for s in marked)
        return {'intervals':[[s['start'],s['end']] for s in asset['shots']],'suspect':[{'id':s['id'],'issues':s['quality_issues'],'candidate':s['local_candidate']['tags']} for s in marked]}
    check('D07_boundary_flash_not_accepted',flash)
    def gray():
        p=json.loads((ROOT/'evidence/audit-2026-10-30/blank-frame-project.json').read_text(encoding='utf8'))
        shot=next(s for s in p['shots'] if 'product' in s['tags']);asset=refreshed(shot['media_id'])
        code,res=api('/api/confirm-shot',{'project':p,'shot_id':shot['id'],'mode':'purpose','checked':True})
        assert code==400;assert asset['shots'][0]['quality']<.25;assert not plan(p)['renderable']
        return {'quality':asset['shots'][0]['quality'],'issues':asset['shots'][0]['quality_issues'],'confirmation_error':res['error']}
    check('D08_gray_source_independently_rejected',gray)
    def preflight():
        p=copy.deepcopy(base);p['goal']='promo';pl=plan(p)
        assert not pl['renderable'];assert any('旁白' in x for x in pl['missing'])
        return {'ready':pl['renderable'],'missing':pl['missing']}
    check('D09_speech_too_long_rejected_before_render',preflight)
    def unused():
        p=copy.deepcopy(base);p['shots'].append({'id':'unused','media_id':'f'*32,'start':0.,'end':6.,'quality':.5,'tags':['other'],'confirmed':False})
        pl=plan(p);assert pl['renderable'],pl['missing'];r=render(p,pl)
        return {'warning':pl['warnings'],'video':r['video']}
    check('D10_unused_missing_source_no_longer_blocks',unused)
    def process():
        p=copy.deepcopy(base);p['goal']='attract';pl=plan(p);assert pl['renderable'];r=render(p,pl)
        for seg,t in zip(r['metrics']['plan']['segments'],r['metrics']['timings']):
            if seg['role']=='process':
                actual=t['end']-t['start'];expected=seg['end']-seg['start'];assert abs(actual-expected)<.02
                return {'source_seconds':expected,'render_seconds':actual,'video':r['video']}
        raise AssertionError('No process segment')
    check('D11_complete_process_interval_preserved',process)
    def bad_file():
        done=job(api('/api/upload?name=FIX_broken.mp4',raw=b'not a real mp4'))
        assert done['status']=='error';msg=done['message'];assert '重新导出' in msg and 'moov' not in msg and 'D:\\' not in msg
        return msg
    check('D12_friendly_corrupt_upload_message',bad_file)
    def blank():
        p=copy.deepcopy(base);p['facts']=[];p['shots']=[];pl=plan(p);assert not pl['renderable'];return pl['missing']
    check('empty_project_remains_actionable',blank)
    def migrate():
        p=copy.deepcopy(base)
        for s in p['shots']:s['analysis_version']=2
        code,res=api('/api/reconcile',{'project':p});assert code==200,res
        assert res['facts']==p['facts'];assert not any(s['confirmed'] for s in res['shots'])
        assert not any(s.get('product_binding') for s in res['shots'])
        return {'facts_preserved':True,'confirmations_revoked':True,'shots':len(res['shots']),'warnings':res['warnings']}
    check('migration_preserves_facts_revokes_old_confirmation',migrate)
    def expand_legacy():
        asset=refreshed(oldby['C21']['media_id']);p=copy.deepcopy(base);p['shots']=copy.deepcopy(asset['shots'][:24])
        for s in p['shots']:s['analysis_version']=2
        code,res=api('/api/reconcile',{'project':p});assert code==200,res
        assert len(res['shots'])==30;assert max(s['end'] for s in res['shots'])==45
        return {'before':24,'after':len(res['shots']),'covered_end':45}
    check('migration_restores_legacy_tail_coverage',expand_legacy)
    def browser_numbers():
        p=copy.deepcopy(base)
        for s in p['shots']:
            for k in ('start','end'):
                if float(s[k]).is_integer():s[k]=int(s[k])
        pl=plan(p);assert pl['renderable'],pl['missing']
        return {'ready_after_browser_number_roundtrip':True}
    check('browser_number_roundtrip_keeps_confirmation',browser_numbers)
    def valid_promo():
        p=copy.deepcopy(base);p['goal']='promo';p['shots']=[s for s in p['shots'] if 'product' not in s['tags']]
        product=next(s for s in base['shots'] if 'product' in s['tags']);png=DATA/product['media_id']/'illustration.png'
        asset=fixture('FIX_8秒可辨商品',['-loop','1','-i',str(png),'-vf','gblur=sigma=4','-t','8','-r','25'])
        add_confirmed(p,asset,'product');pl=plan(p);assert pl['renderable'],pl['missing'];r=render(p,pl)
        return {'validity':next(f['value'] for f in p['facts'] if f['kind']=='validity'),'video':r['video'],'duration':r['metrics']['metadata']['duration']}
    check('normal_valid_promo_with_long_source',valid_promo)
    print('FIX_CHECKS',sum(r['passed'] for r in records),'/',len(records),flush=True)
    raise SystemExit(0 if all(r['passed'] for r in records) else 1)
