"""
Event stream shared by every agent. The UI reads these files.

events.jsonl : one JSON object per line, appended as things happen
run.json     : the current state snapshot, rewritten whenever it changes

Event schema (keep it flat so the UI stays dumb):
  {"t": 12.34, "agent": "verifier", "event": "check", "vehicle": "A",
   "payload": {...}}

Agents: scout, librarian, spec, director, verifier, arbiter, goalcheck, playbook, system
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class Telemetry:
    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_dir / "events.jsonl"
        self.state_path = self.run_dir / "run.json"
        self.t0 = time.time()
        self.state: dict[str, Any] = {
            "mission": "",
            "brand": {},
            "phase": "idle",
            "flight_plan": [],
            "assumptions": [],
            "escalations": [],
            "research": {},
            "vehicles": {},
            "goalcheck": None,
            "human_pings": 0,
            "started_at": self.t0,
            "finished_at": None,
        }
        self.events_path.write_text("")
        self.save()

    def emit(self, agent: str, event: str, payload: dict[str, Any] | None = None,
             vehicle: str | None = None) -> None:
        rec = {"t": round(time.time() - self.t0, 2), "agent": agent, "event": event,
               "vehicle": vehicle, "payload": payload or {}}
        with self.events_path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"[{rec['t']:7.2f}s] {agent:9s} {event:14s} {vehicle or '':2s} {json.dumps(payload or {})[:140]}")

    def set(self, **kw: Any) -> None:
        self.state.update(kw)
        self.save()

    def vehicle(self, vid: str, **kw: Any) -> None:
        v = self.state["vehicles"].setdefault(vid, {"id": vid, "attempts": [], "status": "pending"})
        v.update(kw)
        self.save()

    def save(self) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2, default=str))
        tmp.replace(self.state_path)
