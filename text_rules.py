"""Literal business text shared by narration, validation and subtitles."""
import re

def display_text(value):
    # Preserve literal words while removing document layout separators from ASS.
    return re.sub(r'[\r\n\t\u2028\u2029]+',' ',value)

def supported_text(value):
    return not any(ord(c)<32 and c not in '\r\n\t' for c in value)
