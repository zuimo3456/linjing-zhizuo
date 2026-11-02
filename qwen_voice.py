"""Local-only Qwen worker bridge; no model imports in the video environment."""
import atexit,hashlib,json,queue,subprocess,threading,time
from pathlib import Path
from setup_qwen_voice import REPO,REVISION,WEIGHTS,DEST

ROOT=Path(__file__).resolve().parent
PYTHON=ROOT/'.tts-venv/Scripts/python.exe'
SPEAKER='Vivian'
INSTRUCT='用轻快、活泼、有亲和力的年轻女声说话，像向朋友介绍一家小店。吐字清楚，语速适中，语气自然明亮。'
PROFILE={'engine':'qwen3-tts','model':REPO,'revision':REVISION,'speaker':SPEAKER,
         'language':'Chinese','instruct':INSTRUCT,'seed_policy':'sha256-text-v1',
         'sampling':{'temperature':0.7,'top_p':0.9,'top_k':50,'repetition_penalty':1.05},
         'audio_pipeline':'measured-phrases-v3'}
PROFILE_ID=hashlib.sha256(json.dumps(PROFILE,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
_lock=threading.RLock()
_process=None
_responses=None
_log=None
_idle=None

def status():
    ready=PYTHON.is_file() and (DEST/'verified-manifest.json').is_file()
    ready=ready and all((DEST/name).is_file() for name in WEIGHTS)
    return {'engine':'qwen3-tts','name':'Vivian · 轻快女声','model':REPO,'speaker':SPEAKER,
            'profile_id':PROFILE_ID,'ready':ready,'loaded':_process is not None and _process.poll() is None,
            'offline':True,'license':'Apache-2.0','reason':'' if ready else '请先运行安装开源女声.ps1，下载并校验模型。'}

def _stop():
    global _process,_log,_idle
    with _lock:
        if _idle:_idle.cancel();_idle=None
        if _process:
            if _process.poll() is None:
                _process.terminate()
                try:_process.wait(timeout=5)
                except subprocess.TimeoutExpired:_process.kill();_process.wait(timeout=5)
            for stream in (_process.stdin,_process.stdout):
                if stream:stream.close()
            _process=None
        if _log:_log.close();_log=None

atexit.register(_stop)

def _read_responses(process,responses):
    try:
        for line in process.stdout:
            try:responses.put(json.loads(line))
            except json.JSONDecodeError:continue
    finally:responses.put({'ok':False,'error':'配音进程提前结束，请查看 data/qwen-voice.log。'})

def _response(timeout):
    try:result=_responses.get(timeout=timeout)
    except queue.Empty:
        _stop();raise ValueError('本地女声生成超时。请关闭占用显存的程序后重试；系统没有切回旧声音。')
    if not result.get('ok'):
        _stop();raise ValueError('本地女声生成失败：'+str(result.get('error','未知错误'))[-700:])
    return result

def generate(text,path):
    global _process,_responses,_log,_idle
    if not text.strip() or len(text)>26:raise ValueError('女声每句需为1—26个字符。')
    # These are model protocol tokens, never merchant narration.
    if '<|' in text or '|>' in text:raise ValueError('旁白含模型控制标记，请改为普通文字后重新确认。')
    with _lock:
        if _idle:_idle.cancel();_idle=None
        if _process is None or _process.poll() is not None:
            _stop()
            state=status()
            if not state['ready']:raise ValueError(state['reason'])
            folder=ROOT/'data';folder.mkdir(exist_ok=True)
            _log=(folder/'qwen-voice.log').open('a',encoding='utf8')
            _responses=queue.Queue()
            _process=subprocess.Popen([str(PYTHON),'-u','-X','utf8',str(ROOT/'qwen_voice_worker.py')],
                                      stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=_log,
                                      text=True,encoding='utf8',bufsize=1,creationflags=subprocess.CREATE_NO_WINDOW)
            threading.Thread(target=_read_responses,args=(_process,_responses),daemon=True).start()
            _response(180)
        try:
            _process.stdin.write(json.dumps({'text':text,'path':str(Path(path).resolve())},ensure_ascii=False)+'\n')
            _process.stdin.flush()
            result=_response(180)
        except (OSError,BrokenPipeError):
            _stop();raise ValueError('本地女声进程连接中断，请重试。')
        finally:
            # Release the GPU after two quiet minutes, retain disk audio cache.
            _idle=threading.Timer(120,_stop);_idle.daemon=True;_idle.start()
        return result
