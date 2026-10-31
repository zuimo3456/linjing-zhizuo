"""Third exploratory audit. No application edits or primary-project saves."""
from pathlib import Path
import copy,json,sys,time,urllib.request,urllib.error,urllib.parse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from media import DATA,FFMPEG,run
from demo import create_demo
OUT=ROOT/'evidence/audit3-2026-10-31';OUT.mkdir(exist_ok=True)
FIX=DATA/'audit3-fixtures';FIX.mkdir(exist_ok=True)
ONLY=sys.argv[sys.argv.index('--only')+1] if '--only' in sys.argv else None
records=json.loads((OUT/'results.json').read_text(encoding='utf8'))['cases'] if ONLY and (OUT/'results.json').exists() else []
def api(path,obj=None,raw=None):
    data=raw if raw is not None else (json.dumps(obj,ensure_ascii=False).encode('utf8') if obj is not None else None)
    try:
        with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:4180'+path,data=data,headers={'Content-Type':'application/octet-stream' if raw is not None else 'application/json'}),timeout=150) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
def job(response):
    code,obj=response
    if code!=202:return {'http':code,'response':obj}
    for _ in range(1800):
        _,j=api('/api/jobs/'+obj['job_id'])
        if j['status'] in ('done','error'):return j
        time.sleep(.1)
    return {'status':'timeout','job_id':obj['job_id']}
def save():
    (OUT/'results.json').write_text(json.dumps({'date':'2026-10-31','scope':'Exploratory technical fixtures; no claim of real-merchant accuracy','cases':records},ensure_ascii=False,indent=2),encoding='utf8')
def case(cid,title,fn):
    if ONLY and cid!=ONLY:return
    records[:]=[r for r in records if r['id']!=cid];begun=time.perf_counter()
    try:r=fn()
    except Exception as e:r={'harness_exception':type(e).__name__,'message':str(e)}
    records.append({'id':cid,'title':title,'elapsed_seconds':round(time.perf_counter()-begun,3),'result':r});save()
    print(cid,title,json.dumps(r,ensure_ascii=False)[:1100],flush=True)
def upload(path):
    j=job(api('/api/upload?name='+urllib.parse.quote(path.name),raw=path.read_bytes()))
    if j.get('status')!='done':raise RuntimeError(str(j))
    return j['result']
def fixture(name,args):
    path=FIX/name
    if not path.exists():run([FFMPEG,'-y','-v','error',*args,path])
    return path
def replace_product(asset):
    p=copy.deepcopy(base);p['shots']=[s for s in p['shots'] if 'product' not in s['tags']]+copy.deepcopy(asset['shots'])
    for i,s in enumerate(p['shots']):
        if s['media_id']!=asset['id'] or s['quality_issues'] or s['end']-s['start']<1:continue
        s['tags']=['product']
        for mode in ('purpose','product'):
            code,r=api('/api/confirm-shot',{'project':p,'shot_id':s['id'],'mode':mode,'checked':True})
            if code!=200:raise RuntimeError(str(r))
            p['shots'][i]=r['shot']
    return p
def plan(p):
    code,r=api('/api/plan',{'project':p});return {'http':code,**r}
def render(p,pl):
    j=job(api('/api/render',{'project':p,'plan':pl}))
    if j.get('status')!='done':return j
    return j['result']
def snapshot(path,at,name):
    dest=OUT/name;run([FFMPEG,'-y','-v','error','-ss',at,'-i',path,'-frames:v','1',dest]);return str(dest)
def asset_summary(a):
    return {'id':a['id'],'meta':a['meta'],'coverage':a['coverage'],'intervals':[{'start':s['start'],'end':s['end'],'quality':s['quality'],'issues':s['quality_issues']} for s in a['shots']]}
