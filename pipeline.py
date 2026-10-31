"""Authoritative planning: verified sources, real narration duration, no late surprises."""
from copy import deepcopy
from audio import prepare_voice
from planner import make_plan,clean_project,caption_for,GOALS,CTA,validate_plan,PlanError,segment_seconds
from evidence_store import reconcile,verify_selected

def build_plan(project,method='evidence'):
    p=reconcile(project);lengths={}
    required=GOALS[p['goal']]['required_facts']
    known={f['kind'] for f in p['facts'] if f.get('confirmed') is True and f['value'].strip()}
    from validity import period_problem
    bad_date=p['goal']=='promo' and 'validity' in known and period_problem(next(f['value'] for f in p['facts'] if f['kind']=='validity' and f.get('confirmed') is True))
    if any(k not in known for k in required) or bad_date or not any(s.get('confirmed') for s in p['shots']):
        return make_plan(p,method)
    for role in GOALS[p['goal']]['roles']:
        base=caption_for(role,p['facts'],p['goal'])[0]
        for text in (base,base+CTA[p['goal']]):
            if text not in lengths:lengths[text]=prepare_voice(text)[1]
    plan=make_plan(p,method,lengths)
    if not plan['renderable']:
        from grouped_planner import grouped_fallback
        plan=grouped_fallback(p,plan,lengths,method)
    return plan

def preflight(project,plan):
    p=reconcile(project);checked=deepcopy(plan)
    validate_plan(p,checked);verify_selected(p,checked)
    durations=[]
    for i,seg in enumerate(checked['segments']):
        natural=prepare_voice(seg['text'])[1];available=segment_seconds(seg)
        if natural/1.18+.08>available+.000001:
            raise PlanError(f'第{i+1}段旁白约需{natural:.1f}秒，当前镜头仅{available:.1f}秒，请重新编排或更换更长的素材。')
        seg.update(speech_seconds=natural,minimum_seconds=round(natural/1.18+.08,3))
        from audio import fitted_duration
        durations.append(available if seg.get('clips') else fitted_duration(seg['text'],available,seg['role']))
    total=sum(durations)
    if total>45.000001:
        raise PlanError(f'预计成片共{total:.2f}秒，超过45秒上限，请减少片段或缩短画面区间；旁白不是唯一影响时长的因素。')
    checked['timing_verified']=True
    checked.update(renderable=True,missing=[],estimated_seconds=round(total,3))
    return p,checked
