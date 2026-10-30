"""Exploratory audit, not a passing regression suite. Never changes app code/saved project."""
from pathlib import Path
import copy,json,sys,time,uuid,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from demo import create_demo
from media import DATA,FFMPEG,run,analyze,probe
from planner import make_plan
from local_vision import Engine,decide,frame_paths

OUT=ROOT/'evidence'/('audit-2026-10-30-'+uuid.uuid4().hex[:8] if '--fresh' in sys.argv else 'audit-2026-10-30')
OUT.mkdir(exist_ok=True)
records=json.loads((OUT/'results.json').read_text(encoding='utf8'))['cases'] if (OUT/'results.json').exists() else []
base=create_demo()

def save():
    (OUT/'results.json').write_text(json.dumps({'date':'2026-10-30','scope':'Constructed and CC0 technical cases only. Not merchant accuracy evaluation.',
                                              'cases':records},ensure_ascii=False,indent=2),encoding='utf8')
def record(cid,title,fn):
    previous=next((r for r in records if r['id']==cid),None)
    if previous:return previous['result']
    begun=time.perf_counter()
    try:result=fn()
    except Exception as e:result={'unexpected_exception':type(e).__name__,'message':str(e)}
    records.append({'id':cid,'title':title,'seconds':round(time.perf_counter()-begun,3),'result':result})
    save();print(cid,title,json.dumps(result,ensure_ascii=False)[:700],flush=True)
    return result
