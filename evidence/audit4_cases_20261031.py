"""Exploratory audit 4: API/media fixtures only; application code is unchanged."""
from pathlib import Path
import copy,json,sys,time,urllib.request,urllib.error,urllib.parse,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from media import DATA,FFMPEG,run
from demo import create_demo
OUT=ROOT/'evidence/audit4-2026-10-31';OUT.mkdir(exist_ok=True)
FIX=DATA/'audit4-fixtures';FIX.mkdir(exist_ok=True)
ONLY=sys.argv[sys.argv.index('--only')+1] if '--only' in sys.argv else None
records=json.loads((OUT/'results.json').read_text(encoding='utf8'))['cases'] if ONLY and (OUT/'results.json').exists() else []
def api(path,obj=None,raw=None):
    data=raw if raw is not None else json.dumps(obj,ensure_ascii=False).encode() if obj is not None else None
    try:
        with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:4180'+path,data=data,headers={'Content-Type':'application/octet-stream' if raw is not None else 'application/json'}),timeout=180) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
def job(response):
    code,obj=response
    if code!=202:return {'http':code,'response':obj}
    for _ in range(2400):
        _,item=api('/api/jobs/'+obj['job_id'])
        if item['status'] in ('done','error'):return item
        time.sleep(.1)
    return {'status':'timeout'}
def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def case(cid,title,fn):
    if ONLY and cid!=ONLY:return
    records[:]=[r for r in records if r['id']!=cid];begun=time.perf_counter()
    try:r=fn()
    except Exception as e:r={'harness_exception':type(e).__name__,'message':str(e)}
    records.append({'id':cid,'title':title,'elapsed_seconds':round(time.perf_counter()-begun,3),'result':r})
    save('results.json',{'date':'2026-10-31','baseline':'d02f4aa','scope':'Original simulated technical fixtures, not merchant outcomes; no application edits.','cases':records})
    print(cid,title,json.dumps(r,ensure_ascii=False)[:900],flush=True)
def upload(path):
    item=job(api('/api/upload?name='+urllib.parse.quote(path.name),raw=path.read_bytes()))
    assert item['status']=='done',item
    return item['result']
def confirmed(p,asset,role):
    p['shots']+=copy.deepcopy(asset['shots'])
    for s in list(p['shots']):
        if s['media_id']!=asset['id'] or s['quality_issues']:continue
        s['tags']=[role];i=next(i for i,v in enumerate(p['shots']) if v['id']==s['id'])
        for mode in (['purpose','product'] if role=='product' else ['purpose']):
            code,res=api('/api/confirm-shot',{'project':p,'shot_id':s['id'],'mode':mode,'checked':True});assert code==200,res
            p['shots'][i]=res['shot']
    return p
def plan_render(p,name):
    code,pl=api('/api/plan',{'project':p});save(name+'-project.json',p);save(name+'-plan.json',pl)
    r={'plan_http':code,'plan':pl}
    if code==200 and pl.get('renderable'):r['render']=job(api('/api/render',{'project':p,'plan':pl}))
    return r
def make_clip(seconds,name):
    target=FIX/name
    if not target.exists():
        run([FFMPEG,'-y','-v','error','-stream_loop','-1','-i',coffee,'-t',seconds,'-an','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',target])
    return target

base=create_demo();coffee=DATA/next(s['media_id'] for s in base['shots'] if 'product' in s['tags'])/'source.mp4'
def promo_project(seconds,name):
    p=copy.deepcopy(base);p['goal']='promo';p['shots']=[s for s in p['shots'] if 'product' not in s['tags']]
    next(f for f in p['facts'] if f['kind']=='offer')['value']='第二杯半价，仅限同款饮品，每人每天限购一次，不与其他优惠同享'
    for i in range(2):confirmed(p,upload(make_clip(seconds,f'{name}-{i}.mp4')),'product')
    return p
case('C01','两段各8秒能否承载完整优惠条件',lambda:plan_render(promo_project(8,'eight'),'eight'))
case('C02','两段各7.96秒对照与实际成片',lambda:plan_render(promo_project(7.96,'under-eight'),'under-eight'))
def attract():
    p=copy.deepcopy(base);p['goal']='attract';return plan_render(p,'attract-normal')
case('C03','引流关注正常流程',attract)
def chronology():
    p=json.loads((ROOT/'evidence/fixes3-2026-10-31/short-group-project.json').read_text(encoding='utf8'))
    code,pl=api('/api/plan',{'project':p,'method':'chronological'});save('chronological-plan.json',pl)
    return {'http':code,'plan':pl,'render':job(api('/api/render',{'project':p,'plan':pl})) if code==200 and pl.get('renderable') else None}
