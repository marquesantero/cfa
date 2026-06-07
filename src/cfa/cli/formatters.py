"""
CFA CLI — formatters
====================
Output formatters for CLI results: table, JSON, summary.
Zero external dependencies — uses only stdlib.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Force UTF-8 on Windows if possible
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

# ANSI color codes (only when stdout is a TTY)
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_BLUE = "\033[34m"
_CYAN = "\033[36m"


def _use_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"{code}{text}{_RESET}" if _use_color() else text


_ICONS_UTF8 = {
    "approved": "✓", "approved_with_warnings": "⚠", "blocked": "✗",
    "replanned": "↻", "rolled_back": "↩", "quarantined": "⊘",
    "partially_committed": "◐", "promotion_candidate": "★",
}
_ICONS_ASCII = {
    "approved": "[OK]", "approved_with_warnings": "[!!]", "blocked": "[XX]",
    "replanned": "[>>]", "rolled_back": "[<<]", "quarantined": "[??]",
    "partially_committed": "[~]", "promotion_candidate": "[**]",
}
_BOX_UTF8 = {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│", "ml": "├", "mr": "┤", "x": "┼"}
_BOX_ASCII = {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|", "ml": "+", "mr": "+", "x": "+"}

_UTF8_OK = True
try:
    "┌─✓".encode(sys.stdout.encoding or "ascii")
except (UnicodeEncodeError, UnicodeDecodeError):
    _UTF8_OK = False

# Force ASCII on Windows unless explicitly using UTF-8 terminal
if sys.platform == "win32" and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    _UTF8_OK = False


def _visible_len(text: str) -> int:
    """String length excluding ANSI color codes."""
    return len(_ANSI_RE.sub("", text))


def _pad_right(text: str, width: int) -> str:
    """Pad text to visible width, accounting for ANSI codes."""
    visible = _visible_len(text)
    if visible >= width:
        return text
    return text + " " * (width - visible)


def _pad_center(text: str, width: int, fillchar: str = " ") -> str:
    """Center text accounting for ANSI codes."""
    visible = _visible_len(text)
    if visible >= width:
        return text
    left = (width - visible) // 2
    right = width - visible - left
    return (fillchar * left) + text + (fillchar * right)


def _icon(state: str) -> str:
    icons = _ICONS_UTF8 if _UTF8_OK else _ICONS_ASCII
    return icons.get(state, "?")


def _box(key: str) -> str:
    b = _BOX_UTF8 if _UTF8_OK else _BOX_ASCII
    return b.get(key, key)


def _status_icon(state: str) -> str:
    icon = _icon(state)
    colors = {
        "✓": _GREEN, "[OK]": _GREEN,
        "⚠": _YELLOW, "[!!]": _YELLOW,
        "✗": _RED, "[XX]": _RED,
        "↻": _YELLOW, "[>>]": _YELLOW,
        "↩": _RED, "[<<]": _RED,
        "⊘": _YELLOW, "[??]": _YELLOW,
        "◐": _YELLOW, "[~]": _YELLOW,
        "★": _GREEN, "[**]": _GREEN,
    }
    code = colors.get(icon, "")
    return _c(code, icon)


def _severity_color(severity: str) -> str:
    return {
        "critical": _c(_RED, severity.upper()),
        "high": _c(_RED, severity.upper()),
        "warning": _c(_YELLOW, severity.upper()),
        "info": _c(_BLUE, severity.upper()),
    }.get(severity, severity.upper())


def _table_line(widths: list[int], cells: list[str], pad: int = 1) -> str:
    parts: list[str] = []
    v = _box("v")
    for w, cell in zip(widths, cells, strict=False):
        if w > 2:
            inner = " " + _pad_right(cell, w - 2) + " "
        else:
            inner = cell
        parts.append(inner)
    return v + v.join(parts) + v


def _table_sep(widths: list[int], left: str | None = None, mid: str | None = None, right: str | None = None) -> str:
    left = left or _box("ml")
    mid = mid or _box("x")
    right = right or _box("mr")
    parts = [left]
    for i, w in enumerate(widths):
        parts.append(_box("h") * w)
        if i < len(widths) - 1:
            parts.append(mid)
    parts.append(right)
    return "".join(parts)


def format_evaluate_table(result: dict[str, Any], faults: list[dict[str, Any]]) -> str:
    """Format an evaluate result as a bordered table."""
    state = result.get("state", "unknown")
    lines: list[str] = []
    h = _box("h")
    tl, tr, bl, br = _box("tl"), _box("tr"), _box("bl"), _box("br")

    width = 60
    title = " CFA Evaluation Result "
    lines.append(f"{tl}{_pad_center(title, width - 2, h)}{tr}")
    lines.append(_table_line([width], [""]))
    lines.append(_table_line([width], [f"Intent: {result.get('intent', '')[:width - 12]}"]))
    icon = _status_icon(state)
    lines.append(_table_line([width], [f"State:  {icon} {state}"]))
    hash_val = result.get("signature_hash", "")
    if hash_val:
        lines.append(_table_line([width], [f"Hash:   {hash_val}"]))
    lines.append(_table_line([width], [f"Policy: {result.get('policy_bundle', '')}  |  Replans: {result.get('replan_count', 0)}"]))
    lines.append(_table_line([width], [""]))

    if faults:
        lines.append(_table_line([width], [_c(_BOLD, "Faults")]))
        lines.append(_table_line([width], [""]))
        for f in faults:
            sev = _severity_color(f.get("severity", "high"))
            code = f.get("code", "")
            msg = f.get("message", "")
            lines.append(_table_line([width], [f" {sev}  {code}"]))
            lines.append(_table_line([width], [f"     {msg[:width - 10]}"]))
            remediation = f.get("remediation", [])
            if remediation:
                for i, r in enumerate(remediation[:3]):
                    lines.append(_table_line([width], [f"     {_c(_DIM, f'{i+1}. {r[:width - 12]}')}"]))
            lines.append(_table_line([width], [""]))

    lines.append(f"{bl}{h * (width - 2)}{br}")
    return "\n".join(lines)


def format_json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)


def format_summary(result: dict[str, Any], faults: list[dict[str, Any]]) -> str:
    """Human-readable paragraph summary."""
    state = result.get("state", "unknown")
    icon = _status_icon(state)
    lines = [
        f"{icon}  CFA: {state.upper()}",
        f"Intent: {result.get('intent', '')}",
        f"Hash:   {result.get('signature_hash', 'n/a')}",
        f"Policy: {result.get('policy_bundle', '')}",
        f"Replans: {result.get('replan_count', 0)}",
    ]
    if faults:
        lines.append(f"Faults: {len(faults)}")
        for f in faults:
            lines.append(f"  [{_severity_color(f.get('severity', 'high'))}] {f.get('code', '')}")
    return "\n".join(lines)


def format_rules_table(rules: list[dict[str, str]]) -> str:
    h, tl, tr, bl, br = _box("h"), _box("tl"), _box("tr"), _box("bl"), _box("br")
    width = 80
    lines: list[str] = []
    title = " CFA Policy Rules "
    lines.append(f"{tl}{title.center(width - 2, h)}{tr}")

    header_w = [28, 12, 20, 8, 8]
    lines.append(_table_line(header_w, ["NAME", "ACTION", "FAULT CODE", "SEVERITY", "FAMILY"]))
    lines.append(_table_sep(header_w))
    for r in rules:
        lines.append(_table_line(header_w, [
            r.get("name", "")[:26],
            r.get("action", "").upper()[:10],
            r.get("fault_code", "")[:18],
            r.get("severity", "")[:6],
            r.get("family", "")[:6],
        ]))
    lines.append(f"{bl}{h * (width - 2)}{br}")
    return "\n".join(lines)


def format_backends_list(backends: list[dict[str, Any]]) -> str:
    h, tl, tr, bl, br = _box("h"), _box("tl"), _box("tr"), _box("bl"), _box("br")
    width = 60
    lines: list[str] = []
    title = " CFA Registered Backends "
    lines.append(f"{tl}{title.center(width - 2, h)}{tr}")
    header_w = [20, 18, 18]
    lines.append(_table_line(header_w, ["NAME", "MERGE", "ANONYMIZE"]))
    lines.append(_table_sep(header_w))
    ok, fail = _c(_GREEN, _icon("approved")), _c(_RED, _icon("blocked"))
    for b in backends:
        lines.append(_table_line(header_w, [
            b.get("name", "")[:18],
            ok if b.get("supports_merge") else fail,
            ok if b.get("supports_anonymization") else fail,
        ]))
    lines.append(f"{bl}{h * (width - 2)}{br}")
    return "\n".join(lines)


def format_audit_table(events: list[dict[str, Any]], chain_intact: bool = True) -> str:
    h, tl, tr, bl, br = _box("h"), _box("tl"), _box("tr"), _box("bl"), _box("br")
    width = 80
    lines: list[str] = []
    title = " CFA Audit Trail "
    lines.append(f"{tl}{title.center(width - 2, h)}{tr}")

    chain_status = _c(_GREEN, f"{_icon('approved')} INTACT") if chain_intact else _c(_RED, f"{_icon('blocked')} BROKEN")
    lines.append(_table_line([width], [f"Chain: {chain_status}  |  Events: {len(events)}"]))
    lines.append(_table_line([width], [""]))

    if events:
        header_w = [4, 21, 16, 14, 19]
        lines.append(_table_line(header_w, ["#", "TIMESTAMP", "PHASE", "EVENT", "OUTCOME"]))
        lines.append(_table_sep(header_w))
        for i, e in enumerate(events[:50]):
            ts = e.get("timestamp", "")[:19]
            lines.append(_table_line(header_w, [
                str(i + 1),
                ts,
                e.get("phase", e.get("stage", ""))[:14],
                e.get("event_type", "")[:12],
                e.get("outcome", "")[:17],
            ]))
        if len(events) > 50:
            lines.append(_table_line([width], [f"  ... and {len(events) - 50} more events"]))
    lines.append(f"{bl}{h * (width - 2)}{br}")
    return "\n".join(lines)
