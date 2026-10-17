# Liftoff: instructions for the coding agent (Claude Code, Codex, or anyone else)

Read this whole file before touching code. It is the contract.

## What this is

Liftoff is an agent team for the "Done Means Done" track of the Recursive Agents Hackathon.
One-line mission in. Launch-video directions out, each one proven against a written
definition of done by an independent verifier before a human sees it. Every lap the team
reviews itself and gets measurably better (Version N+1).

Pitch line: "Your launch video doesn't leave the pad until mission control says go."

## Vocabulary (use these words in code, UI and commits)

- mission: the one-line goal
- flight plan: the Spec agent's definition of done, a list of executable checks, locked before any build
- vehicle: one video direction, rendered as an MP4
- go/no-go poll: the verifier running every check in the flight plan
- GO / HOLD / SCRUB / CALL: the arbiter's four decisions (continue / re-plan / stop / ping the human)
- liftoff confirmed: the goal re-check passed on the final vehicle
- flight: one full lap; flights 1..N are the Version N+1 loop
- telemetry: the event stream (events.jsonl)

## Hard rules

1. Every model call goes through `liftoff/llm.py: call()`. Never import openai anywhere else.
   Models live only in `llm.MODELS`. Spec/Verifier/Arbiter are Nemotron, Director is a different family. Keep it that way.
2. The verifier never reads the direction JSON. It gets the MP4, the brand card and the flight plan. Nothing else.
3. The goal re-check never sees the flight plan or the Director's reasoning. Mission + brand card + frames only.
4. `LIFTOFF_MOCK=1` must always run the full pipeline end to end with no network. If you add a model call, add its mock in `liftoff/mock.py`.
5. No scraping, no downloading of other brands' videos. Trend wall = public post URLs rendered by the platforms' own embeds.
6. Use the fictional brand (Fizz) on stage. Real brands appear only as researched references.
7. Do not add Blender, Remotion, or any generative video API. Pillow + ffmpeg is the renderer.
8. Deterministic checks decide wherever they can. The vision model only answers questions pixels can't.
9. One folder per person. Don't edit a module someone else owns in the same hour. Owners are in the task lists below.

## Layout

```
liftoff/
  llm.py        Crusoe wrapper, role->model map, mock switch          (owner: A)
  mock.py       fixtures for LIFTOFF_MOCK=1                           (owner: A)
  brand.py      brand card (Fizz fixture; assets/<name>/brand.json)   (owner: A)
  telemetry.py  events.jsonl + run.json writer                        (owner: A)
  research.py   Scout + Librarian (fixture now, You.com in Phase 2)   (owner: B)
  spec.py       Spec agent -> flight plan + assumption ledger         (owner: A)
  director.py   directions -> Pillow frames -> ffmpeg MP4             (owner: B)
  verifier.py   checks + Nemotron Omni vision calls                   (owner: C)
  arbiter.py    GO/HOLD/SCRUB/CALL, loop detection, drift stub        (owner: C)
  goalcheck.py  independent goal re-check                             (owner: C)
  run.py        one flight, end to end                                (owner: A)
app.py          Streamlit mission control                             (owner: B or UI person)
scripts/make_assets.py   generates can.png, logo.png, brand.json
eval/brands.json         20 missions for Phase 2 flights (10 train / 10 held out)
runs/                    outputs; runs/latest -> newest
```

## Run it

```
pip install -r requirements.txt
python scripts/make_assets.py                     # once
LIFTOFF_MOCK=1 python -m liftoff.run              # full lap with fixtures, ~20s
streamlit run app.py                              # mission control, tails runs/latest
export CRUSOE_API_KEY=...; python -m liftoff.run  # real inference
```

## Phase 1 (before submission): make the slice real

Everything below already runs in mock. Phase 1 is swapping mocks for real calls and
making the demo repeatable. In this order.

A (orchestration, spec, arbiter)
- [ ] Confirm CRUSOE_API_KEY works: `curl $BASE/v1/models` and check the four Nemotron names in `llm.MODELS` exist on your account. Fix names if they differ.
- [ ] Run `python -m liftoff.run` for real. If the Spec agent returns checks outside the vocabulary, tighten `spec.SYSTEM`; `_valid()` already drops bad ones.
- [ ] If Nemotron rejects `response_format=json_object`, llm.call already retries without it; make sure `parse_json` survives the prose.
- [ ] Verify CALL path: add "no palette" to a brand card and confirm the arbiter emits CALL and human_pings increments.
- [ ] Print `llm.usage_report()` at the end of every run (already emitted as a telemetry event).

B (research, director, UI)
- [ ] Replace the six `REPLACE_ME` URLs in `research.FIXTURE` with real public Shorts/TikTok/Reel URLs from the cola category so embeds render.
- [ ] Director real call: check DeepSeek returns the exact JSON shape; `plan()` already clamps duration and logo seconds.
- [ ] UI: confirm `st.video` plays the MP4s and the trend wall embeds load. Record the screen for the submission video.

C (verifier, goal check)
- [ ] Vision checks real: `verifier._vision` sends base64 PNG to Nemotron Omni. Confirm the content format works on Crusoe; if the model wants a different image payload, change only `llm.image_content`.
- [ ] Goal re-check real: same image path.
- [ ] Planted failure: `director.plan(plant_failure=True)` forces logo_seconds 2.4 on vehicle A. Confirm it HOLDs, the Director patches, attempt 2 GOes. That's the live demo beat.
- [ ] Sanity: `text_contrast_at_least` reads 3.78 for white on the orange primary and 14.7 on the navy secondary. That is a real WCAG finding, keep it; the Director's fix is to switch bg.

Submission checklist
- [ ] 2-minute screen recording: mission typed, flight plan appears, vehicle A HOLD with the measured number, Director fix, GO, liftoff confirmed, assumption ledger, human pings = 0.
- [ ] README has the one-line pitch, the sponsor map, and "how to run in mock".
- [ ] Repo public. `LIFTOFF_MOCK=1 python -m liftoff.run` works from a fresh clone.

## Phase 2 (after submission or if time appears): the full product

Research (B)
- [ ] `research._live`: You.com Search for competitors + launch coverage; You.com Contents for article text; YouTube Data API for Shorts view counts. Keep the fixture as fallback on any exception.
- [ ] Pattern tagging: Nemotron Nano reads titles/captions/article text and returns the `patterns` list. No footage is processed.
- [ ] Brand card from a URL: You.com Contents on the brand site -> name, palette (from CSS or logo), tone words.

Telemetry (C)
- [ ] Drift: replace `arbiter.drift_score` heuristic with embedding distance (brief vs mission + tone). Flag above 0.5, HOLD with reason "drift".
- [ ] Loop: already detects same-check-same-measure; add strategy switch in `director.fix` when `switch_strategy` is set (different pattern tag or temperature).

Version N+1 (A)
- [ ] `liftoff/playbook.py`: after a flight, read run.json, write a patch to `spec.SYSTEM` and `director.SYSTEM` (as files in `playbook/`), run flight N+1 on the 10 held-out missions in `eval/brands.json`, keep the patch only if go-rate rises. Report flight 1 vs flight 3 on held-out as the slide.
- [ ] Shared Brain footnote: the brand card + patterns + playbook files are the shared project every agent reads first. Say it in one sentence, don't build more.

Sandbox (anyone)
- [ ] NemoClaw: run `python -m liftoff.run` inside an OpenShell sandbox with network policy allowing only api.inference.crusoecloud.com and api.you.com. Two-hour timebox.

More checks (C)
- [ ] `audio_present`, `safe_zones` (no text in top/bottom 12%), `caption_ocr` via Tesseract when available.
