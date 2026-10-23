"""Pin public upstream sources for review; does not install or execute upstream code."""
import hashlib,json,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'evidence/open-source-snapshots'
SOURCES={
 'harry0703/MoneyPrinterTurbo':['README.md','LICENSE','app/services/video.py'],
 'modelscope/FunClip':['README.md','LICENSE','funclip/videoclipper.py'],
 'QwenLM/Qwen3-VL':['README.md','LICENSE'],
 'Breakthrough/PySceneDetect':['README.md','LICENSE'],
 'SYSTRAN/faster-whisper':['README.md','LICENSE'],
}
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'LocalLens-research-source-review','Accept':'application/vnd.github+json' if 'api.github.com' in url else '*/*'})
    with urllib.request.urlopen(req,timeout=25) as r:return r.read()
if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True);rows=[]
    for repo,paths in SOURCES.items():
        row={'repository':repo,'url':'https://github.com/'+repo,'checked_at_utc':datetime.now(timezone.utc).isoformat(),'execution':'not_installed_or_executed','files':[]}
        try:
            info=json.loads(get('https://api.github.com/repos/'+repo));branch=info['default_branch']
            sha=json.loads(get(f'https://api.github.com/repos/{repo}/commits/{branch}'))['sha'];row['sha']=sha
            for name in paths:
                try:
                    data=get(f'https://raw.githubusercontent.com/{repo}/{sha}/{name}')
                    dest=OUT/repo.replace('/','__')/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
                    row['files'].append({'name':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'url':f'https://github.com/{repo}/blob/{sha}/{name}'})
                except Exception as e:row['files'].append({'name':name,'status':'unavailable','error':type(e).__name__})
        except Exception as e:row['status']='unavailable';row['error']=type(e).__name__
        rows.append(row);print(repo,row.get('sha',row.get('status')),flush=True)
    (ROOT/'evidence/upstream-lock.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
