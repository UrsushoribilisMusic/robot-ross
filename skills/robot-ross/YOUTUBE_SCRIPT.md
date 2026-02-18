# Robot Ross — YouTube Video Script
### "I Built a Robot That Draws Like Bob Ross (and Narrates While It Works)"
**Speaker:** Miguel Rodriguez
**Target length:** ~7-8 minutes spoken
**Format:** Solo talking-head, maker build-journey vlog style

---

## [COLD OPEN — no title card yet]

**[B-ROLL: Tight shot of the robot arm moving slowly across paper. Pen down. Faint hum of a motor. Then, in a warm, gentle AI voice:]**

> *"We got a lovely request to paint 'Robot Ross'. Let's make some happy little marks together."*

**[B-ROLL: Wide shot — small robot arm on a desk, Mac Mini in the background, a Telegram notification visible on screen. The arm starts to draw.]**

---

*[Cut to talking head — Miguel, mid-shot, desk with the arm visible in the background]*

Hey. So — that's Robot Ross.

A small robot arm, sitting on my desk, drawing on paper, and narrating what it's doing in the voice of Bob Ross. Controlled entirely through Telegram. From my phone.

*(pause)*

Why? I don't know, man. It seemed like a wonderful idea at 11pm and then I just... kept going.

This is the story of how I built it, what broke along the way — and there was a lot that broke — and what it feels like to build something weird and physical with AI as your coding partner.

---

## SECTION 1: THE IDEA

So where does this come from?

I have this robot arm. It's called a Huenit. It's a small desktop pen plotter — basically a little arm that you attach a pen to, and it draws things by sending G-code commands over USB. Super cool little machine.

**[B-ROLL: Close-up of the Huenit arm on the desk.]**

And I also have this platform I've been building called OpenClaw. It's a local AI agent system — runs as a background service on my Mac Mini, has skills you can write for it, and routes your commands to the right skill using an AI brain. It's how I talk to my computer and make stuff happen.

So one night I thought — what if I gave the arm a *personality*. What if it didn't just draw things silently, but narrated what it was doing. Like Bob Ross. Gentle. Peaceful. *Happy little accidents.*

*(laughs)*

That was it. That was the whole idea. It's dumb and I love it.

---

## SECTION 2: HOW IT'S BUILT

Okay, quick technical overview.

**[B-ROLL: Simple diagram/graphic of the stack, or terminal screen recording]**

The arm talks over USB serial using G-code. I wrote Python scripts that generate the commands — one for writing text, one for shapes, one for SVG files.

The AI layer is OpenClaw on a Mac Mini. When you send a message via Telegram, it figures out what you want and triggers the right skill. The "brain" for routing is Claude Haiku through the API. For the Bob Ross narration — Qwen 7B running locally via Ollama generates the script, and Kokoro, a local neural TTS engine that runs on Apple Silicon, speaks it in a warm male voice.

Full flow: Telegram message in → OpenClaw routes it → arm readiness check → Qwen generates narration → three warning beeps → Bob Ross speaks the intro → arm draws while commentary plays in the background → outro. Paper comes off. Done.

---

## SECTION 2.5: WHO AM I

Before I go further — a quick word on who I am, because this project lives at an intersection that might feel unusual.

**[B-ROLL: Quick montage — LinkedIn profile, Substack header, music waveform, a glimpse of code]**

I'm Miguel Rodriguez. I'm a technology entrepreneur and product builder — I've spent most of my career building tech products and companies. But I'm also a creative. I write science fiction — I have a novel going on Substack right now. I make AI-generated music. I build weird things in my spare time and write about it on LinkedIn.

Robot Ross is a pretty good summary of who I am: equal parts engineer and storyteller, building things that technically work but also have a personality.

*(beat)*

Okay. Back to the robot.

---

## SECTION 3: THE FIRST PROBLEMS

**[B-ROLL: Early footage of the arm drawing — or log file on screen]**

The first successful run — the arm wrote "OpenClaw". No voice, no narration, just testing the mechanics. Twenty-five seconds. Clean letters.

*(beat)*

And then the problems started.

First: the pen was drawing in the air. The arm was making all the right moves, but the pen was hovering a few millimeters above the paper. Ghost-drawing into nothing.

**[B-ROLL: Arm tip slightly above paper, moving through shapes without touching]**

That's a Z-height calibration problem. The arm doesn't know where the paper surface is. So I wrote a calibration routine — jog the arm down until the pen barely touches, save that value as Z-zero. And I added a "ready flag" — a file that gets written after calibration so the system knows you've done it. Calibrate once, draw all day. Reboot, start fresh.

Second: tilt. My desk isn't perfectly level. The pen was pressing too hard on one side and barely touching the other. The drawings looked like they were done by someone falling asleep halfway through. That one wasn't a code problem — it was a physical problem. I had to measure the slope and add Z-compensation to every single Y-axis move.

None of these are glamorous. They're just the physical reality of working with real hardware.

---

## SECTION 4: BUILDING WITH AI CODING TOOLS

Let me talk about this, because it's central to how this was built.

**[B-ROLL: Claude Code terminal session — code being written]**

I built this in pair-programming sessions with Claude Code — Anthropic's AI coding CLI. I also used Gemini at points, mostly for thinking through architecture.

