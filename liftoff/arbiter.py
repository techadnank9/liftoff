"""
Arbiter: the four-way decision after every verifier poll.

  GO     continue; vehicle cleared
  HOLD   re-plan; send failing checks back to the Director with a fix request
  SCRUB  stop; same check failing after MAX_ATTEMPTS, or budget exhausted
  CALL   ping the flight director (human); only for things an agent must not decide

Loop detection: if the same check id fails on consecutive attempts with the same
measured value, that's a loop, not progress -> switch strategy or SCRUB.
Drift detection (Phase 2): embedding distance between the vehicle's text and the
mission + brand tone; stub included so the UI has a telemetry line.
"""
from __future__ import annotations

from typing import Any

from .telemetry import Telemetry

MAX_ATTEMPTS = 3

HUMAN_ONLY = ("health claim", "medical", "legal", "regulat", "unknown brand color", "no palette")


def decide(vehicle: str, attempts: list[dict[str, Any]], escalations: list[str],
           tel: Telemetry) -> dict[str, Any]:
    last = attempts[-1]
    verdict = last["verdict"]

    # CALL: the Spec agent flagged something only a human should decide.
    if escalations:
        tel.state["human_pings"] += 1
        d = {"decision": "CALL", "reason": f"Spec flagged: {escalations[0]}", "flagged": escalations}
        tel.emit("arbiter", "decision", d, vehicle=vehicle)
        return d

    if verdict["pass"]:
        d = {"decision": "GO", "reason": f"All {verdict['total']} checks pass on attempt {len(attempts)}."}
        tel.emit("arbiter", "decision", d, vehicle=vehicle)
        return d

    failing = [r for r in verdict["results"] if not r["pass"]]

    # Loop: same check, same measurement, two attempts in a row.
    if len(attempts) >= 2:
        prev_fail = {r["id"]: r["measured"] for r in attempts[-2]["verdict"]["results"] if not r["pass"]}
        looping = [r["id"] for r in failing if r["id"] in prev_fail and prev_fail[r["id"]] == r["measured"]]
        if looping:
            tel.emit("arbiter", "loop_detected", {"checks": looping}, vehicle=vehicle)
            if len(attempts) >= MAX_ATTEMPTS:
                d = {"decision": "SCRUB", "reason": f"Loop on {looping}; no progress after {len(attempts)} attempts."}
                tel.emit("arbiter", "decision", d, vehicle=vehicle)
                return d
            d = {"decision": "HOLD", "reason": f"Loop on {looping}; switching strategy.", "switch_strategy": True,
                 "failing": failing}
            tel.emit("arbiter", "decision", d, vehicle=vehicle)
            return d

    if len(attempts) >= MAX_ATTEMPTS:
        d = {"decision": "SCRUB", "reason": f"{len(failing)} checks still failing after {MAX_ATTEMPTS} attempts.",
             "failing": failing}
        tel.emit("arbiter", "decision", d, vehicle=vehicle)
        return d

    ids = ", ".join(f"{r['id']} ({r['measured']} vs {r['expected']})" for r in failing)
    d = {"decision": "HOLD", "reason": f"Failing: {ids}. Sending back to Director.", "failing": failing}
    tel.emit("arbiter", "decision", d, vehicle=vehicle)
    return d


def drift_score(mission: str, brand_tone: list[str], direction: dict[str, Any]) -> float:
    """Phase 2 stub: 0 = on mission. Replace with embedding distance (Nemotron embeddings or
    sentence-transformers). Phase 1 heuristic: share of tone words absent from the brief."""
    text = " ".join(str(direction.get(k, "")) for k in ("name", "hook", "body", "end_card")).lower()
    if not brand_tone:
        return 0.0
    missing = sum(1 for t in brand_tone if t.lower() not in text and t.lower() not in mission.lower())
    return round(missing / len(brand_tone) * 0.5, 2)
