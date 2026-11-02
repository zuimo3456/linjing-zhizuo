"""Local media analysis and deterministic rendering. No model downloads."""
from __future__ import annotations
import json, math, shutil, subprocess, tempfile, time, uuid
from fractions import Fraction
from pathlib import Path
from planner import validate_plan,segment_clips,segment_seconds
from text_rules import display_text

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
FFMPEG=shutil.which('ffmpeg')
FFPROBE=shutil.which('ffprobe')
ANALYSIS_VERSION=7

def square_pixel_scale(width,height):
    # reset_sar includes the input display aspect ratio in proportional scaling.
    return f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2:reset_sar=1'

def frame_quality(frame):
    import cv2
    gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    sharp=float(cv2.Laplacian(gray,cv2.CV_64F).var());light=float(gray.mean())
    quality=min(1,sharp/180)*.6+max(0,1-abs(light-128)/128)*.4
    issues=[]
    if float(gray.std())<3:issues.append('画面接近纯色，没有可辨认的内容')
    elif sharp<5:issues.append('画面严重模糊，细节不足')
    if light<12 or light>245:issues.append('画面过暗或过曝')
    return quality,light,sharp,issues

def quality_ranges(cap,a,b):
    """Keep bad intervals visible, but recover >=1s continuous usable intervals."""
    import cv2
    fps=12;count=max(1,int((b-a)*fps+.001));cap.set(cv2.CAP_PROP_POS_MSEC,a*1000)
    runs=[];start=a;previous=None
    for n in range(count):
        ok,frame=cap.read()
        if not ok:break
        usable=not frame_quality(frame)[3]
        at=min(b,a+n/fps)
        if previous is not None and usable!=previous:
            runs.append((start,at,previous));start=at
        previous=usable
    if previous is None:return [(a,b)]
    runs.append((start,b,previous))
    # A single all-good/all-bad interval retains the original scene boundaries.
    if len(runs)==1:return [(a,b)]
    return [(x,y) for x,y,_ in runs if y>x]

def run(args, timeout=180):
    try:p=subprocess.run([str(x) for x in args],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=timeout)
    except subprocess.TimeoutExpired:raise ValueError('视频处理超时，请缩短素材或重新导出后再试。') from None
    if p.returncode:
        log=DATA/'diagnostics';log.mkdir(exist_ok=True,parents=True);code=uuid.uuid4().hex[:12]
        (log/(code+'.txt')).write_text(p.stderr,encoding='utf8')
        raise ValueError(f'视频无法读取或处理，可能已损坏或格式不兼容。请重新导出为MP4再试。错误编号：{code}')
    return p.stdout

def probe(path):
    obj=json.loads(run([FFPROBE,'-v','error','-show_format','-show_streams','-of','json',path]))
    video=next((s for s in obj.get('streams',[]) if s['codec_type']=='video'),None)
    if not video: raise ValueError('文件中没有视频轨道。')
    container_duration=float(obj['format']['duration']);format_start=float(obj['format'].get('start_time',0))
    video_start=float(video.get('start_time',format_start));offset=max(0.,video_start-format_start)
    try:video_duration=float(video['duration'])
    except (KeyError,ValueError,TypeError):
        try:video_duration=float(video['duration_ts'])*float(Fraction(video['time_base']))
        except (KeyError,ValueError,TypeError,ZeroDivisionError):video_duration=container_duration-offset
    if not all(math.isfinite(v) for v in (container_duration,format_start,video_start,offset,video_duration)) or video_duration<=0:
        raise ValueError('视频时间信息无效，请重新导出为统一起点的MP4。')
    return {'duration':container_duration,'video_duration':video_duration,'format_start':format_start,'video_start':video_start,'video_offset':offset,'width':video['width'],'height':video['height'],
            'audio':any(s['codec_type']=='audio' for s in obj['streams']),
            'color_transfer':video.get('color_transfer'),'color_primaries':video.get('color_primaries'),
            'color_space':video.get('color_space'),'pixel_format':video.get('pix_fmt')}

