"""Second exploratory audit; no changes to application code or primary saved project."""
from pathlib import Path
import copy,json,sys,time,uuid,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from demo import create_demo
from media import DATA,FFMPEG,run,analyze,probe,write_ass
from planner import caption_for,CTA

OUT=ROOT/'evidence/audit2-2026-10-30';OUT.mkdir(exist_ok=True)
FIXTURES=DATA/'audit2-fixtures';FIXTURES.mkdir(exist_ok=True)
records=[]
def save():
    (OUT/'results.json').write_text(json.dumps({'date':'2026-10-30','scope':'Exploratory technical fixtures; not merchant accuracy','cases':records},ensure_ascii=False,indent=2),encoding='utf8')
def api(path,obj=None,raw=None):
    data=raw if raw is not None else (json.dumps(obj,ensure_ascii=False).encode('utf8') if obj is not None else None)
    req=urllib.request.Request('http://127.0.0.1:4180'+path,data=data,headers={'Content-Type':'application/octet-stream' if raw is not None else 'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=90) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
def finish(initial):
    code,obj=initial
    if code!=202:return {'http':code,'response':obj}
    for _ in range(1500):
        _,j=api('/api/jobs/'+obj['job_id'])
        if j['status'] in ('done','error'):return j
        time.sleep(.1)
    return {'status':'timeout','job_id':obj['job_id']}
def case(cid,title,fn):
    begun=time.perf_counter()
    try:r=fn()
    except Exception as e:r={'harness_exception':type(e).__name__,'message':str(e)}
    records.append({'id':cid,'title':title,'elapsed_seconds':round(time.perf_counter()-begun,3),'result':r})
    save();print(cid,title,json.dumps(r,ensure_ascii=False)[:650],flush=True)
    return r
def upload(name,args):
    dest=FIXTURES/name
    if not dest.is_file():run([FFMPEG,'-y','-v','error',*args,dest])
    done=finish(api('/api/upload?name='+urllib.parse.quote(name),raw=dest.read_bytes()))
    if done.get('status')!='done':raise ValueError(str(done))
    return done['result']
def add_confirmed(p,asset,role):
    s=copy.deepcopy(asset['shots'][0]);s.update(tags=[role],confirmed=False);p['shots'].append(s);pos=len(p['shots'])-1
    replies=[]
    for mode in (['purpose','product'] if role=='product' else ['purpose']):
        code,r=api('/api/confirm-shot',{'project':p,'shot_id':s['id'],'mode':mode,'checked':True});replies.append((code,r))
        if code!=200:return replies
        p['shots'][pos]=r['shot']
    return replies
def plan(p,method='evidence'):
    code,r=api('/api/plan',{'project':p,'method':method});return {'http':code,**r}
def render(p,pl):
    j=finish(api('/api/render',{'project':p,'plan':pl}))
    if j.get('status')=='done':
        r=j['result'];return {'status':'exported','video':r['video'],'metadata':r['metrics']['metadata'],'timings':r['metrics']['timings']}
    return j

if __name__=='__main__':
    base=create_demo()
    coffee=ROOT/'evidence/public-test-images/coffee.png';cat=ROOT/'evidence/public-test-images/chelsea.png'
    product=next(s for s in base['shots'] if 'product' in s['tags']);process=next(s for s in base['shots'] if 'process' in s['tags'])
    picture=DATA/product['media_id']/'illustration.png'
    case('B01','当前普通与素材顺序编排对照',lambda:{m:plan(base,m)['renderable'] for m in ('evidence','chronological')})
    def unused_ai():
        p=copy.deepcopy(base);mid='e'*32
        p['shots'].append({'id':'lost-unused','media_id':mid,'start':0.,'end':6.,'quality':.5,'tags':['other'],'confirmed':False,
                           'thumb':f'/media/{mid}/thumb-0.jpg','frames':[{'time':t,'url':f'/media/{mid}/{name}'} for t,name in [(0.1,'frame-0-0.jpg'),(3,'thumb-0.jpg'),(5.9,'frame-0-4.jpg')]],'analysis_version':4})
        j=finish(api('/api/local-analyze',{'project':p}));return {'status':j.get('status'),'message':j.get('message'),'returned_shots':len(j.get('result',{}).get('shots',[]))}
    case('B02','未使用失效素材对AI分析的影响',unused_ai)
    def mov():
        asset=upload('AUDIT2_ProRes.mov',['-loop','1','-i',str(picture),'-vf','scale=320:568','-t','6','-r','12','-c:v','prores_ks','-profile:v','0','-threads','2','-pix_fmt','yuv422p10le','-f','mov'])
        p=copy.deepcopy(base);p['name']='AUDIT2 ProRes预览（模拟素材）';p['shots']=[s for s in p['shots'] if 'product' not in s['tags']]
        reply=add_confirmed(p,asset,'product');pl=plan(p)
        (OUT/'prores-project.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
        codec=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,pix_fmt','-of','json',DATA/asset['id']/'source.mp4']))
        return {'media_id':asset['id'],'codec':codec,'analysis':asset['meta'],'quality':asset['shots'][0]['quality'],'confirm_http':reply[-1][0],
                'source_url':f'/media/{asset["id"]}/source.mp4','render':render(p,pl) if pl.get('renderable') else pl}
    case('B03','允许上传的ProRes MOV能否复核与成片',mov)
    def quality_intro(name,filter_value):
        asset=upload(name,['-loop','1','-i',str(coffee),'-vf',filter_value,'-t','8','-r','25','-c:v','libx264','-preset','ultrafast','-threads','2','-pix_fmt','yuv420p'])
        p=copy.deepcopy(base);p['shots']=[s for s in p['shots'] if 'product' not in s['tags']]
        replies=add_confirmed(p,asset,'product')
        return {'media_id':asset['id'],'duration':asset['meta']['duration'],'shots':[{'start':s['start'],'end':s['end'],'quality':s['quality'],'issues':s.get('quality_issues')} for s in asset['shots']],
                'confirmation_http':replies[-1][0],'confirmation_message':replies[-1][1].get('error'),'plan':plan(p)}
    case('B04','短暂淡入后清晰咖啡是否整段被拒绝',lambda:quality_intro('AUDIT2_fade.mp4','fade=t=in:st=0:d=1'))
    case('B05','前0.5秒失焦后7.5秒清晰咖啡',lambda:quality_intro('AUDIT2_autofocus.mp4',"gblur=sigma=12:enable='lt(t,0.5)'"))
    case('B06','同一咖啡无失焦的正常对照',lambda:quality_intro('AUDIT2_plain.mp4','null'))
    def square_pixels():
        asset=upload('AUDIT2_anamorphic.mp4',['-loop','1','-i',str(coffee),'-vf','setsar=2','-t','8','-r','25','-c:v','libx264','-preset','ultrafast','-threads','2','-pix_fmt','yuv420p'])
        p=copy.deepcopy(base);p['shots']=[s for s in p['shots'] if 'product' not in s['tags']];add_confirmed(p,asset,'product');pl=plan(p);r=render(p,pl)
        info=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,sample_aspect_ratio,display_aspect_ratio','-of','json',DATA/asset['id']/'source.mp4']))
        if r.get('status')=='exported':
            at=next(t for t in r['timings'] if '手冲咖啡' in t['text'])['start']+1
            jpg=OUT/'anamorphic-output.jpg';run([FFMPEG,'-y','-v','error','-ss',str(at),'-i',DATA/r['video'].split('/')[2]/'result.mp4','-frames:v','1',jpg])
            import cv2,numpy as np
            frame=cv2.imdecode(np.fromfile(jpg,dtype=np.uint8),cv2.IMREAD_COLOR)
            bg=np.asarray([30,37,23],dtype=np.int16);mask=(np.max(np.abs(frame.astype(np.int16)-bg),axis=2)>30).astype('uint8')
            count,labels,stats,_=cv2.connectedComponentsWithStats(mask,8)
            best=max(range(1,count),key=lambda k:stats[k,cv2.CC_STAT_AREA]);rect=stats[best].tolist()
        else:rect=None
        return {'source':info,'largest_content_rectangle_xywh_area':rect,'render':r}
    case('B07','非方形像素素材比例',square_pixels)
    def long_plan():
        asset=upload('AUDIT2_process64.mp4',['-stream_loop','10','-i',str(DATA/process['media_id']/'source.mp4'),'-t','64','-c','copy'])
        p=copy.deepcopy(base);p['goal']='attract';p['shots']=[s for s in p['shots'] if 'process' not in s['tags']]
        for s in asset['shots'][:8]:
            single={**asset,'shots':[s]};reply=add_confirmed(p,single,'process');assert reply[-1][0]==200,reply
        pl=plan(p);assert pl['renderable'],pl
        product_seg=next(s for s in pl['segments'] if s['role']=='product');inside_seg=next(s for s in pl['segments'] if s['role']=='interior')
        all_segments=[product_seg]
        for s in p['shots']:
            if s['media_id']==asset['id']:
                text,refs=caption_for('process',p['facts'],p['goal']);all_segments.append({'shot_id':s['id'],'role':'process','start':s['start'],'end':s['end'],'text':text,'fact_ids':refs})
        all_segments.append(inside_seg);pl['segments']=all_segments
        validation=api('/api/validate',{'project':p,'plan':pl})
        (OUT/'long-project.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
        (OUT/'long-plan.json').write_text(json.dumps(pl,ensure_ascii=False,indent=2),encoding='utf8')
        return {'segments':len(all_segments),'selected_process_seconds':sum(s['end']-s['start'] for s in all_segments if s['role']=='process'),
                'validate_http':validation[0],'validate_valid':validation[1].get('valid'),'render':render(p,pl)}
    case('B08','10段合法方案总时长上限预检',long_plan)
    def special_name():
        p=copy.deepcopy(base);next(f for f in p['facts'] if f['kind']=='product')['value']='手冲{A1}咖啡'
        s=next(s for s in p['shots'] if 'product' in s['tags'])
        code,result=api('/api/confirm-shot',{'project':p,'shot_id':s['id'],'mode':'product','checked':True});assert code==200,result
        p['shots'][p['shots'].index(s)]=result['shot'];pl=plan(p);r=render(p,pl)
        text=next(seg['text'] for seg in pl['segments'] if seg['role']=='product')
        ass=OUT/'special-name.ass';write_ass(ass,text,6,True,[{'start':0,'end':5,'text':text}])
        dialogue=[line for line in ass.read_text(encoding='utf-8-sig').splitlines() if line.startswith('Dialogue: 0')]
        if r.get('status')=='exported':
            at=next(t for t in r['timings'] if '{A1}' in t['text'])['start']+1
            run([FFMPEG,'-y','-v','error','-ss',str(at),'-i',DATA/r['video'].split('/')[2]/'result.mp4','-frames:v','1',OUT/'special-name-output.jpg'])
        return {'confirmed_product':'手冲{A1}咖啡','plan_copy':text,'actual_ass_dialogue':dialogue,'render':r}
    case('B09','商品型号含花括号时字幕是否保留',special_name)
    def malformed():
        out=[]
        for value in (None,[],{'segments':None}):
            code,r=api('/api/validate',{'project':base,'plan':value});out.append({'plan_input':value,'http':code,'response':r})
        return out
    case('B10','格式错误的方案返回信息',malformed)
    print('AUDIT2_FINISHED',len(records),flush=True)
