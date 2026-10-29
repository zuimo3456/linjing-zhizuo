"""Download pinned ONNX data with resumable parts; never execute remote code."""
import hashlib,json,time,urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO='Xenova/chinese-clip-vit-base-patch16'
REVISION='f26904860903e70e050b8f48255e5f48401816e9'
DEST=ROOT/'.models/chinese-clip-onnx'
WEIGHTS='onnx/model_quantized.onnx'
WEIGHT_SIZE=190842404
WEIGHT_SHA='a2c2849329eafb24100acec5a9421a39f8cb445296444c5c98855b69e5e7a751'
FILES=['config.json','preprocessor_config.json','tokenizer.json','tokenizer_config.json','vocab.txt','README.md',WEIGHTS]

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b)
    return h.hexdigest()

def fetch_small(name):
    target=DEST/name
    if target.is_file():return
    with urllib.request.urlopen(f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}',timeout=60) as r:
        content=r.read()
    target.write_bytes(content)

def fetch_weights():
    target=DEST/WEIGHTS;target.parent.mkdir(exist_ok=True)
    if target.exists() and digest(target)==WEIGHT_SHA:return
    parts=DEST/'download-parts';parts.mkdir(exist_ok=True)
    chunk_size=8*1024*1024
    def part(index):
        start=index*chunk_size;end=min(WEIGHT_SIZE,start+chunk_size)-1
        path=parts/f'{index:03}.part'
        if path.exists() and path.stat().st_size==end-start+1:return path
        for attempt in range(3):
            try:
                url=f'https://huggingface.co/{REPO}/resolve/{REVISION}/{WEIGHTS}?download=true&part={index}'
                req=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}'})
                with urllib.request.urlopen(req,timeout=90) as r:
                    if r.status!=206 or r.headers.get('Content-Range')!=f'bytes {start}-{end}/{WEIGHT_SIZE}':
                        raise ValueError('Server did not honor model byte range')
                    with path.open('wb') as f:
                        while b:=r.read(256*1024):f.write(b)
                if path.stat().st_size!=end-start+1:raise ValueError('Incomplete model part')
                print(f'part {index+1}/{(WEIGHT_SIZE+chunk_size-1)//chunk_size} ready',flush=True)
                return path
            except Exception:
                if attempt==2:raise
                time.sleep(2)
    count=(WEIGHT_SIZE+chunk_size-1)//chunk_size
    with ThreadPoolExecutor(max_workers=4) as pool:paths=list(pool.map(part,range(count)))
    temporary=target.with_suffix('.partial')
    with temporary.open('wb') as f:
        for path in paths:
            with path.open('rb') as source:
                while b:=source.read(1024*1024):f.write(b)
    if digest(temporary)!=WEIGHT_SHA:raise ValueError('Model SHA256 mismatch; retain parts for diagnosis')
    temporary.replace(target)

if __name__=='__main__':
    DEST.mkdir(exist_ok=True,parents=True)
    for name in FILES[:-1]:fetch_small(name)
    fetch_weights()
    lock={'repository':REPO,'revision':REVISION,'base_model':'OFA-Sys/chinese-clip-vit-base-patch16',
          'base_revision':'36e679e65c2a2fead755ae21162091293ad37834',
          'files':{name:digest(DEST/name) for name in FILES},'remote_code':False,
          'runtime':'ONNX Runtime CPU, quantized int8; no cloud inference',
          'license_note':'Original Chinese-CLIP repository MIT (MIT-LICENSE.txt); converted model card declares base model but no separate license. Review weight redistribution terms before distribution.'}
    (ROOT/'evidence/local-model-lock.json').write_text(json.dumps(lock,ensure_ascii=False,indent=2),encoding='utf8')
    print('Local ONNX model ready',flush=True)
