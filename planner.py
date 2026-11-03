"""Evidence-linked planning. Labels are hypotheses until a person confirms them."""
from __future__ import annotations
import math
from copy import deepcopy
from text_rules import display_text,supported_text,direction_problem,visible_controls
from copy_rules import COPY_POLICY,copy_notes,detail_matches

TAGS = ('storefront', 'product', 'process', 'interior', 'person', 'other')
TAG_NAMES = dict(zip(TAGS, ('门头 / 路线', '商品', '制作过程', '环境', '人物', '其他')))
GOALS = {
    'visit': {'name': '到店消费', 'roles': ['storefront', 'product', 'interior'], 'required_facts': ['shop', 'product', 'address']},
    'attract': {'name': '引流关注', 'roles': ['product', 'process', 'interior'], 'required_facts': ['shop', 'product']},
    'promo': {'name': '优惠促销', 'roles': ['product', 'storefront'], 'required_facts': ['shop', 'product', 'offer', 'validity', 'address']},
}
FACT_NAMES = {'shop': '店名', 'product': '商品', 'product_detail':'商品特点', 'address': '地址', 'offer': '优惠及使用条件', 'validity': '有效期'}
CTA = {'visit': '到店前，请确认营业情况。', 'attract': '感兴趣可以先收藏。', 'promo': '参与前，请核对活动条件。'}

class PlanError(ValueError):
    pass

def segment_clips(seg):
    if 'clips' not in seg:return [{k:seg.get(k) for k in ('shot_id','start','end')}]
    clips=seg['clips']
    if not isinstance(clips,list) or not 2<=len(clips)<=4 or any(not isinstance(c,dict) for c in clips):
        raise PlanError('连续旁白组必须包含2—4个有效片段。')
    if any(seg.get(k)!=clips[0].get(k) for k in ('shot_id','start','end')):
        raise PlanError('旁白组首片段记录不一致，请重新编排。')
    return clips

def segment_seconds(seg):
    return sum(c['end']-c['start'] for c in segment_clips(seg))

def clean_project(project):
    if not isinstance(project,dict):raise PlanError('项目格式无效，请导入正确的项目文件。')
    p = deepcopy(project)
    if p.get('goal') not in GOALS:
        raise PlanError('请选择有效营销目标。')
    facts = p.get('facts', [])
    shots = p.get('shots', [])
    if not isinstance(facts, list) or not isinstance(shots, list) or len(facts)>30 or len(shots)>1000:
        raise PlanError('事实或镜头数量超出限制。')
    ids = set()
    for f in facts:
        if not isinstance(f,dict) or not isinstance(f.get('id'),str) or not f['id'] or f['id'] in ids:
            raise PlanError('事实编号缺失或重复。')
        ids.add(f['id'])
        raw=f.get('original_value');pending=isinstance(raw,str) and f.get('text_review_value')==f.get('value') and visible_controls(raw)==f.get('value')
        if f.get('kind') not in FACT_NAMES or not isinstance(f.get('value'),str) or len(raw if pending else f['value'])>100:
            raise PlanError('事实字段无效或超过100字。')
        if not supported_text(f['value']):raise PlanError('事实包含不支持的控制字符，请重新填写；不要删除必要条件。')
        issue=direction_problem(f['value'])
        if issue:raise PlanError(FACT_NAMES[f['kind']]+issue)
        if f.get('text_review_value')==f['value'] and f.get('confirmed') is True:
            raise PlanError(FACT_NAMES[f['kind']]+'仍是带字符标记的待核对文字，请重新填写并确认。')
        if f.get('text_review_value')!=f['value']:f.pop('text_issue',None)
        if f.get('confirmed') is True and (not isinstance(f.get('source'),str) or not f['source'].strip()):
            raise PlanError('确认事实时请填写来源。')
    confirmed = [f for f in facts if f.get('confirmed') is True and f['value'].strip()]
    for kind in FACT_NAMES:
        if len([f for f in confirmed if f['kind']==kind])>1:
            raise PlanError(f'{FACT_NAMES[kind]}存在多条已确认记录，请先消除冲突。')
    for f in confirmed:
        if f['kind']=='product_detail' and not detail_matches(f,facts):
            raise PlanError('商品特点尚未与当前已确认商品对应，请重新核对商品名称和特点。')
    ids=set()
    for s in shots:
        if not isinstance(s,dict) or not isinstance(s.get('id'),str) or not s['id'] or s['id'] in ids:
            raise PlanError('镜头编号缺失或重复。')
        ids.add(s['id'])
        for key in ('start','end','quality'):
            if not isinstance(s.get(key),(int,float)) or isinstance(s.get(key),bool) or not math.isfinite(s[key]):
                raise PlanError('镜头时间或质量分数无效。')
        if not 0 <= s['start'] < s['end'] or not 0<=s['quality']<=1:
            raise PlanError('镜头范围或质量分数无效。')
        if not isinstance(s.get('tags'),list) or any(t not in TAGS for t in s['tags']):
            raise PlanError('存在未知镜头标签。')
    return p