def analyze(path, media_id, name):
    import cv2
    from scenedetect import detect, ContentDetector
    meta=probe(path)
    duration=meta.get('video_duration',meta['duration']);source_offset=meta.get('video_offset',0.)
    if not 1<=duration<=180: raise ValueError('每段视频画面需要在1—180秒之间。')
    if meta.get('color_transfer') in ('smpte2084','arib-std-b67'):
        raise ValueError('检测到HDR（PQ/HLG）素材。当前版本请先导出为普通SDR / BT.709视频再上传，以保证颜色可核对。原文件已保留。')
    folder=DATA/media_id; folder.mkdir(exist_ok=True,parents=True)
    preview=folder/'review.mp4';temporary=folder/'review-building.mp4'
    try:
        run([FFMPEG,'-y','-v','error','-copyts','-start_at_zero','-i',path,'-map','0:v:0','-map','0:a:0?',
             '-vf','setpts=PTS-STARTPTS,'+square_pixel_scale(720,1280),'-af',f'asetpts=PTS-{source_offset:.9f}/TB,aresample=async=1:first_pts=0',
             '-t',duration,'-c:v','libx264','-preset','veryfast','-crf','23','-threads','2',
             '-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',temporary])
        temporary.replace(preview)
    finally:
        temporary.unlink(missing_ok=True)
    # ASCII-safe temporary proxy, including when the user folder is Chinese.
    with tempfile.TemporaryDirectory(prefix='linjing-') as tmp:
        proxy=Path(tmp)/'proxy.mp4'
        run([FFMPEG,'-y','-v','error','-i',path,'-vf','setpts=PTS-STARTPTS,'+square_pixel_scale(640,360)+',fps=12','-t',duration,'-an','-c:v','libx264','-preset','ultrafast',proxy])
        scenes=detect(str(proxy),ContentDetector(threshold=25,min_scene_len=1),show_progress=False)
        ranges=[(a.get_seconds(),min(b.get_seconds(),duration)) for a,b in scenes if a.get_seconds()<duration]
        if not ranges: ranges=[(0,duration)]
        # Long static shots are broken into reviewable intervals, not semantic cuts.
        chunks=[]
        for a,b in ranges:
            while b-a>8: chunks.append((a,a+8)); a+=8
            if b>a: chunks.append((a,b))
        cap=cv2.VideoCapture(str(proxy)); shots=[]
        chunks=[interval for a,b in chunks for interval in quality_ranges(cap,a,b)]
        for i,(a,b) in enumerate(chunks):
            sampled=[];qualities=[];lights=[];sharps=[];issues=[]
            if b-a<1:issues.append('镜头短于1秒，请与原素材核对或重新拍摄')
            times=sorted(set(round(t,4) for t in [a+min(.025,(b-a)*.05),a+(b-a)*.2,a+(b-a)*.5,a+(b-a)*.8,b-min(.06,(b-a)*.05)]+
                             [a+n*.5 for n in range(1,int((b-a)/.5)+1) if a+n*.5<b-.06]))
            for j,at in enumerate(times):
                cap.set(cv2.CAP_PROP_POS_MSEC,at*1000); ok,frame=cap.read()
                if not ok:continue
                quality,light,sharp,frame_issues=frame_quality(frame)
                qualities.append(quality);issues.extend(frame_issues)
                lights.append(light);sharps.append(sharp)
                thumb=folder/(f'thumb-{i}.jpg' if j==2 else f'frame-{i}-{j}.jpg')
                ok,encoded=cv2.imencode('.jpg',frame)
                if ok:encoded.tofile(str(thumb));sampled.append({'time':round(source_offset+at,3),'url':f'/media/{media_id}/{thumb.name}'})
            if not sampled:continue
            if len(sampled)<len(times):issues.append('抽帧不完整，请重新上传检查')
            quality=round(min(qualities)*.4+sum(qualities)/len(qualities)*.6,3)
            if issues:quality=min(quality,.1)
            thumb_url=next((x['url'] for x in sampled if '/thumb-' in x['url']),sampled[0]['url'])
            shots.append({'id':f'{media_id}-{i}','media_id':media_id,'start':round(source_offset+a,3),'end':round(source_offset+b,3),
                          'review_start':round(a,3),'review_end':round(b,3),
                          'tags':['other'],'confirmed':False,'quality':quality,'brightness':round(sum(lights)/len(lights),2),
                          'sharpness':round(sum(sharps)/len(sharps),2),'label_source':'unlabeled','name':name,
                          'thumb':thumb_url,'frames':sampled,'analysis_version':ANALYSIS_VERSION,'quality_issues':list(dict.fromkeys(issues)),
                          'review_url':f'/media/{media_id}/review.mp4'})
        cap.release()
    from evidence_store import file_hash
    sha=file_hash(path);stat=Path(path).stat()
    for shot in shots:shot['source_sha256']=sha
    return {'id':media_id,'name':name,'meta':meta,'shots':shots,'synthetic':False,'analysis_version':ANALYSIS_VERSION,
            'review_url':f'/media/{media_id}/review.mp4','review_mapping':{'source_start':source_offset,'proxy_start':0,'time_scale':1},
            'source_sha256':sha,'source_bytes':stat.st_size,'source_mtime_ns':stat.st_mtime_ns,
            'coverage':{'total_seconds':duration,'source_start':source_offset,'source_end':source_offset+duration,'analyzed_end':max((s['end'] for s in shots),default=source_offset),
                        'short_or_unusable_intervals':[[s['start'],s['end']] for s in shots if s['quality_issues']],
                        'truncated':any('抽帧不完整，请重新上传检查' in s['quality_issues'] for s in shots) or max((s['end'] for s in shots),default=source_offset)<source_offset+duration-.001,
                        'sampling':'boundaries_and_max_0.5_second_gap; not_full_semantic_coverage'}}