case('C04','短镜头组按素材顺序编排',chronology)
def punctuation():
    p=copy.deepcopy(base);next(f for f in p['facts'] if f['kind']=='address')['value']='示例路18号\u202899室'
    return plan_render(p,'unicode-line-separator')
case('C05','复制文字中的Unicode换行',punctuation)
def malformed():
    samples=[None,[],{}, {**copy.deepcopy(base),'shots':[{'id':'bad'}]}, {**copy.deepcopy(base),'facts':[None]}, {**copy.deepcopy(base),'saved_edit':{'version':1,'method':'evidence','context_id':'bad','plan':None}}]
    return [{'input':i,'http':(r:=api('/api/reconcile',{'project':p}))[0],'response':r[1]} for i,p in enumerate(samples)]
case('C06','损坏或不完整的项目导入',malformed)
def validity():
    p=copy.deepcopy(base);p['goal']='promo';next(f for f in p['facts'] if f['kind']=='validity')['value']='2026年10月1日至2026年10月2日'
    code,pl=api('/api/plan',{'project':p});return {'http':code,'renderable':pl.get('renderable'),'missing':pl.get('missing')}
case('C07','过期促销不允许生成',validity)
def context():
    packed=json.loads((ROOT/'evidence/fixes3-2026-10-31/ui-saved-session.json').read_text(encoding='utf8'))
    results=[]
    for kind in ('unchanged','goal','address','source','confirmation'):
        p=copy.deepcopy(packed)
        if kind=='goal':p['goal']='attract'
        elif kind=='address':next(f for f in p['facts'] if f['kind']=='address')['value']='新的模拟地址'
        elif kind=='source':p['shots'][0]['source_sha256']='0'*64
        elif kind=='confirmation':p['shots'][0]['confirmed']=False
        code,r=api('/api/reconcile',{'project':p});results.append({'change':kind,'http':code,'has_saved_edit':'saved_edit' in r,'warnings':r.get('warnings')})
    return results
case('C08','已保存方案在项目变更后重新核验',context)
def hlg():
    from media import probe
    target=FIX/'hlg-explicit-vui-simulated.mp4'
    if not target.exists():run([FFMPEG,'-y','-v','error','-i',coffee,'-c:v','libx265','-preset','ultrafast','-x265-params','pools=2:log-level=error:colorprim=9:transfer=18:colormatrix=9','-pix_fmt','yuv420p10le','-an',target])
    metadata=probe(target);assert metadata['color_transfer']=='arib-std-b67',metadata
    result=job(api('/api/upload?name=hlg-explicit-vui-simulated.mp4',raw=target.read_bytes()))
    return {'scope':'synthetic transfer-metadata detection only, not real HDR color calibration','fixture_metadata':metadata,'job':result}
case('C09','HLG标记素材应明确拒绝',hlg)
def chronological_diagnostics():
    from audio import prepare_voice
    from planner import caption_for,CTA
    p=json.loads((ROOT/'evidence/fixes3-2026-10-31/short-group-project.json').read_text(encoding='utf8'))
    text=caption_for('product',p['facts'],p['goal'])[0]+CTA[p['goal']]
    length=prepare_voice(text)[1]
    return {'last_role':'product','last_copy':text,'actual_natural_seconds':length,'actual_minimum_seconds':round(length/1.18+.08,3),'total_product_seconds':sum(s['end']-s['start'] for s in p['shots'] if 'product' in s['tags']),'reported_missing':api('/api/plan',{'project':p,'method':'chronological'})[1]['missing']}
case('C10','素材顺序模式末段旁白缺口提示是否准确',chronological_diagnostics)
def normal_visual_change():
    target=FIX/'same-cup-brightness-variation.mp4'
    if not target.exists():run([FFMPEG,'-y','-v','error','-i',DATA/'audit3-fixtures/A3_01_plain.mp4','-vf',"eq=brightness='0.04*sin(t)':eval=frame",'-an','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',target])
    a=upload(target);p=copy.deepcopy(base);p['shots']=copy.deepcopy(a['shots'])
    result=job(api('/api/local-analyze',{'project':p}));save('normal-change-analysis.json',result)
    return {'status':result['status'],'summary':result.get('result',{}).get('vision_analysis',{}).get('summary'),'shots':[{'frames':len(s['frames']),'risk':s.get('semantic_issue'),'candidate':s.get('local_candidate')} for s in result.get('result',{}).get('shots',[])]}
case('C11','同一杯商品的曝光变化是否被误封',normal_visual_change)
