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
import streamlit.components.v1 as components

from liftoff import library
from liftoff.arbiter import MAX_ATTEMPTS

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"

st.set_page_config(page_title="Liftoff", page_icon="🚀", layout="wide",
                   initial_sidebar_state="collapsed")

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
:root {
  --bg: #F7F6F2; --card: #FFFFFF; --line: #E9E6DF; --ink: #1F1E1B; --soft: #6F6C66; --hint: #A19E97;
  --blue: #2E5BA8; --blue-wash: #DCE8FB; --blue-ring: #9DBDF0;
  --green: #2F6B2A; --red: #9A2A1E; --amber: #7A5A12; --violet: #5B3FA0;
}
.stApp { background: var(--bg); color: var(--ink); font-family: 'Inter', system-ui, sans-serif; }
[data-testid="stHeader"] { background: var(--bg); }
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid var(--line); }
.block-container { padding-top: 2.6rem; padding-bottom: 3rem; max-width: 1240px; }
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: none; }
[data-testid="stHeader"] { height: 0; }
.stApp { font-size: 15px; }
[data-testid="stSidebar"] h1 { font-size: 20px; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { height: 40px; padding: 0 14px; font-size: 14px; }
h1,h2,h3,h4,h5 { color: var(--ink) !important; font-family: 'Inter', system-ui, sans-serif; letter-spacing: -.01em; }
p, li, label, span { font-family: 'Inter', system-ui, sans-serif; }
[data-testid="stCaptionContainer"] p { color: var(--soft) !important; }

.lf-head { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; flex-wrap: wrap; }
.lf-title { font-size: 22px; font-weight: 600; letter-spacing: -.01em; }
.lf-meta { color: var(--soft); font-size: 14px; margin-bottom: 14px; }
.lf-badge { font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 999px; background: var(--blue-wash); color: var(--blue); }
.lf-badge.ok { background: #E6F2E4; color: var(--green); } .lf-badge.wait { background: #FBF2DE; color: var(--amber); } .lf-badge.bad { background: #F8E5E2; color: var(--red); }
.lf-steps { display: flex; gap: 0; margin: 4px 0 18px; }
.lf-steps div { flex: 1; font-size: 13px; color: var(--hint); padding-top: 8px; border-top: 3px solid var(--line); margin-right: 6px; }
.lf-steps div.done { color: var(--soft); border-color: #9BC79A; } .lf-steps div.now { color: var(--ink); font-weight: 600; border-color: var(--blue); }
.lf-sq { width: 24px; height: 24px; border: 2.5px solid #3A3936; border-radius: 3px; flex: none; }
.lf-sq.sm { width: 14px; height: 14px; border-width: 2px; border-radius: 2px; display: inline-block; vertical-align: -1px; margin-right: 6px; }
.lf-brand { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px 24px;
  font-size: 20px; font-weight: 500; min-width: 0; }
.lf-pill { background: var(--blue-wash); color: var(--blue); border-radius: 999px; padding: 3px 10px; font-size: 12px; font-weight: 600; }
.lf-round { margin-left: auto; color: var(--soft); font-size: 13px; }
.lf-mission { color: var(--soft); font-size: 15px; margin: -10px 0 18px 46px; }

.lf-grid { display: grid; grid-template-columns: 1fr 2.55fr 1.27fr; gap: 24px; align-items: stretch; }
@media (max-width: 1100px) { .lf-grid { grid-template-columns: 1fr; } }
.lf-card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; }
.lf-h { font-size: 15px; font-weight: 600; margin: 0 0 12px; display: flex; justify-content: space-between; align-items: baseline; }
.lf-h small { color: var(--hint); font-size: 12px; font-weight: 400; }

.lf-comp { display: flex; gap: 10px; align-items: center; padding: 6px 8px; border-radius: 10px; margin: 0 -8px 2px; }
.lf-comp:first-of-type { background: #F7F6F2; }
.lf-av { width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; font-weight: 600; font-size: 12px; flex: none; position: relative; overflow: hidden; }
.lf-av img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; background: #fff; padding: 7px; box-sizing: border-box; border-radius: 50%; border: 1px solid var(--line); }
.lf-tile .top.has-thumb { background-size: cover; background-position: center; position: relative; }
.lf-tile .top.has-thumb i { width: 44px; height: 44px; border: 0; border-radius: 50%; background: rgba(0,0,0,.6); position: relative; transition: transform .15s, background .15s; }
.lf-tile .top.has-thumb i::after { content: ""; position: absolute; left: 17px; top: 13px; border-style: solid; border-width: 9px 0 9px 14px; border-color: transparent transparent transparent #fff; }
.lf-tile[data-embed]:hover .top.has-thumb i { background: #E8732B; }
.lf-tile .plat { position: absolute; top: 8px; left: 8px; background: rgba(0,0,0,.6); color: #fff; font-size: 12px; padding: 2px 8px; border-radius: 8px; }
.lf-comp b { font-weight: 500; font-size: 14px; display: block; }
.lf-comp span { color: var(--soft); font-size: 12px; }
.lf-pats { margin-top: 22px; }
.lf-tag { display: inline-block; background: #F4F2EE; border-radius: 999px; padding: 3px 10px; margin: 0 4px 6px 0; font-size: 12px; }

.lf-wall { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; align-items: start; }
@media (max-width: 700px) { .lf-wall { grid-template-columns: repeat(2, 1fr); } }
.lf-tile { border: 1px solid var(--line); border-radius: 14px; overflow: hidden; text-decoration: none !important; color: var(--ink) !important; display: block; }
.lf-tile .top { aspect-ratio: 16 / 9; height: auto; display: grid; place-items: center; }
.lf-tile .top i { width: 28px; height: 28px; border: 3px solid currentColor; display: block; border-radius: 2px; }
.lf-tile .meta { padding: 8px 10px 10px; }
.lf-tile[data-embed] { cursor: pointer; }
.lf-tile[data-embed]:hover .top i { transform: scale(1.12); }
.lf-tile .top.playing { background: #000 !important; }  /* same horizontal size while it plays */
.lf-tile .top.playing iframe { width: 100%; height: 100%; border: 0; display: block; }
.lf-tile .open { color: var(--hint); font-size: 11px; text-decoration: none; float: right; }
.lf-tile .views { color: var(--soft); font-size: 12px; }
.lf-tile .hook { font-size: 13px; line-height: 1.35; margin-top: 2px; }

.lf-dir { border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; margin-bottom: 10px; background: var(--card); }
.lf-dir.active { border: 2px solid var(--blue-ring); padding: 11px 13px; }
.lf-dir b { font-size: 15px; font-weight: 600; display: block; }
.lf-dir .sub { color: var(--soft); font-size: 13px; margin: 2px 0 8px; }
.lf-sw { display: flex; gap: 6px; margin-bottom: 10px; }
.lf-sw i { flex: 1; height: 36px; border-radius: 6px; display: block; }
.lf-st { font-size: 13px; margin-top: 3px; display: flex; align-items: center; gap: 6px; }
.lf-trail { margin-top: 10px; padding-top: 8px; border-top: 1px dashed var(--line); }
.lf-trail .tr { font-size: 12px; color: var(--soft); padding: 3px 0 3px 14px; position: relative; line-height: 1.4; }
.lf-trail .tr::before { content: ""; position: absolute; left: 2px; top: 8px; width: 6px; height: 6px; border-radius: 50%; background: var(--hint); }
.lf-trail .tr.ok::before { background: var(--green); } .lf-trail .tr.bad::before { background: var(--red); }
.lf-trail .tr + .tr::after { content: ""; position: absolute; left: 4px; top: -5px; height: 10px; border-left: 1px solid var(--line); }
.lf-trail .tr b { color: var(--ink); font-weight: 600; }
.lf-st .ic { width: 16px; height: 16px; border-radius: 50%; display: inline-grid; place-items: center; font-size: 10px; font-weight: 700; color: #fff; flex: none; background: var(--hint); }
.lf-st.ok .ic { background: var(--green); } .lf-st.bad .ic { background: var(--red); }
.lf-st.wait .ic { background: var(--amber); } .lf-st.call .ic { background: var(--violet); }
.ok { color: var(--green); } .bad { color: var(--red); } .wait { color: var(--amber); } .call { color: var(--violet); } .idle { color: var(--hint); }

.lf-ticker { display: flex; align-items: center; gap: 10px; margin: 0 0 10px; font-size: 14px; }
.lf-dot { width: 9px; height: 9px; border-radius: 50%; background: #3BA55C; flex: none; }
.lf-dot.busy { animation: lfpulse 1.2s infinite; }
@keyframes lfpulse { 50% { opacity: .35; } }
.lf-ticker .pings { margin-left: auto; color: var(--soft); white-space: nowrap; }

.lf-sec { font-size: 17px; font-weight: 600; margin: 34px 0 6px; }
.lf-row { display: flex; justify-content: space-between; gap: 16px; padding: 9px 0; border-bottom: 1px solid var(--line); font-size: 14px; }
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
"""
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

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


def brand_icon(c: dict) -> str | None:
    """The brand site's own icon, served by You.com's favicon service; never downloaded.
    Research checks it isn't the service's generic placeholder; older runs guessed the domain."""
    if "icon" in c:
        return c["icon"]
    domain = c.get("domain") or (c["name"].lower().replace(" ", "").replace("'", "") + ".com")
    return f"https://you.com/favicon?domain={domain}&size=128"


def thumb_for(post: dict) -> str | None:
    if post.get("thumb"):
        return post["thumb"]
    url = post.get("url", "")
    if "REPLACE_ME" in url:
        return None
    for marker in ("/shorts/", "v="):
        if "youtube.com" in url and marker in url:
            vid = url.split(marker)[1].split("?")[0].split("&")[0].split("/")[0]
            return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    return None


def embed_url(post: dict) -> str | None:
    """The platform's own embed player for a public post, autoplaying on click."""
    url = post.get("url", "")
    if "youtube.com" in url:
        vid = thumb_for(post).split("/vi/")[1].split("/")[0] if thumb_for(post) else None
        return f"https://www.youtube-nocookie.com/embed/{vid}?autoplay=1&playsinline=1&rel=0" if vid else None
    if "tiktok.com" in url and "/video/" in url:
        return f"https://www.tiktok.com/embed/v2/{url.split('/video/')[1].split('?')[0].split('/')[0]}?autoplay=1"
    return None


def initials(name: str) -> str:
    parts = name.replace("-", " ").split()
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else parts[0][1:2])).upper()


def humanize_tag(tag: str) -> str:
    t = tag.replace("_1_5s", " 1.5s").replace("_", " ").replace("can open", "can-open")
    t = t.replace("asmr", "ASMR")
    return t[:1].upper() + t[1:]


def ago(iso: str) -> str:
    """'2026-10-10' -> '7 days ago'."""
    import datetime
    try:
        d = datetime.date.fromisoformat(str(iso)[:10])
    except ValueError:
        return ""
    n = (datetime.date.today() - d).days
    return "today" if n <= 0 else "yesterday" if n == 1 else f"{n} days ago" if n < 60 else f"{n // 30} months ago"


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


def promise(p: dict) -> tuple[str, str, str]:
    """A check in plain words: (what it checks, the bar it has to clear, how it's verified)."""
    check, a = p.get("check", ""), p.get("args", {})
    measured, looked = "Measured from the video", "An AI looks at frames from the video"
    if check == "duration_between":
        return "The right length", f"{a.get('min_s', 6):g} to {a.get('max_s', 15):g} seconds", measured
    if check == "aspect_ratio":
        shape = {"9:16": "vertical, fills a phone screen", "1:1": "square", "16:9": "widescreen"}
        return "The right shape", f"{a.get('ratio')} {shape.get(a.get('ratio'), '')}".strip(), measured
    if check == "logo_seconds_at_least":
        return "Your logo stays on screen", f"at least {a.get('min_s', 3):g} seconds", measured
    if check == "palette_within":
        return "Looks like your brand", "backgrounds in your brand colours", measured
    if check == "text_contrast_at_least":
        return "Readable on a phone", f"text contrast {a.get('min_ratio', 4.5):g} to 1 or better, the accessibility standard", measured
    q = str(a.get("question", "")).lower()
    want = "yes" if check == "vision_yes" else "no"
    if "hook" in q or "first" in q:
        return "Grabs attention in the first second", "a readable opening line right away", looked
    if "end card" in q or ("brand name" in q and "last" in q):
        return "Ends on your brand name", "the last second shows your name clearly", looked
    if any(w in q for w in ("calorie", "sugar", "nutrition")):
        return "No calorie or sugar claims", "nothing about calories, sugar or nutrition", looked
    if "health" in q or "medical" in q:
        return "No health claims", "nothing that reads as a health or medical promise", looked
    if any(w in q for w in ("competitor", "other brand", "resembles", "well-known")):
        return "No other brand's logo", "nothing that looks like a competitor", looked
    return (str(a.get("question", check)).rstrip("?"), f"answer must be {want}", looked)


WHY = {
    "The right length": "Most vertical feeds cut off after 15 seconds, and under 6 there is no story.",
    "The right shape": "A vertical video fills the phone screen instead of floating in black bars.",
    "Your logo stays on screen": "People remember a brand they have seen for about 3 seconds or more.",
    "Looks like your brand": "The colours are the first thing that tells people whose ad this is.",
    "Readable on a phone": "Small screens in daylight are hard to read; this is the accessibility standard.",
    "Grabs attention in the first second": "Most people decide whether to keep watching in the first second.",
    "Ends on your brand name": "The last thing people see is what they remember.",
    "No other brand's logo": "Showing a competitor's mark confuses viewers and can be a legal problem.",
    "No health claims": "Health claims in ads are regulated, so your brand rules them out.",
    "No calorie or sugar claims": "Your brand asked not to lead with nutrition numbers.",
}


def promise_title(result: dict, plan_by_id: dict) -> str:
    return promise(plan_by_id.get(result["id"], {"check": result.get("check"), "args": {}}))[0]


def status_lines(v: dict, plan_by_id: dict) -> str:
    status = v.get("status", "pending")
    attempts = v.get("attempts", [])
    if status == "call":
        return '<div class="lf-st call"><span class="ic">!</span>Needs your decision</div>'
    if status in ("building", "polling") and len(attempts) >= 1 and not attempts[-1]["verdict"]["pass"]:
        return '<div class="lf-st wait"><span class="ic">↻</span>Sent back, being fixed</div>'
    if not attempts:
        return '<div class="lf-st idle"><span class="ic">…</span>Being made</div>'
    verdict = attempts[-1]["verdict"]
    out = [f'<div class="lf-st {"ok" if verdict["pass"] else "bad"}"><span class="ic">{"✓" if verdict["pass"] else "✕"}</span>'
           f'Passed {verdict["passed"]} of {verdict["total"]} checks</div>']
    for r in [r for r in verdict["results"] if not r["pass"]][:2]:
        out.append(f'<div class="lf-st bad"><span class="ic">✕</span>{safe(failing_phrase(r, plan_by_id))}</div>')
    if status == "go" and v.get("goalcheck"):
        out.append('<div class="lf-st ok"><span class="ic">✓</span>Ready to post</div>')
    elif status == "goal_failed":
        out.append('<div class="lf-st bad"><span class="ic">✕</span>Passes the checks but misses your brief</div>')
    elif status == "scrub":
        out.append('<div class="lf-st bad"><span class="ic">✕</span>Dropped: could not be fixed in 3 tries</div>')
    return "".join(out)


def miss_sentence(r: dict, plan_by_id: dict) -> str:
    """One failed check as a sentence: what was measured against what was needed."""
    p = plan_by_id.get(r["id"], {"check": r.get("check"), "args": {}})
    title = promise(p)[0].lower()
    a, m, check = p.get("args", {}), r["measured"], p.get("check")
    if check == "logo_seconds_at_least":
        return f"logo on screen {m:g}s, needs {a.get('min_s', 3):g}s"
    if check == "text_contrast_at_least":
        return f"text contrast {m:g} to 1, needs {a.get('min_ratio', 4.5):g}"
    if check == "duration_between":
        return f"{m:g}s long, needs {a.get('min_s', 6):g} to {a.get('max_s', 15):g}s"
    if check == "palette_within":
        return "background drifted off the brand colours"
    if check == "aspect_ratio":
        return f"shape {m}, needs {a.get('ratio')}"
    if isinstance(m, list):
        bad = sum(1 for x in m if str(x).lower() != ("yes" if check == "vision_yes" else "no"))
        return f"{title}: the AI reviewer flagged {bad} of {len(m)} frames"
    return title


def footage_credit(d: dict) -> str:
    f = d.get("footage")
    if not f:
        return ""
    return (f'<div class="why" style="font-size:11px;margin-top:8px;color:var(--hint)">Footage: '
            f'<a href="{safe(f.get("url", ""))}" target="_blank" style="color:var(--hint)">{safe(f.get("credit", ""))} on {safe(f.get("source", "Pexels"))}</a></div>')


def try_trail(attempts: list[dict], plan_by_id: dict) -> str:
    """The self-checking loop, visible: each try, what failed and by how much, then the fix."""
    if not attempts:
        return ""
    parts = []
    for a in attempts:
        v = a["verdict"]
        if v["pass"]:
            parts.append(f'<div class="tr ok"><b>Try {a["attempt"]}</b> passed every check</div>')
        else:
            misses = "; ".join(safe(miss_sentence(r, plan_by_id)) for r in v["results"] if not r["pass"])
            parts.append(f'<div class="tr bad"><b>Try {a["attempt"]}</b> sent back: {misses}</div>')
    return f'<div class="lf-trail">{"".join(parts)}</div>'


def ticker_line(events: list[dict], plan_by_id: dict) -> str:
    """The newest thing that happened, as a sentence a marketer would say."""
    for e in reversed(events):
        a, ev, v, p = e["agent"], e["event"], e.get("vehicle"), e["payload"]
        if a == "system" and ev == "liftoff":
            return f"Done. {p['cleared']} of {p['total']} videos are ready to post."
        if a == "goalcheck" and ev == "verdict":
            return (f"Video {v} is ready to post: a fresh reviewer agreed it does what you asked."
                    if p.get("satisfies_goal") else f"Video {v} passed the checks but misses your brief.")
        if a == "arbiter" and ev == "decision":
            d = p["decision"]
            if d == "GO":
                return f"Video {v} passed every check."
            if d == "HOLD":
                misses = [promise_title(r, plan_by_id).lower() for r in p.get("failing", [])][:2]
                return f"Video {v} sent back: {', '.join(misses) or 'a check failed'}. Fixing it."
            if d == "SCRUB":
                return f"Video {v} dropped after three tries."
            return f"Video {v} needs your decision: {p.get('reason', '')}"
        if a == "director" and ev == "fix":
            return f"Fixing video {v}."
        if a == "director" and ev == "rendered":
            return f"Video {v} made, checking it now."
        if a == "spec" and ev == "locked":
            return f"Set {p['checks']} quality checks for this launch. Making the videos."
        if a == "brand" and ev == "card":
            return f"Learned the brand from its website: {p.get('name')}, {p.get('category')}."
        if a == "scout":
            return "Researching the category live."
    return "Starting…"


DEFAULT_MISSION = "Launch video for Fizz cola, bold, for vertical feeds"


def start_flight(mission: str, brand: str, n: int, plant: bool, mock: bool, brand_url: str = "") -> None:
    env = dict(os.environ, LIFTOFF_MOCK="1" if mock else "0", LIFTOFF_SET_LATEST="1")
    cmd = [sys.executable, "-m", "liftoff.run", "--mission", mission, "--brand", brand, "--vehicles", str(n)]
    if brand_url:
        cmd += ["--brand-url", brand_url]  # run.py writes the brief from the brand when it is empty
    if not plant:
        cmd.append("--no-plant")
    subprocess.Popen(cmd, cwd=ROOT, env=env)
    time.sleep(1.5)


# A brand URL from the landing page (?brand_url=...) prefills the sidebar and offers a one-click flight.
url_param = (st.query_params.get("brand_url") or "").strip()[:120]

# ---------------- sidebar: saved flights + launch a flight ----------------
saved = library.flights()
saved_labels = {f["slug"]: f'{f["brand"]}  ·  {f["cleared"]} of {f["total"]} ready' for f in saved}
flight_param = (st.query_params.get("flight") or "").strip()
saved_match = library.find_by_url(url_param) if url_param else None

# No sidebar: new launches start from a website on the landing page; switching launches is a menu
# in the header, the way most apps let you switch projects.
SITE_URL = os.environ.get("LIFTOFF_SITE_URL", "http://localhost:3000")
mock = os.environ.get("LIFTOFF_MOCK", "0") == "1"
auto = True
options = ["live"] + list(saved_labels)
default = flight_param if flight_param in saved_labels else "live"
bar_l, bar_m, bar_r = st.columns([1, 0.42, 0.18], vertical_alignment="center")
bar_l.markdown('<div style="font-weight:700;font-size:16px">Liftoff</div>', unsafe_allow_html=True)
choice = bar_m.selectbox("Launch", options, index=options.index(default), label_visibility="collapsed",
                         format_func=lambda k: "Latest launch" if k == "live" else saved_labels[k])
bar_r.link_button("New launch", SITE_URL, type="primary", use_container_width=True)
if choice != flight_param and (choice != "live" or flight_param):
    st.query_params["flight"] = choice if choice != "live" else ""

# Arriving from the landing page with a website.
arriving = bool(url_param) and st.session_state.get("launched_for") != url_param
if arriving and saved_match and choice == "live":
    # You already have finished videos for this brand: show them, offer new ones.
    choice = saved_match["slug"]
    st.session_state["launched_for"] = url_param
    st.query_params["flight"] = choice
if arriving and not saved_match and choice == "live":
    with st.container(border=True):
        st.markdown(f"#### Make launch videos for **{safe(url_param)}**")
        st.caption("Liftoff reads the website for its name, colours and tone, looks at what is working in its "
                   "category, writes down what ready to post means, then makes three videos and checks each one. "
                   "About two minutes.")
        if st.button("Make videos", type="primary", key="arrive_go"):
            st.session_state["launched_for"] = url_param
            start_flight(DEFAULT_MISSION, "fizz", 3, True, mock, url_param)
            st.rerun()
    st.stop()  # don't show another brand's videos under this one

is_saved = choice != "live"
run_dir = library.path(choice) if is_saved else latest_run_dir()
if not run_dir:
    st.info("No flights yet. Paste a website on the left and start one.")
    st.stop()

state, events = load(run_dir)
if not state:
    time.sleep(1)
    st.rerun()

brand = state.get("brand") or {}
res = state.get("research") or {}
vehicles = state.get("vehicles", {})
plan_by_id = {p["id"]: p for p in state.get("flight_plan", [])}
running = state.get("phase") != "done" and not is_saved


def video_path(rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else run_dir / p


# ---------------- header ----------------
active = next((vid for vid, v in vehicles.items() if v.get("status") in ("building", "polling", "hold")),
              next(iter(vehicles), None))
category = str(brand.get("category", "")).title()
summary = state.get("summary") or {}
if running:
    badge = '<span class="lf-badge wait">In progress</span>'
elif summary.get("cleared") == summary.get("total") and summary.get("total"):
    badge = f'<span class="lf-badge ok">{summary["cleared"]} of {summary["total"]} ready to post</span>'
else:
    badge = f'<span class="lf-badge bad">{summary.get("cleared", 0)} of {summary.get("total", 0)} ready</span>'
phase = state.get("phase", "")
steps = [("Learn the brand", {"brand"}), ("Research", {"research"}), ("Write the checklist", {"spec"}),
         ("Make and check videos", {"build", "verify"}), ("Ready", {"done"})]
order = [ph for _, phs in steps for ph in phs]
now_i = next((i for i, (_, phs) in enumerate(steps) if phase in phs), 0)
step_html = "".join(f'<div class="{"done" if i < now_i or (phase == "done") else "now" if i == now_i else ""}">{t}</div>'
                    for i, (t, _) in enumerate(steps))
pings = state.get("human_pings", 0)
st.markdown(
    f'<div class="lf-head"><div class="lf-title">{safe(brand.get("name", "Brand"))}</div>{badge}'
    f'{"<span class=lf-badge>Saved</span>" if is_saved else ""}</div>'
    f'<div class="lf-meta">{safe(category)} · {safe(brand.get("market", ""))} launch · {safe(state.get("mission", ""))}</div>'
    f'<div class="lf-steps">{step_html}</div>'
    f'<div class="lf-ticker"><span class="lf-dot{" busy" if running else ""}"></span>'
    f'<span>{safe(ticker_line(events, plan_by_id))}</span>'
    f'<span class="pings">{("Needed you " + str(pings) + " times") if pings else "Didn&#39;t need you once"}</span></div>',
    unsafe_allow_html=True,
)
# One page, read top to bottom: what's trending, your videos, posting, the checklist, how it improves.
t_research, t_videos, t_post, t_check, t_activity = (st.container() for _ in range(5))

with t_videos:
    # ---------------- the output: one card per launch video ----------------
    st.markdown('<div class="lf-sec">Your launch videos</div>', unsafe_allow_html=True)
    st.caption("You only see a video once it passes every check on the Quality checklist. One that fails a "
               "check is sent back with exactly what failed, fixed, and checked again.")
    if not vehicles:
        st.info("The Director is writing the directions…" if running else "No videos in this launch.")
    else:
        cols = st.columns(len(vehicles), gap="medium")
        for col, (vid, v) in zip(cols, vehicles.items()):
            d = v.get("direction", {})
            attempts = v.get("attempts", [])
            with col:
                # Video first, like every video grid people know: all three line up whatever the text below.
                mp4 = video_path(attempts[-1]["mp4"]) if attempts else None
                if mp4 and mp4.exists():
                    # Opening a second in shows the ad itself, not the empty frame before the product drops in.
                    _, mid, _ = st.columns([0.1, 0.8, 0.1])
                    with mid:
                        st.video(str(mp4), start_time=1)
                elif running:
                    st.markdown('<div class="lf-dir" style="height:420px;display:grid;place-items:center;color:var(--hint)">'
                                'Being made…</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="lf-dir{" active" if vid == active and running else ""}" style="margin:10px 0">'
                    f'<b>{safe(vid)}. {safe(v.get("name", ""))}</b>'
                    f'<div class="sub">“{safe(d.get("hook", ""))}”<br>{safe(d.get("duration_s", "?"))}s, vertical, '
                    f'{safe(humanize_tag(v.get("pattern", "")).lower())}</div>{status_lines(v, plan_by_id)}'
                    f'{try_trail(attempts, plan_by_id)}'
                    f'{footage_credit(d)}</div>',
                    unsafe_allow_html=True)
                if attempts:
                    with st.expander("Every check, in detail"):
                        for prev in attempts[:-1]:
                            failed = [r for r in prev["verdict"]["results"] if not r["pass"]]
                            if failed:
                                ev = "; ".join(safe(miss_sentence(r, plan_by_id)) for r in failed)
                                st.markdown(f'<div class="lf-note"><b>Try {prev["attempt"]} sent back.</b> {ev}</div>',
                                            unsafe_allow_html=True)
                        rows = "".join(
                            f'<div class="lf-row"><div class="{"ok" if r["pass"] else "bad"}">'
                            f'{safe(promise_title(r, plan_by_id))}</div>'
                            f'<div class="lf-num">{safe(r["measured"])}<small>needs {safe(r["expected"])}</small></div></div>'
                            for r in attempts[-1]["verdict"]["results"])
                        st.markdown(f'<div class="lf-card" style="padding:4px 14px">{rows}</div>', unsafe_allow_html=True)
                        dec, gc = v.get("decision"), v.get("goalcheck")
                        if dec:
                            kind = {"GO": "gocard", "CALL": "callcard"}.get(dec["decision"], "")
                            words = {"GO": "Passed every check.", "HOLD": "Sent back.", "SCRUB": "Dropped.",
                                     "CALL": "Needs your decision."}.get(dec["decision"], dec["decision"])
                            st.markdown(f'<div class="lf-note {kind}"><b>{words}</b></div>', unsafe_allow_html=True)
                        if gc:
                            word = ("Ready to post. A fresh reviewer, who saw only your brief and the video, agreed:"
                                    if gc["satisfies_goal"] else "Misses your brief:")
                            st.markdown(f'<div class="lf-note {"gocard" if gc["satisfies_goal"] else ""}"><b>{word}</b> '
                                        f'{safe(gc["reason"])}</div>', unsafe_allow_html=True)
                else:
                    st.caption("Rendering…")


# ---------------- review & post: one video at a time, approve or skip (posting is a demo) ----------------
PLATFORMS = ["TikTok", "Instagram Reels", "YouTube Shorts"]


def source_post(d: dict) -> dict | None:
    """The real viral post this direction's pattern came from, if the research has one."""
    tag = str(d.get("pattern", ""))
    wall = res.get("trend_wall", [])
    return next((w for w in wall if tag in (w.get("patterns") or [])), None) or (wall[0] if wall else None)


@st.dialog("Post this video")
def post_dialog(vid: str, v: dict) -> None:
    key = f"post_{run_dir.name}_{vid}"
    step = st.session_state.get(key + "_step", 1)
    st.caption(f"Step {step} of 3 · {safe(v.get('name', ''))}")
    if step == 1:
        st.markdown("**What would you like to do?**")
        c1, c2 = st.columns(2)
        if c1.button("Save to library", use_container_width=True):
            st.session_state.setdefault("posted", {})[key] = {"vid": vid, "what": "Saved to library"}
            st.toast(f"Video {vid} saved to your library.")
            st.rerun()
        if c2.button("Schedule post", type="primary", use_container_width=True):
            st.session_state[key + "_step"] = 2
            st.rerun(scope="fragment")
    elif step == 2:
        st.markdown("**Details**")
        st.multiselect("Post to", PLATFORMS, default=PLATFORMS[:2], key=key + "_where")
        st.text_input("Caption", v.get("direction", {}).get("hook", ""), max_chars=150, key=key + "_cap")
        st.selectbox("Who can see it", ["Public", "Followers", "Only me"], key=key + "_priv")
        b, n = st.columns(2)
        if b.button("Back", use_container_width=True):
            st.session_state[key + "_step"] = 1
            st.rerun(scope="fragment")
        if n.button("Next", type="primary", use_container_width=True, disabled=not st.session_state.get(key + "_where")):
            st.session_state[key + "_step"] = 3
            st.rerun(scope="fragment")
    else:
        import datetime
        st.markdown("**When**")
        when = st.radio("When", ["Post now", "Schedule for later"], label_visibility="collapsed", key=key + "_when")
        stamp = "now"
        if when == "Schedule for later":
            dcol, tcol = st.columns(2)
            day = dcol.date_input("Date", datetime.date.today() + datetime.timedelta(days=1), key=key + "_day")
            tm = tcol.time_input("Time", datetime.time(17, 0), key=key + "_time")
            stamp = f"{day:%b %d} at {tm:%I:%M %p}".replace(" 0", " ")
        b, n = st.columns(2)
        if b.button("Back", use_container_width=True):
            st.session_state[key + "_step"] = 2
            st.rerun(scope="fragment")
        if n.button("Schedule" if stamp != "now" else "Post now", type="primary", use_container_width=True):
            where = ", ".join(st.session_state.get(key + "_where", []))
            st.session_state.setdefault("posted", {})[key] = {
                "vid": vid, "what": f"Scheduled for {stamp}" if stamp != "now" else "Queued to post now",
                "where": where, "caption": st.session_state.get(key + "_cap", "")}
            st.session_state[key + "_step"] = 1
            st.toast(f"Video {vid} {'scheduled for ' + stamp if stamp != 'now' else 'queued'} on {where} (demo).")
            st.rerun()


with t_post:
    st.markdown('<div class="lf-sec" style="margin-top:28px">Review and post</div>', unsafe_allow_html=True)
    ready = [(vid, v) for vid, v in vehicles.items() if v.get("status") == "go" and v.get("attempts")]
    if not ready:
        st.info("Videos appear here once they pass every check." if running else "No videos are ready to post yet.")
    else:
        posted = st.session_state.get("posted", {})
        skipped = st.session_state.setdefault("skipped", set())
        queue = [(vid, v) for vid, v in ready
                 if f"post_{run_dir.name}_{vid}" not in posted and f"{run_dir.name}_{vid}" not in skipped]
        st.caption(f"{len(ready)} videos ready to post. Approve the ones you want, skip the rest.")
        if queue:
            vid, v = queue[0]
            d = v.get("direction", {})
            src = source_post(d)
            left, mid, right = st.columns([0.9, 1.1, 1.1], gap="large")
            with left:
                st.markdown('<div class="why" style="font-size:12px;color:var(--soft);margin-bottom:6px">Built from</div>',
                            unsafe_allow_html=True)
                if src and thumb_for(src):
                    st.markdown(
                        f'<a href="{safe(src["url"])}" target="_blank" style="text-decoration:none;color:inherit">'
                        f'<img src="{safe(thumb_for(src))}" style="width:100%;border-radius:12px;aspect-ratio:9/12;object-fit:cover">'
                        f'<div style="font-size:13px;margin-top:6px">{safe(src.get("hook", ""))}</div>'
                        f'<div class="why" style="font-size:12px;color:var(--soft)">'
                        f'{(views(src["views"]) + " views · ") if src.get("views") else ""}{safe(ago(src.get("age", "")))}</div></a>',
                        unsafe_allow_html=True)
                else:
                    st.caption("A pattern from this month's viral videos.")
            with mid:
                st.video(str(video_path(v["attempts"][-1]["mp4"])), start_time=1)
                b1, b2 = st.columns(2)
                if b1.button("✕  Skip", use_container_width=True, key=f"skip_{vid}"):
                    skipped.add(f"{run_dir.name}_{vid}")
                    st.rerun()
                if b2.button("✓  Approve", type="primary", use_container_width=True, key=f"ok_{vid}"):
                    post_dialog(vid, v)
            with right:
                st.markdown(f"**{safe(vid)}. {safe(v.get('name', ''))}**")
                st.markdown(f"“{safe(d.get('hook', ''))}”")
                st.markdown('<div class="lf-sec" style="margin-top:12px">Why this video?</div>', unsafe_allow_html=True)
                verdict = v["attempts"][-1]["verdict"]
                gc = v.get("goalcheck") or {}
                tries = (f" after {len(v['attempts'])} tries" if len(v["attempts"]) > 1 else " on the first try")
                st.markdown("\n".join([
                    f"- Uses **{safe(humanize_tag(d.get('pattern', '')).lower())}**, a pattern working in this month's viral videos",
                    f"- Passed **{verdict['passed']} of {verdict['total']}** quality checks{tries}",
                    "- A fresh reviewer agreed it fits your brief"]), unsafe_allow_html=True)
                if gc.get("reason"):
                    st.caption(gc["reason"])
            st.caption(f"{len(queue) - 1} more to review after this one.")
        else:
            st.success("All videos reviewed.")
            if st.button("Review them again"):
                st.session_state["skipped"] = set()
                for k in [k for k in posted if k.startswith(f"post_{run_dir.name}_")]:
                    posted.pop(k)
                st.rerun()
        mine = [(k, x) for k, x in posted.items() if k.startswith(f"post_{run_dir.name}_")]
        if mine:
            st.markdown('<div class="lf-sec">Scheduled</div>', unsafe_allow_html=True)
            rows = "".join(
                f'<div class="lf-row"><div><b>Video {safe(x["vid"])}</b>'
                f'<div class="why">{safe(x.get("where", "Library"))}{" · “" + safe(x["caption"]) + "”" if x.get("caption") else ""}</div></div>'
                f'<div class="lf-num">{safe(x["what"])}<small>demo, not published</small></div></div>' for _, x in mine)
            st.markdown(f'<div class="lf-card">{rows}</div>', unsafe_allow_html=True)

with t_check:
    # ---------------- what ready to post means ----------------
    left, right = st.columns([1.35, 1], gap="large")
    with left:
        st.markdown('<div class="lf-sec">Quality checklist</div>', unsafe_allow_html=True)
        st.caption("Every video is checked against this list before you see it. Liftoff wrote it from your brief "
                   "before making anything, so the videos are held to it and not the other way round.")

        def promise_row(p: dict) -> str:
            title, bar, how = promise(p)
            why = WHY.get(title, "")
            return (f'<div class="lf-row"><div><b style="font-weight:600">{safe(title)}</b>'
                    f'<div class="why" style="font-size:14px;color:var(--ink);margin-top:2px">{safe(bar)}</div>'
                    f'{f"<div class=why>{safe(why)}</div>" if why else ""}</div>'
                    f'<div class="lf-num"><small style="font-size:12px">{safe(how)}</small></div></div>')

        rows = "".join(promise_row(p) for p in state.get("flight_plan", [])) or '<div class="lf-row">Writing it down…</div>'
        st.markdown(f'<div class="lf-card">{rows}</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="lf-sec">What we assumed</div>', unsafe_allow_html=True)
        st.caption("Your brief didn't say these, so Liftoff chose and tells you. Put them in the brief to change them.")
        led = "".join(f'<div class="lf-row"><div>{safe(a.removeprefix("Assumed ").rstrip("."))}</div></div>'
                      for a in state.get("assumptions", []))
        esc = "".join(f'<div class="lf-note callcard"><b>Needs your decision:</b> {safe(e)}</div>'
                      for e in state.get("escalations", []))
        st.markdown(f'<div class="lf-card">{led or "<div class=lf-row>Nothing yet</div>"}{esc}</div>', unsafe_allow_html=True)


with t_research:
    # ---------------- research: what the directions were built from ----------------
    comps = "".join(
        f'<div class="lf-comp"><div class="lf-av" style="background:{AVATAR[i % 5][0]};color:{AVATAR[i % 5][1]}">'
        f'{safe(initials(c["name"]))}'
        f'{f"<img alt=\"\" src=\"{safe(brand_icon(c))}\">" if res.get("live") and brand_icon(c) else ""}</div><div><b>{safe(c["name"])}</b>'
        f'<span>{c["videos"]} {"mentions" if res.get("live") else "videos"}</span></div></div>'
        for i, c in enumerate(res.get("competitors", [])[:4])
    )
    pats = "".join(f'<span class="lf-tag">{safe(humanize_tag(p["tag"]))}</span>' for p in res.get("patterns", [])[:5])
    tiles = []
    for i, post in enumerate(res.get("trend_wall", [])[:8]):
        bg, fg = TILE[i % 6]
        linked = "REPLACE_ME" not in post.get("url", "")
        embed = embed_url(post) if linked else None
        # Plays in place through the platform's own embed player; nothing is downloaded.
        open_tag = f'<div class="lf-tile" data-embed="{safe(embed)}">' if embed else '<div class="lf-tile">'
        thumb = thumb_for(post)
        top = (f'<div class="top has-thumb" style="background-color:{bg};background-image:url(\'{safe(thumb)}\')">'
               f'<span class="plat">{safe({"youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram"}.get(post.get("platform", ""), post.get("platform", "")))}</span><i></i></div>' if thumb
               else f'<div class="top" style="background:{bg};color:{fg}"><i></i></div>')
        open_link = f'<a class="open" href="{safe(post["url"])}" target="_blank">open ↗</a>' if linked else ""
        tiles.append(
            f'{open_tag}{top}'
            f'<div class="meta"><div class="views">'
            f'{(views(post["views"]) + " views") if post.get("views") else ""}{" · " if post.get("views") and post.get("age") else ""}{safe(ago(post.get("age", "")))}</div>'
            f'{open_link}<div class="hook">{safe(post["hook"])}</div></div></div>')

    TOP_JS = """
    <script>
    document.querySelectorAll('.lf-tile[data-embed]').forEach(function (tile) {
      tile.addEventListener('click', function (e) {
        if (e.target.closest('a.open')) return;
        var top = tile.querySelector('.top');
        if (top.classList.contains('playing')) return;
        top.classList.add('playing');
        top.innerHTML = '<iframe src="' + tile.dataset.embed + '" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen></iframe>';
      });
    });
    </script>"""
    if res:
        st.markdown('<div class="lf-sec">Recent, viral videos in your category</div>', unsafe_allow_html=True)
        st.caption("Short videos from the last 30 days with 100K+ views, most watched first. Your videos are built "
                   "from what is working here. Tap one to play it.")
        source = "Live from You.com" if res.get("live") is True else "Cached search" if res.get("live") else "Sample research"
        research_html = (
            f'<div class="lf-card"><div class="lf-h">Viral this month <small>{source}</small></div>'
            f'{f"<div class=lf-pats style=margin:0 0 12px><span class=why style=font-size:12px;color:var(--soft);margin-right:6px>Working now:</span>{pats}</div>" if pats else ""}'
            f'<div class="lf-wall">{"".join(tiles)}</div></div>')
        components.html(f'<!doctype html><html><head><style>{CSS}\nbody{{margin:0;background:var(--bg);font-family:Inter,system-ui,sans-serif;color:var(--ink)}}'
                        f'.lf-wall{{grid-template-columns:repeat(4,1fr)}}@media(max-width:900px){{.lf-wall{{grid-template-columns:repeat(2,1fr)}}}}</style></head>'
                        f'<body>{research_html}{TOP_JS}</body></html>', height=560, scrolling=False)


with t_activity:
    # ---------------- learning: the playbook loop (liftoff/playbook.py) ----------------
    report_path = RUNS / "playbook" / "report.json"
    if report_path.exists():
        rep = json.loads(report_path.read_text())
        fl = rep.get("flights", [])
        if fl:
            n_missions = (rep.get("missions_per_split") or 6)
            st.markdown('<div class="lf-sec">It learns from every launch</div>', unsafe_allow_html=True)
            st.caption(
                "Every time a video is sent back, Liftoff records what failed, the number it measured, and the fix "
                "that made it pass. After a batch of launches it turns those into rules for itself, like \"keep the "
                "logo on screen at least 3.25 seconds\". Before trusting a rule it tries it on launch briefs it has "
                "never seen. If more videos pass on the first try, the rule stays. If not, it is thrown away.")

            def label(f: dict) -> tuple[str, str]:
                if f["flight"] == 1:
                    return "Before learning", "no rules yet"
                if f["kept"]:
                    return f"After learning round {f['flight'] - 1}", "rules kept: more videos passed first time"
                return f"After learning round {f['flight'] - 1}", "rules thrown away: no improvement"

            rows = ""
            for f in fl:
                title, sub = label(f)
                ho = f["held_out"]
                rows += (f'<div class="lf-row"><div>{safe(title)}<div class="why">{safe(sub)}</div></div>'
                         f'<div class="lf-num"><b class="{"ok" if f["kept"] and f["flight"] > 1 else "idle"}">'
                         f'{ho["first_attempt_go_rate"]:.0%}</b><small>passed on the first try</small></div></div>')
            kept = next((f["playbook"] for f in reversed(fl) if f["kept"]), {})
            who = {"director": "The video maker follows", "spec": "The checklist writer follows"}
            rules = "".join(f'<div class="lf-row"><div><div class="why">{safe(who.get(role, role))}</div>{safe(line.lstrip("- "))}</div></div>'
                            for role, text in kept.items() for line in text.splitlines() if line.strip())
            c1, c2 = st.columns([1, 1.25], gap="large")
            c1.markdown(f'<div class="lf-card"><div class="why" style="padding:10px 0 4px">Tested on new launch briefs '
                        f'it had never seen</div>{rows}</div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="lf-card"><div class="why" style="padding:10px 0 4px">Rules it wrote for itself '
                        f'and kept</div>{rules or "<div class=lf-row>No rules kept yet</div>"}</div>',
                        unsafe_allow_html=True)

    # ---------------- raw telemetry ----------------
    with st.expander("Full activity log"):
        rows = "".join(
            f'<div><span>{e["t"]:.2f}s</span><span>{safe(e["agent"])}</span><span>{safe(e["event"])}</span>'
            f'<span>{safe(e.get("vehicle") or "")}</span><span>{safe(json.dumps(e["payload"], default=str)[:160])}</span></div>'
            for e in events[-60:][::-1]
        )
        st.markdown(f'<div class="lf-tele">{rows}</div>', unsafe_allow_html=True)


if auto and running:
    time.sleep(2)
    st.rerun()
