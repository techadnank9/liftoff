"""
Version N+1: the team reviews its own flights and rewrites its own playbook.

    python -m liftoff.playbook                 # baseline -> train -> patch -> held-out
    python -m liftoff.playbook --rounds 2      # repeat the loop

1. Score the held-out missions with the current playbook (no planted failures).
   Score = first-attempt GO rate: how often a vehicle clears every check without a HOLD.
2. Fly the train missions and collect every HOLD with the fix that cleared it.
3. The playbook agent (Nemotron) turns those into short rules for the Director and Spec,
   written to playbook/director.md and playbook/spec.md.
4. Score held-out again. Keep the patch only if first-attempt GO rate rises; otherwise revert.

Writes runs/playbook/report.json for the UI and the slide.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from . import llm, playbook_files
from .run import RUNS, flight

ROOT = Path(__file__).resolve().parent.parent
EVAL = json.loads((ROOT / "eval" / "brands.json").read_text())
OUT = RUNS / "playbook"

SYSTEM = """You are the playbook agent on a launch-video team. You read what went wrong in
recent flights: each HOLD with the failing checks, their measured values, and the Director's
patch that fixed it on the next attempt. Write lessons so the NEXT flight clears on the first
attempt. Rules must be concrete and checkable (numbers, field values), at most 6 per role,
one line each, no hyphens or dashes. Rules must hold for EVERY mission: never copy a
constraint that one mission asked for (a duration, a setting, a theme); the mission itself
always wins. Leave margin above measured thresholds (sampling loses up to 0.25s of logo time). Keep any existing rule that still holds. Director rules
shape the first draft of a direction (fields: duration_s, logo_seconds, bg, hook, body,
end_card, pattern). Spec rules shape the flight plan. Return JSON only:
{"director":[str], "spec":[str], "summary":str}"""


def _fly(mission: str, label: str, i: int, vehicles: int) -> dict[str, Any]:
    run_dir = OUT / label / f"m{i:02d}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    try:
        flight(mission, n_vehicles=vehicles, plant_failure=False, run_dir=run_dir, set_latest=False)
    except Exception as e:  # noqa: BLE001
        return {"mission": mission, "error": str(e)[:200], "vehicles": {}}
    state = json.loads((run_dir / "run.json").read_text())
    return {"mission": mission, "vehicles": state.get("vehicles", {}), "human_pings": state.get("human_pings", 0)}


def batch(missions: list[str], label: str, vehicles: int, workers: int) -> list[dict[str, Any]]:
    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(lambda a: _fly(a[1], label, a[0], vehicles), enumerate(missions)))


def score(flights: list[dict[str, Any]]) -> dict[str, Any]:
    total = first = cleared = attempts = 0
    for f in flights:
        for v in f["vehicles"].values():
            n = len(v.get("attempts", []))
            if not n:
                continue
            total += 1
            attempts += n
            first += int(n == 1 and v.get("status") == "go")
            cleared += int(v.get("status") == "go")
    return {"vehicles": total,
            "first_attempt_go_rate": round(first / total, 3) if total else 0.0,
            "go_rate": round(cleared / total, 3) if total else 0.0,
            "avg_attempts": round(attempts / total, 2) if total else 0.0}


def lessons(flights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every HOLD, the failing checks, and the direction fields that changed before the next attempt."""
    out = []
    for f in flights:
        for vid, v in f["vehicles"].items():
            atts = v.get("attempts", [])
            for a, b in zip(atts, atts[1:]):
                failing = [{"id": r["id"], "check": r.get("check"), "measured": r["measured"], "expected": r["expected"]}
                           for r in a["verdict"]["results"] if not r["pass"]]
                before, after = a.get("direction", {}), b.get("direction", {})
                changed = {k: [before.get(k), after.get(k)] for k in after
                           if k != "notes" and before.get(k) != after.get(k)}
                out.append({"mission": f["mission"], "vehicle": vid, "failing": failing, "fix": changed,
                            "fixed": b["verdict"]["pass"]})
            gc = v.get("goalcheck") or {}
            if atts and gc and not gc.get("satisfies_goal"):
                d = atts[-1].get("direction", {})
                out.append({"mission": f["mission"], "vehicle": vid, "goal_recheck_failed": gc.get("reason", ""),
                            "direction": {k: d.get(k) for k in ("hook", "body", "end_card", "pattern")}})
    return out


