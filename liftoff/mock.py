"""
Fixtures so the whole pipeline runs with LIFTOFF_MOCK=1 and no API key.
The mock keys off the role and a few words in the last message.
Keep these shaped exactly like the real model outputs so swapping to
real inference is a one-variable change.
"""
from __future__ import annotations

import json
from typing import Any

SPEC_FIXTURE = {
    "flight_plan": [
        {"id": "duration", "check": "duration_between", "args": {"min_s": 6, "max_s": 15},
         "why": "Vertical feeds cut off after 15s; under 6s there is no story."},
        {"id": "aspect", "check": "aspect_ratio", "args": {"ratio": "9:16"},
         "why": "Mission says vertical feeds."},
        {"id": "logo_time", "check": "logo_seconds_at_least", "args": {"min_s": 3.0},
         "why": "Industry norm for brand recall in short-form; cited in spec notes."},
        {"id": "palette", "check": "palette_within", "args": {"max_distance": 60},
         "why": "Background must read as the brand color, not a neighbor."},
        {"id": "hook_first_second", "check": "vision_yes", "args": {
            "question": "Is there a short, readable hook line visible in this first-second frame?"},
         "why": "Hook under 1.5s is the dominant pattern on the trend wall."},
        {"id": "no_competitor_marks", "check": "vision_no", "args": {
            "question": "Does this frame contain any logo, script, or color-block that resembles a well-known cola brand other than the one named in the overlay?"},
         "why": "Brand safety."},
        {"id": "text_legible", "check": "text_contrast_at_least", "args": {"min_ratio": 4.5},
         "why": "WCAG AA contrast so text reads on a phone in daylight."},
        {"id": "end_card", "check": "vision_yes", "args": {
            "question": "Does this last-second frame show the brand name clearly as an end card?"},
         "why": "Every direction must land the name."},
    ],
    "assumptions": [
        "Assumed 9:16 vertical because the mission said 'for vertical feeds'.",
        "Assumed English on-screen text; mission did not specify a language.",
        "Assumed US launch because no market was named; competitor set chosen accordingly.",
        "Assumed no audio track is required for pass/fail; sound is a Phase 2 check.",
    ],
    "escalations": [],
    "spec_notes": "Logo threshold of 3s from category norms (see research.sources).",
}

DIRECTIONS_FIXTURE = {
    "directions": [
        {"id": "A", "name": "Street taste test", "pattern": "taste_test",
         "hook": "We swapped their cola. Watch.", "body": "Nobody noticed.",
         "end_card": "Fizz. Try the swap.", "duration_s": 9, "logo_seconds": 2.4,
         "bg": "primary", "notes": "Planted: logo under threshold on first attempt."},
        {"id": "B", "name": "Ice drop ASMR", "pattern": "asmr",
         "hook": "Turn your sound on.", "body": "Ice. Fizz. Done.",
         "end_card": "Fizz.", "duration_s": 8, "logo_seconds": 4.0,
         "bg": "secondary", "notes": ""},
        {"id": "C", "name": "Launch countdown", "pattern": "countdown",
         "hook": "3 days. 12 cities.", "body": "The cola that isn't theirs.",
         "end_card": "Fizz. Launching Friday.", "duration_s": 10, "logo_seconds": 3.5,
         "bg": "secondary", "notes": ""},
    ]
}

FIX_FIXTURE = {"logo_seconds": 3.4, "notes": "Extended logo hold on end card to clear 3.0s threshold."}

GOALCHECK_FIXTURE = {"satisfies_goal": True,
                     "reason": "A 9s vertical spot with a hook in the first second, the Fizz name held for over 3s, and an end card. Matches 'launch video for Fizz cola, bold, vertical feeds'."}

PLAYBOOK_FIXTURE = {
    "director": ["Draft logo_seconds at 3.4 or more; the flight plan asks for 3.0 and sampling loses about 0.25s.",
                 "Use bg secondary for any direction with white overlay text; white on primary measures 3.8 against 4.5."],
    "spec": ["Keep logo_seconds_at_least at 3.0 and text_contrast_at_least at 4.5; both caught real misses."],
    "summary": "Most holds were logo time and contrast on the primary background.",
}

ARBITER_FIXTURE = {"decision": "GO", "reason": "All checks pass; nothing left to fix."}


def respond(role: str, messages: list[dict[str, Any]]) -> str:
    system = messages[0]["content"] if messages and messages[0].get("role") == "system" else ""
    last = messages[-1]["content"]
    text = last if isinstance(last, str) else " ".join(p.get("text", "") for p in last if isinstance(p, dict))
    low = text.lower()
    if role == "spec":
        return json.dumps(SPEC_FIXTURE)
    if role == "director":
        if "failing checks" in low and "fields to change" in low:
            # Repair based on which checks failed, the way a real Director would.
            patch: dict[str, Any] = {"notes": "mock fix"}
            if "logo_time" in low or "logo_seconds" in low:
                patch["logo_seconds"] = 3.4
            if "text_legible" in low or "contrast" in low:
                patch["bg"] = "secondary"
            return json.dumps(patch)
        if "PLAYBOOK" in str(system) and "logo_seconds" in str(system):
            # A Director that read the playbook drafts above the thresholds it learned.
            fixed = json.loads(json.dumps(DIRECTIONS_FIXTURE))
            for d in fixed["directions"]:
                d["logo_seconds"] = max(d["logo_seconds"], 3.4)
                d["bg"] = "secondary"
            return json.dumps(fixed)
        return json.dumps(DIRECTIONS_FIXTURE)
    if role == "verifier_vision":
        # The vision verifier answers yes/no. In mock we answer the way a good
        # frame would. "no_competitor" questions want NO; others want YES.
        if "other than" in low or "resembles" in low:
            return json.dumps({"answer": "no", "confidence": 0.9, "reason": "Only the Fizz mark is visible."})
        return json.dumps({"answer": "yes", "confidence": 0.85, "reason": "Visible and readable."})
    if role == "goalcheck":
        return json.dumps(GOALCHECK_FIXTURE)
    if role == "arbiter":
        return json.dumps(ARBITER_FIXTURE)
    if role == "playbook":
        return json.dumps(PLAYBOOK_FIXTURE)
    if role in ("scout", "librarian"):
        return json.dumps({"note": "mock"})
    return "{}"