def ass_time(t):
    cent=round(t*100); s,c=divmod(cent,100); m,s=divmod(s,60); h,m=divmod(m,60)
    return f'{h}:{m:02}:{s:02}.{c:02}'

def write_ass(path, text, duration, synthetic, cues=None):
    def escape(s):
        # libass supports \{ and \}; a word joiner prevents literal \N/\h
        # from becoming formatting while retaining the visible backslash.
        return s.replace('\\','\\\u2060').replace('{',r'\{').replace('}',r'\}').replace('\n',' ')
    # Lines are capped at 15 Chinese characters for a 720-wide mobile frame.
    body=''
    for cue in cues or [{'start':0,'end':duration,'text':text}]:
        literal=display_text(cue['text'])
        lines=[escape(literal[i:i+14]) for i in range(0,len(literal),14)]
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
            clips=segment_clips(seg);length=segment_seconds(seg)
            wav,spoken,cues,speed=synthesize(seg['text'],tmp,f'seg-{i}',length)
            duration=length if plan.get('pacing') or seg['role']=='process' or seg.get('clips') else min(length,max(2.5,spoken+.08))
            from pacing import narration_offset
            voice_offset=narration_offset(spoken,duration) if plan.get('pacing') else 0.
            cues=[{**c,'start':round(c['start']+voice_offset,4),'end':round(c['end']+voice_offset,4)} for c in cues]
            ass=tmp/f'caption-{i}.ass';write_ass(ass,seg['text'],duration,project.get('synthetic') is True,cues)
            ass_filter=str(ass).replace('\\','/').replace(':',r'\:')
            source=DATA/shots[seg['shot_id']]['media_id']/'source.mp4';source_start=seg['start']
            if seg.get('clips'):
                visuals=[]
                for ci,clip in enumerate(clips):
                    original=DATA/shots[clip['shot_id']]['media_id']/'source.mp4';visual=tmp/f'visual-{i}-{ci}.mp4'
                    filt=square_pixel_scale(720,1280)+',pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x17251e,setsar=1,fps=25'
                    run([FFMPEG,'-y','-v','error','-ss',clip['start'],'-t',clip['end']-clip['start'],'-i',original,
                         '-an','-vf',filt,'-c:v','libx264','-preset','veryfast','-crf','22','-threads','2','-pix_fmt','yuv420p',visual])
                    visuals.append(visual)
                listing=tmp/f'visual-{i}.txt';listing.write_text('\n'.join(f"file '{v.as_posix()}'" for v in visuals),encoding='utf8')
                source=tmp/f'group-{i}.mp4';source_start=0
                run([FFMPEG,'-y','-v','error','-f','concat','-safe','0','-i',listing,'-c','copy',source])
            if not source.is_file(): raise ValueError('本地素材缺失，请重新上传。')
            dest=tmp/f'part-{i}.mp4'
            # Preserve full frame. Refuse excessive narration instead of freezing.
            vf=square_pixel_scale(720,1280)+f',pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x17251e,setsar=1,fps=25,ass=filename=\'{ass_filter}\''
            run([FFMPEG,'-y','-v','error','-ss',source_start,'-t',length,'-i',source,'-i',wav,'-vf',vf,
                 '-map','0:v:0','-map','1:a:0','-af',f'adelay={round(voice_offset*48000)}S:all=1,apad','-t',duration,'-c:v','libx264','-preset','veryfast','-crf','22',
                 '-threads','2','-c:a','aac','-ar','48000','-ac','2','-pix_fmt','yuv420p',dest])
            rendered.append(dest); timings.append({'index':i,'start':round(cursor,3),'end':round(cursor+duration,3),'text':seg['text'],
                                                    'alignment':'measured_phrase_audio','held_frame_seconds':0,
                                                    'voice_speed':speed,'captions':cues,'voice_offset_seconds':voice_offset,'voice_seconds':spoken})
            if seg.get('clips'):
                offset=cursor;mapping=[]
                for clip in clips:
                    stop=offset+clip['end']-clip['start'];mapping.append({**clip,'output_start':round(offset,3),'output_end':round(stop,3)});offset=stop
                timings[-1]['visual_clips']=mapping
            cursor+=duration
        if cursor>45.000001: raise ValueError('成片总时长超过45秒，请减少片段或缩短画面区间。')
        listing=tmp/'parts.txt'; listing.write_text('\n'.join(f"file '{p.as_posix()}'" for p in rendered),encoding='utf8')
        run([FFMPEG,'-y','-v','error','-f','concat','-safe','0','-i',listing,'-c','copy','-movflags','+faststart',out/'result.mp4'])
    result_meta=probe(out/'result.mp4')
    if plan.get('pacing') and not 15<=result_meta['duration']<=30:
        raise ValueError(f'实际编码视频{result_meta["duration"]:.2f}秒，未满足15–30秒，请重新编排。')
    run([FFMPEG,'-y','-v','error','-ss','0.5','-i',out/'result.mp4','-frames:v','1',out/'cover.jpg'])
    from datetime import datetime,timezone
    report={'job_id':job_id,'created_at_utc':datetime.now(timezone.utc).isoformat(),'synthetic':project.get('synthetic') is True,
            'status':'technical_export_only','metadata':result_meta,'elapsed_seconds':round(time.perf_counter()-begun,3),
            'api_calls':0,'api_direct_cost_cny':0,'total_cost_cny':None,'cost_note':'本次本地运行没有付费API调用；电力、设备与人工成本未计量。',
            'tts':'Qwen3-TTS-1.7B CustomVoice · Vivian · local CUDA','timings':timings,'plan':plan,
            'acceptance':{'playback':'pending_browser_check','human_audio_visual_quality':'pending','merchant_willingness':'not_measured'},
            'analysis':project.get('vision_analysis'),
            'limitations':['画外音路径，不包含原声保留。','短句字幕按实际语音段测时，不是逐字对齐。','语义仍需确认；本地图文相似度不是商业事实验证。']}
    from qwen_voice import PROFILE,PROFILE_ID
    report['voice']={**PROFILE,'profile_id':PROFILE_ID,'human_listening':'pending'}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    (out/'project.json').write_text(json.dumps(project,ensure_ascii=False,indent=2),encoding='utf8')
    import zipfile
    with zipfile.ZipFile(out/'evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ['report.json','project.json','cover.jpg']: z.write(out/name,name)
    return {'video':f'/media/{job_id}/result.mp4','cover':f'/media/{job_id}/cover.jpg','report':f'/media/{job_id}/report.json',
            'bundle':f'/media/{job_id}/evidence.zip','metrics':report}
