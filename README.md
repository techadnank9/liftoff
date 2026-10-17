# Liftoff

**Your launch video doesn't leave the pad until mission control says go.**

Liftoff is an agent team for the Done Means Done track. Give it a one-line mission
("Launch video for Fizz cola, bold, for vertical feeds"). Before building anything, a Spec
agent writes the definition of done as executable checks and an assumption ledger of every
gap it filled in. A Director builds video directions ("vehicles"). An independent verifier,
on a different model family, runs every check against the rendered MP4. An arbiter decides
GO, HOLD, SCRUB or CALL the human. A final goal re-check that never saw the spec confirms
the asset satisfies the mission as written. Then the team reviews the flight and gets better.

## Why this is Done Means Done

| Track line | How Liftoff does it |
|---|---|
| Writes its own definition of done | Spec agent -> flight plan of 6 to 10 executable checks, locked before any build |
| Checks with tests or independent verifiers | ffprobe, pixel checks (logo seconds, palette, WCAG contrast) + Nemotron Omni vision on sampled frames. Verifier never reads the Director's output |
| Catches drifting | drift score per vehicle (brief vs mission + brand tone) |
| Catches looping | same check, same measurement, two attempts in a row -> strategy switch or SCRUB |
| Continue / re-plan / stop / ping human | GO / HOLD / SCRUB / CALL with a reason on every transition |
| One-line goal, walk away | mission in, verified vehicles out, human pings counted on screen |
| Asset satisfies the goal, not just the checks | independent goal re-check with mission + frames only |

## Sponsors

- **Crusoe Managed Inference**: every model call. OpenAI-compatible endpoint, `liftoff/llm.py`.
- **NVIDIA Nemotron 3**: Super for Spec and Arbiter, Nano for cheap classification, Nano Omni as the verifier's eyes. The Director runs on a different family (DeepSeek) so the verifier can't share its blind spots.
- **You.com**: Scout and Librarian (Phase 2 live; Phase 1 fixture): competitor discovery, launch coverage, public post URLs, and citations for the spec's thresholds.
- **NemoClaw**: Phase 2 sandbox for the Director and renderer. Network locked to Crusoe and You.com.

## Run

```bash
pip install -r requirements.txt
python scripts/make_assets.py                 # generates the fictional brand (Fizz)
LIFTOFF_MOCK=1 python -m liftoff.run          # full lap with fixtures, no key, ~20s
streamlit run app.py                          # mission control
```

Real inference:

```bash
cp .env.example .env   # fill CRUSOE_API_KEY (and YDC_API_KEY for Phase 2)
export $(cat .env | xargs)
python -m liftoff.run --mission "Launch video for Fizz cola, bold, for vertical feeds"
```

## Demo script (2 minutes)

1. Type the mission. Watch the flight plan and the assumption ledger appear before any build.
2. Vehicle A renders. Verifier polls: logo on screen 2.25s, needs 3.0; text contrast 3.78, needs 4.5. Arbiter: HOLD, sends both numbers back to the Director.
3. Director patches (logo hold 3.4s, background to secondary). Attempt 2: 8 of 8. GO.
4. Goal re-check, with only the mission and three frames: liftoff confirmed.
5. B and C clear first time. Human pings: 0. Elapsed: about 20 seconds.
6. Point at the ledger: "Assumed 9:16, assumed English, assumed US." Nothing silent.

## Status

Phase 1 (this submission): the full loop runs end to end; research uses a fixture; vision checks and goal re-check call Nemotron Omni on Crusoe.
Phase 2 (next): live You.com research, drift via embeddings, flights 1..N with the held-out eval set, NemoClaw sandbox. See `AGENTS.md`.

Fizz is a fictional brand. Real brands appear only as researched references.
