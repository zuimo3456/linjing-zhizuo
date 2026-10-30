"""Server-owned source identity and persisted confirmation attestations."""
import hashlib,hmac,json,re,threading
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parent;DATA=ROOT/'data'
_lock=threading.RLock()

def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()

def identity(shot):
    value={k:shot.get(k) for k in ('id','media_id','source_sha256','start','end')}
    # JSON.stringify emits 0 for Python's 0.0. Numeric representation is not a source change.
    for key in ('start','end'):
        if isinstance(value[key],(int,float)):value[key]=round(float(value[key]),6)
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def _sign(payload):
    with _lock:
        path=DATA/'confirmation.key';DATA.mkdir(exist_ok=True)
        if not path.exists():
            import secrets
            path.write_bytes(secrets.token_bytes(32))
        return hmac.new(path.read_bytes(),json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode(),hashlib.sha256).hexdigest()

def _payload(shot,product=None):
    p={'version':2,'evidence_id':identity(shot),'tags':sorted(shot['tags'])}
    if product:p['product']={k:product[k] for k in ('id','value')}
    return p

def valid_attestation(shot,product=None):
    container=shot.get('product_binding') if product else shot.get('attestation')
    if not isinstance(container,dict):return False
    payload=_payload(shot,product)
    return bool(container.get('evidence_id')==identity(shot) and
                isinstance(container.get('signature'),str) and hmac.compare_digest(container['signature'],_sign(payload)))

def attest(shot,product=None):
    out={**_payload(shot,product),'signature':_sign(_payload(shot,product)),'confirmed':True}
    if product:out.update(fact_id=product['id'],value=product['value'])
    return out

def canonical(shot,verify_hash=False):
    mid=shot.get('media_id','')
    if not isinstance(mid,str) or not re.fullmatch('[a-f0-9]{32}',mid):raise ValueError('素材编号无效，请重新上传。')
    folder=DATA/mid;src=folder/'source.mp4';cache=folder/'asset.json'
    if not src.is_file():raise ValueError('原视频文件缺失，请重新上传这段素材，或移除未使用的镜头。')
    if not cache.is_file():raise ValueError('素材分析记录缺失，请重新上传这段素材。')
    try:asset=json.loads(cache.read_text(encoding='utf8'))
    except (ValueError,OSError):raise ValueError('素材分析记录无法读取，请重新上传这段视频。') from None
    source=next((s for s in asset['shots'] if s['id']==shot['id']),None)
    if source is None:raise ValueError('镜头与原视频不对应，请重新上传并确认。')
    if source.get('analysis_version')!=4:raise ValueError('这段素材需要更新分析，请重新上传或载入新版模拟案例。')
    if (source['start'],source['end'])!=(shot['start'],shot['end']):raise ValueError('镜头范围已经变化，请重新分析并确认。')
    expected=asset.get('source_sha256')
    if not expected:raise ValueError('素材缺少文件校验，请重新上传。')
    stat=src.stat()
    if verify_hash or stat.st_size!=asset.get('source_bytes') or stat.st_mtime_ns!=asset.get('source_mtime_ns'):
        if file_hash(src)!=expected:raise ValueError('原视频文件已变化，请重新上传并确认，旧确认不能沿用。')
    return source,expected

