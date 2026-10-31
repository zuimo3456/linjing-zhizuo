"""Bounded fallback: one narration role may span multiple confirmed short clips."""
from copy import deepcopy
from planner import GOALS,CTA,caption_for,product_matches

def grouped_fallback(project,original,lengths,method):
    p=project;roles=GOALS[p['goal']]['roles'];order={s['id']:i for i,s in enumerate(p['shots'])}
    eligible=[s for s in p['shots'] if s.get('confirmed') is True and not any(s.get(k) for k in ('quality_issues','semantic_issue','unavailable')) and s['quality']>=.25 and s['end']-s['start']>=1]
    candidates={}
    for role in roles:
        support=[s for s in eligible if role in s['tags'] and (role!='product' or product_matches(s,p['facts']))]
        support.sort(key=(lambda s:order[s['id']]) if method=='chronological' else (lambda s:(-s['quality'],-min(8,s['end']-s['start']),order[s['id']])))
        # Keep strong single candidates; add windows of 2-4 short confirmed clips.
        choices=[[s] for s in support[:12]]
        short=[s for s in support if s['end']-s['start']<8][:12]
        for count in (2,3,4):
            for i in range(max(0,len(short)-count+1)):
                bundle=short[i:i+count]
                if sum(min(8,s['end']-s['start']) for s in bundle)<=16:choices.append(bundle)
        candidates[role]=choices
    best=None;best_score=-1
    def visit(index,assigned,used,count):
        nonlocal best,best_score
        if index==len(roles):
            selected=list(assigned.items())
            if method=='chronological':
                selected.sort(key=lambda item:min(order[s['id']] for s in item[1]))
                if any(max(order[s['id']] for s in a[1])>=min(order[s['id']] for s in b[1]) for a,b in zip(selected,selected[1:])):return
            segments=[];score=0
            for n,(role,bundle) in enumerate(selected):
                clips=[{'shot_id':s['id'],'start':s['start'],'end':min(s['end'],s['start']+8)} for s in bundle]
                text,refs=caption_for(role,p['facts'],p['goal']);text+=CTA[p['goal']] if n==len(selected)-1 else ''
                available=sum(c['end']-c['start'] for c in clips)
                if lengths.get(text,float('inf'))/1.18+.08>available+.000001:return
                seg={**clips[0],'role':role,'text':text,'fact_ids':refs,'reason':f'{len(clips)}个已确认片段共同承载一段旁白。','speech_seconds':lengths[text],'minimum_seconds':round(lengths[text]/1.18+.08,3)}
                if len(clips)>1:seg['clips']=clips
                segments.append(seg);score+=sum(s['quality'] for s in bundle)/len(bundle)-.03*(len(bundle)-1)
            if score>best_score:best_score=score;best=segments
            return
        role=roles[index]
        for bundle in candidates[role]:
            ids={s['id'] for s in bundle}
            if ids&used or count+len(bundle)>10:continue
            visit(index+1,{**assigned,role:bundle},used|ids,count+len(bundle))
    visit(0,{},set(),0)
    if best is None:return original
    result=deepcopy(original);result.update(segments=best,missing=[],renderable=True,timing_verified=True)
    result['assignment']={'algorithm':'bounded_grouped_fallback','score':round(best_score,3),'max_clips_per_role':4,'max_total_clips':10}
    result['coverage']={'roles':len(roles),'required_roles':len(roles),'facts':len(GOALS[p['goal']]['required_facts']),'required_facts':len(GOALS[p['goal']]['required_facts'])}
    return result
