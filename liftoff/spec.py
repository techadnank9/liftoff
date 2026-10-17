"""
Spec agent: one-line mission + brand card + research -> flight plan.

The flight plan is a list of executable predicates (see verifier.CHECKS for
the vocabulary). It is written BEFORE any vehicle is built and then locked.
The agent also writes the assumption ledger: every gap it filled in.
"""
from __future__ import annotations

import json
from typing import Any

from . import llm
from .brand import Brand
from .telemetry import Telemetry

CHECK_VOCAB = """
Available checks (use only these; args must match):
- duration_between {min_s, max_s}
- aspect_ratio {ratio: "9:16"|"1:1"|"16:9"}
- logo_seconds_at_least {min_s}
- palette_within {max_distance}            (RGB distance of background to brand primary/secondary)
- text_contrast_at_least {min_ratio}       (WCAG contrast of overlay text vs background)
- vision_yes {question}                    (asked of sampled frames; must be YES)
- vision_no {question}                     (asked of sampled frames; must be NO)
"""

SYSTEM = """You are the Spec agent on a launch-video team. You write the definition of done
BEFORE anyone builds anything. Turn the mission into 6 to 10 executable checks from the
vocabulary, each with a one-line 'why' that cites the research or brand card where possible.
Then list every assumption you had to make because the mission was vague (format, language,
market, duration, audio). If something cannot be assumed safely (a legal claim, an unknown
brand color, a market with rules you don't know) put it in 'escalations' instead of guessing.
Use each check's argument names exactly as listed, numbers as numbers. Every id must be unique.
Never invent a check name. Return JSON only, no prose, no code fences:
{"flight_plan":[{"id":str,"check":str,"args":{},"why":str}],
 "assumptions":[str], "escalations":[str], "spec_notes":str}
"""


def run(mission: str, brand: Brand, research: dict[str, Any], tel: Telemetry) -> dict[str, Any]:
    tel.emit("spec", "start", {"mission": mission})
    user = (
        f"MISSION: {mission}\n\nBRAND CARD:\n{json.dumps(brand.to_dict(), indent=1)}\n\n"
        f"RESEARCH (patterns, stats, sources):\n{json.dumps({k: research.get(k) for k in ('patterns', 'stats', 'sources')}, indent=1)}\n\n"
        f"{CHECK_VOCAB}\nWrite the flight plan."
    )
    plan = llm.call_json("spec", [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}])
    plan.setdefault("assumptions", [])
    plan.setdefault("escalations", [])
    plan["flight_plan"] = [p for p in plan.get("flight_plan", []) if _valid(p)]
    tel.set(flight_plan=plan["flight_plan"], assumptions=plan["assumptions"],
            escalations=plan["escalations"], spec_locked=True)
    tel.emit("spec", "locked", {"checks": len(plan["flight_plan"]),
                                "assumptions": len(plan["assumptions"]),
                                "escalations": len(plan["escalations"])})
    for a in plan["assumptions"]:
        tel.emit("spec", "assumption", {"text": a})
    for e in plan["escalations"]:
        tel.emit("spec", "escalation", {"text": e})
    return plan


ARGS = {
    "duration_between": {"min_s", "max_s"},
    "aspect_ratio": {"ratio"},
    "logo_seconds_at_least": {"min_s"},
    "palette_within": {"max_distance"},
    "text_contrast_at_least": {"min_ratio"},
    "vision_yes": {"question"},
    "vision_no": {"question"},
}


def _valid(p: dict[str, Any]) -> bool:
    """Keep only checks in the vocabulary with exactly the right args. Coerces numeric strings."""
    from .verifier import CHECKS

    if not (isinstance(p, dict) and p.get("check") in CHECKS and isinstance(p.get("args"), dict)):
        return False
    args = p["args"]
    if set(args) != ARGS[p["check"]]:
        return False
    for k, v in args.items():
        if k not in ("ratio", "question"):
            try:
                args[k] = float(v)
            except (TypeError, ValueError):
                return False
    p.setdefault("id", p["check"])
    return True