def reconcile(project):
    from planner import clean_project
    p=clean_project(project);warnings=[]
    for mid in dict.fromkeys(s.get('media_id','') for s in p['shots']):
        if not isinstance(mid,str) or not re.fullmatch('[a-f0-9]{32}',mid):continue
        folder=DATA/mid;cache=folder/'asset.json';src=folder/'source.mp4'
        if not (cache.is_file() and src.is_file()):continue
        try:asset=json.loads(cache.read_text(encoding='utf8'))
        except (ValueError,OSError):continue
        needs_refresh=asset.get('analysis_version')!=4
        old_shots=[s for s in p['shots'] if s['media_id']==mid]
        if needs_refresh:
            from media import analyze
            asset=analyze(src,mid,asset.get('name','已保存素材'))
            cache.write_text(json.dumps(asset,ensure_ascii=False,indent=2),encoding='utf8')
        if needs_refresh or any(s.get('analysis_version')!=4 for s in old_shots):
            previous={s['id']:s for s in old_shots};fresh=[]
            for source in asset['shots']:
                item=deepcopy(source);old=previous.get(item['id'])
                if old and (old['start'],old['end'])==(item['start'],item['end']):item['tags']=old['tags']
                item.update(confirmed=False,attestation=None,product_binding=None);fresh.append(item)
            first=next(i for i,s in enumerate(p['shots']) if s['media_id']==mid)
            remaining=[s for s in p['shots'] if s['media_id']!=mid]
            p['shots']=remaining[:first]+fresh+remaining[first:]
            warnings.append('素材分析已升级并列出完整镜头，请重新查看和确认；旧确认未自动沿用。')
    product=next((f for f in p['facts'] if f['kind']=='product' and f.get('confirmed') is True),None)
    for shot in p['shots']:
        try:
            source,sha=canonical(shot)
            shot.update({k:deepcopy(source[k]) for k in ('quality','quality_issues','frames','thumb','analysis_version') if k in source})
            shot['source_sha256']=sha;shot.pop('unavailable',None)
            if shot.get('quality_issues'):
                shot['confirmed']=False
            if shot.get('confirmed') and not valid_attestation(shot):
                shot['confirmed']=False;warnings.append('素材或确认版本已变化，请重新确认镜头用途。')
            if shot.get('product_binding') and (not product or not valid_attestation(shot,product)):
                shot['product_binding']=None;warnings.append('商品对应确认已失效，请查看画面后重新确认。')
        except ValueError as e:
            shot.update(confirmed=False,product_binding=None,unavailable=str(e));warnings.append(str(e))
    p['warnings']=list(dict.fromkeys(warnings))
    return p

def confirm(project,shot_id,mode,checked):
    from planner import clean_project
    p=clean_project(project)
    shot=next((s for s in p['shots'] if s['id']==shot_id),None)
    if shot is None:raise ValueError('镜头不存在。')
    if mode not in ('purpose','product'):raise ValueError('未知确认类型。')
    if not checked:
        if mode=='purpose':shot.update(confirmed=False,attestation=None)
        else:shot['product_binding']=None
        return shot
    source,sha=canonical(shot,verify_hash=True)
    if source.get('quality_issues'):raise ValueError('这段素材不能使用：'+'；'.join(source['quality_issues']))
    shot['source_sha256']=sha
    if mode=='purpose':
        if not shot['tags'] or shot['tags']==['other']:raise ValueError('请先选择明确的镜头用途。')
        shot.update(confirmed=True,attestation=attest(shot))
    else:
        product=next((f for f in p['facts'] if f['kind']=='product' and f.get('confirmed') is True and f['value'].strip()),None)
        if product is None:raise ValueError('请先填写并确认商品事实卡。')
        if 'product' not in shot['tags']:raise ValueError('请先将用途选择为商品。')
        shot['product_binding']=attest(shot,product)
    return shot

def verify_selected(project,plan):
    shots={s['id']:s for s in project['shots']}
    product=next((f for f in project['facts'] if f['kind']=='product' and f.get('confirmed') is True),None)
    for seg in plan['segments']:
        s=shots[seg['shot_id']];source,sha=canonical(s,verify_hash=True)
        if s.get('source_sha256')!=sha or not valid_attestation(s):raise ValueError('镜头确认已失效，请重新核对原视频。')
        if source.get('quality_issues'):raise ValueError('选中的画面质量不合格，请更换素材。')
        if seg['role']=='product' and (not product or not valid_attestation(s,product)):
            raise ValueError('商品对应确认与原视频不一致，请重新确认。')