def save_project(name,p):(OUT/name).write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':
    base=create_demo();coffee=ROOT/'evidence/public-test-images/coffee.png';cat=ROOT/'evidence/public-test-images/chelsea.png'
    ordinary=FIX/'A3_01_plain.mp4'
    if not ordinary.exists():
        import shutil
        shutil.copy2(DATA/'audit2-fixtures/AUDIT2_plain.mp4',ordinary)
    (FIX/'A3_02_corrupt.mp4').write_bytes(b'Third audit deliberately invalid MP4')
    if not (FIX/'A3_03_after_corrupt.mp4').exists():
        import shutil
        shutil.copy2(ordinary,FIX/'A3_03_after_corrupt.mp4')
    def baseline():
        a=upload(ordinary);p=replace_product(a);pl=plan(p);r=render(p,pl)
        save_project('baseline-project.json',p)
        return {'asset':asset_summary(a),'plan_ready':pl.get('renderable'),'video':r.get('video'),'metadata':r.get('metrics',{}).get('metadata')}
    case('T01','正常咖啡素材完整链路对照',baseline)
    def dissolve():
        graph="[0:v]scale=600:400,setsar=1,format=yuv420p[a];[1:v]scale=600:400,setsar=1,format=yuv420p[b];[a][b]blend=all_expr='A*(1-if(between(T,2,3),sin((T-2)*PI),0))+B*if(between(T,2,3),sin((T-2)*PI),0)'"
        path=fixture('A3_dissolve_cat.mp4',['-loop','1','-framerate','25','-i',coffee,'-loop','1','-framerate','25','-i',cat,'-filter_complex',graph,'-t','8','-c:v','libx264','-preset','ultrafast','-threads','2','-pix_fmt','yuv420p'])
        a=upload(path);p=replace_product(a)
        analyzed=job(api('/api/local-analyze',{'project':p}))
        candidates=[{'start':s['start'],'end':s['end'],'candidate':s.get('local_candidate'),'frames':s['frames']} for s in analyzed.get('result',{}).get('shots',[]) if s['media_id']==a['id']]
        # This explicit confirmation simulates a reviewer missing the inserted content;
        # AI never confirms automatically. The mixed source is NOT true pure coffee.
        human_roles={s['id']:s['tags'] for s in p['shots']};p=analyzed['result']
        for i,s in enumerate(p['shots']):
            s['tags']=human_roles[s['id']]
            for mode in (['purpose','product'] if 'product' in s['tags'] else ['purpose']):
                code,response=api('/api/confirm-shot',{'project':p,'shot_id':s['id'],'mode':mode,'checked':True})
                assert code==200,response;p['shots'][i]=response['shot']
        pl=plan(p);r=render(p,pl) if pl.get('renderable') else {}
        save_project('dissolve-project.json',p)
        snapshot(path,2.5,'dissolve-source-cat.jpg')
        if r.get('video'):
            product_index=next(i for i,s in enumerate(pl['segments']) if s['role']=='product')
            snapshot(DATA/r['video'].split('/')[2]/'result.mp4',r['metrics']['timings'][product_index]['start']+2.5,'dissolve-output-cat.jpg')
        return {'asset':asset_summary(a),'local_candidates':candidates,'confirmation_note':'After AI clears confirmations, explicitly reconfirmed purpose and product through API to simulate human oversight; not automatic AI confirmation','plan_ready':pl.get('renderable'),'video':r.get('video')}
    case('T02','溶解转场内混入猫画面',dissolve)
    def timestamp():
        path=fixture('A3_timestamp_offset.mp4',['-i',ordinary,'-c','copy','-output_ts_offset','5'])
        a=upload(path);p=replace_product(a);pl=plan(p)
        raw=json.loads(run(['ffprobe','-v','error','-show_entries','format=start_time,duration:stream=start_time,duration','-of','json',path]))
        review=json.loads(run(['ffprobe','-v','error','-show_entries','format=start_time,duration','-of','json',DATA/a['id']/'review.mp4']))
        return {'source_timing':raw,'review_timing':review,'asset':asset_summary(a),'mapping':a['review_mapping'],'plan_ready':pl.get('renderable')}
    case('T03','有效视频带非零起始时间戳',timestamp)
    def vfr():
        path=fixture('A3_vfr.mp4',['-loop','1','-framerate','60','-i',coffee,'-vf',"select='if(lt(t,3),not(mod(n,6)),not(mod(n,2)))'",'-t','6','-fps_mode','vfr','-c:v','libx264','-preset','ultrafast','-threads','2','-pix_fmt','yuv420p'])
        a=upload(path);p=replace_product(a);pl=plan(p);r=render(p,pl)
        return {'asset':asset_summary(a),'plan_ready':pl.get('renderable'),'video':r.get('video'),'metadata':r.get('metrics',{}).get('metadata')}
    case('T04','手机式可变帧率素材',vfr)
    def rotation():
        path=fixture('A3_rotate90_matrix.mp4',['-display_rotation','90','-i',ordinary,'-c','copy'])
        source=json.loads(run(['ffprobe','-v','error','-show_entries','stream_side_data','-of','json',path]))
        assert source['streams'][0].get('side_data_list'),source
        a=upload(path);p=replace_product(a);pl=plan(p);r=render(p,pl)
        review=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,sample_aspect_ratio','-of','json',DATA/a['id']/'review.mp4']))
        if r.get('video'):
            i=next(i for i,s in enumerate(pl['segments']) if s['role']=='product');snapshot(DATA/r['video'].split('/')[2]/'result.mp4',r['metrics']['timings'][i]['start']+1,'rotation-output.jpg')
        return {'source_display_matrix':source,'asset':asset_summary(a),'review':review,'plan_ready':pl.get('renderable'),'video':r.get('video')}
    case('T05','手机90度旋转元数据',rotation)
    def short_clips():
        path=fixture('A3_two_seconds.mp4',['-i',ordinary,'-t','2','-c','copy'])
        assets=[upload(path),upload(path)];p=replace_product(assets[0]);second=copy.deepcopy(assets[1]['shots'][0]);second['tags']=['product'];p['shots'].append(second)
        for mode in ('purpose','product'):
            code,r=api('/api/confirm-shot',{'project':p,'shot_id':second['id'],'mode':mode,'checked':True});assert code==200,r;p['shots'][-1]=r['shot']
        pl=plan(p)
        return {'confirmed_product_clips':2,'individual_seconds':2,'total_product_seconds':4,'plan_ready':pl.get('renderable'),'missing':pl.get('missing')}
    case('T06','多段清晰短素材合计足够但单段不足',short_clips)
    def carriage_return():
        p=copy.deepcopy(base);f=next(f for f in p['facts'] if f['kind']=='product');f['value']='手冲\rA1咖啡'
        i=next(i for i,s in enumerate(p['shots']) if 'product' in s['tags'])
        code,r=api('/api/confirm-shot',{'project':p,'shot_id':p['shots'][i]['id'],'mode':'product','checked':True});assert code==200,r;p['shots'][i]=r['shot']
        pl=plan(p);result=render(p,pl);save_project('carriage-return-project.json',p)
        if result.get('video'):
            n=next(i for i,s in enumerate(pl['segments']) if s['role']=='product');snapshot(DATA/result['video'].split('/')[2]/'result.mp4',result['metrics']['timings'][n]['start']+1,'carriage-return-output.jpg')
        from media import write_ass
        text=next(s['text'] for s in pl['segments'] if s['role']=='product');write_ass(OUT/'carriage-return.ass',text,5,False)
        return {'confirmed_value':f['value'],'plan_text':text,'plan_ready':pl.get('renderable'),'render_status':result.get('status','exported' if result.get('video') else 'unknown'),'video':result.get('video')}
    case('T07','导入的商品名称含回车字符',carriage_return)
    def hdr():
        filt='zscale=matrixin=gbr:transferin=iec61966-2-1:primariesin=bt709:rangein=full:matrix=bt2020nc:transfer=smpte2084:primaries=bt2020:range=limited:npl=100,format=yuv420p10le'
        path=fixture('A3_HDR_PQ.mp4',['-loop','1','-framerate','25','-i',coffee,'-vf',filt,'-t','8','-c:v','libx265','-preset','ultrafast','-x265-params','log-level=error:pools=2:frame-threads=2','-pix_fmt','yuv420p10le','-color_primaries','bt2020','-color_trc','smpte2084','-colorspace','bt2020nc'])
        a=upload(path);p=replace_product(a);pl=plan(p);r=render(p,pl) if pl.get('renderable') else {}
        if r.get('video'):
            n=next(i for i,s in enumerate(pl['segments']) if s['role']=='product');snapshot(DATA/r['video'].split('/')[2]/'result.mp4',r['metrics']['timings'][n]['start']+1,'hdr-output.jpg')
        source=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=color_space,color_transfer,color_primaries,pix_fmt','-of','json',path]))
        return {'source_color':source,'asset':asset_summary(a),'plan_ready':pl.get('renderable'),'video':r.get('video')}
    case('T08','正确转换为PQ的10bit HDR素材',hdr)
