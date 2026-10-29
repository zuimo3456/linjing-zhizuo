"""Local media analysis and deterministic rendering. No model downloads."""
from __future__ import annotations
import json, shutil, subprocess, tempfile, time, uuid
from pathlib import Path
from planner import validate_plan

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
FFMPEG=shutil.which('ffmpeg')
FFPROBE=shutil.which('ffprobe')

def run(args, timeout=180):
    p=subprocess.run([str(x) for x in args],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=timeout)
    if p.returncode:
        raise RuntimeError(p.stderr[-1600:] or '媒体工具执行失败。')
    return p.stdout

def probe(path):
    obj=json.loads(run([FFPROBE,'-v','error','-show_format','-show_streams','-of','json',path]))
    video=next((s for s in obj.get('streams',[]) if s['codec_type']=='video'),None)
    if not video: raise ValueError('文件中没有视频轨道。')
    return {'duration':float(obj['format']['duration']),'width':video['width'],'height':video['height'],
            'audio':any(s['codec_type']=='audio' for s in obj['streams'])}

def analyze(path, media_id, name):
    import cv2
    from scenedetect import detect, ContentDetector
    meta=probe(path)
    if not 1<=meta['duration']<=180: raise ValueError('每段素材需要在1—180秒之间。')
    folder=DATA/media_id; folder.mkdir(exist_ok=True,parents=True)
    # ASCII-safe temporary proxy, including when the user folder is Chinese.
    with tempfile.TemporaryDirectory(prefix='linjing-') as tmp:
        proxy=Path(tmp)/'proxy.mp4'
        run([FFMPEG,'-y','-v','error','-i',path,'-vf','scale=-2:360,fps=6','-an','-c:v','libx264','-preset','ultrafast',proxy])
        scenes=detect(str(proxy),ContentDetector(threshold=25,min_scene_len=6),show_progress=False)
        ranges=[(a.get_seconds(),min(b.get_seconds(),meta['duration'])) for a,b in scenes]
        if not ranges: ranges=[(0,meta['duration'])]
        # Long static shots are broken into reviewable intervals, not semantic cuts.
        chunks=[]
        for a,b in ranges:
            while b-a>8: chunks.append((a,a+8)); a+=8
            if b-a>=1: chunks.append((a,b))
        cap=cv2.VideoCapture(str(proxy)); shots=[]
        for i,(a,b) in enumerate(chunks[:24]):
            sampled=[];qualities=[];lights=[];sharps=[]
            for j,fraction in enumerate((.2,.5,.8)):
                at=a+(b-a)*fraction
                cap.set(cv2.CAP_PROP_POS_MSEC,at*1000); ok,frame=cap.read()
                if not ok:continue
                gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
                sharp=float(cv2.Laplacian(gray,cv2.CV_64F).var());light=float(gray.mean())
                qualities.append(min(1,sharp/180)*.6+max(0,1-abs(light-128)/128)*.4)
                lights.append(light);sharps.append(sharp)
                thumb=folder/(f'thumb-{i}.jpg' if j==1 else f'frame-{i}-{j}.jpg')
                ok,encoded=cv2.imencode('.jpg',frame)
                if ok:encoded.tofile(str(thumb));sampled.append({'time':round(at,3),'url':f'/media/{media_id}/{thumb.name}'})
            if not sampled:continue
            quality=round(min(qualities)*.4+sum(qualities)/len(qualities)*.6,3)
            thumb_url=next((x['url'] for x in sampled if '/thumb-' in x['url']),sampled[0]['url'])
            shots.append({'id':f'{media_id}-{i}','media_id':media_id,'start':round(a,3),'end':round(b,3),
                          'tags':['other'],'confirmed':False,'quality':quality,'brightness':round(sum(lights)/len(lights),2),
                          'sharpness':round(sum(sharps)/len(sharps),2),'label_source':'unlabeled','name':name,
                          'thumb':thumb_url,'frames':sampled,'analysis_version':2})
        cap.release()
    return {'id':media_id,'name':name,'meta':meta,'shots':shots,'synthetic':False}

def ass_time(t):
    cent=round(t*100); s,c=divmod(cent,100); m,s=divmod(s,60); h,m=divmod(m,60)
    return f'{h}:{m:02}:{s:02}.{c:02}'

