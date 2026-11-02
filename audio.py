"""Offline, phrase-timed narration with bounded speed and no long held frames."""
import json,re,shutil,subprocess,hashlib,tempfile,threading
from pathlib import Path
from qwen_voice import PROFILE,PROFILE_ID,generate as generate_neural_voice
from text_rules import display_text

FFMPEG=shutil.which('ffmpeg');FFPROBE=shutil.which('ffprobe')
ROOT=Path(__file__).resolve().parent

def run(args,timeout=90):
    result=subprocess.run([str(x) for x in args],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=timeout)
    if result.returncode:raise ValueError('离线配音处理失败：'+result.stderr[-500:])
    return result.stdout

def duration(path):
    return float(json.loads(run([FFPROBE,'-v','error','-show_entries','format=duration','-of','json',path]))['format']['duration'])

def phrases(text,max_chars=26):
    pieces=[p.strip() for p in re.findall(r'[^。！？；]+[。！？；]?',text) if p.strip()]
    result=[]
    for p in pieces:
        while len(p)>max_chars:
            cut=max(p.rfind(c,0,max_chars) for c in ('，','、','：'))+1
            if cut<4:cut=max_chars
            result.append(p[:cut]);p=p[cut:]
        if p:result.append(p)
    if not result:raise ValueError('旁白不能为空。')
    return result

def _synthesize_uncached(text,work,prefix,available):
    cues=[];parts=[];cursor=0
    chunks=phrases(text)
    for i,phrase in enumerate(chunks):
        raw=work/f'{prefix}-{i}-raw.wav';trim=work/f'{prefix}-{i}.wav'
        phrase_key=hashlib.sha256((PROFILE_ID+'\0'+phrase).encode('utf8')).hexdigest()
        phrase_folder=ROOT/'data/voice-phrases';phrase_folder.mkdir(parents=True,exist_ok=True)
        cached=phrase_folder/(phrase_key+'.wav');metrics=phrase_folder/(phrase_key+'.json')
        if not (cached.is_file() and metrics.is_file()):
            info=generate_neural_voice(phrase,raw)
            shutil.copyfile(raw,cached)
            metrics.write_text(json.dumps({**info,'text':phrase,'profile_id':PROFILE_ID},ensure_ascii=False),encoding='utf8')
        else:shutil.copyfile(cached,raw)
        filt='silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04,areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04,areverse'
        run([FFMPEG,'-y','-v','error','-i',raw,'-af',filt,'-ar','48000','-ac','1',trim])
        length=duration(trim)
        if length<.08:raise ValueError('开源女声没有生成可用的人声，请重试或检查配音日志。')
        cues.append({'start':cursor,'end':cursor+length,'text':phrase})
        parts.append(trim);cursor+=length
        if i<len(chunks)-1:
            gap=work/f'{prefix}-{i}-gap.wav'
            run([FFMPEG,'-y','-v','error','-f','lavfi','-i','anullsrc=r=48000:cl=mono','-t','0.14',gap])
            parts.append(gap);cursor+=.14
    speed=max(1,cursor/max(.1,available-.08))
    if speed>1.18:
        raise ValueError(f'本段旁白约需{cursor:.1f}秒，镜头仅{available:.1f}秒。请缩短事实文案或提供更长镜头；系统不使用长停帧凑时长。')
    speed=round(speed,5)
    listing=work/f'{prefix}-audio.txt';listing.write_text('\n'.join(f"file '{p.as_posix()}'" for p in parts),encoding='utf8')
    final=work/f'{prefix}-voice.wav'
    run([FFMPEG,'-y','-v','error','-f','concat','-safe','0','-i',listing,'-af',f'atempo={speed},alimiter=limit=0.95:level=false','-ar','48000','-ac','1',final])
    measured=duration(final)
    for cue in cues:
        cue['start']=round(min(measured,cue['start']/speed),4)
        cue['end']=round(min(measured,cue['end']/speed),4)
    return final,measured,cues,speed

_voice_lock=threading.RLock()

def prepare_voice(text):
    """Measure the real speech once; reuse the same audio for planning/rendering."""
    text=display_text(text)
    if not text.strip():raise ValueError('旁白不能为空。')
    if '<|' in text or '|>' in text:raise ValueError('旁白含模型控制标记，请改为普通文字后重新确认。')
    key=hashlib.sha256((PROFILE_ID+'\0'+text).encode('utf8')).hexdigest()
    folder=ROOT/'data/voice-cache';folder.mkdir(parents=True,exist_ok=True)
    wav=folder/(key+'.wav');meta=folder/(key+'.json')
    with _voice_lock:
        if not (wav.is_file() and meta.is_file()):
            with tempfile.TemporaryDirectory(prefix='linjing-preflight-') as tmp:
                natural,length,cues,_=_synthesize_uncached(text,Path(tmp),'natural',10000)
                shutil.copyfile(natural,wav)
                meta.write_text(json.dumps({'duration':length,'cues':cues,'text':text,'voice':PROFILE,'profile_id':PROFILE_ID},ensure_ascii=False),encoding='utf8')
        info=json.loads(meta.read_text(encoding='utf8'))
    return wav,info['duration'],info['cues']

def synthesize(text,work,prefix,available):
    natural,length,cues=prepare_voice(text)
    speed=round(max(1,length/max(.1,available-.08)),5)
    if speed>1.18:
        raise ValueError(f'本段旁白约需{length:.1f}秒，镜头仅{available:.1f}秒。请补充足够长的素材或调整文案；系统不使用长停帧凑时长。')
    final=work/f'{prefix}-voice.wav'
    run([FFMPEG,'-y','-v','error','-i',natural,'-af',f'atempo={speed}','-ar','48000','-ac','1',final])
    measured=duration(final)
    adjusted=[{**c,'start':round(min(measured,c['start']/speed),4),'end':round(min(measured,c['end']/speed),4)} for c in cues]
    return final,measured,adjusted,speed

def fitted_duration(text,available,role):
    """Use the exact fitted audio for both preflight and rendering duration."""
    if role=='process':return available
    with tempfile.TemporaryDirectory(prefix='linjing-fit-') as tmp:
        _,measured,_,_=synthesize(text,Path(tmp),'check',available)
    return min(available,max(2.5,measured+.08))
