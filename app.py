"""
Liftoff mission control. Reads runs/latest/run.json and events.jsonl and redraws.

    streamlit run app.py

Top band: brand header | competitors + patterns | trend wall | directions (live go/no-go)
Ticker: the latest telemetry event in plain words, human pings on the right.
Below: flight plan, assumption ledger, each vehicle's video and checks, raw telemetry.
Start a flight from the sidebar; it runs in a subprocess so the UI keeps refreshing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from html import escape
from pathlib import Path

import streamlit as st

from liftoff.arbiter import MAX_ATTEMPTS

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"

st.set_page_config(page_title="Liftoff · Mission control", page_icon="🚀", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
:root {
  --bg: #F7F6F2; --card: #FFFFFF; --line: #E9E6DF; --ink: #1F1E1B; --soft: #6F6C66; --hint: #A19E97;
  --blue: #2E5BA8; --blue-wash: #DCE8FB; --blue-ring: #9DBDF0;
  --green: #2F6B2A; --red: #9A2A1E; --amber: #7A5A12; --violet: #5B3FA0;
}
.stApp { background: var(--bg); color: var(--ink); font-family: 'Inter', system-ui, sans-serif; }
[data-testid="stHeader"] { background: var(--bg); }
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid var(--line); }
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1500px; }
h1,h2,h3,h4,h5 { color: var(--ink) !important; font-family: 'Inter', system-ui, sans-serif; letter-spacing: -.01em; }
p, li, label, span { font-family: 'Inter', system-ui, sans-serif; }
[data-testid="stCaptionContainer"] p { color: var(--soft) !important; }

.lf-head { display: flex; align-items: center; gap: 22px; margin-bottom: 22px; flex-wrap: wrap; }
.lf-sq { width: 24px; height: 24px; border: 2.5px solid #3A3936; border-radius: 3px; flex: none; }
.lf-sq.sm { width: 14px; height: 14px; border-width: 2px; border-radius: 2px; display: inline-block; vertical-align: -1px; margin-right: 6px; }
.lf-brand { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px 24px;
  font-size: 28px; font-weight: 500; min-width: 320px; }
.lf-pill { background: var(--blue-wash); color: var(--blue); border-radius: 12px; padding: 9px 20px; font-size: 21px; }
.lf-round { margin-left: auto; color: var(--soft); font-size: 21px; }
.lf-mission { color: var(--soft); font-size: 15px; margin: -10px 0 18px 46px; }

.lf-grid { display: grid; grid-template-columns: 1fr 2.55fr 1.27fr; gap: 24px; align-items: stretch; }
@media (max-width: 1100px) { .lf-grid { grid-template-columns: 1fr; } }
.lf-card { background: var(--card); border: 1px solid var(--line); border-radius: 20px; padding: 24px 24px 22px; }
.lf-h { font-size: 24px; font-weight: 600; margin: 0 0 18px; display: flex; justify-content: space-between; align-items: baseline; }
.lf-h small { color: var(--hint); font-size: 18px; font-weight: 400; }

.lf-comp { display: flex; gap: 16px; align-items: center; padding: 10px 12px; border-radius: 14px; margin: 0 -12px 6px; }
.lf-comp:first-of-type { background: #F7F6F2; }
.lf-av { width: 44px; height: 44px; border-radius: 50%; display: grid; place-items: center; font-weight: 600; font-size: 18px; flex: none; }
.lf-comp b { font-weight: 500; font-size: 21px; display: block; }
.lf-comp span { color: var(--soft); font-size: 18px; }
.lf-pats { margin-top: 22px; }
.lf-tag { display: inline-block; background: #F4F2EE; border-radius: 12px; padding: 8px 16px; margin: 0 6px 10px 0; font-size: 19px; }

.lf-wall { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
@media (max-width: 700px) { .lf-wall { grid-template-columns: repeat(2, 1fr); } }
.lf-tile { border: 1px solid var(--line); border-radius: 14px; overflow: hidden; text-decoration: none !important; color: var(--ink) !important; display: block; }
.lf-tile .top { height: 140px; display: grid; place-items: center; }
.lf-tile .top i { width: 28px; height: 28px; border: 3px solid currentColor; display: block; border-radius: 2px; }
.lf-tile .meta { padding: 12px 12px 14px; }
.lf-tile .views { color: var(--soft); font-size: 19px; }
.lf-tile .hook { font-size: 20px; line-height: 1.3; margin-top: 2px; }

.lf-dir { border: 1px solid var(--line); border-radius: 14px; padding: 16px 16px 14px; margin-bottom: 16px; }
.lf-dir.active { border: 3px solid var(--blue-ring); padding: 14px 14px 12px; }
.lf-dir b { font-size: 21px; font-weight: 600; display: block; }
.lf-dir .sub { color: var(--soft); font-size: 18px; margin: 2px 0 10px; }
.lf-sw { display: flex; gap: 6px; margin-bottom: 10px; }
.lf-sw i { flex: 1; height: 36px; border-radius: 6px; display: block; }
.lf-st { font-size: 18px; margin-top: 4px; }
.ok { color: var(--green); } .bad { color: var(--red); } .wait { color: var(--amber); } .call { color: var(--violet); } .idle { color: var(--hint); }

.lf-ticker { display: flex; align-items: center; gap: 16px; margin: 26px 4px 8px; font-size: 19px; }
.lf-dot { width: 14px; height: 14px; border-radius: 50%; background: #3BA55C; flex: none; }
.lf-dot.busy { animation: lfpulse 1.2s infinite; }
@keyframes lfpulse { 50% { opacity: .35; } }
.lf-ticker .pings { margin-left: auto; color: var(--soft); white-space: nowrap; }

.lf-sec { font-size: 22px; font-weight: 600; margin: 30px 0 12px; }
.lf-row { display: flex; justify-content: space-between; gap: 16px; padding: 11px 0; border-bottom: 1px solid var(--line); font-size: 15px; }
.lf-row:last-child { border-bottom: none; }
.lf-row .why { color: var(--soft); font-size: 13px; margin-top: 3px; }
.lf-row code { background: #F4F2EE; color: var(--ink); border-radius: 6px; padding: 1px 6px; font-size: 12px; }
.lf-num { text-align: right; white-space: nowrap; }
.lf-num small { display: block; color: var(--hint); font-size: 12px; }
.lf-note { border-left: 3px solid #E0B15A; background: #FBF5E8; padding: 10px 14px; border-radius: 0 10px 10px 0; margin: 8px 0; font-size: 14px; }
.lf-note.gocard { border-color: #3BA55C; background: #EEF7EE; }
.lf-note.callcard { border-color: #8B6FD6; background: #F2EEFB; }
.lf-tele { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 6px 16px; max-height: 320px; overflow: auto; }
.lf-tele div { display: grid; grid-template-columns: 70px 90px 120px 26px 1fr; gap: 10px; padding: 6px 0; border-bottom: 1px solid #F1EFEA;
  font: 12px ui-monospace, Menlo, monospace; color: var(--soft); }
[data-testid="stVerticalBlockBorderWrapper"] { background: var(--card); border-color: var(--line) !important; border-radius: 18px; }
</style>
""", unsafe_allow_html=True)

