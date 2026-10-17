"""
Goal re-check: the last line of defense against "passed every predicate, missed the goal".

A fresh call that gets ONLY the original one-line mission, the brand card, and
sampled frames of the final vehicle. No flight plan, no Director reasoning.
It answers: does this satisfy the goal as written?
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import llm
from .brand import Brand
from .telemetry import Telemetry

SYSTEM = """You are an independent reviewer. You will see a one-line mission, a brand card and
three frames (first second, middle, last second) from a finished short video. Decide whether
the video satisfies the mission AS WRITTEN. Ignore polish. Return JSON only:
{"satisfies_goal": true|false, "reason": str}"""


def run(mission: str, brand: Brand, frames: list[Path], tel: Telemetry, vehicle: str) -> dict[str, Any]:
    tel.emit("goalcheck", "start", {}, vehicle=vehicle)
    pick = [frames[1 if len(frames) > 1 else 0], frames[len(frames) // 2], frames[-1]]
    content: list[dict[str, Any]] = [{"type": "text", "text": f"MISSION: {mission}\nBRAND: {json.dumps(brand.to_dict())}"}]
    for fp in pick:
        content += llm.image_content(fp, f"frame {fp.name}")
    out = llm.call_json("goalcheck", [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}])
    raw = out.get("satisfies_goal") if isinstance(out, dict) else None
    # Models sometimes answer "false" or "no" as strings; bool("false") would be True.
    ok = raw is True or str(raw).strip().lower() in ("true", "yes", "1")
    out = {"satisfies_goal": ok, "reason": out.get("reason", "") if isinstance(out, dict) else str(out)}
    tel.emit("goalcheck", "verdict", out, vehicle=vehicle)
    return out
