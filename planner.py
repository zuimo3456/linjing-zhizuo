"""Evidence-linked planning. Labels are hypotheses until a person confirms them."""
from __future__ import annotations
import math
from copy import deepcopy

TAGS = ('storefront', 'product', 'process', 'interior', 'person', 'other')
TAG_NAMES = dict(zip(TAGS, ('门头 / 路线', '商品', '制作过程', '环境', '人物', '其他')))
GOALS = {
    'visit': {'name': '到店消费', 'roles': ['storefront', 'product', 'interior'], 'required_facts': ['shop', 'product', 'address']},
    'attract': {'name': '引流关注', 'roles': ['product', 'process', 'interior'], 'required_facts': ['shop', 'product']},
    'promo': {'name': '优惠促销', 'roles': ['product', 'storefront'], 'required_facts': ['shop', 'product', 'offer', 'validity', 'address']},
}
FACT_NAMES = {'shop': '店名', 'product': '商品', 'address': '地址', 'offer': '优惠及使用条件', 'validity': '有效期'}
CTA = {'visit': '到店前，请确认营业情况。', 'attract': '感兴趣可以先收藏。', 'promo': '参与前，请核对活动条件。'}

class PlanError(ValueError):
    pass

def clean_project(project):
    p = deepcopy(project)
    if p.get('goal') not in GOALS:
        raise PlanError('请选择有效营销目标。')
    facts = p.get('facts', [])
    shots = p.get('shots', [])
    if not isinstance(facts, list) or not isinstance(shots, list) or len(facts)>30 or len(shots)>100:
        raise PlanError('事实或镜头数量超出限制。')
    ids = set()
    for f in facts:
        if f.get('id') in ids or not isinstance(f.get('id'), str):
            raise PlanError('事实编号缺失或重复。')
        ids.add(f['id'])
        if f.get('kind') not in FACT_NAMES or not isinstance(f.get('value'),str) or len(f['value'])>100:
            raise PlanError('事实字段无效或超过100字。')
        if f.get('confirmed') is True and not str(f.get('source','')).strip():
            raise PlanError('确认事实时请填写来源。')
    confirmed = [f for f in facts if f.get('confirmed') is True and f['value'].strip()]
    for kind in FACT_NAMES:
        if len([f for f in confirmed if f['kind']==kind])>1:
            raise PlanError(f'{FACT_NAMES[kind]}存在多条已确认记录，请先消除冲突。')
    ids=set()
    for s in shots:
        if s.get('id') in ids or not isinstance(s.get('id'), str):
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
    by_kind = {f['kind']:f for f in facts if f.get('confirmed') is True and f.get('value','').strip()}
    kinds = {'product':['shop','product'], 'storefront':['address'], 'process':[], 'interior':[]}.get(role,[])
    if goal=='promo' and role=='product':
        kinds=['shop','product','offer','validity']
    refs=[by_kind[k]['id'] for k in kinds if k in by_kind]
    if role=='product':
        if 'shop' in by_kind and 'product' in by_kind and goal!='promo':
            text=f"{by_kind['shop']['value']}，带你看看{by_kind['product']['value']}。"
        else:
            text='。'.join(by_kind[k]['value'] for k in kinds if k in by_kind)+'。'
    elif role=='storefront':
        text=('门店地址：'+by_kind['address']['value']+'。') if 'address' in by_kind else '出发前，请确认门店位置。'
    elif role=='process':
        text='这是制作过程。'
    elif role=='interior':
        text='这是店内环境。'
    else:
        text=CTA[goal]
    return text,refs

def product_matches(shot,facts):
    product=next((f for f in facts if f['kind']=='product' and f.get('confirmed') is True),None)
    binding=shot.get('product_binding')
    return bool(product and isinstance(binding,dict) and binding.get('confirmed') is True
                and binding.get('fact_id')==product['id'] and binding.get('value')==product['value'])

