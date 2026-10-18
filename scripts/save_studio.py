"""Check the Remotion-made poppi videos with Liftoff's own verifier and save them as a launch.

The videos are hand made in studio/ (Remotion), not by the Director, so this launch is labelled that way.
"""
import copy, json, shutil, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from liftoff import library  # noqa: E402
from liftoff.brand import Brand  # noqa: E402
from liftoff.telemetry import Telemetry  # noqa: E402
from liftoff.verifier import verify  # noqa: E402

src = json.loads((ROOT / "library/drinkpoppi-com/run.json").read_text())
brand = Brand(**{k: v for k, v in src["brand"].items() if k in Brand.__dataclass_fields__})
run_dir = ROOT / "runs" / f"studio-poppi-{int(time.time())}"
tel = Telemetry(run_dir)
videos = {"A": "PoppiProcess", "B": "PoppiSecret", "C": "PoppiBeat"}

state = copy.deepcopy(src)
state["vehicles"] = {}
cleared = 0
for vid, comp in videos.items():
    old = src["vehicles"][vid]
    mp4 = run_dir / f"studio_{vid}.mp4"
    shutil.copy2(ROOT / "studio/out" / f"{comp}.mp4", mp4)
    verdict = verify(str(mp4), brand, src["flight_plan"], run_dir / f"work_{vid}", tel, vid)
    print(vid, comp, f'{verdict["passed"]}/{verdict["total"]}',
          [(r["id"], r["measured"]) for r in verdict["results"] if not r["pass"]])
    direction = dict(old["attempts"][-1]["direction"], style="remotion", footage=None,
                     notes="Hand made in Remotion (studio/), from this direction's words.")
    ok = verdict["pass"]
    cleared += ok
    tel.emit("arbiter", "decision", {"decision": "GO" if ok else "HOLD",
                                     "failing": [r for r in verdict["results"] if not r["pass"]]}, vehicle=vid)
    if old.get("goalcheck"):
        tel.emit("goalcheck", "verdict", old["goalcheck"], vehicle=vid)
    state["vehicles"][vid] = {
        "id": vid, "name": old["name"], "pattern": old["pattern"], "drift": old.get("drift"),
        "status": "go" if ok else "hold", "mp4": str(mp4),
        "attempts": [{"attempt": 1, "direction": direction, "mp4": str(mp4), "verdict": verdict}],
        "decision": {"decision": "GO" if ok else "HOLD",
                     "reason": f'{verdict["passed"]} of {verdict["total"]} checks pass on the Remotion cut.'},
        "goalcheck": old.get("goalcheck"),
    }
state["brand"] = dict(src["brand"], name="poppi (Remotion)")
tel.emit("system", "liftoff", {"cleared": cleared, "total": len(videos)})
state["summary"] = {"cleared": cleared, "total": len(videos), "human_pings": 0}
state["phase"] = "done"
state["finished_at"] = time.time()
(run_dir / "run.json").write_text(json.dumps(state, indent=1, default=str))
print(library.save(run_dir, slug="drinkpoppi-com-studio", url="https://drinkpoppi.com/?made=remotion"))
