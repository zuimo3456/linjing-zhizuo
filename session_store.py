"""Restore edit decisions only against the same, freshly verified project state."""
import hashlib,json,threading,uuid
from copy import deepcopy
from evidence_store import DATA,reconcile
from pipeline import preflight
from planner import PlanError
_lock=threading.RLock()

def context_id(project):
    keys=('id','media_id','source_sha256','start','end','tags','confirmed','attestation','product_binding','analysis_version','quality_issues','semantic_issue')
    value={'goal':project['goal'],'synthetic':project.get('synthetic') is True,'facts':project['facts'],
           'shots':[{k:s.get(k) for k in keys} for s in project['shots']]}
    # Browser JSON round-trips 0.0 as 0, just as source identity does.
    for s in value['shots']:
        for k in ('start','end'):
            if isinstance(s[k],(int,float)):s[k]=float(s[k])
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def prepare_session(project,plan=None,method='evidence'):
    if method not in ('evidence','chronological'):raise PlanError('未知编排方式。')
    p=reconcile(project);p.pop('saved_edit',None)
    checked=None
    if plan is not None:p,checked=preflight(p,plan)
    p['saved_edit']={'version':1,'method':method,'context_id':context_id(p),'plan':checked}
    return p

def restore_session(raw):
    p=reconcile(raw);edit=p.pop('saved_edit',None)
    if not edit:return p
    try:
        if not isinstance(edit,dict) or edit.get('version')!=1 or edit.get('method') not in ('evidence','chronological'):
            raise PlanError('保存的剪辑记录格式不兼容。')
        if edit.get('context_id')!=context_id(p):raise PlanError('素材、事实或确认状态已经变化。')
        checked=None
        if edit.get('plan') is not None:_,checked=preflight(p,edit['plan'])
        p['saved_edit']={**edit,'plan':checked}
    except (ValueError,TypeError,KeyError) as e:
        p['warnings']=list(dict.fromkeys(p.get('warnings',[])+['素材与事实已恢复；原剪辑方案需重新核对：'+str(e)]))
    return p

def save_session(project,plan=None,method='evidence'):
    p=prepare_session(project,plan,method);DATA.mkdir(exist_ok=True)
    temporary=DATA/('saved-project-'+uuid.uuid4().hex+'.tmp')
    with _lock:
        try:
            temporary.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
            temporary.replace(DATA/'saved-project.json')
        finally:temporary.unlink(missing_ok=True)
    return {'saved':True,'plan_saved':p['saved_edit']['plan'] is not None}
