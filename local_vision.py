"""Offline Chinese-CLIP candidates. Similarity is NOT calibrated confidence."""
from collections import Counter
from copy import deepcopy
import importlib.util,json,re,time,threading
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MODEL=ROOT/'.models/chinese-clip-onnx'
PROMPTS={
 'storefront':['一张店铺门头和招牌的照片','一张商店入口的照片','一张街边店面外观的照片'],
 'product':['一张商品特写的照片','一张食品或饮品的特写照片','一张展示待售产品的照片'],
 'process':['一张双手制作食品的照片','一张店员加工产品的照片','一张正在手工制作的照片'],
 'interior':['一张店铺室内环境的照片','一张咖啡店桌椅和装修的照片','一张餐厅内部空间的照片'],
 'person':['一张人物肖像的照片','一张人脸特写的照片','一张人站在镜头前的照片'],
 'other':['一张电脑或手机屏幕截图','一张自然风景或动物的照片','一张模糊黑暗看不清的照片'],
}
_engine=None
_engine_fingerprint=None
_engine_lock=threading.RLock()
_integrity_cache={}
_load_failure=None

def installation():
    """Cache hashes by file metadata, never confuse file presence with integrity."""
    from setup_onnx_model import WEIGHT_SHA,WEIGHTS,REPO,REVISION,digest
    lock_path=ROOT/'evidence/local-model-lock.json'
    try:
        lock=json.loads(lock_path.read_text(encoding='utf8'))
        if lock.get('repository')!=REPO or lock.get('revision')!=REVISION:raise ValueError('本地模型版本记录无效，请重新安装。')
        expected={name:lock.get('files',{}).get(name) for name in (WEIGHTS,'tokenizer.json','preprocessor_config.json')}
        if expected[WEIGHTS]!=WEIGHT_SHA or any(not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v) for v in expected.values()):
            raise ValueError('本地模型校验记录不完整，请重新安装。')
        fingerprint=[str(MODEL.resolve()),lock_path.stat().st_mtime_ns]
        for name,want in expected.items():
            path=MODEL/name;stat=path.stat();key=(str(path.resolve()),stat.st_size,stat.st_mtime_ns,want)
            with _engine_lock:
                if key not in _integrity_cache:
                    _integrity_cache.clear() if len(_integrity_cache)>30 else None
                    _integrity_cache[key]=digest(path)==want
                matches=_integrity_cache[key]
            if not matches:raise ValueError('本地模型文件校验失败，请重新安装。')
            fingerprint.append(key)
        return tuple(fingerprint),None
    except FileNotFoundError:return None,'本地模型文件缺失，请运行 setup-local-ai.ps1 安装。'
    except (OSError,ValueError,TypeError,AttributeError):return None,'本地模型文件或校验记录损坏，请运行 setup-local-ai.ps1 重新安装。'

def status():
    deps=all(importlib.util.find_spec(n) is not None for n in ('onnxruntime','tokenizers'))
    fingerprint,problem=installation()
    if not deps:problem='本地模型依赖缺失，请运行 setup-local-ai.ps1 安装；也可以先手工标注。'
    if _load_failure and _load_failure[0]==fingerprint:problem=_load_failure[1]
    state='invalid' if problem else ('loaded' if _engine is not None and _engine_fingerprint==fingerprint else 'verified')
    return {'ready':problem is None,'weights_present':(MODEL/'onnx/model_quantized.onnx').is_file(),'dependencies_present':deps,
            'integrity_verified':fingerprint is not None,'state':state,'reason':problem,
            'model':'Chinese-CLIP / ONNX int8','mode':'offline_candidates','score_note':'相对相似度不是正确概率，必须人工确认。'}

