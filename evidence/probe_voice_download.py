"""Anonymous download-only connection checks; no project or personal data."""
import concurrent.futures,time,urllib.request
URLS=[
 'https://modelscope.cn/models/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/resolve/master/model.safetensors',
 'https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/resolve/0c0e3051f131929182e2c023b9537f8b1c68adfe/model.safetensors?download=true',
]
def check(url):
    begun=time.perf_counter()
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'Range':'bytes=0-4194303'}),timeout=25) as response:
            count=len(response.read(4194304));status=response.status
        return {'host':url.split('/')[2],'bytes':count,'seconds':round(time.perf_counter()-begun,2),'status':status}
    except Exception as exc:return {'host':url.split('/')[2],'error':str(exc)}
if __name__=='__main__':print(list(concurrent.futures.ThreadPoolExecutor(2).map(check,URLS)))
