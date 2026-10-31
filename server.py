from __future__ import annotations
import json,mimetypes,re,threading,time,uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,unquote
from planner import make_plan,validate_plan,PlanError
from media import DATA,ROOT,analyze,render,FFMPEG,FFPROBE

MAX_UPLOAD=200*1024*1024
jobs={}; jobs_lock=threading.Lock(); pool=ThreadPoolExecutor(max_workers=1)

def job(fn):
    with jobs_lock:
        if sum(j['status'] in ('queued','running') for j in jobs.values())>=6:
            raise ValueError('等待任务过多，请等当前任务完成。')
        jid=uuid.uuid4().hex; jobs[jid]={'id':jid,'status':'queued','message':'等待本地处理','created':time.time()}
    def work():
        def progress(msg):
            with jobs_lock: jobs[jid].update(status='running',message=msg)
        try:
            progress('正在处理'); result=fn(jid,progress)
            with jobs_lock: jobs[jid].update(status='done',message='处理完成',result=result)
        except Exception as e:
            with jobs_lock: jobs[jid].update(status='error',message=str(e)[-1600:])
    pool.submit(work)
    return {'job_id':jid}

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args): pass
    def reply(self,obj,status=200):
        data=json.dumps(obj,ensure_ascii=False,allow_nan=False).encode('utf8')
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def body(self):
        n=int(self.headers.get('Content-Length','0'))
        if not 0<n<=4*1024*1024: raise ValueError('项目数据超过限制，请分开处理素材。')
        return json.loads(self.rfile.read(n))
    def same_origin(self):
        origin=self.headers.get('Origin')
        if origin and origin not in ('http://127.0.0.1:4180','http://localhost:4180'):
            raise ValueError('不接受来自其他网站的写入请求。')
    def do_GET(self):
        try:
            url=urlsplit(self.path); path=unquote(url.path)
            if path=='/api/health':
                from local_vision import status as local_status
                return self.reply({'ok':bool(FFMPEG and FFPROBE),'ffmpeg':bool(FFMPEG),'ffprobe':bool(FFPROBE),
                                   'version':'local-ai-prototype-4','vision_configured':False,'local_vision':local_status(),'tts':'offline_windows'})
            if path.startswith('/api/jobs/'):
                with jobs_lock: item=jobs.get(path.rsplit('/',1)[-1])
                return self.reply(item or {'error':'任务不存在'},200 if item else 404)
            if path=='/api/saved':
                saved=DATA/'saved-project.json'
                from evidence_store import reconcile
                return self.reply(reconcile(json.loads(saved.read_text(encoding='utf8'))) if saved.exists() else None)
            if path=='/api/benchmark':
                p=ROOT/'evidence/constraint-results.json'
                return self.reply(json.loads(p.read_text(encoding='utf8')) if p.exists() else {'status':'not_run'})
            if path=='/': return self.file(ROOT/'static/index.html')
            if path in ('/app.js','/style.css'): return self.file(ROOT/'static'/path[1:])
            if path.startswith('/media/'):
                parts=path.split('/')[2:]
                if len(parts)!=2 or not re.fullmatch('[a-f0-9]{32}',parts[0]): return self.reply({'error':'无效素材路径'},404)
                if not (re.fullmatch(r'(thumb-\d+|frame-\d+-\d+)\.jpg',parts[1]) or parts[1] in ('source.mp4','review.mp4','result.mp4','cover.jpg','report.json','project.json','evidence.zip','context.zip')):
                    return self.reply({'error':'文件不可访问'},404)
                return self.file(DATA/parts[0]/parts[1])
            return self.reply({'error':'页面不存在'},404)
        except (ValueError,OSError) as e: self.reply({'error':str(e)},400)
        except (BrokenPipeError,ConnectionResetError): pass
    def file(self,p):
        if not p.is_file(): return self.reply({'error':'文件不存在'},404)
        length=p.stat().st_size;start=0;end=length-1; status=200
        range_value=self.headers.get('Range','')
        if range_value:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',range_value)
            if not match: return self.reply({'error':'无效Range'},416)
            a,b=match.groups()
            if not a:
                if not b or int(b)==0:return self.reply({'error':'无效Range'},416)
                start=max(0,length-int(b))
            else:
                start=int(a);end=min(int(b),end) if b else end
            if start>end or start>=length:return self.reply({'error':'超出Range'},416)
            status=206
        self.send_response(status);self.send_header('Content-Type',mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{length}')
        self.end_headers()
        with p.open('rb') as f:
            f.seek(start);remaining=end-start+1
            while remaining:
                chunk=f.read(min(remaining,65536))
                if not chunk: break
                self.wfile.write(chunk);remaining-=len(chunk)
    def do_POST(self):
        try:
            self.same_origin();url=urlsplit(self.path);path=url.path
            if path=='/api/upload':
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=MAX_UPLOAD: raise ValueError('请选择小于200MB的视频。')
                name=parse_qs(url.query).get('name',['video.mp4'])[0]
                if Path(name).suffix.lower() not in ('.mp4','.mov','.m4v','.webm','.mkv'):raise ValueError('请选择MP4、MOV、M4V、WebM或MKV。')
                mid=uuid.uuid4().hex;folder=DATA/mid;folder.mkdir(parents=True);dest=folder/'source.mp4'
                with dest.open('wb') as f:
                    remaining=n
                    while remaining:
                        chunk=self.rfile.read(min(remaining,1024*1024))
                        if not chunk: raise ValueError('上传中断。')
                        f.write(chunk);remaining-=len(chunk)
                def work(jid,progress):
                    progress('识别镜头边界与画面质量');result=analyze(dest,mid,Path(name).name)
                    (folder/'asset.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result
                return self.reply(job(work),202)
            if path=='/api/demo':
                self.body()
                from demo import create_demo
                return self.reply(job(lambda jid,progress:create_demo(progress)),202)
            obj=self.body()
            if path=='/api/reconcile':
                from evidence_store import reconcile
                return self.reply(reconcile(obj['project']))
            if path=='/api/confirm-shot':
                from evidence_store import confirm
                return self.reply({'shot':confirm(obj['project'],obj['shot_id'],obj['mode'],obj['checked'] is True)})
            if path=='/api/local-analyze':
                from local_vision import analyze_project
                from evidence_store import reconcile
                project=reconcile(obj['project'])
                return self.reply(job(lambda jid,progress:analyze_project(project,progress)),202)
            if path=='/api/plan':
                from pipeline import build_plan
                return self.reply(build_plan(obj['project'],obj.get('method','evidence')))
            if path=='/api/labels':
                from vision_adapter import parse_labels
                return self.reply({'labels':parse_labels(obj['candidates'],{s['id'] for s in obj['project']['shots']})})
            if path=='/api/validate':
                from pipeline import preflight
                _,plan=preflight(obj['project'],obj['plan']);return self.reply({'valid':True,'plan':plan})
            if path=='/api/render':
                from pipeline import preflight
                project,plan=preflight(obj['project'],obj['plan'])
                def render_checked(jid,progress):
                    current,checked=preflight(project,plan)
                    return render(current,checked,jid,progress)
                return self.reply(job(render_checked),202)
            if path=='/api/save':
                from evidence_store import reconcile
                p=reconcile(obj['project']);(DATA/'saved-project.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
                return self.reply({'saved':True})
            if path=='/api/context':
                from vision_adapter import context_pack
                return self.reply(context_pack(obj['project']))
            return self.reply({'error':'接口不存在'},404)
        except (ValueError,KeyError,TypeError,OSError) as e:self.reply({'error':str(e)},400)
        except Exception as e:self.reply({'error':str(e)[-1000:]},500)

if __name__=='__main__':
    DATA.mkdir(exist_ok=True)
    if not FFMPEG or not FFPROBE: raise SystemExit('请先安装FFmpeg并确保ffmpeg/ffprobe可用。')
    print('邻镜智作研究原型 http://127.0.0.1:4180',flush=True)
    ThreadingHTTPServer(('127.0.0.1',4180),Handler).serve_forever()
