"""Bounded fallback: one narration role may span multiple confirmed short clips."""
from copy import deepcopy
import math
from itertools import combinations
from planner import GOALS,CTA,TAG_NAMES,caption_for,product_matches
MAX_COMBINATION_ATTEMPTS=100000

def choice_score(bundle):
    return sum(s['quality'] for s in bundle)/len(bundle)-.03*(len(bundle)-1)

def grouped_fallback(project,original,lengths,method,duration_policy=None):
    p=project;roles=GOALS[p['goal']]['roles'];order={s['id']:i for i,s in enumerate(p['shots'])}
    eligible=[s for s in p['shots'] if s.get('confirmed') is True and not any(s.get(k) for k in ('quality_issues','semantic_issue','unavailable')) and s['quality']>=.25 and s['end']-s['start']>=1]
    candidates={};pool_limited=False
    for role in roles:
        support=[s for s in eligible if role in s['tags'] and (role!='product' or product_matches(s,p['facts']))]
        support.sort(key=(lambda s:order[s['id']]) if method=='chronological' else (lambda s:(-s['quality'],-min(8,s['end']-s['start']),order[s['id']])))
        pool_limited=pool_limited or len(support)>12
        # Every source contributes at most 8s, including sources exactly 8s long.
        choices=[[s] for s in support[:12]]
        groupable=support[:12]
        for count in (2,3,4):
            for bundle in combinations(groupable,count):
                if sum(min(8,s['end']-s['start']) for s in bundle)<=16.000001:choices.append(list(bundle))
        base=caption_for(role,p['facts'],p['goal'])[0];minimum=lengths.get(base,float('inf'))/1.18+.08
        if duration_policy:
            target=duration_policy['preferred_seconds']/len(roles)
            choices=[b for b in choices if sum(min(8,s['end']-s['start']) for s in b)>=minimum]
            candidates[role]=sorted(choices,key=lambda b:(abs(sum(min(8,s['end']-s['start']) for s in b)-target),-choice_score(b),len(b)))
        else:candidates[role]=sorted(choices,key=lambda bundle:(sum(min(8,s['end']-s['start']) for s in bundle)>=minimum,choice_score(bundle)),reverse=True)
    suffix_best=[0.]*(len(roles)+1)
    for i in range(len(roles)-1,-1,-1):suffix_best[i]=suffix_best[i+1]+max((choice_score(b) for b in candidates[roles[i]]),default=0)
    best=None;best_score=-1;best_key=None;closest=None;closest_key=None;attempts=0;exhausted=False;longest=0.
    def visit(index,assigned,used,count,partial_score=0.):
        nonlocal best,best_score,best_key,closest,closest_key,attempts,exhausted,longest
        if not duration_policy and best is not None and partial_score+suffix_best[index]<=best_score+1e-10:return
        if index==len(roles):
            selected=list(assigned.items())
            if method=='chronological':
                selected.sort(key=lambda item:min(order[s['id']] for s in item[1]))
                if any(max(order[s['id']] for s in a[1])>=min(order[s['id']] for s in b[1]) for a,b in zip(selected,selected[1:])):return
            elif duration_policy:
                # Keep the usual order when its final role can carry the CTA.
                # Otherwise close on another already-confirmed role; don't ask
                # for new footage merely because the last environment shot is short.
                def can_close(item):
                    role,bundle=item;text=caption_for(role,p['facts'],p['goal'])[0]+CTA[p['goal']]
                    return lengths.get(text,float('inf'))/1.18+.08<=sum(min(8,s['end']-s['start']) for s in bundle)+.000001
                if not can_close(selected[-1]):
                    closer=next((item for item in selected if can_close(item)),None)
                    if closer is not None:selected=[item for item in selected if item[0]!=closer[0]]+[closer]
            segments=[];score=0;diagnostics=[]
            for n,(role,bundle) in enumerate(selected):
                clips=[{'shot_id':s['id'],'start':s['start'],'end':min(s['end'],s['start']+8)} for s in bundle]
                text,refs=caption_for(role,p['facts'],p['goal']);text+=CTA[p['goal']] if n==len(selected)-1 else ''
                available=sum(c['end']-c['start'] for c in clips)
                natural=lengths.get(text,float('inf'));minimum=natural/1.18+.08
                if not math.isfinite(natural):return
                diagnostics.append({'role':role,'text':text,'speech_seconds':natural,'minimum_seconds':round(minimum,3),
                                    'available_seconds':round(available,3),'clip_count':len(clips),'includes_cta':n==len(selected)-1,
                                    'shortfall_seconds':max(0,minimum-available) if minimum>available+.000001 else 0})
                seg={**clips[0],'role':role,'text':text,'fact_ids':refs,'reason':f'{len(clips)}个已确认片段共同承载一段旁白。','speech_seconds':lengths[text],'minimum_seconds':round(lengths[text]/1.18+.08,3)}
                if len(clips)>1:seg['clips']=clips
                segments.append(seg);score+=sum(s['quality'] for s in bundle)/len(bundle)-.03*(len(bundle)-1)
            failed=[d for d in diagnostics if d['shortfall_seconds']>0]
            if failed:
                key=(sum(d['shortfall_seconds'] for d in failed),len(failed),-score)
                if closest_key is None or key<closest_key:closest_key=key;closest=diagnostics
                return
            if duration_policy:
                from pacing import PLANNING_MAX
                total=sum(c['end']-c['start'] for s in segments for c in s.get('clips',[s]));longest=max(longest,total)
                if not duration_policy['min_seconds']<=total<=PLANNING_MAX+.000001:return
                key=(round(abs(total-duration_policy['preferred_seconds']),3),-score,count)
                if best_key is None or key<best_key:best_key=key;best_score=score;best=segments
            elif score>best_score:best_score=score;best=segments
            return
        role=roles[index]
        for bundle in candidates[role]:
            if attempts>=MAX_COMBINATION_ATTEMPTS:exhausted=True;return
            attempts+=1
            ids={s['id'] for s in bundle}
            if ids&used or count+len(bundle)>10:continue
            visit(index+1,{**assigned,role:bundle},used|ids,count+len(bundle),partial_score+choice_score(bundle))
    visit(0,{},set(),0)
    if best is None:
        if duration_policy:
            result=deepcopy(original);result.update(renderable=False,pacing=deepcopy(duration_policy))
            result['search']={'attempts':attempts,'attempt_limit':MAX_COMBINATION_ATTEMPTS,'candidate_pool_limited':pool_limited,'exhausted':exhausted}
            if exhausted or pool_limited:
                message='本次有界搜索未找到15–30秒方案，不能据此认定素材不足；请精简候选或确认更多同用途画面。'
            elif longest and longest<duration_policy['min_seconds']:
                message=f'已确认且能承载旁白的不同画面最多组合{longest:.1f}秒，至少需要15秒；请补充或确认更多商品、制作或环境镜头。'
            else:message='当前已确认画面无法同时满足完整旁白、必需用途及15–30秒时长，请补充镜头后重新编排。'
            result['missing']=list(dict.fromkeys(original.get('missing',[])+[message]));return result
        if closest is None or not original.get('timing_verified'):
            if not (exhausted or pool_limited):return original
            result=deepcopy(original);result['missing']=['本次有界组合搜索未找到方案，不能据此认定现有素材一定不足。请减少候选素材后重试。'];return result
        result=deepcopy(original);result['timing_diagnostics']=closest
        # A complete, disjoint assignment exists; report its actual speech gaps,
        # including the last role's CTA and the available multi-source duration.
        result['missing']=[f'{TAG_NAMES[d["role"]]}{ "（包含结尾引导语）" if d["includes_cta"] else ""}旁白约{d["speech_seconds"]:.1f}秒，至少需要{d["minimum_seconds"]:.1f}秒画面；当前{d["clip_count"]}个可组合片段合计{d["available_seconds"]:.1f}秒。请补充画面或调整非必要文案，保留完整活动条件。'
                           for d in closest if d['shortfall_seconds']>0]
        if exhausted or pool_limited:result['missing']=['本次搜索受候选数量或计算上限限制，不能认定现有素材一定不足；以下只说明已检查组合的缺口。']+result['missing']
        result['search']={'attempts':attempts,'attempt_limit':MAX_COMBINATION_ATTEMPTS,'candidate_pool_limited':pool_limited,'exhausted':exhausted}
        return result
    result=deepcopy(original);result.update(segments=best,missing=[],renderable=True,timing_verified=True)
    if duration_policy:
        result['pacing']=deepcopy(duration_policy)
        result['estimated_seconds']=round(sum(c['end']-c['start'] for s in best for c in s.get('clips',[s])),3)
        result['closing_role']=best[-1]['role']
    result['assignment']={'algorithm':'bounded_grouped_fallback','score':round(best_score,3),'max_clips_per_role':4,'max_total_clips':10,
                          'attempts':attempts,'attempt_limit':MAX_COMBINATION_ATTEMPTS,'candidate_pool_limited':pool_limited,'exhausted':exhausted}
    result['coverage']={'roles':len(roles),'required_roles':len(roles),'facts':len(GOALS[p['goal']]['required_facts']),'required_facts':len(GOALS[p['goal']]['required_facts'])}
    return result
