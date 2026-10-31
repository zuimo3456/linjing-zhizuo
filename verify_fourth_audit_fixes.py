"""Actual regressions for audit 4. Historical failed-case evidence is read only."""
from pathlib import Path
import copy,json,time,urllib.request,urllib.error,urllib.parse
from media import ROOT,DATA,FFMPEG,run,write_ass
from planner import caption_for,CTA

OUT=ROOT/'evidence/fixes4-2026-10-31';OUT.mkdir(exist_ok=True)
records=[]
def api(path,obj=None,raw=None):
    data=raw if raw is not None else json.dumps(obj,ensure_ascii=False).encode() if obj is not None else None
    try:
        with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:4180'+path,data=data,headers={'Content-Type':'application/octet-stream' if raw is not None else 'application/json'}),timeout=180) as res:return res.status,json.load(res)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
def done(response):
    code,item=response;assert code==202,(code,item)
    for _ in range(1800):
        _,job=api('/api/jobs/'+item['job_id'])
        if job['status']=='done':return job['result']
        if job['status']=='error':raise AssertionError(job['message'])
        time.sleep(.1)
    raise AssertionError('job timed out')
def save(name,obj):(OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
def load(name):return json.loads((ROOT/name).read_text(encoding='utf8'))
def case(cid,fn):
    begun=time.perf_counter()
    try:result=fn();passed=True
    except Exception as e:result={'exception':type(e).__name__,'message':str(e)};passed=False
    records.append({'id':cid,'passed':passed,'seconds':round(time.perf_counter()-begun,3),'result':result})
    save('results.json',{'date':'2026-10-31','scope':'Local technical regression, not merchant or human listening acceptance.','passed':sum(c['passed'] for c in records),'total':len(records),'cases':records})
    print(cid,passed,json.dumps(result,ensure_ascii=False)[:750],flush=True)
def plan(p,method='evidence'):
    code,result=api('/api/plan',{'project':p,'method':method});assert code==200,result
    return result
def checked(p,pl):
    code,out=api('/api/validate',{'project':p,'plan':pl});assert code==200,out
    return out['plan']
def render(p,pl):return done(api('/api/render',{'project':p,'plan':pl}))
def export(p,pl,method='evidence'):
    code,out=api('/api/export-project',{'project':p,'plan':pl,'method':method});assert code==200,out
    return out
def screenshot(r,at,name):run([FFMPEG,'-y','-v','error','-ss',at,'-i',DATA/r['video'].split('/')[2]/'result.mp4','-frames:v','1',OUT/name])

if __name__=='__main__':
    eight=load('evidence/audit4-2026-10-31/eight-project.json')
    def exact():
        pl=plan(eight);assert pl['renderable'],pl
        group=next(s for s in pl['segments'] if s['role']=='product');assert len(group['clips'])==2 and sum(c['end']-c['start'] for c in group['clips'])==16
        pl=checked(eight,pl);r=render(eight,pl);save('eight-session.json',export(eight,pl));save('eight-render.json',r)
        screenshot(r,4,'eight-output.jpg')
        return {'group':group,'video':r['video'],'timings':r['metrics']['timings'],'metadata':r['metrics']['metadata']}
    case('F02_exact_eight',exact)
    def near():
        p=load('evidence/audit4-2026-10-31/under-eight-project.json');pl=checked(p,plan(p));group=next(s for s in pl['segments'] if s['role']=='product')
        assert len(group['clips'])==2 and abs(sum(c['end']-c['start'] for c in group['clips'])-15.92)<.001
        return {'near_eight_still_valid':True,'estimated_seconds':pl['estimated_seconds']}
    case('F02_near_eight',near)
    short=load('evidence/fixes3-2026-10-31/short-group-project.json')
    def negative():
        pl=plan(short,'chronological');assert not pl['renderable'],pl
        d=next(d for d in pl['timing_diagnostics'] if d['role']=='product')
        assert d['includes_cta'] and d['available_seconds']==4 and abs(d['minimum_seconds']-4.779)<.001,d
        assert '包含结尾引导语' in ''.join(pl['missing']) and '2个可组合片段合计4.0秒' in ''.join(pl['missing'])
        code,out=api('/api/render',{'project':short,'plan':pl});assert code==400,(code,out)
        save('chronological-short-project.json',short);save('chronological-short-plan.json',pl)
        return {'diagnostics':pl['timing_diagnostics'],'missing':pl['missing'],'still_rejects_render':code}
    case('F03_real_deficit',negative)
    def positive():
        p=copy.deepcopy(short);asset=done(api('/api/upload?name=extra-two-seconds.mp4',raw=(DATA/'audit3-fixtures/THIRD_FIX_short_B.mp4').read_bytes()))
        p['shots']+=asset['shots']
        for s in list(p['shots']):
            if s['media_id']!=asset['id']:continue
            s['tags']=['product'];index=next(i for i,v in enumerate(p['shots']) if v['id']==s['id'])
            for mode in ('purpose','product'):
                code,out=api('/api/confirm-shot',{'project':p,'shot_id':s['id'],'mode':mode,'checked':True});assert code==200,out;p['shots'][index]=out['shot']
        pl=checked(p,plan(p,'chronological'));group=pl['segments'][-1]
        assert group['role']=='product' and len(group['clips'])==3 and group['text'].endswith(CTA[p['goal']]),pl
        r=render(p,pl);save('chronological-six-session.json',export(p,pl,'chronological'))
        return {'group':group,'video':r['video'],'metadata':r['metrics']['metadata']}
    case('F03_enough_footage',positive)
    def unicode():
        p=load('evidence/audit4-2026-10-31/unicode-line-separator-project.json');f=next(f for f in p['facts'] if f['kind']=='address');f['value']='示例路18号\u2028\u202999室'
        raw=f['value'];pl=checked(p,plan(p));seg=next(s for s in pl['segments'] if s['role']=='storefront')
        assert seg['text']=='门店地址：示例路18号 99室。' and f['value']==raw
        r=render(p,pl);save('unicode-session.json',export(p,pl));screenshot(r,.8,'unicode-fixed.jpg')
        write_ass(OUT/'unicode-fixed.ass',seg['text'],5,False)
        bad=copy.deepcopy(p);next(f for f in bad['facts'] if f['kind']=='address')['value']+='\x00'
        code,out=api('/api/plan',{'project':bad});assert code==400 and '控制字符' in out['error']
        return {'raw_fact':raw,'copy':seg['text'],'video':r['video'],'metadata':r['metrics']['metadata'],'unsupported_control_http':code}
    case('F04_unicode_layout',unicode)
    def guards():
        p=copy.deepcopy(eight);s=next(s for s in p['shots'] if 'product' in s['tags']);s['confirmed']=False
        assert not plan(p)['renderable']
        p=copy.deepcopy(eight);next(f for f in p['facts'] if f['kind']=='validity')['value']='2026年10月1日至2026年10月2日'
        expired=plan(p);assert not expired['renderable'] and '结束' in ''.join(expired['missing'])
        risky=load('evidence/fixes3-2026-10-31/semantic-risk-project.json');s=next(s for s in risky['shots'] if s.get('semantic_issue'));s.pop('semantic_issue',None)
        code,out=api('/api/confirm-shot',{'project':risky,'shot_id':s['id'],'mode':'purpose','checked':True});assert code==400 and '风险' in out['error']
        return {'second_product_must_still_be_confirmed':True,'expired_promo_blocked':True,'semantic_risk_confirmation_http':code}
    case('existing_guards',guards)
    def sessions():
        packed=load('evidence/fixes4-2026-10-31/eight-session.json');code,restored=api('/api/reconcile',{'project':packed})
        assert code==200 and restored['saved_edit']['plan']['segments']==packed['saved_edit']['plan']['segments']
        next(f for f in packed['facts'] if f['kind']=='address')['value']='变更地址'
        code,stale=api('/api/reconcile',{'project':packed});assert code==200 and 'saved_edit' not in stale and stale['warnings']
        return {'group_session_restores':True,'changed_fact_invalidates_plan':True}
    case('session_regression',sessions)
    if not all(c['passed'] for c in records):raise SystemExit(1)
