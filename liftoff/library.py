"""
Saved flights: keep a finished flight and open it instantly instead of flying it again.

    python -m liftoff.library save runs/20261017-161204 --slug drinkpoppi-com --url drinkpoppi.com
    python -m liftoff.library list

A saved flight is a folder under library/<slug>/ (run.json, events.jsonl and every attempt's
MP4, with paths made relative) plus one row in library/library.db (SQLite). Mission control
lists them, and a landing page URL that matches a saved flight opens it without a new run.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "library"
DB = LIB / "library.db"

SCHEMA = """create table if not exists flights (
  slug text primary key, brand text, url text, mission text,
  cleared integer, total integer, human_pings integer, saved_at real, run_id text)"""


def _db() -> sqlite3.Connection:
    LIB.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute(SCHEMA)
    return con


def save(run_dir: Path, slug: str | None = None, url: str | None = None) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    state = json.loads((run_dir / "run.json").read_text())
    if state.get("phase") != "done":
        raise SystemExit(f"{run_dir.name} has not finished; save a finished flight")
    brand = state.get("brand", {})
    url = url or state.get("brand_url") or ""
    slug = slug or (url.replace("https://", "").replace("http://", "").strip("/").replace(".", "-") if url
                    else brand.get("name", "flight").lower())
    out = LIB / slug
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    # every attempt's video, referenced by file name so the folder can move (and live in git)
    for v in state.get("vehicles", {}).values():
        for a in v.get("attempts", []):
            src = Path(a["mp4"])
            if src.exists():
                shutil.copy2(src, out / src.name)
            a["mp4"] = src.name
        if v.get("mp4"):
            v["mp4"] = Path(v["mp4"]).name
    state["saved_from"] = run_dir.name
    (out / "run.json").write_text(json.dumps(state, indent=1, default=str))
    shutil.copy2(run_dir / "events.jsonl", out / "events.jsonl")
    s = state.get("summary") or {}
    row = {"slug": slug, "brand": brand.get("name", ""), "url": url, "mission": state.get("mission", ""),
           "cleared": s.get("cleared", 0), "total": s.get("total", 0), "human_pings": s.get("human_pings", 0),
           "saved_at": time.time(), "run_id": run_dir.name}
    with _db() as con:
        con.execute("insert or replace into flights values (:slug,:brand,:url,:mission,:cleared,:total,"
                    ":human_pings,:saved_at,:run_id)", row)
    return row


def flights() -> list[dict[str, Any]]:
    if not DB.exists():
        return []
    with _db() as con:
        return [dict(r) for r in con.execute("select * from flights order by saved_at desc")]


def find_by_url(url: str) -> dict[str, Any] | None:
    host = url.lower().replace("https://", "").replace("http://", "").split("/")[0].removeprefix("www.")
    return next((f for f in flights() if f["url"] and host == f["url"].lower().removeprefix("www.")), None)


def path(slug: str) -> Path:
    return LIB / slug


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("save")
    s.add_argument("run_dir")
    s.add_argument("--slug")
    s.add_argument("--url")
    sub.add_parser("list")
    a = ap.parse_args()
    if a.cmd == "save":
        print(save(Path(a.run_dir), a.slug, a.url))
    else:
        for f in flights():
            print(f"{f['slug']:20} {f['brand']:14} {f['cleared']}/{f['total']} pings={f['human_pings']}  {f['url'] or '-'}")


if __name__ == "__main__":
    main()