AVATAR = [("#FBE9E5", "#9A2A1E"), ("#E3ECFA", "#2E5BA8"), ("#E6F4EA", "#2F6B2A"), ("#F6EAF1", "#8A2E5C"),
          ("#FBF1DE", "#7A5A12")]
TILE = [("#F8ECE8", "#7A2E1C"), ("#ECEBFA", "#3C3290"), ("#E6F5EE", "#24503A"), ("#F7E9EE", "#6B2340"),
        ("#FAF0DF", "#6B4410"), ("#F0EFEB", "#3D3C39")]


def safe(v) -> str:
    if isinstance(v, list):
        v = ", ".join(str(x) for x in v)
    return escape(str(v))


def latest_run_dir() -> Path | None:
    link = RUNS / "latest"
    if link.exists():
        return link.resolve()
    txt = RUNS / "latest.txt"
    if txt.exists():
        return Path(txt.read_text().strip())
    runs = sorted(p for p in RUNS.glob("*") if p.is_dir())
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


def initials(name: str) -> str:
    parts = name.replace("-", " ").split()
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else parts[0][1:2])).upper()


def humanize_tag(tag: str) -> str:
    t = tag.replace("_1_5s", " 1.5s").replace("_", " ").replace("can open", "can-open")
    t = t.replace("asmr", "ASMR")
    return t[:1].upper() + t[1:]