def caption_for(role, facts, goal):
    by_kind = {f['kind']:{**f,'value':display_text(f['value'])} for f in facts if f.get('confirmed') is True and f.get('value','').strip()
               and (f.get('kind')!='product_detail' or detail_matches(f,facts))}
    kinds = {'product':['shop','product','product_detail'], 'storefront':['shop','address'], 'process':['shop'], 'interior':['shop']}.get(role,[])
    if goal=='promo' and role=='product':
        kinds=['shop','product','product_detail','offer','validity']
    refs=[by_kind[k]['id'] for k in kinds if k in by_kind]
    def sentence(value):return value if value.endswith(('。','！','？','!','?')) else value+'。'
    if role=='product':
        if 'shop' in by_kind and 'product' in by_kind and goal!='promo':
            text=f"{by_kind['shop']['value']}，带你看看{by_kind['product']['value']}。"
            if 'product_detail' in by_kind:text+=sentence(by_kind['product_detail']['value'])
        else:
            text=''.join(sentence(by_kind[k]['value']) for k in kinds if k in by_kind) or '请先确认商品信息。'
    elif role=='storefront':
        prefix=(by_kind['shop']['value']+'，就在') if 'shop' in by_kind else '门店地址：'
        text=(prefix+by_kind['address']['value']+'。') if 'address' in by_kind else '出发前，请确认门店位置。'
    elif role=='process':
        text=('接着看看'+by_kind['shop']['value']+'的制作画面。') if 'shop' in by_kind else '这是制作过程。'
    elif role=='interior':
        text=('也看看'+by_kind['shop']['value']+'的门店环境。') if 'shop' in by_kind else '这是门店环境。'
    else:
        text=CTA[goal]
    return text,refs

def product_matches(shot,facts):
    from evidence_store import identity
    product=next((f for f in facts if f['kind']=='product' and f.get('confirmed') is True),None)
    binding=shot.get('product_binding')
    return bool(product and isinstance(binding,dict) and binding.get('confirmed') is True
                and binding.get('fact_id')==product['id'] and binding.get('value')==product['value']
                and binding.get('evidence_id')==identity(shot))