def api(path,obj=None,raw=None):
    req=urllib.request.Request('http://127.0.0.1:4180'+path,
        data=raw if raw is not None else (json.dumps(obj,ensure_ascii=False).encode('utf8') if obj is not None else None),
        headers={'Content-Type':'application/octet-stream' if raw is not None else 'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
def finish(initial):
    code,obj=initial
    if code!=202:return {'http':code,'response':obj}
    end=time.monotonic()+100
    while time.monotonic()<end:
        _,j=api('/api/jobs/'+obj['job_id'])
        if j['status'] in ('done','error'):return j
        time.sleep(.15)
    return {'status':'timeout','job_id':obj['job_id']}
def plan_case(p):
    code,r=api('/api/plan',{'project':p})
    return {'http':code,**r}
def render_case(p,keep=None):
    code,plan=api('/api/plan',{'project':p})
    if code!=200 or not plan.get('renderable'):return {'stage':'plan','http':code,'plan':plan}
    j=finish(api('/api/render',{'project':p,'plan':plan}))
    if j.get('status')!='done':return {'stage':'render','plan_renderable':True,**j}
    r=j['result'];metrics=r['metrics']
    if keep:
        (OUT/f'{keep}-project.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
        (OUT/f'{keep}-report.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf8')
    return {'status':'exported','video':r['video'],'metadata':metrics['metadata'],'elapsed':metrics['elapsed_seconds'],
            'segments':metrics['plan']['segments'],'timings':metrics['timings']}
def altered(fn,goal=None):
    p=copy.deepcopy(base)
    if goal:p['goal']=goal
    fn(p)
    return p
def fact(p,kind,value):next(f for f in p['facts'] if f['kind']==kind)['value']=value
def fixture(name,args):
    for cache in DATA.glob('*/asset.json'):
        cached=json.loads(cache.read_text(encoding='utf8'))
        if cached.get('name')==name and (cache.parent/'source.mp4').is_file():return cached
    mid=uuid.uuid4().hex;folder=DATA/mid;folder.mkdir()
    run([FFMPEG,'-y','-v','error',*args,'-c:v','libx264','-preset','ultrafast','-threads','2','-pix_fmt','yuv420p',folder/'source.mp4'])
    asset=analyze(folder/'source.mp4',mid,name)
    (folder/'asset.json').write_text(json.dumps(asset,ensure_ascii=False,indent=2),encoding='utf8')
    return asset
def replace_product(p,asset):
    original=next(s for s in p['shots'] if 'product' in s['tags'])
    new=copy.deepcopy(asset['shots'][0]);new.update(tags=['product'],confirmed=True,product_binding=original['product_binding'])
    p['shots'][p['shots'].index(original)]=new
    return p

if __name__=='__main__':
    record('C01','正常到店完整渲染',lambda:render_case(copy.deepcopy(base),'normal-visit'))
    record('C02','正常引流完整渲染',lambda:render_case(altered(lambda p:None,'attract'),'normal-attract'))
    record('C03','缺少已确认地址',lambda:plan_case(altered(lambda p:next(f for f in p['facts'] if f['kind']=='address').update(confirmed=False))))
    record('C04','同类地址互相矛盾',lambda:plan_case(altered(lambda p:p['facts'].append({'id':'conflict','kind':'address','value':'另一地址','source':'模拟','confirmed':True}))))
    record('C05','商品改名保留旧绑定',lambda:plan_case(altered(lambda p:fact(p,'product','柠檬茶'))))
    record('C06','6秒素材完整促销文案',lambda:render_case(altered(lambda p:None,'promo')))
    product=next(s for s in base['shots'] if 'product' in s['tags'])
    illustration=DATA/product['media_id']/'illustration.png'
    long_asset=fixture('AUDIT_8秒模拟商品',['-loop','1','-i',str(illustration),'-t','8','-r','25'])
    p8=replace_product(copy.deepcopy(base),long_asset)
    record('C07','8秒素材完整促销文案',lambda:render_case(altered8:=dict(copy.deepcopy(p8),goal='promo'),'promo-eight'))
    expired=copy.deepcopy(p8);expired['goal']='promo';fact(expired,'offer','第二杯半价，限同款');fact(expired,'validity','2020年1月1日至2日')
    record('C08','已过期优惠仍确认',lambda:render_case(expired,'expired-offer'))
    reverse=copy.deepcopy(p8);reverse['goal']='promo';fact(reverse,'validity','2027年5月10日至2027年5月1日')
    record('C09','有效期结束早于开始',lambda:plan_case(reverse))
    short=copy.deepcopy(base);orig=next(s for s in short['shots'] if 'product' in s['tags']);orig.update(end=1.,quality=.99)
    alt=copy.deepcopy(next(s for s in p8['shots'] if 'product' in s['tags']));alt['quality']=.6;short['shots'].append(alt)
    record('C10','短高清镜头与足够长稍低分镜头共存',lambda:render_case(short))
    record('C11','只有较长候选时能够生成',lambda:render_case(p8))
    record('C12','同一项目包含两种商品事实',lambda:plan_case(altered(lambda p:p['facts'].append({'id':'product2','kind':'product','value':'柠檬茶','source':'模拟','confirmed':True}))))
    extra=altered(lambda p:p['shots'].append({'id':'unused','media_id':'f'*32,'start':0.,'end':6.,'quality':.5,'tags':['other'],'confirmed':False}))
    record('C13','未选用的失效素材影响生成',lambda:render_case(extra))
    record('C14','损坏文件上传',lambda:finish(api('/api/upload?name=AUDIT_broken.mp4',raw=b'This is not a real video.')))
    gray=fixture('AUDIT_纯灰视频',['-f','lavfi','-i','color=c=0x808080:s=320x240:r=25:d=8'])
    grayp=replace_product(copy.deepcopy(base),gray)
    record('C15','纯灰画面质量检测与人工确认',lambda:{'quality':gray['shots'][0]['quality'],'render':render_case(grayp,'blank-frame')})
    coffee=ROOT/'evidence/public-test-images/coffee.png';cat=ROOT/'evidence/public-test-images/chelsea.png'
    cat_asset=fixture('AUDIT_CC0猫静帧',['-loop','1','-i',str(cat),'-vf','scale=452:300','-t','8','-r','25'])
    rebound=copy.deepcopy(base);next(s for s in rebound['shots'] if 'product' in s['tags'])['media_id']=cat_asset['id']
    record('C16','商品确认后导入替换素材编号',lambda:render_case(rebound,'source-rebound'))
    photo=fixture('AUDIT_CC0横拍咖啡静帧',['-loop','1','-i',str(coffee),'-t','8','-r','25'])
    record('C17','横拍商品进入竖屏成片',lambda:render_case(replace_product(copy.deepcopy(base),photo),'landscape-product'))
    engine=Engine()
    for cid,title,asset in [('C18','咖啡静帧实际模型候选',photo),('C19','猫静帧实际模型候选',cat_asset),('C20','纯灰画面实际模型候选',gray)]:
        def classify(asset=asset):
            shot=asset['shots'][0];paths,_=frame_paths(shot);return decide(engine.score(paths),shot['quality'])
        record(cid,title,classify)
    cuts=fixture('AUDIT_30段快切合成视频',['-f','lavfi','-i',"color=c=red:s=320x240:r=12:d=45,negate=enable='gte(mod(t,3),1.5)'"])
    record('C21','45秒30段快切素材覆盖',lambda:{'duration':cuts['meta']['duration'],'shots':len(cuts['shots']),
              'covered_end':max(s['end'] for s in cuts['shots']),'uncovered_tail_seconds':cuts['meta']['duration']-max(s['end'] for s in cuts['shots']),
              'warnings':cuts.get('warnings'),'media_id':cuts['id']})
    flash=fixture('AUDIT_短时异物咖啡视频',['-loop','1','-i',str(coffee),'-loop','1','-i',str(cat),
            '-filter_complex',"[0:v]scale=600:400[b];[1:v]scale=600:400[c];[b][c]overlay=enable='between(t,2.5,2.7)'",'-t','8','-r','25'])
    def flash_case():
        entries=[]
        for s in flash['shots']:
            paths,frames=frame_paths(s);entries.append({'start':s['start'],'end':s['end'],'frames':frames,'candidate':decide(engine.score(paths),s['quality'])})
        return {'media_id':flash['id'],'known_cat_interval':[2.5,2.7],'shots':entries}
    record('C22','短时异物是否被三帧捕获',flash_case)
    # Inputs for isolated UI testing; does not call /api/save.
    (OUT/'ui-demo-project.json').write_text(json.dumps(base,ensure_ascii=False,indent=2),encoding='utf8')
    print('AUDIT_FINISHED',len(records),flush=True)
