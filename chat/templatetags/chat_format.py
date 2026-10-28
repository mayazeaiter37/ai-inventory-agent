"""Render the agent's simple bold labels and lists with escaped content."""
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def format_reply(value):
    text = str(escape(str(value)))
    # Also separate inline list labels in replies already stored in the session.
    text = re.sub(r"\s+-\s+(?=\*\*)", "\n- ", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        is_detail = line.startswith(("- ", "* "))
        if is_detail:
            line = line[2:]
        css = "detail" if is_detail else "reply-line"
        if is_detail and re.search(r"(?:final total|grand total|total including)", line, re.I):
            css += " total"
        lines.append(f'<div class="{css}">{line}</div>')
    return mark_safe("".join(lines))