def make_plan(project, method='evidence', speech_lengths=None):
    p=clean_project(project)
    if method not in ('evidence','chronological'):
        raise PlanError('未知编排方法。')
    goal=p['goal']; spec=GOALS[goal]
    facts=[f for f in p['facts'] if f.get('confirmed') is True and f['value'].strip()]
    missing_facts=[k for k in spec['required_facts'] if not any(f['kind']==k for f in facts)]
    date_problem=None
    if goal=='promo' and not missing_facts:
        from validity import period_problem
        date_problem=period_problem(next(f['value'] for f in facts if f['kind']=='validity'))
    eligible=[s for s in p['shots'] if s.get('confirmed') is True and not s.get('quality_issues') and not s.get('semantic_issue') and not s.get('unavailable') and s['quality']>=0.25 and s['end']-s['start']>=1]
    # Maximum-coverage weighted assignment, O(shots * roles * 2^roles).
    # A versatile shot must not greedily consume the only evidence for a later role.
    roles=spec['roles'];timing_verified=speech_lengths is not None
    def fits(s,role,last=False):
        if role not in s['tags'] or (role=='product' and not product_matches(s,facts)):return False
        text=caption_for(role,facts,goal)[0]+(CTA[goal] if last else '')
        return not timing_verified or speech_lengths.get(text,float('inf'))/1.18+.08<=min(s['end']-s['start'],8)+.00001
    def solve(candidates,anchor=None):
        initial={} if anchor is None else {anchor[0]:anchor[1]}
        mask=sum(1<<roles.index(r) for r in initial)
        states={mask:(sum(s['quality']+min(s['end']-s['start'],8)*.01 for s in initial.values()),initial)}
        for shot in candidates:
            updated=dict(states)
            for used,(score,assigned) in states.items():
                for index,role in enumerate(roles):
                    bit=1<<index
                    if used&bit or not fits(shot,role,method=='evidence' and role==roles[-1]):continue
                    newmask=used|bit;value=score+shot['quality']+min(shot['end']-shot['start'],8)*.01
                    if newmask not in updated or value>updated[newmask][0]:updated[newmask]=(value,{**assigned,role:shot})
            states=updated
        best=max(states,key=lambda m:(m.bit_count(),states[m][0]))
        return best,states[best]
    if method=='chronological':
        options=[]
        for pos,shot in enumerate(eligible):
            for role in roles:
                if fits(shot,role,True):options.append(solve(eligible[:pos],(role,shot)))
        bestmask,(score,assignment)=max(options,key=lambda x:(x[0].bit_count(),x[1][0])) if options else (0,(0,{}))
    else:bestmask,(score,assignment)=solve(eligible)
    selected=[(role,assignment[role]) for role in roles if role in assignment]
    missing_roles=[role for role in roles if role not in assignment]
    if method=='chronological':
        # Same candidates/captions, source order: a transparent, weak baseline.
        order={s['id']:i for i,s in enumerate(p['shots'])}
        selected.sort(key=lambda rs:order[rs[1]['id']])
    segments=[]
    for role,s in selected:
        text,refs=caption_for(role,facts,goal)
        segments.append({'shot_id':s['id'],'role':role,'start':s['start'],'end':min(s['end'],s['start']+8),'text':text,'fact_ids':refs,
                         'reason':f'{TAG_NAMES[role]}覆盖目标结构；标签已人工确认；质量分 {s["quality"]:.2f}。'})
    if segments:
        # CTA uses the last evidence frame, with no extra business assertions.
        last=segments[-1]
        last['text']+=CTA[goal]
    missing=[f'请确认{FACT_NAMES[k]}' for k in missing_facts]
    for role in missing_roles:
        support=[s for s in eligible if role in s['tags'] and (role!='product' or product_matches(s,facts))]
        text=caption_for(role,facts,goal)[0]+(CTA[goal] if method=='evidence' and role==roles[-1] else '')
        spoken=speech_lengths.get(text) if timing_verified else None
        if support and spoken is not None and all(min(s['end']-s['start'],8)<spoken/1.18+.08 for s in support):
            longest=max(min(s['end']-s['start'],8) for s in support)
            missing.append(f'{TAG_NAMES[role]}旁白约{spoken:.1f}秒，至少需要{spoken/1.18+.08:.1f}秒画面；当前最长可用{longest:.1f}秒。请更换素材或调整非必要文案。')
        else:missing.append(f'请补拍或确认{TAG_NAMES[role]}镜头，建议稳定竖拍5—8秒')
    if 'product' in missing_roles and any('product' in s['tags'] for s in eligible) and not any(product_matches(s,facts) for s in eligible if 'product' in s['tags']):
        missing.append('请单独确认商品镜头与事实卡中的商品一致；修改商品名称后需要重新确认。')
    if missing_roles and timing_verified:
        missing.append('候选镜头还需能放下对应旁白；请换足够长的镜头或调整非必要文案，保留完整活动条件。')
    if date_problem:missing.append(date_problem)
    if not timing_verified:missing.append('请先完成实际配音时长预检。')
    for seg in segments:
        seg['speech_seconds']=speech_lengths.get(seg['text']) if timing_verified else None
        seg['minimum_seconds']=round(seg['speech_seconds']/1.18+.08,3) if seg['speech_seconds'] is not None else None
    return {'schema_version':'2.0','copy_policy':COPY_POLICY,'copy_notes':copy_notes(facts),'goal':goal,'method':method,'synthetic':p.get('synthetic') is True,
            'segments':segments,'missing':missing,'renderable':bool(segments) and not missing,'timing_verified':timing_verified,'warnings':p.get('warnings',[]),
            'limitations':['质量分来自抽帧检测，不能证明语义正确。','人工确认仅表示本次输入状态，不能自动证明商户陈述真实。'],
            'assignment':{'algorithm':'speech_feasible_maximum_coverage','score':round(score,4),'quality_weight':1,'duration_weight':0.01},
            'coverage':{'roles':len(spec['roles'])-len(missing_roles),'required_roles':len(spec['roles']),
                        'facts':len(spec['required_facts'])-len(missing_facts),'required_facts':len(spec['required_facts'])}}