def views(n) -> str:
    if not n:
        return "n/a"
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}K"


def tint(hex_: str, amount: float) -> str:
    """Mix a hex color toward white. amount 0 = color, 1 = white."""
    h = hex_.lstrip("#")
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(c + (255 - c) * amount):02X}" for c in rgb)


def failing_phrase(r: dict, plan_by_id: dict) -> str:
    """One short human line for a failing check, e.g. 'Logo under 3s'."""
    p = plan_by_id.get(r["id"], {})
    check, args = p.get("check", r.get("check", "")), p.get("args", {})
    if check == "logo_seconds_at_least":
        return f"Logo under {args.get('min_s', 3):g}s"
    if check == "text_contrast_at_least":
        return f"Text contrast {r['measured']}, needs {args.get('min_ratio', 4.5):g}"
    if check == "palette_within":
        return "Background off palette"
    if check == "duration_between":
        return f"Runs {r['measured']}s"
    if check == "aspect_ratio":
        return f"Not {args.get('ratio', '9:16')}"
    q = str(args.get("question", r["id"]))
    return (q[:38] + "…") if len(q) > 40 else q


def status_lines(v: dict, plan_by_id: dict) -> str:
    status = v.get("status", "pending")
    attempts = v.get("attempts", [])
    if status == "call":
        return '<div class="lf-st call"><span class="lf-sq sm"></span>Waiting on a human</div>'
    if status in ("building", "polling") and len(attempts) >= 1 and not attempts[-1]["verdict"]["pass"]:
        return '<div class="lf-st wait"><span class="lf-sq sm"></span>Re-planning</div>'
    if not attempts:
        return '<div class="lf-st idle"><span class="lf-sq sm"></span>Building</div>'
    verdict = attempts[-1]["verdict"]
    out = [f'<div class="lf-st {"ok" if verdict["pass"] else "bad"}"><span class="lf-sq sm"></span>'
           f'{verdict["passed"]} of {verdict["total"]} checks pass</div>']
    for r in [r for r in verdict["results"] if not r["pass"]][:2]:
        out.append(f'<div class="lf-st bad"><span class="lf-sq sm"></span>{safe(failing_phrase(r, plan_by_id))}</div>')
    if status == "go" and v.get("goalcheck"):
        out.append('<div class="lf-st ok"><span class="lf-sq sm"></span>Liftoff confirmed</div>')
    elif status == "goal_failed":
        out.append('<div class="lf-st bad"><span class="lf-sq sm"></span>Goal re-check failed</div>')
    elif status == "scrub":
        out.append('<div class="lf-st bad"><span class="lf-sq sm"></span>Scrubbed</div>')
    return "".join(out)