def write_ass(path, text, duration, synthetic, cues=None):
    def escape(s): return s.replace('\\','\\\\').replace('{','').replace('}','').replace('\n',' ')
    # Lines are capped at 15 Chinese characters for a 720-wide mobile frame.
    body=''
    for cue in cues or [{'start':0,'end':duration,'text':text}]:
        lines=[escape(cue['text'][i:i+14]) for i in range(0,len(cue['text']),14)]
        if len(lines)>2:raise ValueError('单条字幕超过两行，请缩短文案。')
        body+=f'Dialogue: 0,{ass_time(cue["start"])},{ass_time(cue["end"])},Main,,0,0,0,,'+r'\N'.join(lines)+'\n'
    if synthetic:
        body+=f'Dialogue: 1,0:00:00.00,{ass_time(duration)},Mark,,0,0,0,,模拟素材 · 非真实商户\n'
    path.write_text('[Script Info]\nScriptType: v4.00+\nPlayResX: 720\nPlayResY: 1280\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Main,Microsoft YaHei,34,&H00FFFFFF,&H00FFFFFF,&H001B221E,&H77000000,0,0,0,0,100,100,1,0,1,2,0,2,38,38,245,1\nStyle: Mark,Microsoft YaHei,23,&H00FFFFFF,&H00FFFFFF,&H001B221E,&H77000000,0,0,0,0,100,100,0,0,1,2,0,8,30,30,42,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'+body,encoding='utf-8-sig')

def render(project,plan,job_id,progress):
    validate_plan(project,plan)
    begun=time.perf_counter(); out=DATA/job_id; out.mkdir(parents=True,exist_ok=True)
    shots={s['id']:s for s in project['shots']}; timings=[]; segments=plan['segments']
    with tempfile.TemporaryDirectory(prefix='linjing-render-') as temp:
        tmp=Path(temp); rendered=[]; cursor=0
        for i,seg in enumerate(segments):
            progress(f'合成第 {i+1}/{len(segments)} 段旁白与画面')
            from audio import synthesize
            length=seg['end']-seg['start']
            wav,spoken,cues,speed=synthesize(seg['text'],tmp,f'seg-{i}',length)
            duration=min(length,max(2.5,spoken+.08))
            ass=tmp/f'caption-{i}.ass';write_ass(ass,seg['text'],duration,project.get('synthetic') is True,cues)
            ass_filter=str(ass).replace('\\','/').replace(':',r'\:')
            source=DATA/shots[seg['shot_id']]['media_id']/'source.mp4'
            if not source.is_file(): raise ValueError('本地素材缺失，请重新上传。')
            dest=tmp/f'part-{i}.mp4'
            # Preserve full frame. Refuse excessive narration instead of freezing.
            vf=f'scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x17251e,setsar=1,fps=25,ass=filename=\'{ass_filter}\''
            run([FFMPEG,'-y','-v','error','-ss',seg['start'],'-t',length,'-i',source,'-i',wav,'-vf',vf,
                 '-map','0:v:0','-map','1:a:0','-af','apad','-t',duration,'-c:v','libx264','-preset','veryfast','-crf','22',
                 '-threads','2','-c:a','aac','-ar','48000','-ac','2','-pix_fmt','yuv420p',dest])
            rendered.append(dest); timings.append({'index':i,'start':round(cursor,3),'end':round(cursor+duration,3),'text':seg['text'],
                                                    'alignment':'measured_phrase_audio','held_frame_seconds':0,
                                                    'voice_speed':speed,'captions':cues})
            cursor+=duration
        if cursor>45: raise ValueError('总旁白超过45秒，请缩短事实字段。')
        listing=tmp/'parts.txt'; listing.write_text('\n'.join(f"file '{p.as_posix()}'" for p in rendered),encoding='utf8')
        run([FFMPEG,'-y','-v','error','-f','concat','-safe','0','-i',listing,'-c','copy','-movflags','+faststart',out/'result.mp4'])
    result_meta=probe(out/'result.mp4')
    run([FFMPEG,'-y','-v','error','-ss','0.5','-i',out/'result.mp4','-frames:v','1',out/'cover.jpg'])
    from datetime import datetime,timezone
    report={'job_id':job_id,'created_at_utc':datetime.now(timezone.utc).isoformat(),'synthetic':project.get('synthetic') is True,
            'status':'technical_export_only','metadata':result_meta,'elapsed_seconds':round(time.perf_counter()-begun,3),
            'api_calls':0,'api_direct_cost_cny':0,'total_cost_cny':None,'cost_note':'本次本地运行没有付费API调用；电力、设备与人工成本未计量。',
            'tts':'Windows Microsoft Huihui Desktop offline','timings':timings,'plan':plan,
            'acceptance':{'playback':'pending_browser_check','human_audio_visual_quality':'pending','merchant_willingness':'not_measured'},
            'analysis':project.get('vision_analysis'),
            'limitations':['画外音路径，不包含原声保留。','短句字幕按实际语音段测时，不是逐字对齐。','语义仍需确认；本地图文相似度不是商业事实验证。']}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    (out/'project.json').write_text(json.dumps(project,ensure_ascii=False,indent=2),encoding='utf8')
    import zipfile
    with zipfile.ZipFile(out/'evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ['report.json','project.json','cover.jpg']: z.write(out/name,name)
    return {'video':f'/media/{job_id}/result.mp4','cover':f'/media/{job_id}/cover.jpg','report':f'/media/{job_id}/report.json',
            'bundle':f'/media/{job_id}/evidence.zip','metrics':report}