def decide(rows,quality):
    """Require agreement across all sampled moments; otherwise abstain."""
    if not rows:raise ValueError('没有可分析的抽帧。')
    import numpy as np
    scores=np.asarray(rows,dtype=float)
    if scores.ndim!=2 or scores.shape[1]!=len(PROMPTS) or not np.isfinite(scores).all():
        raise ValueError('本地模型返回无效分数。')
    keys=list(PROMPTS);mean=scores.mean(axis=0);order=np.argsort(-mean)
    best=keys[int(order[0])];margin=float(mean[order[0]]-mean[order[1]])
    winners=[keys[int(i)] for i in scores.argmax(axis=1)]
    stable=all(w==best for w in winners)
    accepted=len(rows)>=3 and stable and quality>=.25 and margin>=1.5 and best not in ('other','person')
    reasons=[]
    if len(rows)<3:reasons.append('抽帧不足3张')
    if not stable:reasons.append('不同时间画面判断不一致')
    if quality<.25:reasons.append('画面质量偏低')
    if margin<1.5:reasons.append('候选用途区分不明显')
    if best in ('other','person'):reasons.append('未识别到稳定的门店用途')
    return {'tags':[best if accepted else 'other'],'suggested_tag':best,'confirmed':False,
            'needs_review':True,'abstained':not accepted,'review_reasons':reasons,
            'description':('候选用途，需查看视频确认。' if accepted else '暂不判定用途：'+'；'.join(reasons)+'。'),
            'relative_scores':{keys[int(i)]:round(float(mean[i]),4) for i in order},
            'margin':round(margin,4),'frame_votes':dict(Counter(winners)),
            'threshold_note':'全部采样帧一致（至少3张）、logit差值≥1.5的启发式门槛；尚未用真实店铺数据校准。'}

class Engine:
    def __init__(self):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        check=status()
        if not check['ready']:raise ValueError(check['reason'])
        options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(MODEL/'onnx/model_quantized.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        self.tokenizer=Tokenizer.from_file(str(MODEL/'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=52)
        self.tokenizer.enable_padding(pad_id=0,pad_token='[PAD]')
        self.config=json.loads((MODEL/'preprocessor_config.json').read_text(encoding='utf8'))
        self.prompts=[s for group in PROMPTS.values() for s in group]

    def score(self,paths):
        import numpy as np
        from PIL import Image
        cfg=self.config;pixels=[]
        for path in paths:
            with Image.open(path) as image:
                image=image.convert('RGB').resize((cfg['size']['width'],cfg['size']['height']),Image.Resampling.BICUBIC)
                arr=np.asarray(image,dtype=np.float32)*cfg['rescale_factor']
                arr=(arr-np.asarray(cfg['image_mean'],np.float32))/np.asarray(cfg['image_std'],np.float32)
                pixels.append(arr.transpose(2,0,1))
        tokens=self.tokenizer.encode_batch(self.prompts)
        possible={'input_ids':np.array([t.ids for t in tokens],np.int64),
                  'attention_mask':np.array([t.attention_mask for t in tokens],np.int64),
                  'token_type_ids':np.array([t.type_ids for t in tokens],np.int64),
                  'pixel_values':np.stack(pixels).astype(np.float32)}
        inputs={v.name:possible[v.name] for v in self.session.get_inputs()}
        result=self.session.run(['logits_per_image'],inputs)[0]
        if result.shape!=(len(paths),len(self.prompts)):raise ValueError('模型输出维度不符合预期。')
        # Every category has exactly three prompts; average instead of picking a lucky prompt.
        return result.reshape(len(paths),len(PROMPTS),3).mean(axis=2).tolist()

def frame_paths(shot):
    mid=shot.get('media_id','')
    if not re.fullmatch('[a-f0-9]{32}',mid):raise ValueError('素材编号无效。')
    frames=shot.get('frames') or [{'time':(shot['start']+shot['end'])/2,'url':shot.get('thumb','')}]
    paths=[];evidence=[]
    for frame in frames:
        name=frame.get('url','').rsplit('/',1)[-1]
        if not re.fullmatch(r'(thumb-\d+|frame-\d+-\d+)\.jpg',name):raise ValueError('抽帧路径无效。')
        path=ROOT/'data'/mid/name
        if not path.is_file():raise ValueError('抽帧文件缺失，请重新上传素材。')
        paths.append(path);evidence.append({'time':frame['time'],'url':f'/media/{mid}/{name}'})
    return paths,evidence