def make_plan(project, method='evidence'):
    p=clean_project(project)
    if method not in ('evidence','chronological'):
        raise PlanError('未知编排方法。')
    goal=p['goal']; spec=GOALS[goal]
    facts=[f for f in p['facts'] if f.get('confirmed') is True and f['value'].strip()]
    missing_facts=[k for k in spec['required_facts'] if not any(f['kind']==k for f in facts)]
    eligible=[s for s in p['shots'] if s.get('confirmed') is True and s['quality']>=0.25 and s['end']-s['start']>=1]
    # Maximum-coverage weighted assignment, O(shots * roles * 2^roles).
    # A versatile shot must not greedily consume the only evidence for a later role.
    roles=spec['roles']; states={0:(0.0,{})}
    for shot in eligible:
        updated=dict(states)
        for mask,(score,assignment) in states.items():
            for index,role in enumerate(roles):
                bit=1<<index
                if mask&bit or role not in shot['tags']:continue
                if role=='product' and not product_matches(shot,facts):continue
                newmask=mask|bit
                value=score+shot['quality']+min(shot['end']-shot['start'],8)*0.01
                if newmask not in updated or value>updated[newmask][0]:
                    updated[newmask]=(value,{**assignment,role:shot})
        states=updated
    bestmask=max(states,key=lambda mask:(mask.bit_count(),states[mask][0]))
    assignment=states[bestmask][1]
    selected=[(role,assignment[role]) for role in roles if role in assignment]
    missing_roles=[role for role in roles if role not in assignment]
    if method=='chronological':
        # Same candidates/captions, source order: a transparent, weak baseline.
        order={s['id']:i for i,s in enumerate(p['shots'])}
        selected.sort(key=lambda rs:order[rs[1]['id']])
    segments=[]
    for role,s in selected:
        text,refs=caption_for(role,facts,goal)
        segments.append({'shot_id':s['id'],'role':role,'start':s['start'],'end':min(s['end'],s['start']+7.5),'text':text,'fact_ids':refs,
                         'reason':f'{TAG_NAMES[role]}覆盖目标结构；标签已人工确认；质量分 {s["quality"]:.2f}。'})
    if segments:
        # CTA uses the last evidence frame, with no extra business assertions.
        last=segments[-1]
        last['text']+=CTA[goal]
    missing=[f'请确认{FACT_NAMES[k]}' for k in missing_facts]+[f'请补拍或确认{TAG_NAMES[k]}镜头，建议稳定竖拍5—8秒' for k in missing_roles]
    if 'product' in missing_roles and any('product' in s['tags'] for s in eligible):
        missing.append('请单独确认商品镜头与事实卡中的商品一致；修改商品名称后需要重新确认。')
    return {'schema_version':'1.0','goal':goal,'method':method,'synthetic':p.get('synthetic') is True,
            'segments':segments,'missing':missing,'renderable':bool(segments) and not missing,
            'limitations':['质量分来自抽帧检测，不能证明语义正确。','人工确认仅表示本次输入状态，不能自动证明商户陈述真实。'],
            'assignment':{'algorithm':'maximum_coverage_weighted_matching','score':round(states[bestmask][0],4),'quality_weight':1,'duration_weight':0.01},
            'coverage':{'roles':len(spec['roles'])-len(missing_roles),'required_roles':len(spec['roles']),
                        'facts':len(spec['required_facts'])-len(missing_facts),'required_facts':len(spec['required_facts'])}}

def validate_plan(project, plan):
    p=clean_project(project)
    if plan.get('goal')!=p['goal'] or plan.get('synthetic')!=(p.get('synthetic') is True):
        raise PlanError('目标或模拟样本标记与项目不一致。')
    shots={s['id']:s for s in p['shots']}
    facts={f['id']:f for f in p['facts'] if f.get('confirmed') is True}
    segments=plan.get('segments',[])
    if not isinstance(segments,list) or not 1<=len(segments)<=10:
        raise PlanError('剪辑方案必须包含1—10个镜头。')
    used=set(); roles=set()
    for i,seg in enumerate(segments):
        s=shots.get(seg.get('shot_id'))
        if not s or s.get('confirmed') is not True or s['quality']<0.25 or s['id'] in used:
            raise PlanError('镜头不存在、未确认、质量过低或被重复使用。')
        used.add(s['id']); role=seg.get('role'); roles.add(role)
        if role not in GOALS[p['goal']]['roles'] or role not in s['tags']:
            raise PlanError('镜头标签无法支持本段表达。')
        if role=='product' and not product_matches(s,list(facts.values())):
            raise PlanError('请确认画面中的商品与当前事实卡一致。')
        for k in ('start','end'):
            if not isinstance(seg.get(k),(int,float)) or not math.isfinite(seg[k]):
                raise PlanError('剪辑时间不是有限数值。')
        if seg['start']<s['start'] or seg['end']>s['end']+0.001 or not 1<=seg['end']-seg['start']<=8:
            raise PlanError('剪辑片段超出素材范围或不在1—8秒内。')
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
