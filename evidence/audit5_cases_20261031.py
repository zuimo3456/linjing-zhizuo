"""Fifth exploratory audit; application and historical evidence are read only."""
from pathlib import Path
import copy,json,sys,time,urllib.parse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from verify_fourth_audit_fixes import api,done
from media import DATA,FFMPEG,FFPROBE,run,probe
from planner import CTA,caption_for
from demo import create_demo
OUT=ROOT/'evidence/audit5-2026-10-31';OUT.mkdir(exist_ok=True)
FIX=DATA/'audit5-fixtures';FIX.mkdir(exist_ok=True)
ONLY=sys.argv[sys.argv.index('--only')+1] if '--only' in sys.argv else None
records=json.loads((OUT/'results.json').read_text(encoding='utf8'))['cases'] if ONLY and (OUT/'results.json').exists() else []
def save(name,obj):(OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
def load(name):return json.loads((ROOT/name).read_text(encoding='utf8'))
def case(cid,title,fn):
    if ONLY and cid!=ONLY:return
    records[:]=[r for r in records if r['id']!=cid];begun=time.perf_counter()
    try:r=fn()
    except Exception as e:r={'harness_exception':type(e).__name__,'message':str(e)}
    records.append({'id':cid,'title':title,'seconds':round(time.perf_counter()-begun,3),'result':r})
    save('results.json',{'date':'2026-10-31','baseline':'1f4d1ed','scope':'Exploratory original/authorized technical fixtures; no merchant or human listening acceptance.','cases':records})
    print(cid,title,json.dumps(r,ensure_ascii=False)[:1050],flush=True)
def upload(path):return done(api('/api/upload?name='+urllib.parse.quote(path.name),raw=path.read_bytes()))
def add_confirmed(p,asset,role):
    p['shots']+=copy.deepcopy(asset['shots'])
    for s in list(p['shots']):
        if s['media_id']!=asset['id'] or s['quality_issues'] or s['end']-s['start']<1:continue
        s['tags']=[role];index=next(i for i,x in enumerate(p['shots']) if x['id']==s['id'])
        for mode in (['purpose','product'] if role=='product' else ['purpose']):
            code,out=api('/api/confirm-shot',{'project':p,'shot_id':s['id'],'mode':mode,'checked':True});assert code==200,out;p['shots'][index]=out['shot']
    return p
def plan(p,method='evidence'):
    code,out=api('/api/plan',{'project':p,'method':method});assert code==200,out
    return out
def render(p,pl):return done(api('/api/render',{'project':p,'plan':pl}))
def frame(r,at,name):run([FFMPEG,'-y','-v','error','-ss',at,'-i',DATA/r['video'].split('/')[2]/'result.mp4','-frames:v','1',OUT/name])

if __name__=='__main__':
    base=create_demo();eight=load('evidence/audit4-2026-10-31/eight-project.json')
    coffee=DATA/next(s['media_id'] for s in base['shots'] if 'product' in s['tags'])/'source.mp4'
    def interrupted_group():
        path=FIX/'one-second-product.mp4'
        if not path.exists():run([FFMPEG,'-y','-v','error','-i',coffee,'-t','1','-an','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',path])
        asset=upload(path);p=copy.deepcopy(eight);products=[s for s in p['shots'] if 'product' in s['tags']]
        p['shots']=[s for s in p['shots'] if 'storefront' in s['tags']];p['shots'].append(products[0]);add_confirmed(p,asset,'product');p['shots'].append(products[1])
        automatic=plan(p,'chronological');save('interrupted-project.json',p);save('interrupted-auto-plan.json',automatic)
        control=copy.deepcopy(p);control['shots']=[s for s in control['shots'] if s['media_id']!=asset['id']];alternative=plan(control,'chronological');assert alternative['renderable'],alternative
        code,checked=api('/api/validate',{'project':p,'plan':alternative});assert code==200,checked
        r=render(p,checked['plan']);save('interrupted-manual-plan.json',checked['plan']);save('interrupted-control-render.json',r)
        return {'shot_order':[[s['id'],s['end']-s['start']] for s in p['shots']],'automatic':automatic,'remove_short_control_renderable':alternative['renderable'],'same_project_manual_plan_http':code,'valid_video':r['video']}
    case('D01','8秒—1秒—8秒商品组合与可行对照',interrupted_group)
    def trailing_short():
        p=load('evidence/audit5-2026-10-31/interrupted-project.json');short=next(s for s in p['shots'] if s['end']-s['start']<2);p['shots'].remove(short);p['shots'].append(short)
        pl=plan(p,'chronological');save('trailing-short-plan.json',pl)
        return {'renderable':pl['renderable'],'plan':pl}
    case('D02','同样素材仅将1秒片段移到最后',trailing_short)
    def delayed_video():
        from PIL import Image,ImageDraw,ImageFont
        folder=FIX/'counter';folder.mkdir(exist_ok=True);png=DATA/next(s['media_id'] for s in base['shots'] if 'product' in s['tags'])/'illustration.png'
        font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',50)
        for n in range(6):
            target=folder/f'{n:02d}.png'
            if not target.exists():
                im=Image.open(png).convert('RGB');d=ImageDraw.Draw(im);d.rectangle((24,970,690,1060),fill='black');d.text((38,980),f'SOURCE SECOND {n}',fill='white',font=font);im.save(target)
        plain=FIX/'counter-plain.mp4';delayed=FIX/'counter-video-delay2.mp4'
        if not plain.exists():run([FFMPEG,'-y','-v','error','-framerate','1','-i',folder/'%02d.png','-vf','fps=25','-t','6','-an','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',plain])
        if not delayed.exists():run([FFMPEG,'-y','-v','error','-itsoffset','2','-i',plain,'-f','lavfi','-i','sine=frequency=300:duration=8','-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-t','8',delayed])
        streams=json.loads(run([FFPROBE,'-v','error','-show_streams','-show_format','-of','json',delayed]));save('delayed-source-metadata.json',streams)
        video=next(s for s in streams['streams'] if s['codec_type']=='video');assert float(video['start_time'])==2,video
        a=upload(delayed);save('delayed-asset.json',a);p=copy.deepcopy(base);p['shots']=[s for s in p['shots'] if 'product' not in s['tags']];add_confirmed(p,a,'product')
        pl=plan(p);save('delayed-project.json',p);save('delayed-plan.json',pl)
        result={'source_video_start':video['start_time'],'asset':a,'plan':pl}
        if pl['renderable']:
            r=render(p,pl);save('delayed-render.json',r);t=next(t for t in r['metrics']['timings'] if '带你看看' in t['text'])
            frame(r,t['start']+.3,'delayed-output-early.jpg');frame(r,t['start']+2.3,'delayed-output-later.jpg');result.update(video=r['video'],timings=r['metrics']['timings'],metadata=r['metrics']['metadata'])
        return result
    case('D03','画面晚于音轨2秒开始的素材',delayed_video)
    def long_text():
        p=copy.deepcopy(eight);next(f for f in p['facts'] if f['kind']=='offer')['value']='仅限同款商品，每人每天限购一次，需到店核销，不与其他优惠同享，仅限工作日下午使用，特殊节假日不参与活动，使用前请先联系门店确认库存'
        pl=plan(p);save('long-offer-project.json',p);save('long-offer-plan.json',pl)
        return {'plan':pl,'validate_http':api('/api/validate',{'project':p,'plan':pl})[0]}
    case('D04','完整长优惠条件超过可用画面',long_text)
    def near_clip_boundary():
        p=copy.deepcopy(base);asset=upload(DATA/'audit4-fixtures/under-eight-0.mp4');p['shots']=[s for s in p['shots'] if 'product' not in s['tags']];add_confirmed(p,asset,'product');pl=plan(p);r=render(p,pl)
        return {'renderable':pl['renderable'],'video':r['video'],'duration':r['metrics']['metadata']['duration']}
    case('D05','7.96秒单镜头正常对照',near_clip_boundary)
    def text_controls():
        p=copy.deepcopy(base);p['goal']='promo';next(f for f in p['facts'] if f['kind']=='offer')['value']='单杯\u202e19\u202c元'
        # Use existing long confirmed sources so text handling, not lack of footage, is tested.
        p['shots']=copy.deepcopy(eight['shots']);pl=plan(p);save('direction-control-project.json',p);save('direction-control-plan.json',pl)
        result={'plan':pl}
        if pl['renderable']:
            r=render(p,pl);save('direction-control-render.json',r);cues=r['metrics']['timings'][0]['captions'];cue=next(c for c in cues if '19' in c['text']);frame(r,(cue['start']+cue['end'])/2,'direction-control-output.jpg');result['video']=r['video'];result['captions']=cues
        return result
    case('D06','价格复制文本含方向控制符',text_controls)
    def no_offset_control():
        a=upload(FIX/'counter-plain.mp4');p=copy.deepcopy(base);p['shots']=[s for s in p['shots'] if 'product' not in s['tags']];add_confirmed(p,a,'product');pl=plan(p);save('plain-counter-asset.json',a)
        result={'asset':a,'plan':pl}
        if pl['renderable']:
            r=render(p,pl);result['video']=r['video'];frame(r,next(t['start'] for t in r['metrics']['timings'] if '带你看看' in t['text'])+.3,'plain-counter-output.jpg')
        return result
    case('D07','相同6秒计数画面没有音画起点偏移的对照',no_offset_control)
    def ordinary_price():
        p=load('evidence/audit5-2026-10-31/direction-control-project.json');next(f for f in p['facts'] if f['kind']=='offer')['value']='单杯19元'
        pl=plan(p);assert pl['renderable'],pl;r=render(p,pl);cues=r['metrics']['timings'][0]['captions'];cue=next(c for c in cues if '19' in c['text'])
        frame(r,(cue['start']+cue['end'])/2,'ordinary-price-output.jpg');save('ordinary-price-project.json',p)
        return {'plan':pl,'video':r['video'],'captions':cues}
    case('D08','普通19元文字的价格对照',ordinary_price)
