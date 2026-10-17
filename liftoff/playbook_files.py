"""Playbook files: lessons the team wrote for itself after earlier flights.

The Spec agent and the Director read these before every call (the shared brain).
liftoff/playbook.py writes them, and keeps a change only if held-out missions improve.
"""
from __future__ import annotations

from pathlib import Path

from .llm import MOCK

_ROOT = Path(__file__).resolve().parent.parent
# Mock runs write their own playbook so fixtures never overwrite the real lessons.
DIR = _ROOT / "runs" / "playbook_mock" if MOCK else _ROOT / "playbook"


def read(role: str) -> str:
    p = DIR / f"{role}.md"
    if not p.exists() or not p.read_text().strip():
        return ""
    return "\n\nPLAYBOOK (lessons from earlier flights; follow them):\n" + p.read_text().strip()
