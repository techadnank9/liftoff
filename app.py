"""
Liftoff mission control. Reads runs/latest/run.json and events.jsonl and redraws.

    streamlit run app.py

Panes: mission + flight plan + assumption ledger | competitors + trend wall | vehicles with go/no-go poll
Bottom: telemetry (the event stream).
Start a flight from the sidebar; it runs in a subprocess so the UI keeps refreshing.
"""
from __future__ import annotations

import json
from html import escape
import os
import subprocess
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"

st.set_page_config(page_title="Liftoff · Mission control", page_icon="🚀", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.stApp { background: #0b1220; color: #e5edf7; }
[data-testid="stHeader"] { background: #0b1220; }
[data-testid="stSidebar"] { background: #111c2e; color: #e5edf7; }
.block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 1900px; }
h1,h2,h3,h4 { color: #f0f5ff !important; letter-spacing: -.025em; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: #a5b5ca !important; }
[data-testid="stWidgetLabel"] p, [data-testid="stCheckbox"] label p { color: #d1deee !important; }
@media (max-width: 1100px) {
  [data-testid="stMain"] [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
  [data-testid="stMain"] [data-testid="stColumn"] { flex: 1 1 280px !important; min-width: min(280px, 100%) !important; }
}
[data-testid="stVerticalBlockBorderWrapper"] { border-color: #2b3d56 !important; border-radius: 14px; }
[data-testid="stMetric"] { background: #152238; border: 1px solid #2b3d56; border-radius: 10px; padding: 12px; }
[data-testid="stMetricLabel"], [data-testid="stMetricValue"] { color: #e5edf7; }
[data-testid="stExpander"] { background: #111c2e; color: #e5edf7; }
.eyebrow { color: #83baff; font: 600 11px monospace; letter-spacing: .16em; text-transform: uppercase; margin-bottom: 8px; }
.panel-title { border-top: 2px solid #36587c; padding-top: 16px; margin: 18px 0 8px; font-size: 20px; font-weight: 650; }
.plan-check { border-bottom: 1px solid #26364b; padding: 12px 0; }
.plan-check strong { color: #c9def8; }
.plan-check p { color: #a5b5ca; margin: 6px 0 0; font-size: 13px; }
.plan-check code { color: #d2e3f8; background: #17253b; overflow-wrap: anywhere; }
.vehicle-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 10px; }
.vehicle-title { font-weight: 650; font-size: 20px; }
.badge { display: inline-block; border: 1px solid currentColor; padding: 5px 10px; border-radius: 6px; font: 700 12px monospace; white-space: nowrap; }
.go { color: #77e6b0; background: #10372b; }
.hold { color: #ffd080; background: #432f15; }
.scrub,.goal_failed { color: #ffaaaa; background: #43232b; }
.call { color: #d5b5ff; background: #35264d; }
.building,.polling { color: #9bcaff; background: #193650; }
.pending { color: #bac8da; background: #253247; }
.check-row { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 14px; border-bottom: 1px solid #2b3d56; padding: 10px 0; font-size: 13px; }
.check-row .check-name { grid-column: 1 / -1; font-weight: 600; overflow-wrap: anywhere; }
.check-row small { display: block; color: #a5b5ca; font-size: 11px; margin-bottom: 3px; }
.check-row b { overflow-wrap: anywhere; }
.pass-text { color: #77e6b0; } .fail-text { color: #ffd080; }
.history { border-left: 3px solid #ffd080; padding: 8px 12px; background: #241e18; margin: 10px 0; font-size: 13px; }
.telemetry { background: #070d17; border: 1px solid #2b3d56; border-radius: 10px; max-height: 300px; overflow: auto; padding: 14px; }
.telemetry-row { display: grid; grid-template-columns: 65px 85px 120px 25px minmax(240px,1fr); gap: 12px; padding: 7px 0; border-bottom: 1px solid #182437; font: 11px monospace; min-width: 660px; }
.telemetry-row span { overflow-wrap: anywhere; color: #b7c8dd; }
.telemetry-row .event { color: #83baff; }
</style>
""", unsafe_allow_html=True)


def safe(value):
    return escape(str(value))


def badge(status):
    kind = status if status in STATUS_LABEL else "pending"
    return f'<span class="badge {kind}">{safe(STATUS_LABEL.get(status, status.upper()))}</span>'


def checks(results):
    for result in results:
        passed = result["pass"]
        label = "PASS" if passed else "FAIL"
        tone = "pass-text" if passed else "fail-text"
        st.markdown(
            f'<div class="check-row"><div class="check-name {tone}">{label} · {safe(result["id"])}</div>'
            f'<div><small>MEASURED</small><b>{safe(result["measured"])}</b></div>'
            f'<div><small>REQUIRED</small><b>{safe(result["expected"])}</b></div></div>',
            unsafe_allow_html=True,
        )

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
    st.markdown('<div class="eyebrow">Launch operations</div>', unsafe_allow_html=True)
    st.title("Liftoff")
    st.caption("Your launch video doesn’t leave the pad until mission control says go.")
    mission = st.text_input("Mission", "Launch video for Fizz cola, bold, for vertical feeds")
    brand = st.text_input("Brand", "fizz")
    n = st.slider("Vehicles to build", 1, 5, 3)
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
    auto = st.checkbox("Live telemetry refresh", True)
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
st.markdown('<div class="eyebrow">Liftoff / Mission control</div>', unsafe_allow_html=True)
summary = state.get("summary") or {}
h1, h2, h3, h4 = st.columns([3, 1, 1, 1])
with h1:
    st.subheader(state["mission"])
    st.caption(f"{state['phase'].replace('_', ' ').upper()}  /  Flight {run_dir.name}")
with h2:
    st.metric("Vehicles · GO", f"{summary.get('cleared', 0)} / {summary.get('total', len(state['vehicles']) or '-')}")
with h3:
    st.metric("Human pings", state.get("human_pings", 0))
with h4:
    elapsed = (state.get("finished_at") or time.time()) - state["started_at"]
    st.metric("Elapsed", f"{elapsed:.0f}s")

left, mid, right = st.columns([1, 1.15, 1.65], gap="large")

# ---------------- left: flight plan + ledger ----------------
with left:
    st.markdown('<div class="panel-title">01 / Flight plan</div>', unsafe_allow_html=True)
    st.caption("Written by the Spec agent before any build. Locked.")
    if not state["flight_plan"]:
        st.write("Writing...")
    for p in state["flight_plan"]:
        st.markdown(
            f'<div class="plan-check"><strong>{safe(p["id"])} · {safe(p["check"].replace("_", " "))}</strong>'
            f'<p><code>{safe(json.dumps(p["args"]))}</code></p><p>{safe(p.get("why", ""))}</p></div>',
            unsafe_allow_html=True,
        )
    st.divider()
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
    st.markdown('<div class="panel-title">02 / Research</div>', unsafe_allow_html=True)
    st.caption("Category references · Scout + Librarian")
    st.markdown("#### Competitors")
    for c in res.get("competitors", []):
        st.markdown(f"- **{c['name']}** · {c['role'].replace('_', ' ')} · {c['videos']} videos")
    stats = res.get("stats", {})
    if stats:
        s1, s2, s3 = st.columns(3)
        s1.metric("Posts scanned", stats.get("posts_scanned", "-"))
        s2.metric("Top asset · days", stats.get("top_asset_days_running", "-"))
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
                st.caption("Reference pending · public post not linked yet")
            else:
                st.components.v1.html(embed(post["url"], post["platform"]), height=330)

# ---------------- right: vehicles ----------------
with right:
    st.markdown('<div class="panel-title">03 / Vehicles</div>', unsafe_allow_html=True)
    st.caption("Go/no-go poll · independent verification")
    vehicles = state.get("vehicles", {})
    if not vehicles:
        st.info("Director is planning the vehicles…")
    for vid, v in vehicles.items():
        status = v.get("status", "pending")
        with st.container(border=True):
            st.markdown(
                f'<div class="vehicle-head"><div class="vehicle-title">Vehicle {safe(vid)}'
                f'<br>{safe(v.get("name", ""))}</div>{badge(status)}</div>',
                unsafe_allow_html=True,
            )
            st.caption(f"{v.get('pattern', '').replace('_', ' ')} · Drift {v.get('drift', 0)}")
            attempts = v.get("attempts", [])
            for previous in attempts[:-1]:
                failed = [r for r in previous["verdict"]["results"] if not r["pass"]]
                if failed:
                    evidence = " · ".join(
                        f'{r["id"]}: {r["measured"]} (required {r["expected"]})' for r in failed
                    )
                    st.markdown(
                        f'<div class="history"><b>Attempt {safe(previous["attempt"])} · HOLD evidence</b>'
                        f'<br>{safe(evidence)}</div>', unsafe_allow_html=True,
                    )
            if attempts:
                last = attempts[-1]
                st.caption(f"Latest poll · Attempt {last['attempt']} · {last['verdict']['passed']} / {last['verdict']['total']} checks passed")
                vcol, ccol = st.columns([1, 1.35], gap="medium")
                with vcol:
                    mp4 = Path(last["mp4"])
                    if mp4.exists():
                        st.video(str(mp4))
                    else:
                        st.caption("Vehicle preview unavailable")
                with ccol:
                    checks(last["verdict"]["results"])
                if len(attempts) > 1:
                    with st.expander("Earlier go/no-go polls"):
                        for previous in attempts[:-1]:
                            st.markdown(f"**Attempt {previous['attempt']} · {previous['verdict']['passed']} / {previous['verdict']['total']} passed**")
                            checks(previous["verdict"]["results"])
            dec = v.get("decision")
            if dec:
                st.caption(f"Arbiter · {dec['decision']} · {dec['reason']}")
            gc = v.get("goalcheck")
            if gc:
                if gc["satisfies_goal"]:
                    st.success("Liftoff confirmed · " + gc["reason"])
                else:
                    st.error("Goal re-check failed · " + gc["reason"])

# ---------------- bottom: telemetry ----------------
st.divider()
st.markdown("#### Telemetry")
st.caption("Latest 40 events · newest first · mission time in seconds")
rows = events[-40:][::-1]
lines = []
for e in rows:
    pl = e["payload"]
    short = {k: pl[k] for k in list(pl)[:4]}
    lines.append(
        f'<div class="telemetry-row"><span>{e["t"]:.2f}s</span><span>{safe(e["agent"])}</span>'
        f'<span class="event">{safe(e["event"])}</span><span>{safe(e.get("vehicle") or "—")}</span>'
        f'<span>{safe(json.dumps(short, default=str)[:160])}</span></div>'
    )
st.markdown('<div class="telemetry">' + ("".join(lines) or "Awaiting telemetry…") + '</div>', unsafe_allow_html=True)

if auto and state.get("phase") != "done":
    time.sleep(2)
    st.rerun()
