"""Offline, phrase-timed narration with bounded speed and no long held frames."""
import json,re,shutil,subprocess
from pathlib import Path

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

def synthesize(text,work,prefix,available):
    cues=[];parts=[];cursor=0
    chunks=phrases(text)
    for i,phrase in enumerate(chunks):
        txt=work/f'{prefix}-{i}.txt';raw=work/f'{prefix}-{i}-raw.wav';trim=work/f'{prefix}-{i}.wav'
        txt.write_text(phrase,encoding='utf8')
        run(['powershell','-NoProfile','-NonInteractive','-File',ROOT/'synthesize.ps1','-InputPath',txt,'-OutputPath',raw])
        filt='silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04,areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04,areverse'
        run([FFMPEG,'-y','-v','error','-i',raw,'-af',filt,'-ar','48000','-ac','1',trim])
        length=duration(trim)
        if length<.08:raise ValueError('没有生成可用的人声，请检查系统中文语音。')
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