def semantic_risk(paths,frames,rows):
    """Flag visible content change toward unsupported classes, not a calibrated truth test."""
    import numpy as np
    from PIL import Image
    keys=list(PROMPTS);winners=[keys[int(np.argmax(r))] for r in rows]
    supported=[i for i,k in enumerate(winners) if k not in ('person','other')]
    if len(supported)<2 or not any(k in ('person','other') for k in winners):return None
    with Image.open(paths[supported[0]]) as im:reference=np.asarray(im.convert('RGB').resize((32,32)),dtype=float)
    for i,k in enumerate(winners):
        if k not in ('person','other'):continue
        with Image.open(paths[i]) as im:current=np.asarray(im.convert('RGB').resize((32,32)),dtype=float)
        a=reference.mean(axis=2);b=current.mean(axis=2);a=a-a.mean();b=b-b.mean()
        norm=float(np.linalg.norm(a)*np.linalg.norm(b));correlation=float((a*b).sum())/norm if norm>1 else 0
        # Exposure/fade changes alone preserve structure and should not be a semantic veto.
        if float(np.abs(current-reference).mean())/255>.12 and correlation<.85:
            return f'约{frames[i]["time"]:.2f}秒出现明显内容切换，模型同时给出无关/人物风险。请使用不含混入内容的区间或重新上传；当前区间不能直接确认。'
    return None

def analyze_project(project,progress=lambda _:None):
    from planner import clean_project
    global _engine,_load_failure,_engine_fingerprint
    p=clean_project(project);begun=time.perf_counter()
    if not p['shots']:raise ValueError('请先上传素材。')
    progress('载入本地图文模型，素材不会上传到云端')
    eligible=any(not s.get('unavailable') and not s.get('quality_issues') for s in p['shots'])
    if eligible:
        fingerprint,problem=installation()
        if problem:raise ValueError(problem)
        with _engine_lock:
            if _engine is None or _engine_fingerprint!=fingerprint:
                try:_engine=Engine();_engine_fingerprint=fingerprint;_load_failure=None
                except Exception:
                    _load_failure=(fingerprint,'本地模型无法加载，请重新安装；当前仍可手工标注。')
                    raise ValueError(_load_failure[1]) from None
    counts={'succeeded':0,'failed':0,'skipped':0};failures=[]
    for i,shot in enumerate(p['shots']):
        progress(f'本地分析镜头 {i+1}/{len(p["shots"])}，检查多时刻画面')
        frames=[];problem=None
        if shot.get('unavailable'):
            problem=shot['unavailable'];outcome='failed'
        elif shot.get('quality_issues'):
            problem='；'.join(shot['quality_issues']);outcome='skipped'
        else:
            try:
                paths,frames=frame_paths(shot);rows=[]
                from review_store import load_review,store_review
                cached=load_review(shot)
                if cached:candidate=deepcopy(cached['candidate'])
                else:
                    for start in range(0,len(paths),3):rows.extend(_engine.score(paths[start:start+3]))
                    candidate=decide(rows,shot['quality'])
                    risk=semantic_risk(paths,frames,rows)
                    if risk:candidate.update(semantic_issue=risk,tags=['other'],abstained=True,description=risk,review_reasons=[risk])
                    # Persist only canonical, real media; direct structural tests have no source record.
                    if shot.get('analysis_version') and shot.get('source_sha256'):store_review(shot,candidate)
                shot['semantic_issue']=candidate.get('semantic_issue');outcome='succeeded'
            except Exception:
                problem='本镜头抽帧或分析失败，请重新上传此素材；其他镜头继续分析。';outcome='failed'
        counts[outcome]+=1
        if problem:
            failures.append({'shot_id':shot['id'],'status':outcome,'reason':problem})
            candidate={'tags':['other'],'suggested_tag':'other','confirmed':False,'abstained':True,'needs_review':True,
                       'review_reasons':[problem],'description':problem}
        shot['analysis_outcome']=outcome
        # Preserve human chosen tags for comparison; revoke all confirmations below.
        shot['local_candidate']={**candidate,'frames':frames}
        if not shot.get('confirmed'):
            shot.update(candidate,label_source='local_model_candidate')
        shot['product_binding']=None
        shot['confirmed']=False;shot['attestation']=None
    from setup_onnx_model import REPO,REVISION,WEIGHT_SHA
    p['vision_analysis']={'engine':REPO,'revision':REVISION,'weights_sha256':WEIGHT_SHA,
                          'runtime':'onnxruntime CPU','elapsed_seconds':round(time.perf_counter()-begun,3),'remote_requests':0,
                          'shots':len(p['shots']),'summary':counts,'failures':failures,'status':'partial' if counts['failed'] or counts['skipped'] else 'complete',
                          'prompts':PROMPTS,'thresholds':{'min_frames':3,'margin':1.5,'agreement':'all','sampling':'max_0.5_second_gap; not_full_semantic_coverage'},
                          'scope':'用途候选；不识别价格、地址、优惠或确切商品，不自动确认事实。'}
    return p