def write_patch(holds: list[dict[str, Any]]) -> dict[str, Any]:
    current = {r: (playbook_files.DIR / f"{r}.md").read_text() if (playbook_files.DIR / f"{r}.md").exists() else ""
               for r in ("director", "spec")}
    user = (f"CURRENT PLAYBOOK:\n{json.dumps(current, indent=1)}\n\n"
            f"HOLDS AND GOAL RE-CHECK FAILURES FROM TRAIN FLIGHTS ({len(holds)}):\n{json.dumps(holds[:40], indent=1)}")
    out = llm.call_json("playbook", [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}])
    playbook_files.DIR.mkdir(exist_ok=True)
    for role in ("director", "spec"):
        rules = [str(r).strip() for r in out.get(role, []) if str(r).strip()][:6]
        (playbook_files.DIR / f"{role}.md").write_text("".join(f"- {r}\n" for r in rules))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--vehicles", type=int, default=2)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--limit", type=int, default=10, help="missions per split (fewer = faster, noisier)")
    args = ap.parse_args()

    if llm.MOCK:
        # Mock fixtures always start from an empty playbook so the loop is repeatable.
        shutil.rmtree(playbook_files.DIR, ignore_errors=True)
    # One live search for the whole batch; every flight reads the cached result.
    os.environ["LIFTOFF_RESEARCH_CACHED"] = "1"
    train, held = EVAL["train"][: args.limit], EVAL["held_out"][: args.limit]
    t0 = time.time()
    report: dict[str, Any] = {"started_at": t0, "flights": []}

    print(f"Flight 1: baseline on {len(held)} held-out missions")
    base = score(batch(held, "flight1_heldout", args.vehicles, args.workers))
    report["flights"].append({"flight": 1, "held_out": base, "kept": True, "playbook": _snapshot()})
    print("  ", base)

    best = base
    for rnd in range(args.rounds):
        n = rnd + 2
        print(f"Flight {n}: train on {len(train)} missions, then patch the playbook")
        holds = lessons(batch(train, f"flight{n}_train", args.vehicles, args.workers))
        backup = _snapshot()
        patch = write_patch(holds)
        print(f"   {len(holds)} holds -> {patch.get('summary', '')}")
        new = score(batch(held, f"flight{n}_heldout", args.vehicles, args.workers))
        # Keep only a real improvement: more first-attempt GOs without losing overall GOs.
        kept = (new["first_attempt_go_rate"] > best["first_attempt_go_rate"]
                and new["go_rate"] >= best["go_rate"])
        if kept:
            best = new
        else:
            _restore(backup)
        print(f"   held-out {new}  ->  {'KEPT' if kept else 'reverted'}")
        report["flights"].append({"flight": n, "held_out": new, "kept": kept, "holds": len(holds),
                                  "summary": patch.get("summary", ""), "playbook": _snapshot()})

    report["elapsed_s"] = round(time.time() - t0, 1)
    report["usage"] = llm.usage_report()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(report, indent=1))
    first, last = report["flights"][0]["held_out"], best
    print(f"\nheld-out first-attempt GO rate: flight 1 {first['first_attempt_go_rate']:.0%} "
          f"-> best {last['first_attempt_go_rate']:.0%}  ({report['elapsed_s']}s)")
    print(f"report: {OUT / 'report.json'}")


def _snapshot() -> dict[str, str]:
    return {r: (playbook_files.DIR / f"{r}.md").read_text() if (playbook_files.DIR / f"{r}.md").exists() else ""
            for r in ("director", "spec")}


def _restore(snap: dict[str, str]) -> None:
    playbook_files.DIR.mkdir(exist_ok=True)
    for r, text in snap.items():
        (playbook_files.DIR / f"{r}.md").write_text(text)


if __name__ == "__main__":
    main()