def ticker_line(events: list[dict], plan_by_id: dict) -> str:
    """The newest event that reads well as a sentence."""
    for e in reversed(events):
        a, ev, v, p = e["agent"], e["event"], e.get("vehicle"), e["payload"]
        if a == "arbiter" and ev == "decision":
            return f"Arbiter: {p['decision']} on direction {v}. {p.get('reason', '')}"
        if a == "verifier" and ev == "check" and not p.get("pass"):
            return (f"Verifier checked direction {v}, {p['id']}: measured {p['measured']}, needs {p['expected']}.")
        if a == "verifier" and ev == "poll":
            return f"Verifier polled direction {v}: {p['passed']} of {p['total']} checks pass."
        if a == "director" and ev == "fix":
            fields = ", ".join(f"{k} {val}" for k, val in p.get("patch", {}).items() if k != "notes")
            return f"Director patched direction {v}: {fields or 'notes only'}."
        if a == "director" and ev == "rendered":
            return f"Director rendered direction {v}: {p.get('frames')} frames, {p.get('duration_s')}s."
        if a == "goalcheck" and ev == "verdict":
            word = "Liftoff confirmed" if p.get("satisfies_goal") else "Goal re-check failed"
            return f"{word} on direction {v}. {p.get('reason', '')}"
        if a == "spec" and ev == "locked":
            return f"Spec locked the flight plan: {p['checks']} checks, {p['assumptions']} assumptions."
        if a == "system" and ev == "liftoff":
            return f"Flight complete: {p['cleared']} of {p['total']} directions cleared."
    return "Awaiting telemetry…"


# ---------------- sidebar: launch a flight ----------------
with st.sidebar:
    st.title("Liftoff")
    st.caption("Your launch video doesn't leave the pad until mission control says go.")
    mission = st.text_input("Mission", "Launch video for Fizz cola, bold, for vertical feeds")
    brand_in = st.text_input("Brand", "fizz")
    n = st.slider("Directions to build", 1, 5, 3)
    plant = st.checkbox("Plant a failure on direction A (demo)", True)
    mock = st.checkbox("Mock inference (no API key)", os.environ.get("LIFTOFF_MOCK", "0") == "1")
    if st.button("Start flight", type="primary"):
        env = dict(os.environ, LIFTOFF_MOCK="1" if mock else "0")
        cmd = [sys.executable, "-m", "liftoff.run", "--mission", mission, "--brand", brand_in, "--vehicles", str(n)]
        if not plant:
            cmd.append("--no-plant")
        subprocess.Popen(cmd, cwd=ROOT, env=env)
        time.sleep(1.5)
    auto = st.checkbox("Live refresh", True)
    st.caption("Crusoe Managed Inference. Spec and verifier on Nemotron 3; Director on a different model family.")

run_dir = latest_run_dir()
if not run_dir:
    st.info("No flights yet. Open the sidebar and start one.")
    st.stop()

state, events = load(run_dir)
if not state:
    time.sleep(1)
    st.rerun()

brand = state.get("brand") or {}
res = state.get("research") or {}
vehicles = state.get("vehicles", {})
plan_by_id = {p["id"]: p for p in state.get("flight_plan", [])}
running = state.get("phase") != "done"

# ---------------- header ----------------
active = next((vid for vid, v in vehicles.items() if v.get("status") in ("building", "polling", "hold")),
              next(iter(vehicles), None))
active_round = len(vehicles[active].get("attempts", [])) if active else 0
category = str(brand.get("category", "")).title()
st.markdown(
    f'<div class="lf-head"><span class="lf-sq"></span>'
    f'<div class="lf-brand">{safe(brand.get("name", "Brand"))} {safe(category)}</div>'
    f'<div class="lf-pill">{safe(category or "Launch")}, {safe(brand.get("market", ""))} launch</div>'
    f'<div class="lf-round"><span class="lf-sq sm"></span>Round {max(active_round, 1)} of {MAX_ATTEMPTS}</div></div>'
    f'<div class="lf-mission">{safe(state.get("mission", ""))}</div>',
    unsafe_allow_html=True,
)

