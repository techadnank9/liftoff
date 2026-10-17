# Liftoff: submission answers

## Project Description

Liftoff makes launch videos for a brand and proves each one is ready to post before a person ever sees it.

Paste a brand's website. Liftoff reads the site for the brand's name, colours and tone, then pulls this month's viral short videos in its category (100K+ views, last 30 days) to see what is working right now. Before making anything, it writes a quality checklist for this launch: the right length and shape, the logo on screen for at least 3 seconds, text readable on a phone (WCAG contrast 4.5:1), a hook in the first second, ending on the brand name, no competitor logos, no health claims. Then it makes three videos and an independent checker measures every one against that list. A video that misses is sent back with exactly what failed ("logo on screen 2.25s, needs 3s") and fixed, until it passes or is dropped after three tries. A final reviewer that sees only the brief and the frames confirms each video does what was asked.

The problem: AI can generate content endlessly, but nobody checks whether it is actually done. Brand rules get broken, text is unreadable, logos flash by, and a human has to review everything. Liftoff writes its own definition of done first, verifies against it with measurements and a different model family from the one that made the video, and only asks a human when an agent must not decide (for example, a brand with no colours on its site).

It also improves itself: after each batch of launches it turns its own failures into rules and keeps a rule only if it raises first-try passes on briefs it has never seen. In a real run, first-try passes on unseen briefs went from 0% to 50%, with overall passes holding at 100%.

Real results: poppi (from drinkpoppi.com) 3 of 3 videos ready to post, 0 times a human was needed; the fictional Fizz demo, 3 of 3.

## Public GitHub Repository

https://github.com/techadnank9/liftoff

## Public Demo Video

(record and paste the YouTube link)

## Which problem statement are you submitting to?

Done Means Done

## Are you submitting for NVIDIA's Best Use of Nemotron?

Yes

## Are you submitting for NVIDIA's Best Use of NemoClaw & OpenShell?

No. We designed the sandbox (network limited to Crusoe, You.com and YouTube) and wrote the Crusoe Cloud VM tooling, but did not get it running in time.

## Did you use NVIDIA tools for your project?

Yes. NVIDIA Nemotron 3 Super 120B writes the quality checklist and the self-improvement rules. Nemotron 3 Nano reads a brand's website into a brand card and tags what is working in viral videos. Nemotron 3 Nano Omni is the checker's eyes (hook, end card, competitor logos, health claims on sampled frames) and the final independent reviewer. All served through Crusoe Managed Inference.

## Did you use You.com tools for your project?

Yes. You.com Contents reads the brand's website to build its brand card (name, colours from the site's own CSS, tone). You.com Search finds competitor brands, launch coverage, public TikToks, and citations that back the checklist's thresholds.

## Describe your use of Crusoe Managed Inference to build the submitted project

Every model call in Liftoff goes through Crusoe Managed Inference, behind one OpenAI-compatible wrapper (liftoff/llm.py) that maps each role to a model:

- Nemotron 3 Super: writes the per-launch quality checklist (with thinking turned off through chat_template_kwargs, which cut that call from 56s to about 25s) and writes the rules the system learns from its own failures.
- Nemotron 3 Nano: builds a brand card from a website and tags patterns in viral videos.
- Nemotron 3 Nano Omni: answers per-frame questions for the checker and does the final goal review with three frames.
- DeepSeek V4 Pro: writes the video directions, deliberately a different model family from the checkers so they don't share its blind spots. We picked it from an 8-model bake-off on Crusoe (copy quality plus reliable JSON).
- DeepSeek V4 Flash: fast field fixes after a failed check, and fallback if a creative reply is unusable.

We run checks in parallel with a shared concurrency cap and jittered backoff on Crusoe's rate limits. A full launch (research, checklist, three videos, every check, retries, final review) takes about 2 minutes.

## Provide feedback from your experience with using Crusoe products

What worked well: the OpenAI-compatible endpoint meant one wrapper for every model; switching models was a one-line change. Having Nemotron (Super, Nano, Omni), DeepSeek, GLM, Qwen and others on one key made it easy to run a real model bake-off and to keep builder and checker in different families. Turning thinking off per call worked and made a big latency difference. Latency was good.

What we hit:
- Model names on the account (for example "NVIDIA-Nemotron-3-Super-120B-A12B", "Deepseek-V4-Flash") differed from names in examples; listing models was the only reliable source.
- Nemotron Super is text only and Super VL accepts one image per prompt; Nano Omni handled three frames. A per-model capability table would save time.
- Some reasoning models put the answer in the reasoning field or think out loud before the JSON, so parsing had to be defensive. GLM-5.3 had the best ad copy in our bake-off but broke JSON about half the time, even with thinking off.
- Parallel load hit 429 max_requests_limit; documenting the concurrency limit would help size parallelism.
- Infrastructure Cloud: inference credits don't cover VMs, the docs' API host (api.cloud.crusoe.ai) returned 404 while api.crusoecloud.com worked, and a default Python user agent was blocked by Cloudflare (error 1010) until we set one.

## Provide feedback from your experience of using partner products to build the submitted project

You.com: Search was fast (about 2 to 3 seconds) and the include_domains and country filters were exactly what we needed to find public TikToks and competitor coverage without scraping. Contents returned full HTML of a brand site, which let us pull real brand colours from its CSS, so we never invent a brand's palette. Small notes: include_domains wants a list (a comma string fails validation), and the SDK prints deprecation warnings for search.unified and contents.generate.

NVIDIA Nemotron: Nano Omni was dependable for narrow yes/no questions on single frames when the question was about something a still frame can show; it correctly declined questions about sound or beats, which taught us to ban those from the checklist. Super wrote good checklists once the prompt was strict, with thinking off.

YouTube Data API: the official search (recent, by view count, by region) plus statistics gave us real viral videos with real view counts, legally, in two calls.
