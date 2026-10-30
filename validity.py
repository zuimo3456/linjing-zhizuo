"""Strict, local-calendar validation; unknown date wording never silently passes."""
import re
from datetime import date,datetime,timedelta,timezone

def current_date():return datetime.now(timezone(timedelta(hours=8))).date()

def parse_period(text):
    text=re.sub(r'\s+','',text)
    full=r'(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})日?'
    parts=re.split(r'至|到|~|～|—|–',text)
    try:
        if len(parts) not in (1,2):raise ValueError()
        start_match=re.fullmatch(full,parts[0])
        if not start_match:raise ValueError()
        start=date(*map(int,start_match.groups()));end=start
        if len(parts)==2:
            ending=parts[1];m=re.fullmatch(full,ending)
            if m:end=date(*map(int,m.groups()))
            else:
                md=re.fullmatch(r'(\d{1,2})月(\d{1,2})日?',ending)
                dd=re.fullmatch(r'(\d{1,2})日?',ending)
                if md:end=date(start.year,*map(int,md.groups()))
                elif dd:end=date(start.year,start.month,int(dd.group(1)))
                else:raise ValueError()
        return start,end
    except (ValueError,TypeError):
        raise ValueError('有效期无法识别，请填写明确日期，例如2027年5月1日至2027年5月7日。') from None

def period_problem(text,today=None):
    try:start,end=parse_period(text)
    except ValueError as e:return str(e)
    if end<start:return '活动结束日期早于开始日期，请更正有效期。'
    if end<(today or current_date()):return f'活动已于{end.isoformat()}结束，请更新有效期后再生成促销视频。'
    return None
