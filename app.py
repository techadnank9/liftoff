"""
Liftoff mission control. Reads runs/latest/run.json and events.jsonl and redraws.

    streamlit run app.py

Panes: mission + flight plan + assumption ledger | competitors + trend wall | vehicles with go/no-go poll
Bottom: telemetry (the event stream).
Start a flight from the sidebar; it runs in a subprocess so the UI keeps refreshing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"

st.set_page_config(page_title="Liftoff", layout="wide")

STATUS_LABEL = {"go": "GO", "hold": "HOLD", "scrub": "SCRUB", "call": "CALL FLIGHT DIRECTOR",
                "building": "BUILDING", "polling": "POLLING", "pending": "PENDING", "goal_failed": "GOAL FAILED"}
STATUS_COLOR = {"go": "green", "hold": "orange", "scrub": "red", "call": "violet", "building": "blue",
                "polling": "blue", "pending": "gray", "goal_failed": "red"}


def latest_run_dir() -> Path | None:
    link = RUNS / "latest"
    if link.exists():
        return link.resolve()
    txt = RUNS / "latest.txt"
    if txt.exists():
        return Path(txt.read_text().strip())
    runs = sorted([p for p in RUNS.glob("*") if p.is_dir()])
    return runs[-1] if runs else None


def load(run_dir: Path):
    state = json.loads((run_dir / "run.json").read_text()) if (run_dir / "run.json").exists() else None
    events = []
    ep = run_dir / "events.jsonl"
    if ep.exists():
        for line in ep.read_text().splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return state, events


def embed(url: str, platform: str) -> str:
    if platform == "youtube":
        vid = url.rstrip("/").split("/")[-1].split("?")[0]
        return f'<iframe width="100%" height="320" src="https://www.youtube.com/embed/{vid}" frameborder="0" allowfullscreen></iframe>'
    if platform == "tiktok":
        vid = url.rstrip("/").split("/")[-1].split("?")[0]
        return f'<iframe width="100%" height="320" src="https://www.tiktok.com/embed/v2/{vid}" frameborder="0" allowfullscreen></iframe>'
    if platform == "instagram":
        return f'<iframe width="100%" height="320" src="{url.rstrip("/")}/embed" frameborder="0"></iframe>'
    return f'<a href="{url}">{url}</a>'


# ---------------- sidebar: launch a flight ----------------
with st.sidebar:
    st.title("Liftoff")
    mission = st.text_input("Mission", "Launch video for Fizz cola, bold, for vertical feeds")
    brand = st.text_input("Brand", "fizz")
    n = st.slider("Vehicles", 1, 5, 3)
    plant = st.checkbox("Plant a failure on vehicle A (demo)", True)
    mock = st.checkbox("Mock inference (no API key)", os.environ.get("LIFTOFF_MOCK", "0") == "1")
    if st.button("Start flight", type="primary"):
        env = dict(os.environ, LIFTOFF_MOCK="1" if mock else "0")
        cmd = [sys.executable, "-m", "liftoff.run", "--mission", mission, "--brand", brand, "--vehicles", str(n)]
        if not plant:
            cmd.append("--no-plant")
        subprocess.Popen(cmd, cwd=ROOT, env=env)
        st.session_state["started"] = time.time()
        time.sleep(1.5)
    auto = st.checkbox("Auto refresh", True)
    st.caption("Runs on Crusoe Managed Inference. Spec, verifier and arbiter on Nemotron 3; Director on a different model family.")

run_dir = latest_run_dir()
if not run_dir:
    st.info("No flights yet. Start one from the sidebar.")
    st.stop()

state, events = load(run_dir)
if not state:
    st.info("Flight starting...")
    time.sleep(1)
    st.rerun()

# ---------------- header ----------------
summary = state.get("summary") or {}
h1, h2, h3, h4 = st.columns([3, 1, 1, 1])
with h1:
    st.subheader(f"Mission: {state['mission']}")
    st.caption(f"Phase: {state['phase']}  ·  run {run_dir.name}")
with h2:
    st.metric("Cleared", f"{summary.get('cleared', 0)} / {summary.get('total', len(state['vehicles']) or '-')}")
with h3:
    st.metric("Human pings", state.get("human_pings", 0))
with h4:
    elapsed = (state.get("finished_at") or time.time()) - state["started_at"]
    st.metric("Elapsed", f"{elapsed:.0f}s")

left, mid, right = st.columns([1.1, 1.3, 1.6])

# ---------------- left: flight plan + ledger ----------------
with left:
    st.markdown("#### Flight plan")
    st.caption("Written by the Spec agent before any build. Locked.")
    if not state["flight_plan"]:
        st.write("Writing...")
    for p in state["flight_plan"]:
        st.markdown(f"**{p['id']}** · `{p['check']}` {json.dumps(p['args'])}  \n<span style='color:gray'>{p.get('why','')}</span>",
                    unsafe_allow_html=True)
    st.markdown("#### Assumption ledger")
    st.caption("Gaps the Spec agent filled in, out loud.")
    for a in state["assumptions"]:
        st.markdown(f"- {a}")
    if state["escalations"]:
        st.markdown("#### Escalations (human only)")
        for e in state["escalations"]:
            st.error(e)

# ---------------- mid: research ----------------
with mid:
    res = state.get("research") or {}
    st.markdown("#### Competitors")
    for c in res.get("competitors", []):
        st.markdown(f"- **{c['name']}** · {c['role'].replace('_', ' ')} · {c['videos']} videos")
    stats = res.get("stats", {})
    if stats:
        s1, s2, s3 = st.columns(3)
        s1.metric("Posts scanned", stats.get("posts_scanned", "-"))
        s2.metric("Top asset, days running", stats.get("top_asset_days_running", "-"))
        s3.metric("No captions", f"{int(100 * stats.get('share_no_captions', 0))}%")
    st.markdown("#### Patterns")
    for p in res.get("patterns", []):
        st.markdown(f"- `{p['tag']}` {int(p['share'] * 100)}% · {p['note']}")
    st.markdown("#### Trend wall")
    st.caption("Public posts, embedded by the platforms. Nothing downloaded.")
    cols = st.columns(2)
    for i, post in enumerate(res.get("trend_wall", [])[:6]):
        with cols[i % 2]:
            views = f"{post['views'] / 1e6:.1f}M" if post.get("views") else "n/a"
            st.markdown(f"**{post['hook']}** · {post['platform']} · {views}")
            if "REPLACE_ME" in post["url"]:
                st.info("Add a real public post URL in liftoff/research.py")
            else:
                st.components.v1.html(embed(post["url"], post["platform"]), height=330)

# ---------------- right: vehicles ----------------
with right:
    st.markdown("#### Vehicles · go/no-go poll")
    vehicles = state.get("vehicles", {})
    if not vehicles:
        st.write("Director is planning...")
    for vid, v in vehicles.items():
        status = v.get("status", "pending")
        color = STATUS_COLOR.get(status, "gray")
        with st.container(border=True):
            top = st.columns([3, 1])
            top[0].markdown(f"**{vid}. {v.get('name', '')}** · `{v.get('pattern', '')}` · drift {v.get('drift', 0)}")
            top[1].markdown(f":{color}[**{STATUS_LABEL.get(status, status.upper())}**]")
            d = v.get("direction", {})
            if d:
                st.caption(f"Hook: {d.get('hook')} · {d.get('duration_s')}s · logo {d.get('logo_seconds')}s · bg {d.get('bg')}")
            attempts = v.get("attempts", [])
            if attempts:
                last = attempts[-1]
                vcol, ccol = st.columns([1, 1.4])
                with vcol:
                    mp4 = Path(last["mp4"])
                    if mp4.exists():
                        st.video(str(mp4))
                with ccol:
                    st.caption(f"Attempt {last['attempt']} · {last['verdict']['passed']}/{last['verdict']['total']} checks")
                    for r in last["verdict"]["results"]:
                        mark = "✅" if r["pass"] else "❌"
                        st.markdown(f"{mark} `{r['id']}` {r['measured']} (want {r['expected']})")
            dec = v.get("decision")
            if dec:
                st.markdown(f":{color}[{dec['decision']}] {dec['reason']}")
            gc = v.get("goalcheck")
            if gc:
                st.markdown(("✅ Liftoff confirmed: " if gc["satisfies_goal"] else "❌ Goal re-check failed: ") + gc["reason"])

# ---------------- bottom: telemetry ----------------
st.markdown("#### Telemetry")
rows = events[-40:][::-1]
for e in rows:
    pl = e["payload"]
    short = {k: pl[k] for k in list(pl)[:4]}
    st.text(f"{e['t']:7.2f}s  {e['agent']:9s} {e['event']:14s} {e.get('vehicle') or '':2s} {json.dumps(short, default=str)[:160]}")

if auto and state.get("phase") != "done":
    time.sleep(2)
    st.rerun()
