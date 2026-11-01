"""Literal business text shared by narration, validation and subtitles."""
import re
from copy import deepcopy

DIRECTION_CONTROLS=re.compile('[\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]')

def direction_problem(value):
    found=sorted(set(DIRECTION_CONTROLS.findall(value)))
    if not found:return None
    codes='、'.join(f'U+{ord(c):04X}' for c in found)
    return f'包含隐藏方向控制字符（{codes}），网页与字幕可能显示不同数字。请重新填写可见文字并确认；系统不会静默删除字符。'

def visible_controls(value):
    return DIRECTION_CONTROLS.sub(lambda m:f'[U+{ord(m[0]):04X}]',value)

def quarantine_text(project):
    """Recover an editable draft, while preserving raw input and revoking consent."""
    p=deepcopy(project)
    if not isinstance(p,dict) or not isinstance(p.get('facts'),list):return p
    for f in p['facts']:
        if not isinstance(f,dict) or not isinstance(f.get('value'),str):continue
        issue=direction_problem(f['value'])
        if issue:
            f.update(original_value=f['value'],value=visible_controls(f['value']),text_review_value=visible_controls(f['value']),text_issue=issue,confirmed=False)
    return p

def display_text(value):
    issue=direction_problem(value)
    if issue:raise ValueError(issue)
    # Preserve literal words while removing document layout separators from ASS.
    return re.sub(r'[\r\n\t\u2028\u2029]+',' ',value)

def supported_text(value):
    return not any(ord(c)<32 and c not in '\r\n\t' for c in value)
