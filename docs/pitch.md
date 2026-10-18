# Liftoff pitch script

About 3 minutes. Words in **bold** are worth hitting hard. Lines in *italics* are what to do on screen.

Before you start, have these open in tabs:
1. The landing page, http://localhost:3000
2. Mission control on the poppi launch, http://localhost:8501/?flight=drinkpoppi-com-studio
3. The demo video, `docs/liftoff-demo.mp4`, as a backup if the Wi-Fi or a live call misbehaves

---

## 1. The opening (20 seconds)

> Every AI tool will make you a launch video in seconds now. Nobody checks them.
>
> The logo flashes by in under two seconds. The text is yellow on white, so you can't read it on a phone. The colours are a little off brand. And a human finds that out after it's posted.
>
> **Liftoff doesn't let a video out until it can prove it's done.**

Start with the problem, not the product. Let "nobody checks them" land before you move on.

## 2. What it is (15 seconds)

> Liftoff is a team of AI agents. You give it a brand's website. It writes down what "done" means for that launch, makes three videos, and has a separate checker measure every one. If a video misses, it goes back with exactly what failed. And it learns from its own misses.

## 3. Live demo (90 seconds)

*Landing page. Type `drinkpoppi.com`, press Launch.*

> I paste poppi's website. That's the whole brief.

*Mission control opens. Point at the top.*

> First it learns the brand from the site itself: name, colours pulled from poppi's own CSS, the logo, the tone. Then it looks at what's working right now.

*Scroll through the viral Shorts. Tap one so it plays in place.*

> These are real Shorts in poppi's category from the last 30 days, over 100,000 views each. It tags what's working, like process videos and slow motion, and builds from that.

*Scroll to Your launch videos.*

> **Before it makes a single frame, it writes the checklist.** Ten checks. Logo on screen at least three seconds. Text contrast at 4.5 or better, the accessibility standard. Brand colours. A hook in the first second. No competitor logos, no health claims. Every one is a number it can measure, or a yes or no a model can answer from a frame.

*Open "Every check, in detail" on one video.*

> Here's the evidence. Logo: measured 4.5 seconds. Contrast: 15.6. It doesn't say "looks good". It shows the number.

*If you have the Fizz demo or the GIF handy, show the HOLD then GO.*

> And this is what happens on a miss. First try, logo on screen for 2 seconds and contrast 3.8. Sent back. The fix: 3.25 seconds and 13.3. Passed. **Nobody had to tell it.**

*Scroll to Review and post.*

> When they pass, you review and approve. For poppi, three for three, and it didn't need me once.

## 4. Why you can trust it (30 seconds)

This is the "Done Means Done" part. Say it plainly.

> Three rules make the checking honest, and they're enforced in code, not asked for in a prompt.
>
> One: **the checker never sees the maker's notes.** It can't be told "the logo is on for 3.4 seconds". It has to measure.
>
> Two: **the maker and the checker are different model families.** DeepSeek makes, NVIDIA Nemotron checks, so they don't share blind spots.
>
> Three: **a final reviewer sees only your original ask and three frames.** Never the checklist. That catches a video that passes every check but misses the point.

## 5. It learns (20 seconds)

*Scroll to "It checks itself, and it learns".*

> After each launch it looks at what failed and writes itself rules. But a rule stays only if it helps on launch briefs it has never seen. We tested on held-out briefs: **first-try passes went from 0% to 50%**. A second round of rules didn't help, so it threw them away.

## 6. The close (10 seconds)

> Paste a website, get launch videos that are proven before they go out. Liftoff. **Done means done.**

---

## The technical parts, if they ask or you have time

**The flow.** Brand card, then research, then the Spec agent writes the checklist, then the Director writes three directions, they're rendered, the verifier checks each, the Arbiter decides GO, HOLD, SCRUB or ask a human, and a goal re-check gives the final yes.

**The checker is mostly maths, not vibes.** Pixel checks run in Python: logo time by template matching on sampled frames, WCAG contrast measured on the actual text pixels, colour distance from the brand palette, duration, aspect ratio. Only things that need eyes, like "is there a hook in the first second", go to a vision model, one frame and one yes or no question at a time.

**The fix loop.** On a HOLD, the Arbiter hands the Director exactly what failed with the measured number. The Director can only move real levers, like logo time, background colour or the footage, so every fix maps to something the checker measures. Up to three tries, then it's dropped.

**Learning (Version N+1).** 20 missions, 10 to train on and 10 held out. A playbook agent reads every miss and writes at most six rules per role. They're kept only if the held-out first-try pass rate goes up and the overall pass rate doesn't go down.

**Speed.** Checks run in parallel with a shared limit and retry with backoff on rate limits. A full launch, with research, checklist, three videos, every check, retries and the final review, takes about two minutes.

**The videos.** The pipeline renders with Pillow and ffmpeg so every lever is measurable. The poppi showcase videos were animated in Remotion from the ideas Liftoff wrote, then held to exactly the same 10 checks. All three passed.

**It runs offline too.** `LIFTOFF_MOCK=1` runs the whole thing end to end with no keys, for testing.

---

## How each sponsor is used

Say this in one breath if there's a sponsor moment: *"Every model call runs on Crusoe. Nemotron is the checker. You.com does the research."*

**Crusoe Managed Inference.** Every model call goes through Crusoe, behind one wrapper (`liftoff/llm.py`) that maps each agent role to a model. Having Nemotron, DeepSeek, GLM and Qwen on one key let us run a real 8-model bake-off to pick the video writer, and keep maker and checker in different families. Turning thinking off for the checklist call cut it from 56 seconds to about 25.

**NVIDIA Nemotron 3.** Nemotron is the judge.
- **Super 120B** writes the checklist for each launch, and writes the rules the system learns from its failures.
- **Nano 30B** reads the brand's website into a brand card and tags what's working in viral videos.
- **Nano Omni** is the checker's eyes: hook, end card, competitor logos and health claims on sampled frames. It's also the final independent reviewer, because it can take three frames in one prompt.

**You.com.** Contents reads the brand's own website, so brand colours come from the site's real CSS and are never made up. Search finds what's happening in the category and backs the checklist's thresholds with sources.

**Also used:** the YouTube Data API for real viral Shorts and view counts, legally, with no scraping. ElevenLabs for the demo video's voiceover. Remotion for the poppi showcase videos and the demo video.

---

## Questions you'll probably get

**"Isn't this just an AI checking an AI?"**
> Mostly not. Logo time, contrast, colour, length and shape are measured in code. The model only answers narrow yes or no questions about single frames, and it's a different family from the one that made the video.

**"Why not use a video generation model?"**
> Because "done" has to be fixable. If the checker says the logo was on for 2 seconds and needs 3, our maker can change exactly that. A generative model would just roll the dice again.

**"How do you know the learning is real?"**
> It's scored on briefs it never trained on, and a rule that doesn't improve that score gets thrown away. One round helped, 0 to 50%. The next didn't, so it was reverted.

**"What would you build next?"**
> Real footage from stock libraries, posting straight to TikTok and Instagram after approval, and running the agents in a locked-down sandbox on Crusoe Cloud.

**"What's the human's role?"**
> Approve or skip. It only asks you something mid-launch when a check can't be measured, and for poppi that was zero times.
