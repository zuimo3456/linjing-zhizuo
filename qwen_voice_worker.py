"""Isolated CUDA inference process. JSON stdin/stdout; model logs go to stderr."""
import contextlib,hashlib,json,os,sys,time
from pathlib import Path

os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'

def reply(value):
    print(json.dumps(value,ensure_ascii=False),flush=True)

def main():
    from setup_qwen_voice import DEST,WEIGHTS,REVISION,file_hash
    from qwen_voice import SPEAKER,INSTRUCT,PROFILE
    started=time.perf_counter()
    try:
        manifest=json.loads((DEST/'verified-manifest.json').read_text(encoding='utf8'))
        if manifest['revision']!=REVISION:raise ValueError('模型版本不匹配，请重新安装并校验。')
        for name,sha in manifest['files'].items():
            target=(DEST/name).resolve()
            if not target.is_relative_to(DEST.resolve()) or file_hash(target)!=sha:
                raise ValueError('模型文件校验失败：'+name)
        for name,sha in WEIGHTS.items():
            if manifest['files'].get(name)!=sha:raise ValueError('模型权重不是固定版本。')
        with contextlib.redirect_stdout(sys.stderr):
            import numpy as np
            import soundfile as sf
            import torch
            from qwen_tts import Qwen3TTSModel
            if not torch.cuda.is_available():raise ValueError('未找到可用CUDA显卡；此版本需要本机NVIDIA显卡。')
            torch.set_num_threads(4)
            model=Qwen3TTSModel.from_pretrained(str(DEST),device_map='cuda:0',dtype=torch.bfloat16,
                                              attn_implementation='sdpa',local_files_only=True)
        reply({'ok':True,'ready':True,'load_seconds':round(time.perf_counter()-started,3)})
    except Exception as exc:
        reply({'ok':False,'error':str(exc)});return
    for line in sys.stdin:
        try:
            request=json.loads(line);text=request['text'];path=Path(request['path'])
            if not isinstance(text,str) or not text.strip() or len(text)>26 or '<|' in text or '|>' in text:
                raise ValueError('旁白不是有效的普通短句。')
            seed=int(hashlib.sha256(text.encode()).hexdigest()[:8],16)
            begun=time.perf_counter()
            with contextlib.redirect_stdout(sys.stderr),torch.inference_mode():
                torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
                wavs,sr=model.generate_custom_voice(text=text,language='Chinese',speaker=SPEAKER,
                                                    instruct=INSTRUCT,max_new_tokens=250,
                                                    **PROFILE['sampling'])
            wave=np.asarray(wavs[0],dtype=np.float32).reshape(-1);seconds=len(wave)/sr
            if not np.isfinite(wave).all() or not .15<seconds<19.8:
                raise ValueError('配音为空、超长或到达生成上限，请调整文案重试。')
            rms=float(np.sqrt(np.mean(wave**2)));peak=float(np.max(np.abs(wave)))
            if rms<.0001 or peak>2:raise ValueError('配音音量异常，请重新生成。')
            sf.write(str(path),wave,sr,subtype='PCM_16')
            reply({'ok':True,'seconds':seconds,'elapsed_seconds':round(time.perf_counter()-begun,3),
                   'sample_rate':sr,'rms':rms,'peak':peak,'seed':seed,
                   'cuda_peak_mb':round(torch.cuda.max_memory_allocated()/1024**2,1)})
        except Exception as exc:
            reply({'ok':False,'error':str(exc)})

if __name__=='__main__':main()
