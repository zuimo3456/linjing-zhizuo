"""Literal business text shared by narration, validation and subtitles."""
import re

def display_text(value):
    # CRLF is one separator, never an ASS event boundary; words are not dropped.
    return re.sub(r'[\r\n\t]+',' ',value)

def supported_text(value):
    return not any(ord(c)<32 and c not in '\r\n\t' for c in value)