# ---------------- top band ----------------
comps = "".join(
    f'<div class="lf-comp"><div class="lf-av" style="background:{AVATAR[i % 5][0]};color:{AVATAR[i % 5][1]}">'
    f'{safe(initials(c["name"]))}</div><div><b>{safe(c["name"])}</b>'
    f'<span>{c["videos"]} {"mentions" if res.get("live") else "videos"}</span></div></div>'
    for i, c in enumerate(res.get("competitors", [])[:3])
)
pats = "".join(f'<span class="lf-tag">{safe(humanize_tag(p["tag"]))}</span>' for p in res.get("patterns", [])[:4])

tiles = []
for i, post in enumerate(res.get("trend_wall", [])[:6]):
    bg, fg = TILE[i % 6]
    linked = "REPLACE_ME" not in post.get("url", "")
    open_tag = f'<a class="lf-tile" href="{safe(post["url"])}" target="_blank">' if linked else '<div class="lf-tile">'
    tiles.append(
        f'{open_tag}<div class="top" style="background:{bg};color:{fg}"><i></i></div>'
        f'<div class="meta"><div class="views"><span class="lf-sq sm"></span>'
        f'{views(post["views"]) if post.get("views") else safe(post.get("age") or post.get("platform", ""))}</div>'
        f'<div class="hook">{safe(post["hook"])}</div></div>{"</a>" if linked else "</div>"}'
    )

dirs = []
for vid, v in vehicles.items():
    d = v.get("direction", {})
    base = brand.get("secondary_hex" if d.get("bg") == "secondary" else "primary_hex", "#D85A30")
    swatches = "".join(f'<i style="background:{tint(base, a)}"></i>' for a in (0.85, 0.55, 0.3, 0))
    dirs.append(
        f'<div class="lf-dir{" active" if vid == active else ""}"><b>{safe(vid)}. {safe(v.get("name", ""))}</b>'
        f'<div class="sub">{safe(d.get("duration_s", "?"))}s, vertical, {safe(humanize_tag(v.get("pattern", "")).replace("ASMR", "asmr").lower().replace("asmr", "ASMR"))}</div>'
        f'<div class="lf-sw">{swatches}</div>{status_lines(v, plan_by_id)}</div>'
    )
if not dirs:
    dirs.append('<div class="lf-st idle">The Director is planning…</div>')

st.markdown(
    f'<div class="lf-grid">'
    f'<div class="lf-card"><div class="lf-h">Competitors</div>{comps}<div class="lf-pats"><div class="lf-h">Patterns found</div>{pats}</div></div>'
    f'<div class="lf-card"><div class="lf-h">Trend wall <small>{"Live from You.com" if res.get("live") is True else "Cached search" if res.get("live") else "Last 14 days"}</small></div><div class="lf-wall">{"".join(tiles)}</div></div>'
    f'<div class="lf-card"><div class="lf-h">Directions</div>{"".join(dirs)}</div>'
    f'</div>'
    f'<div class="lf-ticker"><span class="lf-dot{" busy" if running else ""}"></span>'
    f'<span>{safe(ticker_line(events, plan_by_id))}</span>'
    f'<span class="pings">Human pings: {state.get("human_pings", 0)}</span></div>',
    unsafe_allow_html=True,
)

# ---------------- flight plan + ledger ----------------
left, right = st.columns([1.25, 1], gap="large")
with left:
    st.markdown('<div class="lf-sec">Flight plan</div>', unsafe_allow_html=True)
    st.caption("Written by the Spec agent before anything was built, then locked.")
    def plan_row(p: dict) -> str:
        args = p["args"]
        if "question" in args:
            body = f'“{safe(args["question"])}”<div class="why">{safe(p.get("why", ""))}</div>'
            chip = "expect " + ("yes" if p["check"] == "vision_yes" else "no")
        else:
            body = f'<div class="why">{safe(p.get("why", ""))}</div>'
            chip = ", ".join(f"{k} {v:g}" if isinstance(v, float) else f"{k} {v}" for k, v in args.items())
        return (f'<div class="lf-row"><div>{safe(p["id"])} · {safe(p["check"].replace("_", " "))}'
                f'<div style="margin-top:3px">{body}</div></div><div class="lf-num"><code>{safe(chip)}</code></div></div>')

    rows = "".join(plan_row(p) for p in state.get("flight_plan", [])) or '<div class="lf-row">Writing the definition of done…</div>'
    st.markdown(f'<div class="lf-card">{rows}</div>', unsafe_allow_html=True)
