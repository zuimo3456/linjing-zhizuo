"""Download the pinned, official Qwen3-TTS checkpoint. Never uploads project text."""
import concurrent.futures,hashlib,json,os,shutil,time,urllib.request
from pathlib import Path
os.environ['HF_HUB_DISABLE_XET']='1'
os.environ['HF_HUB_DOWNLOAD_TIMEOUT']='120'

ROOT=Path(__file__).resolve().parent
DEST=ROOT/'.models/qwen3-tts-1.7b-customvoice'
REPO='Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice'
REVISION='0c0e3051f131929182e2c023b9537f8b1c68adfe'
WEIGHTS={
    'model.safetensors':'38b1d5971bdbd982b561cccec982669a53b0537c3cf5e9bd4778ed07bb2f5137',
    'speech_tokenizer/model.safetensors':'836b7b357f5ea43e889936a3709af68dfe3751881acefe4ecf0dbd30ba571258',
}
SIZES={'model.safetensors':3833402552,'speech_tokenizer/model.safetensors':682293092}

def file_hash(path):
    with open(path,'rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def download_weight(name):
    """Official Qwen ModelScope mirror, verified against pinned HF SHA256."""
    target=DEST/name
    if target.is_file() and file_hash(target)==WEIGHTS[name]:return
    total=SIZES[name];chunk=32*1024*1024
    pieces=DEST/'.download-parts'/name.replace('/','-');pieces.mkdir(parents=True,exist_ok=True)
    def part(start):
        end=min(total,start+chunk)-1;path=pieces/f'{start}.part'
        if path.is_file() and path.stat().st_size==end-start+1:return path
        url=f'https://modelscope.cn/models/{REPO}/resolve/master/{name}?part={start}'
        for attempt in range(3):
            try:
                request=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}'})
                with urllib.request.urlopen(request,timeout=120) as response:
                    if response.status!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {start}-{end}/'):
                        raise ValueError('Download server did not honor byte range')
                    with path.with_suffix('.pending').open('wb') as output:shutil.copyfileobj(response,output,1024*1024)
                if path.with_suffix('.pending').stat().st_size!=end-start+1:raise ValueError('Incomplete byte range')
                path.with_suffix('.pending').replace(path);return path
            except Exception:
                if attempt==2:raise
                time.sleep(1)
    starts=list(range(0,total,chunk));paths={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(part,start):start for start in starts}
        for count,future in enumerate(concurrent.futures.as_completed(futures),1):
            paths[futures[future]]=future.result()
            if count%6==0 or count==len(starts):print(f'{name}: {count}/{len(starts)} chunks',flush=True)
    target.parent.mkdir(exist_ok=True,parents=True);temporary=target.with_suffix('.verified-download')
    with temporary.open('wb') as output:
        for start in starts:
            with paths[start].open('rb') as source:shutil.copyfileobj(source,output,1024*1024)
    if file_hash(temporary)!=WEIGHTS[name]:raise ValueError('Downloaded weight SHA256 mismatch: '+name)
    temporary.replace(target)
    for path in paths.values():path.unlink()

def main():
    from huggingface_hub import snapshot_download
    snapshot_download(REPO,revision=REVISION,local_dir=str(DEST),max_workers=3,
                      allow_patterns=['*.json','*.txt','README.md'])
    for name in WEIGHTS:download_weight(name)
    for name,expected in WEIGHTS.items():
        actual=file_hash(DEST/name)
        if actual!=expected:raise ValueError(f'Model checksum mismatch: {name}')
    files={p.relative_to(DEST).as_posix():file_hash(p) for p in DEST.rglob('*')
           if p.is_file() and not any(x.startswith('.') for x in p.relative_to(DEST).parts)
           and p.name!='verified-manifest.json'}
    manifest={'repo':REPO,'revision':REVISION,'license':'Apache-2.0','files':files}
    (DEST/'verified-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(json.dumps({'ready':True,'model':REPO,'revision':REVISION,'files':len(files)}),flush=True)

if __name__=='__main__':main()
