"""
One lap (one "flight") of Liftoff.

    python -m liftoff.run --mission "Launch video for Fizz cola, bold, for vertical feeds" --brand fizz

Writes runs/<timestamp>/run.json and events.jsonl which the Streamlit UI tails.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from . import arbiter, director, goalcheck, llm, research, spec, verifier
from .brand import load as load_brand
from .telemetry import Telemetry

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"


def flight(mission: str, brand_name: str = "fizz", n_vehicles: int = 3, plant_failure: bool = True,
           run_dir: Path | None = None) -> Path:
    run_dir = run_dir or RUNS / time.strftime("%Y%m%d-%H%M%S")
    tel = Telemetry(run_dir)
    (RUNS / "latest").unlink(missing_ok=True)
    try:
        (RUNS / "latest").symlink_to(run_dir.name)
    except OSError:
        (RUNS / "latest.txt").write_text(str(run_dir))

    brand = load_brand(brand_name)
    tel.set(mission=mission, brand=brand.to_dict(), phase="research")
    tel.emit("system", "mission", {"mission": mission, "mock": llm.MOCK})

    # 1. Research (fixture in Phase 1, You.com in Phase 2)
    res = research.run(brand, tel)

    # 2. Spec: definition of done, locked before any build
    tel.set(phase="spec")
    plan = spec.run(mission, brand, res, tel)
    flight_plan = plan["flight_plan"]

    # 3. Director plans vehicles
    tel.set(phase="build")
    directions = director.plan(brand, res, tel, n=n_vehicles, plant_failure=plant_failure)

    # 4. Build -> verify -> arbitrate loop per vehicle
    tel.set(phase="verify")
    for d in directions:
        vid = d["id"]
        attempts: list[dict] = []
        tel.vehicle(vid, name=d["name"], pattern=d["pattern"], status="building", direction=d,
                    drift=arbiter.drift_score(mission, brand.tone, d))
        while True:
            attempt_no = len(attempts) + 1
            rendered = director.render(d, brand, run_dir, tel, attempt=attempt_no)
            verdict = verifier.verify(rendered["mp4"], brand, flight_plan, run_dir / f"verify_{vid}_a{attempt_no}",
                                      tel, vehicle=vid)
            attempts.append({"attempt": attempt_no, "direction": d, "mp4": rendered["mp4"], "verdict": verdict})
            tel.vehicle(vid, attempts=attempts, mp4=rendered["mp4"], status="polling")
            decision = arbiter.decide(vid, attempts, plan.get("escalations", []), tel)
            tel.vehicle(vid, decision=decision, status=decision["decision"].lower())
            if decision["decision"] in ("GO", "SCRUB", "CALL"):
                break
            # HOLD: Director fixes and we go again
            d = director.fix(d, decision["failing"], tel)
            tel.vehicle(vid, direction=d, status="building")

        if decision["decision"] == "GO":
            frames = sorted((run_dir / f"verify_{vid}_a{len(attempts)}" / "samples").glob("s_*.png"))
            gc = goalcheck.run(mission, brand, frames, tel, vehicle=vid)
            tel.vehicle(vid, goalcheck=gc, status="go" if gc["satisfies_goal"] else "goal_failed")

    cleared = [v for v in tel.state["vehicles"].values() if v["status"] == "go"]
    tel.set(phase="done", finished_at=time.time(),
            summary={"cleared": len(cleared), "total": len(directions), "human_pings": tel.state["human_pings"]})
    tel.emit("system", "liftoff", {"cleared": len(cleared), "total": len(directions)})
    tel.emit("system", "usage", llm.usage_report())
    print(f"\nrun dir: {run_dir}")
    return run_dir


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mission", default="Launch video for Fizz cola, bold, for vertical feeds")
    ap.add_argument("--brand", default="fizz")
    ap.add_argument("--vehicles", type=int, default=3)
    ap.add_argument("--no-plant", action="store_true", help="don't plant the demo failure on vehicle A")
    args = ap.parse_args()
    flight(args.mission, args.brand, args.vehicles, plant_failure=not args.no_plant)


if __name__ == "__main__":
    main()
