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
BEFORE anyone builds anything. Every direction the team builds must pass EVERY check, so
checks are about the brand and the mission, never about one creative pattern.

Write 8 to 10 checks from the vocabulary, each with a one-line 'why' citing the research or
brand card. Always include this core, then add up to 2 more that the mission implies:
- duration_between (6 to 15 s for vertical feeds unless the mission says otherwise)
- aspect_ratio from the mission's format
- logo_seconds_at_least 3.0 (the category norm in research sources: brand visible 3s+)
- palette_within 60
- text_contrast_at_least 4.5 (WCAG AA)
- vision_yes about a readable hook in the "first-second frame"
- vision_yes about the brand name shown as an end card in the "last-second frame"
- vision_no about logos of other brands or a health claim being visible

Vision checks see ONE still frame at a time and nothing else. Only ask what a single
picture can answer: text, logos, colors, objects. Never ask about sound, music, beats,
motion, timing or pacing. Name the frame in the question ("first-second frame",
"last-second frame", or "this frame").

Assumptions: list every gap you filled in because the mission was vague (format, language,
market, duration, audio). Ordinary unknowns go here, stated as the choice you made.

Escalations stop the whole flight and page a human, so they are rare. Escalate ONLY when
building would require a decision an agent must not make: the brand card has no palette
or no brand name, or the mission asks for a health, medical or legal claim. Otherwise
"escalations" is an empty list.
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
    plan["escalations"] += [e for e in _card_escalations(brand) if e not in plan["escalations"]]
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


def _card_escalations(brand: Brand) -> list[str]:
    """Deterministic backstop: some brand card gaps always page a human, whatever the model says."""
    from .arbiter import HUMAN_ONLY

    out = []
    if not (brand.primary_hex and brand.secondary_hex):
        out.append("Brand card has no palette; an agent must not pick brand colors.")
    for line in brand.must_haves + brand.never:
        hit = next((w for w in HUMAN_ONLY if w in line.lower()), None)
        # "never: health claims" is a rule we enforce, not a gap; only must_haves can raise it.
        if hit and line in brand.must_haves:
            out.append(f"Brand card says '{line}'; needs a human decision ({hit}).")
    return out


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
