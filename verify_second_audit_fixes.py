"""Real API/media regression for second audit, with immutable failed-case evidence."""
from pathlib import Path
import copy,hashlib,json,shutil,subprocess,sys,tempfile,time,urllib.request,urllib.error,urllib.parse
from demo import create_demo
from media import ROOT,DATA,FFMPEG,run,ANALYSIS_VERSION
from planner import caption_for,CTA

OUT=ROOT/(sys.argv[sys.argv.index('--out')+1] if '--out' in sys.argv else 'evidence/fixes2-2026-10-31');OUT.mkdir(parents=True,exist_ok=True)
BASE='http://127.0.0.1:4180'
ONLY=sys.argv[sys.argv.index('--only')+1] if '--only' in sys.argv else None
records=json.loads((OUT/'results.json').read_text(encoding='utf8'))['cases'] if ONLY and (OUT/'results.json').exists() else []
def api(path,obj=None,raw=None):
    data=raw if raw is not None else (json.dumps(obj,ensure_ascii=False).encode('utf8') if obj is not None else None)
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,data=data,headers={'Content-Type':'application/octet-stream' if raw is not None else 'application/json'}),timeout=180) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
def done(response):
    code,obj=response
    assert code==202,(code,obj)
    for _ in range(1800):
        _,j=api('/api/jobs/'+obj['job_id'])
        if j['status']=='error':raise AssertionError(j['message'])
        if j['status']=='done':return j['result']
        time.sleep(.1)
    raise AssertionError('job timed out')
def check(cid,fn):
    if ONLY and cid!=ONLY:return
    records[:]=[r for r in records if r['id']!=cid]
    begun=time.perf_counter()
    try:result=fn();passed=True
    except Exception as e:result={'error':type(e).__name__,'message':str(e)};passed=False
    records.append({'id':cid,'passed':passed,'elapsed_seconds':round(time.perf_counter()-begun,3),'result':result})
    (OUT/'results.json').write_text(json.dumps({'date':'2026-10-31','scope':'Actual local API/model/media checks with technical fixtures; browser and human acceptance separate','passed':sum(r['passed'] for r in records),'total':len(records),'cases':records},ensure_ascii=False,indent=2),encoding='utf8')
    print(cid,passed,json.dumps(result,ensure_ascii=False)[:800],flush=True)
    return result
def upload(name):
    path=DATA/'audit2-fixtures'/name;raw=path.read_bytes()
    asset=done(api('/api/upload?name='+urllib.parse.quote(name),raw=raw))
    assert asset['analysis_version']==ANALYSIS_VERSION
    assert hashlib.sha256(raw).hexdigest()==hashlib.sha256((DATA/asset['id']/'source.mp4').read_bytes()).hexdigest()
    return asset
def confirm(p,s,role):
    s['tags']=[role]
    pos=next(i for i,x in enumerate(p['shots']) if x['id']==s['id'])
    for mode in (['purpose','product'] if role=='product' else ['purpose']):
        code,response=api('/api/confirm-shot',{'project':p,'shot_id':s['id'],'mode':mode,'checked':True})
        assert code==200,response;p['shots'][pos]=response['shot']
    return p['shots'][pos]
def with_asset(asset,role):
    p=copy.deepcopy(base);p['shots']=[s for s in p['shots'] if role not in s['tags']]+copy.deepcopy(asset['shots'])
    for s in list(p['shots']):
        if s['media_id']==asset['id'] and not s['quality_issues'] and s['end']-s['start']>=1:confirm(p,s,role)
    return p
def plan(p):
    code,pl=api('/api/plan',{'project':p});assert code==200 and pl['renderable'],pl
    return pl
def render(p):
    pl=plan(p);result=done(api('/api/render',{'project':p,'plan':pl}))
    return pl,result
def save_project(name,p):
    (OUT/name).write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
def product_frame(result,name):
    t=next(t for t in result['metrics']['timings'] if '带你看看' in t['text'])['start']+1
    path=OUT/name;run([FFMPEG,'-y','-v','error','-ss',t,'-i',DATA/result['video'].split('/')[2]/'result.mp4','-frames:v','1',path]);return path