def validate_plan(project, plan):
    p=clean_project(project)
    if not isinstance(plan,dict):raise PlanError('剪辑方案格式无效，请重新生成方案。')
    if plan.get('goal')!=p['goal'] or plan.get('synthetic')!=(p.get('synthetic') is True):
        raise PlanError('目标或模拟样本标记与项目不一致。')
    if plan.get('timing_verified') is not True:raise PlanError('请先完成配音时长预检，再生成视频。')
    if 'pacing' in plan:
        from pacing import valid_duration_plan
        valid_duration_plan(plan)
    if p['goal']=='promo':
        from validity import period_problem
        validity=next((f['value'] for f in p['facts'] if f['kind']=='validity' and f.get('confirmed') is True),'')
        problem=period_problem(validity)
        if problem:raise PlanError(problem)
    shots={s['id']:s for s in p['shots']}
    facts={f['id']:f for f in p['facts'] if f.get('confirmed') is True}
    segments=plan.get('segments',[])
    if not isinstance(segments,list) or not 1<=len(segments)<=10:
        raise PlanError('剪辑方案必须包含1—10个镜头。')
    used=set(); roles=set();physical_count=0
    for i,seg in enumerate(segments):
        if not isinstance(seg,dict) or not isinstance(seg.get('shot_id'),str) or not isinstance(seg.get('role'),str):
            raise PlanError(f'第{i+1}段方案格式无效，请重新生成方案。')
        role=seg['role'];roles.add(role);clips=segment_clips(seg);physical_count+=len(clips)
        if physical_count>10:raise PlanError('一个视频最多使用10个实际片段。')
        for clip in clips:
            if not isinstance(clip.get('shot_id'),str):raise PlanError('片段编号格式无效。')
            s=shots.get(clip['shot_id'])
            if not s or s.get('confirmed') is not True or s.get('quality_issues') or s.get('semantic_issue') or s.get('unavailable') or s['quality']<0.25 or s['id'] in used:
                raise PlanError('镜头不存在、未确认、质量过低或被重复使用。')
            used.add(s['id'])
            if role not in GOALS[p['goal']]['roles'] or role not in s['tags']:raise PlanError('镜头标签无法支持本段表达。')
            if role=='product' and not product_matches(s,list(facts.values())):raise PlanError('请确认画面中的商品与当前事实卡一致。')
            for k in ('start','end'):
                if not isinstance(clip.get(k),(int,float)) or isinstance(clip[k],bool) or not math.isfinite(clip[k]):raise PlanError('剪辑时间不是有限数值。')
            if clip['start']<s['start'] or clip['end']>s['end']+.001 or not 1<=clip['end']-clip['start']<=8:raise PlanError('剪辑片段超出素材范围或不在1—8秒内。')
        if len(clips)>1 and segment_seconds(seg)>16.000001:raise PlanError('同一旁白组的画面总长不能超过16秒。')
        text,refs=caption_for(role,list(facts.values()),p['goal'])
        if i==len(segments)-1: text+=CTA[p['goal']]
        if seg.get('text')!=text or seg.get('fact_ids')!=refs:
            raise PlanError('文案不符合已确认事实的受限组合，请修改事实卡后重新编排。')
    if any(role not in roles for role in GOALS[p['goal']]['roles']):
        raise PlanError('缺少目标要求的镜头，请补拍或确认。')
    for kind in GOALS[p['goal']]['required_facts']:
        if not any(f['kind']==kind and f['value'].strip() for f in facts.values()):
            raise PlanError('缺少必需的已确认事实。')
    return True