with right:
    st.markdown('<div class="lf-sec">Assumption ledger</div>', unsafe_allow_html=True)
    st.caption("Every gap the Spec agent filled in, said out loud.")
    led = "".join(f'<div class="lf-row"><div>{safe(a)}</div></div>' for a in state.get("assumptions", []))
    esc = "".join(f'<div class="lf-note callcard">Human only: {safe(e)}</div>' for e in state.get("escalations", []))
    st.markdown(f'<div class="lf-card">{led or "<div class=lf-row>None yet</div>"}{esc}</div>', unsafe_allow_html=True)

# ---------------- each direction: video + go/no-go poll ----------------
if vehicles:
    st.markdown('<div class="lf-sec">Go/no-go polls</div>', unsafe_allow_html=True)
    tabs = st.tabs([f"{vid}. {v.get('name', '')}" for vid, v in vehicles.items()])
    for tab, (vid, v) in zip(tabs, vehicles.items()):
        with tab:
            attempts = v.get("attempts", [])
            if not attempts:
                st.caption("Rendering…")
                continue
            last = attempts[-1]
            vcol, ccol = st.columns([0.55, 1.6], gap="large")
            with vcol:
                mp4 = Path(last["mp4"])
                if mp4.exists():
                    st.video(str(mp4))
            with ccol:
                for prev in attempts[:-1]:
                    failed = [r for r in prev["verdict"]["results"] if not r["pass"]]
                    if failed:
                        ev = " · ".join(f'{r["id"]} {r["measured"]} (needs {r["expected"]})' for r in failed)
                        st.markdown(f'<div class="lf-note"><b>Attempt {prev["attempt"]}: HOLD.</b> {safe(ev)}</div>',
                                    unsafe_allow_html=True)
                rows = "".join(
                    f'<div class="lf-row"><div class="{"ok" if r["pass"] else "bad"}">'
                    f'{"Pass" if r["pass"] else "Fail"} · {safe(r["id"])}</div>'
                    f'<div class="lf-num">{safe(r["measured"])}<small>needs {safe(r["expected"])}</small></div></div>'
                    for r in last["verdict"]["results"]
                )
                st.markdown(f'<div class="lf-card" style="padding:8px 20px">{rows}</div>', unsafe_allow_html=True)
                dec, gc = v.get("decision"), v.get("goalcheck")
                if dec:
                    kind = {"GO": "gocard", "CALL": "callcard"}.get(dec["decision"], "")
                    st.markdown(f'<div class="lf-note {kind}"><b>Arbiter: {safe(dec["decision"])}.</b> '
                                f'{safe(dec["reason"])}</div>', unsafe_allow_html=True)
                if gc:
                    word = "Liftoff confirmed." if gc["satisfies_goal"] else "Goal re-check failed."
                    st.markdown(f'<div class="lf-note {"gocard" if gc["satisfies_goal"] else ""}"><b>{word}</b> '
                                f'{safe(gc["reason"])}</div>', unsafe_allow_html=True)

# ---------------- raw telemetry ----------------
with st.expander("Telemetry"):
    rows = "".join(
        f'<div><span>{e["t"]:.2f}s</span><span>{safe(e["agent"])}</span><span>{safe(e["event"])}</span>'
        f'<span>{safe(e.get("vehicle") or "")}</span><span>{safe(json.dumps(e["payload"], default=str)[:160])}</span></div>'
        for e in events[-60:][::-1]
    )
    st.markdown(f'<div class="lf-tele">{rows}</div>', unsafe_allow_html=True)

if auto and running:
    time.sleep(2)
    st.rerun()