if __name__=='__main__':
    backup=DATA/'backups/saved-project-before-second-fixes-20261031.json';backup.parent.mkdir(exist_ok=True)
    saved=DATA/'saved-project.json'
    if saved.is_file() and not backup.exists():shutil.copy2(saved,backup)
    base=create_demo()
    def b02():
        p=copy.deepcopy(base);mid='e'*32
        p['shots'].append({'id':'lost-unused','media_id':mid,'start':0.,'end':6.,'quality':.5,'tags':['other'],'confirmed':False,'thumb':f'/media/{mid}/thumb-0.jpg'})
        out=done(api('/api/local-analyze',{'project':p}));summary=out['vision_analysis']['summary']
        assert summary=={'succeeded':4,'failed':1,'skipped':0},summary
        assert out['facts']==p['facts'] and all(not s['confirmed'] for s in out['shots'])
        save_project('partial-ai-project.json',out)
        return {'summary':summary,'failures':out['vision_analysis']['failures'],'returned_shots':len(out['shots'])}
    check('B02',b02)
    def b03():
        asset=upload('AUDIT2_ProRes.mov');p=with_asset(asset,'product');save_project('prores-project.json',p)
        _,r=render(p)
        codec=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,sample_aspect_ratio','-of','json',DATA/asset['id']/'review.mp4']))['streams'][0]
        assert codec['codec_name']=='h264' and codec['sample_aspect_ratio']=='1:1'
        return {'media_id':asset['id'],'review_url':asset['review_url'],'mapping':asset['review_mapping'],'codec':codec,'video':r['video'],'metadata':r['metrics']['metadata']}
    check('B03',b03)
    def b04():
        asset=upload('AUDIT2_fade.mp4');p=with_asset(asset,'product')
        good=[s for s in p['shots'] if s['media_id']==asset['id'] and s.get('confirmed')]
        bad=[s for s in p['shots'] if s['media_id']==asset['id'] and s['quality_issues']]
        assert good and bad and good[0]['start']>0 and good[0]['end']-good[0]['start']>=6
        code,rejection=api('/api/confirm-shot',{'project':p,'shot_id':bad[0]['id'],'mode':'purpose','checked':True});assert code==400
        save_project('recovered-fade-project.json',p);pl,r=render(p)
        chosen=next(s for s in pl['segments'] if s['role']=='product');assert chosen['start']>=good[0]['start']
        product_frame(r,'fade-recovered-output.jpg')
        return {'intervals':[{'start':s['start'],'end':s['end'],'quality':s['quality'],'issues':s['quality_issues']} for s in asset['shots']],
                'bad_confirmation_http':code,'selected_range':[chosen['start'],chosen['end']],'video':r['video']}
    check('B04',b04)
    def b07():
        asset=upload('AUDIT2_anamorphic.mp4');p=with_asset(asset,'product');_,r=render(p)
        path=product_frame(r,'aspect-preserved-output.jpg')
        import cv2,numpy as np
        frame=cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_COLOR);bg=np.asarray([30,37,23],dtype=np.int16)
        mask=(np.max(np.abs(frame.astype(np.int16)-bg),axis=2)>30).astype('uint8')
        n,labels,stats,_=cv2.connectedComponentsWithStats(mask,8);best=max(range(1,n),key=lambda k:stats[k,cv2.CC_STAT_AREA]);rect=stats[best].tolist()
        assert abs(rect[2]/rect[3]-3)<.04,rect
        return {'content_rectangle_xywh_area':rect,'display_ratio':rect[2]/rect[3],'expected_ratio':3,'video':r['video']}
    check('B07',b07)
    def b09():
        p=copy.deepcopy(base);next(f for f in p['facts'] if f['kind']=='product')['value']='手冲{A1}咖啡'
        s=next(s for s in p['shots'] if 'product' in s['tags']);confirm(p,s,'product');save_project('literal-name-project.json',p)
        pl,r=render(p);product_frame(r,'literal-name-output.jpg')
        from media import write_ass
        path=OUT/'literal-name.ass';copy_text=next(s['text'] for s in pl['segments'] if s['role']=='product');write_ass(path,copy_text,4,False)
        # Layout may wrap within the literal name; ignore only the generated line break.
        assert r'\{A1\}' in path.read_text(encoding='utf-8-sig').replace(r'\N','')
        return {'confirmed_name':'手冲{A1}咖啡','plan_copy':copy_text,'video':r['video'],'frame':'literal-name-output.jpg'}
    check('B09',b09)
    def b08():
        p=copy.deepcopy(base);p['goal']='attract';p['shots']=[s for s in p['shots'] if 'process' not in s['tags']]
        source=DATA/'audit2-fixtures/AUDIT2_process64.mp4'
        if not source.exists():
            process=next(s for s in base['shots'] if 'process' in s['tags'])
            run([FFMPEG,'-y','-v','error','-stream_loop','10','-i',DATA/process['media_id']/'source.mp4','-t','64','-c','copy',source])
        asset=upload(source.name);p['shots'].extend(copy.deepcopy(asset['shots']))
        for s in list(p['shots']):
            if s['media_id']==asset['id']:confirm(p,s,'process')
        pl=plan(p);product=next(s for s in pl['segments'] if s['role']=='product');interior=next(s for s in pl['segments'] if s['role']=='interior')
        segments=[product]
        for s in p['shots']:
            if s['media_id']==asset['id']:
                text,refs=caption_for('process',p['facts'],p['goal']);segments.append({'shot_id':s['id'],'role':'process','start':s['start'],'end':s['end'],'text':text,'fact_ids':refs})
        segments.append(interior);pl['segments']=segments
        validation=api('/api/validate',{'project':p,'plan':pl});rendering=api('/api/render',{'project':p,'plan':pl})
        assert validation[0]==rendering[0]==400 and '成片' in validation[1]['error']
        assert '总旁白' not in validation[1]['error']
        from audio import fitted_duration
        fixed=sum(fitted_duration(s['text'],s['end']-s['start'],s['role']) for s in (product,interior))
        shorter=copy.deepcopy(pl);shorter['segments']=[copy.deepcopy(product)]+copy.deepcopy(segments[1:6])+[copy.deepcopy(interior)]
        for s in shorter['segments'][1:-1]:s['end']=s['start']+(44.5-fixed)/5
        code,checked=api('/api/validate',{'project':p,'plan':shorter});assert code==200 and abs(checked['plan']['estimated_seconds']-44.5)<.01
        near=done(api('/api/render',{'project':p,'plan':shorter}))
        assert abs(near['metrics']['metadata']['duration']-44.5)<.1
        for s in shorter['segments'][1:-1]:s['end']+=.2
        above=api('/api/validate',{'project':p,'plan':shorter});assert above[0]==400 and '45.50' in above[1]['error']
        return {'segments':len(segments),'validate_http':validation[0],'render_http':rendering[0],'error':validation[1]['error'],'no_job_accepted':True,
                'near_limit_positive':{'estimated_seconds':44.5,'actual_seconds':near['metrics']['metadata']['duration'],'video':near['video']},'above_limit_http':above[0]}
    check('B08',b08)
    def b10():
        normal=plan(base);values=[None,[],{'goal':base['goal'],'synthetic':True,'timing_verified':True,'segments':None}]
        for bad in (None,[],{'shot_id':[],'role':'product'}):
            value=copy.deepcopy(normal);value['segments'][0]=bad;values.append(value)
        replies=[api('/api/validate',{'project':base,'plan':value}) for value in values]
        assert all(c==400 and 'attribute' not in r['error'] for c,r in replies)
        return [{'http':c,'error':r['error']} for c,r in replies]
    check('B10',b10)
    def b12():
        clone=DATA/'second-fixes-model-isolation';clone.mkdir(exist_ok=True)
        for src in ROOT.glob('*.py'):shutil.copy2(src,clone/src.name)
        (clone/'evidence').mkdir(exist_ok=True);shutil.copy2(ROOT/'evidence/local-model-lock.json',clone/'evidence/local-model-lock.json')
        model=clone/'.models/chinese-clip-onnx/onnx';model.mkdir(parents=True,exist_ok=True);(model/'model_quantized.onnx').write_bytes(b'x')
        worker="import json,server,threading,urllib.request; s=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=s.serve_forever,daemon=True).start();r=json.load(urllib.request.urlopen('http://127.0.0.1:'+str(s.server_port)+'/api/health'));print(json.dumps(r['local_vision'],ensure_ascii=False));s.shutdown();s.server_close();server.pool.shutdown()"
        proc=subprocess.run([sys.executable,'-X','utf8','-c',worker],cwd=clone,capture_output=True,text=True,encoding='utf8',timeout=30);assert proc.returncode==0,proc.stderr
        bad=json.loads(proc.stdout);assert bad['ready'] is False
        healthy=api('/api/health')[1]['local_vision'];assert healthy['ready'] and healthy['state']=='loaded'
        return {'corrupt_isolated_model':bad,'healthy_primary':healthy,'primary_model_untouched':True}
    check('B12',b12)
    def controls():
        results={}
        for name in ('AUDIT2_plain.mp4','AUDIT2_autofocus.mp4'):
            asset=upload(name);p=with_asset(asset,'product');pl=plan(p)
            assert pl['renderable'];results[name]=[s['quality'] for s in asset['shots'] if not s['quality_issues']]
        grey=DATA/'audit2-fixtures/SECOND_grey.mp4'
        run([FFMPEG,'-y','-v','error','-f','lavfi','-i','color=c=gray:s=360x640:d=3','-c:v','libx264','-pix_fmt','yuv420p',grey])
        asset=upload(grey.name);assert all(s['quality_issues'] and s['quality']<=.1 for s in asset['shots'])
        return {'normal_and_autofocus':results,'grey_rejected':True}
    check('controls',controls)
    def migration():
        old=json.loads((OUT/'prores-project.json').read_text(encoding='utf8'))
        for s in old['shots']:s['analysis_version']=4
        facts=copy.deepcopy(old['facts']);code,out=api('/api/reconcile',{'project':old})
        assert code==200 and out['facts']==facts and all(not s['confirmed'] for s in out['shots'])
        assert all(s['analysis_version']==ANALYSIS_VERSION and s['review_url'] for s in out['shots'])
        return {'facts_preserved':True,'confirmations_revoked':True,'review_urls_present':True,'shots':len(out['shots'])}
    check('migration',migration)
    if not all(r['passed'] for r in records):sys.exit(1)