Here's what I'll say: it's genuinely fast. I'd describe what I needed and the AI would write it — correctly, first try sometimes. That used to take me an hour. Now it takes five minutes.

But *you still have to understand the code*. When something goes wrong — and something always goes wrong — the AI isn't in the room with you. You're the one looking at a robot arm drawing in mid-air. You have to be able to read the code and know where to look.

The quality of your output is tied to the quality of your problem description. That hasn't changed.

---

## SECTION 5: THE FUNNY FAILURES

**[B-ROLL: Terminal log file — then cut back to Miguel]**

Two real failures from my actual log file, because they're both instructive and kind of hilarious.

**The wrong Python environment.**

Everything checked out. Arm connected, calibrated, narration ready. The voice said the Bob Ross intro — *"We got a lovely request... let's make some happy little marks together"* — and then the arm immediately stopped. Failed in 0.2 seconds.

**[B-ROLL: Log file: "SUBPROCESS ERROR — ModuleNotFoundError: No module named 'serial'"]**

`pyserial` — the library that talks to the USB port — wasn't installed in the Python environment the subprocess was using. The fix was one line of code. I stared at it for a long time before I found it.

**The AI that refused to move the arm.**

Before I switched the routing brain to Claude Haiku, Qwen 7B was doing the routing. And occasionally — not every time — instead of running the draw skill, it would respond with... an audio file. An MP3. You'd ask it to write something on paper, and Telegram would send you back music.

*(pause)*

I never fully figured out what was going on in Qwen's head. I switched to Haiku. Problem solved.

---

## SECTION 6: THE MOUNTAIN

Okay. This is the part I want you to watch.

**[B-ROLL: Time-lapse — arm drawing the mountain SVG from start to finish. Let it breathe. No talking over it for a few seconds.]**

This is Robot Ross drawing a mountain landscape — a full vector illustration — in real time. Well, time-lapse. The actual draw took about 14 minutes. Over 7,000 individual pen moves.

*(beat)*

The arm lifts and lowers the pen at every path. Traces every ridge, every valley. And while it draws, Kokoro narrates in that warm Bob Ross voice.

There's something about watching a machine do this slowly and deliberately that I find genuinely meditative. It's not fast. It doesn't need to be. It's just... drawing.

**[B-ROLL: Close-up of the finished mountain drawing being lifted from the desk.]**

---

## SECTION 7: WHAT'S NEXT

**[B-ROLL: Arm at rest on the desk. Eyes/screen display visible on the arm or setup.]**

So where does this go?

Robot Ross already has a small screen — a little display that's part of the setup. The next thing I want to build is giving it *emotions*. Having the eyes change as it draws — focused and calm during the work, maybe a little proud when it finishes. Making it feel less like a machine executing commands and more like a character that's genuinely engaged in what it's doing.

I also want to build a text-to-drawing pipeline — you describe a scene, AI generates the SVG, Robot Ross draws it. Full natural language to physical paper.

And longer term, OpenClaw — the platform underneath all of this — is something I want to share more widely. If you have a robot arm, a 3D printer, any physical machine you want to talk to and control with natural language, the architecture applies.

---

## OUTRO

**[B-ROLL: Final wide shot of the desk — arm, Mac Mini, completed drawings pinned up or laid out.]**

*[Cut to talking head]*

Alright. That's Robot Ross.

A silly idea that took longer than it should have, broke in ways I didn't expect, and produced something I genuinely couldn't have built alone this fast.

The AI tools make you faster. They don't make the hard parts disappear. But they lower the bar for what a solo maker can attempt — and that changes everything.

If you want to see more of this — subscribe. Drop a comment with what you'd want Robot Ross to draw next. I'll pick some and draw them on camera.

And if you want more from me — I write about tech, AI, and building things on **LinkedIn** — link below. I'm also writing a **sci-fi novel** chapter by chapter on **Substack** — link below. And I make **AI-generated music** — [PLATFORM + LINK] — that one's a whole other story.

*(small smile)*

Thanks for watching. And remember —

There are no mistakes. Only happy little accidents.

**[B-ROLL: The arm's pen lifting off paper. Final drawing revealed.]*

*(Fade to black.)*

---

## PRODUCTION NOTES

**Target spoken length:** ~7-8 minutes

**B-ROLL checklist:**
- [ ] Robot arm drawing — close-up and wide
- [ ] Overhead shot of full desk setup (arm + Mac Mini + display/eyes)
- [ ] Arm eyes / screen display (for Section 7)
- [ ] Telegram app on phone — sending trigger message
- [ ] Mountain SVG time-lapse (14 min compressed to ~30-60 sec)
- [ ] Completed drawings as hero shots
- [ ] Claude Code / terminal screen recording
- [ ] Log file — especially the SUBPROCESS ERROR line
- [ ] Quick montage for "who I am" section: LinkedIn, Substack, music

**Placeholders to fill in:**
- `[PLATFORM + LINK]` — where is the AI music hosted?
- Substack URL / novel title
- LinkedIn URL

**Audio:**
- Use actual Kokoro voice clips as voice-over during B-roll
- Warning beeps as a transition sound

---
*Script — Robot Ross build video — Miguel Rodriguez, 2026*
