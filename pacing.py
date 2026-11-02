"""Shared duration contract: use real footage without repeats or held frames."""
POLICY={'version':'real-footage-15-30-v1','min_seconds':15.,'preferred_seconds':22.,'max_seconds':30.}
PLANNING_MAX=29.8  # Allow frame quantization and AAC container padding.

def narration_offset(spoken,available):
    """Balance visual breathing room before and after the measured narration."""
    return round(max(0.,(available-spoken-.08)/2),4)

def valid_duration_plan(plan):
    from planner import PlanError,segment_seconds
    if plan.get('pacing')!=POLICY:
        raise PlanError('成片时长规则已更新为15–30秒，请重新生成可检查的方案；素材与事实会保留。')
    try:seconds=sum(segment_seconds(s) for s in plan.get('segments',[]))
    except (TypeError,KeyError,AttributeError):raise PlanError('剪辑时长或片段格式无效，请重新编排。') from None
    if not POLICY['min_seconds']<=seconds<=PLANNING_MAX+.000001:
        raise PlanError(f'当前已选画面共{seconds:.1f}秒，未满足15–30秒成片要求，请重新编排或补充已确认素材。')
    return seconds
