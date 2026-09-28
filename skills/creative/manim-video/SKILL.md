---
name: manim-video
description: "Manim CE animations: 3Blue1Brown math/algo videos."
version: 1.0.0
author: SHL0MS, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Manim, Animation, Math, Video]
    related_skills: []
---

# Manim Video Production Pipeline

## When to use

Use when users request: animated explanations, math animations, concept visualizations, algorithm walkthroughs, technical explainers, 3Blue1Brown style videos, or any programmatic animation with geometric/mathematical content. Creates 3Blue1Brown-style explainer videos, algorithm visualizations, equation derivations, architecture diagrams, and data stories using Manim Community Edition.

## Creative Standard

This is educational cinema. Every frame teaches. Every animation reveals structure.

**Before writing a single line of code**, articulate the narrative arc. What misconception does this correct? What is the "aha moment"? What visual story takes the viewer from confusion to understanding? The user's prompt is a starting point — interpret it with pedagogical ambition.

**Geometry before algebra.** Show the shape first, the equation second. Visual memory encodes faster than symbolic memory. When the viewer sees the geometric pattern before the formula, the equation feels earned.

**First-render excellence is non-negotiable.** The output must be visually clear and aesthetically cohesive without revision rounds. If something looks cluttered, poorly timed, or like "AI-generated slides," it is wrong.

**Opacity layering directs attention.** Use salience to separate currently taught elements from already-introduced context—for example, primary elements at 1.0, contextual elements at 0.4, structural elements (axes, grids) at 0.15. Never use low opacity to preview an unexplained answer or future teaching content.

**Breathing room.** Every animation needs `self.wait()` after it. The viewer needs time to absorb what just appeared. Never rush from one animation to the next. A 2-second pause after a key reveal is never wasted.

**Cohesive visual language.** All scenes share a color palette, consistent typography sizing, matching animation speeds. A technically correct video where every scene uses random different colors is an aesthetic failure.

## Prerequisites

Run `scripts/setup.sh` to verify all dependencies. Requires: Python 3.10+, Manim Community Edition v0.20+ (`pip install manim`), LaTeX (`texlive-full` on Linux, `mactex` on macOS), and ffmpeg. Reference docs tested against Manim CE v0.20.1.

## Modes

| Mode | Input | Output | Reference |
|------|-------|--------|-----------|
| **Concept explainer** | Topic/concept | Animated explanation with geometric intuition | `references/scene-planning.md` |
| **Equation derivation** | Math expressions | Step-by-step animated proof | `references/equations.md` |
| **Algorithm visualization** | Algorithm description | Step-by-step execution with data structures | `references/graphs-and-data.md` |
| **Data story** | Data/metrics | Animated charts, comparisons, counters | `references/graphs-and-data.md` |
| **Architecture diagram** | System description | Components building up with connections | `references/mobjects.md` |
| **Paper explainer** | Research paper | Key findings and methods animated | `references/scene-planning.md` |
| **3D visualization** | 3D concept | Rotating surfaces, parametric curves, spatial geometry | `references/camera-and-3d.md` |

## Stack

Single Python script per project. No browser, no Node.js, no GPU required.

| Layer | Tool | Purpose |
|-------|------|---------|
| Core | Manim Community Edition | Scene rendering, animation engine |
| Math | LaTeX (texlive/MiKTeX) | Equation rendering via `MathTex` |
| Video I/O | ffmpeg | Scene stitching, format conversion, audio muxing |
| TTS | ElevenLabs / Qwen3-TTS (optional) | Narration voiceover |
| ASR / forced alignment | Available transcription/alignment tooling | Word/phrase timings from final voice audio |

## Pipeline

For narrated educational videos, the final voice track is locked before subtitle or animation timing is finalized:

```
SOURCE / COVERAGE → SCRIPT → FINAL VOICE AUDIO → TRANSCRIPTION / ALIGNMENT
→ MASTER TIMELINE → SUBTITLES + WHITEBOARD / ANIMATION → RENDER / STITCH → THREE-LAYER QA
```

For silent videos, use the same visual-planning and render/review stages without the audio-alignment steps. See **33A. Three-Layer Synchronization** for the mandatory narrated-video contract.

1. **PLAN** — Write `plan.md` with source coverage, narrative arc, scene list, visual beats, color palette, and narration script. For source-based explainers, account for each material teaching point before batching it into scenes.
2. **LOCK VOICE** (when narrated) — Generate or record the final approved narration before final visual timing. Preserve the exact final audio as the timing master.
3. **ALIGN** (when narrated) — Transcribe and word/phrase-align the final audio where tooling permits. Correct transcript errors against the audio, then build the shared timeline for subtitles and visual events.
4. **CODE** — Write `script.py` with one class per scene, each independently renderable. Drive caption cues, reveals, and highlights from the shared audio-derived timeline; do not guess their times independently.
5. **RENDER / STITCH** — Render the scenes, stitch them into `final.mp4`, then mux the locked audio and aligned subtitle track as needed. See `references/rendering.md`.
6. **REVIEW** — Review the complete video at normal speed and audit voice, subtitle, whiteboard/animation, and highlights together. Repair and re-render any mismatch.

## 33A. THREE-LAYER SYNCHRONIZATION — NON-NEGOTIABLE

### VOICE + SUBTITLES + WHITEBOARD MUST WORK AS ONE SYSTEM

For every narrated educational or technical video, treat the voice, subtitles, and visual explanation (whiteboard, diagram, or animated canvas) as one production system—not separate deliverables. They must remain semantically, temporally, and visually coherent throughout the entire video. The learner must never hear one concept while reading another and seeing a third unrelated concept.

The **final voice track is the master timing reference**. Subtitles and visual events are derived from its actual timing, not independently estimated from the source or script.

### 33A.1 MASTER SYNCHRONIZATION PRINCIPLE

> **ONE IDEA → ONE MOMENT → THREE ALIGNED CHANNELS**

For every important teaching point:

1. **Voice** explains it.
2. **Subtitle** displays the corresponding spoken content.
3. **Whiteboard / animated canvas** demonstrates the same concept.

Subtitle wording must follow the final-audio transcript; concise whiteboard labels may use natural graphical notation only when they preserve the spoken meaning and timing.

Example:

**Voice:** “The maximum period is 300 days.”

**Subtitle:** “The maximum period is 300 days.”

**Whiteboard:**

```text
┌──────────────────────┐
│   MAXIMUM PERIOD     │
│                      │
│      300 DAYS        │
└──────────────────────┘
```

The number **300 DAYS** appears or receives emphasis when it is spoken.

### 33A.2 SUBTITLES MUST FOLLOW THE ACTUAL VOICE

Do not create subtitles from the source or pre-TTS script independently. Do not manually guess subtitle timestamps. Use this pipeline for narrated work:

```text
FINAL TTS / RECORDED AUDIO (locked)
    ↓
TRANSCRIPTION + FORCED ALIGNMENT against that audio
    ↓
WORD / PHRASE / SENTENCE TIMESTAMPS + PAUSES
    ↓
SUBTITLE SEGMENTATION
    ↓
WHITEBOARD / ANIMATION EVENTS MAPPED TO THE SAME TIMELINE
    ↓
FINAL VIDEO + THREE-LAYER QA
```

Use the final audio waveform as the timing authority. Correct transcription errors against the audio, then preserve its actual word and phrase timings. If the voice track changes, regenerate or re-check the transcript, alignment, subtitles, and dependent visual timings before rendering again.

### 33A.3 WORD- AND PHRASE-LEVEL SYNCHRONIZATION

Where the available tooling supports it, obtain word timestamps, phrase timestamps, sentence timestamps, and pause locations. Use them to coordinate subtitle changes and the drawing, highlighting, arrows, numbers, Rule references, table rows, and flowchart branches. When exact word alignment is unavailable, align at the finest reliable phrase or sentence level from the final audio—never fabricate precision.

Example:

```text
VOICE:     “Rule 39-A provides for...”
SUBTITLE:  “Rule 39-A provides for...”
WHITEBOARD:
           Rule 39-A
               ↓
           [Main provision]
```

Progress all three layers together.

### 33A.4 DO NOT LET SUBTITLES LEAD TOO FAR AHEAD

Subtitles must not reveal a complete explanation substantially before the teacher speaks it. Avoid showing later conditions, conclusions, or exceptions while the narration is still introducing the topic. Reveal only the current spoken thought, progressively.

Prefer:

```text
VOICE:     “First, let’s understand the basic rule.”
SUBTITLE:  “First, let’s understand the basic rule.”
WHITEBOARD: [Basic Rule]
```

Then reveal the next information when the narration reaches it.

### 33A.5 DO NOT LET SUBTITLES LAG BEHIND

A subtitle must not remain after its spoken idea has finished or continue to show the previous sentence while the voice moves on. Change or remove it naturally at the aligned phrase boundary; do not keep stale text on screen for convenience.

### 33A.6 SUBTITLE SEGMENTATION

Do not use enormous subtitle paragraphs. Break narration into short, meaningful, comfortably readable chunks while preserving the exact spoken meaning and all substantive information. Do not arbitrarily paraphrase technically precise narration or omit qualifiers to shorten a cue.

Prefer:

> The maximum period<br />
> is 300 days.

rather than forcing an unnecessarily long sentence into one fast-reading caption. If the spoken explanation is long, segment it across the actual speech; do not display the full paragraph early.

### 33A.7 READABILITY RULE

Subtitles must be large enough to read, high contrast, clean, uncluttered, appropriately positioned, synchronized, and free from unnecessary decoration. Optimize for comfortable reading at the final delivery resolution and playback size.

### 33A.8 SUBTITLE POSITIONING

Default to the lower portion of the frame, but dynamically avoid covering critical whiteboard content. If that region contains a table, formula, flowchart, important Rule text, diagram, or calculation, move the subtitle to a clear safe area. Never obscure the key teaching visual to preserve a fixed caption position.

### 33A.9 WHITEBOARD-SAFE SUBTITLE AREA

Plan a subtitle-safe region in the composition. It should integrate naturally with the whiteboard aesthetic; do not add a visually obvious, permanent “subtitle box” that makes the video look like a conventional presentation. Reposition the actual subtitle when the visual layout needs the reserved area.

### 33A.10 HIGHLIGHTING KEY WORDS

Emphasize only genuinely important spoken elements, such as **Rule 39-A**, **300 DAYS**, **WITHIN 30 DAYS**, **EXCEPTION**, **SHALL**, **MAY**, or **ELIGIBLE**. Each highlight must correspond to the moment that word or concept is spoken. Do not highlight everything.

### 33A.11 WHITEBOARD MUST NOT RACE AHEAD OF THE NARRATION

Never draw or display the complete answer before the teacher has explained it. Reveal conditions, rows, branches, labels, and conclusions progressively at their corresponding spoken beats. For example, when the narration says “There are three conditions,” do not show all three conditions several seconds before they are explained.

### 33A.12 WHITEBOARD MAY ANTICIPATE SLIGHTLY ONLY WHEN PEDAGOGICALLY NECESSARY

A visual may appear a small amount before its exact verbal explanation only when this genuinely improves comprehension. The anticipation must function as an orientation cue, not a spoiler. Do not reveal the answer prematurely, and do not let the visual get materially ahead of the narration.

### 33A.13 SYNCHRONIZED REVEAL SYSTEM

For important concepts, coordinate the reveal as one teaching rhythm:

1. **VOICE** introduces the concept.
2. **SUBTITLE** displays the corresponding spoken phrase.
3. **HAND / ANIMATION** begins drawing.
4. **WHITEBOARD** builds the concept.
5. **HIGHLIGHT** emphasizes the key element at its spoken anchor.

### 33A.14 EXAMPLE — FLOWCHART SYNCHRONIZATION

Voice:

> “First, check whether the condition is satisfied.”

Subtitle:

> “First, check whether the condition is satisfied.”

Whiteboard:

```text
       ┌───────────────┐
       │   CONDITION   │
       └───────────────┘
```

Then, when the voice says “If the condition is satisfied, move to the next step,” show that spoken sentence in the subtitle and draw the branch and arrow at that moment. The whiteboard may use the concise label **YES → NEXT STEP**:

```text
       CONDITION
          │
       YES ↓
     NEXT STEP
```

### 33A.15 EXAMPLE — COMPARISON TABLE SYNCHRONIZATION

When the voice says “Now compare the two situations,” show that full phrase in the subtitle and introduce the table headings. When it says “The first difference is the applicable authority,” keep the matching spoken phrase in the subtitle and reveal or highlight only the first row. When it says “The second difference is the time limit,” align that phrase and reveal the second row. Do not display later rows before they are taught.

```text
┌──────────────┬──────────────┐
│ Situation A  │ Situation B  │
└──────────────┴──────────────┘
```

### 33A.16 EXAMPLE — NUMERICAL LIMIT

- **Voice:** “The maximum period is 300 days.”
- **Subtitle:** “The maximum period is 300 days.”
- **Whiteboard:**

```text
MAXIMUM
   ↓
300 DAYS
```

At the words **“300 days,”** the number receives the primary visual emphasis.

### 33A.17 SUBTITLE TEXT MUST NOT CONFLICT WITH THE WHITEBOARD

Any disagreement among the voice, subtitle, and whiteboard about a key fact, number, Rule reference, condition, or exception is an **AUTOMATIC FATAL QA ERROR**. For example, if the voice says “300 days” while the subtitle says “180 days,” do not render or deliver the video until the conflict is corrected and all affected layers are re-checked.

### 33A.18 TERMINOLOGY CONSISTENCY

Use consistent terminology across the source, narration, subtitles, whiteboard, storyboard, and coverage matrix. If the source says “earned leave,” do not switch randomly to “annual leave,” “EL,” or “vacation leave.” A deliberate plain-language explanation is fine when it is clearly introduced and does not alter the technical meaning.

### 33A.19 RULE NUMBERS MUST MATCH EVERYWHERE

If the narration says **Rule 39-A**, the subtitle and whiteboard must also say **Rule 39-A**. Any storyboard or coverage-matrix entry must match too. Check all numbers and references against the source; inconsistent references are not permitted.

### 33A.20 SUBTITLE QUALITY CONTROL

For every subtitle segment verify:

- [ ] Exact synchronization with the final voice audio
- [ ] Correct wording and spoken meaning
- [ ] Correct Rule references and numbers
- [ ] Consistent terminology
- [ ] No missing qualifiers or unintended paraphrasing
- [ ] No spelling errors
- [ ] Readable line length and reading speed
- [ ] No overlap with important whiteboard content
- [ ] Appropriate display duration and phrase boundaries

### 33A.21 READING SPEED

Do not prioritize fitting more text over comfortable reading. If narration is too dense for subtitles, do not display an entire paragraph faster. Instead, improve TTS sentence segmentation before locking the voice, create shorter meaningful subtitle segments, preserve the complete spoken information, and provide adequate reading time. Never remove substantive content solely to make subtitles shorter.

### 33A.22 THREE-LAYER QA

Before final rendering, compare all three layers for every important teaching unit:

1. **Voice:** What is actually being said?
2. **Subtitle:** What is the learner reading?
3. **Whiteboard:** What is the learner seeing?

> **VOICE = SUBTITLE = VISUAL MEANING**

The wording need not be identical when the whiteboard represents the idea graphically, but the meaning and timing must align.

### 33A.23 FINAL SYNCHRONIZATION AUDIT

For every scene, verify the progression:

```text
VOICE
  ↓
SUBTITLE
  ↓
WHITEBOARD
  ↓
HIGHLIGHT
  ↓
NEXT CONCEPT
```

Ask whether the learner hears the correct concept, reads its corresponding spoken content, sees a visual that explains the same concept, and receives each visual at the appropriate moment. Confirm that subtitles remain readable, the frame stays uncluttered, and the next concept begins only after the current one is established. If any answer is no, **fail the scene → repair → re-render**.

### 33A.24 MASTER TIMELINE

Maintain one master timeline derived from the final audio. All subtitle cues, whiteboard drawing events, highlights, and transitions must use it. The times below illustrate the structure; production timings must come from the actual audio alignment:

```text
TIME
│
├── 00:00 Voice begins
│       ├── Subtitle appears
│       └── Whiteboard title appears
│
├── 00:04 Key term spoken
│       ├── Subtitle updates
│       └── Key term is drawn
│
├── 00:08 Condition explained
│       ├── Subtitle updates
│       └── Flowchart branch is drawn
│
├── 00:15 Exception spoken
│       ├── Subtitle updates
│       └── Exception branch appears
│
└── 00:22 Transition to next concept
        ├── Subtitle changes
        ├── Camera pans
        ├── Hand moves
        └── Next concept begins
```

### 33A.25 FINAL PRODUCTION PRINCIPLE

The finished video must feel as though:

> **The teacher is speaking, the subtitles are faithfully following the teacher, and the teacher’s hand is simultaneously building the explanation on one continuous whiteboard.**

Not:

> **Voice + unrelated captions + unrelated animation.**

The learner should be able to **HEAR IT + READ IT + SEE IT** at the same moment. That three-channel coherence is mandatory.

For narrated work, the production architecture is:

```text
SOURCE
→ ATOMIC COVERAGE
→ BATCHING
→ TTS
→ WORD / PHRASE TIMESTAMPS
→ SUBTITLES
→ CONTINUOUS WHITEBOARD / ANIMATED CANVAS
→ SYNCHRONIZED HIGHLIGHTS
→ FINAL VIDEO
→ THREE-LAYER QA
```

The actual final TTS audio is the master clock: derive subtitle and whiteboard timing from it, never time those layers independently.

## Project Structure

```
project-name/
  plan.md                # Narrative arc, scene breakdown
  script.py              # All scenes in one file
  concat.txt             # ffmpeg scene list
  final.mp4              # Stitched output
  media/                 # Auto-generated by Manim
    videos/script/480p15/
```

## Creative Direction

### Color Palettes

| Palette | Background | Primary | Secondary | Accent | Use case |
|---------|-----------|---------|-----------|--------|----------|
| **Classic 3B1B** | `#1C1C1C` | `#58C4DD` (BLUE) | `#83C167` (GREEN) | `#FFFF00` (YELLOW) | General math/CS |
| **Warm academic** | `#2D2B55` | `#FF6B6B` | `#FFD93D` | `#6BCB77` | Approachable |
| **Neon tech** | `#0A0A0A` | `#00F5FF` | `#FF00FF` | `#39FF14` | Systems, architecture |
| **Monochrome** | `#1A1A2E` | `#EAEAEA` | `#888888` | `#FFFFFF` | Minimalist |

### Animation Speed

| Context | run_time | self.wait() after |
|---------|----------|-------------------|
| Title/intro appear | 1.5s | 1.0s |
| Key equation reveal | 2.0s | 2.0s |
| Transform/morph | 1.5s | 1.5s |
| Supporting label | 0.8s | 0.5s |
| FadeOut cleanup | 0.5s | 0.3s |
| "Aha moment" reveal | 2.5s | 3.0s |

### Typography Scale

| Role | Font size | Usage |
|------|-----------|-------|
| Title | 48 | Scene titles, opening text |
| Heading | 36 | Section headers within a scene |
| Body | 30 | Explanatory text |
| Label | 24 | Annotations, axis labels |
| Caption | 20 | Subtitles, fine print |

### Fonts

**Use monospace fonts for all text.** Manim's Pango renderer produces broken kerning with proportional fonts at all sizes. See `references/visual-design.md` for full recommendations.

```python
MONO = "Menlo"  # define once at top of file

Text("Fourier Series", font_size=48, font=MONO, weight=BOLD)  # titles
Text("n=1: sin(x)", font_size=20, font=MONO)                  # labels
MathTex(r"\nabla L")                                            # math (uses LaTeX)
```

Minimum `font_size=18` for readability.

### Per-Scene Variation

Never use identical config for all scenes. For each scene:
- **Different dominant color** from the palette
- **Different layout** — don't always center everything
- **Different animation entry** — vary between Write, FadeIn, GrowFromCenter, Create
- **Different visual weight** — some scenes dense, others sparse

## Workflow

### Step 1: Plan (plan.md)

Before any code, write `plan.md`. For source-based explainers, identify and account for each material teaching point before batching it into narration and scenes. Include the narrative arc, visual beats, voiceover script, and intended subtitle/visual relationship. See `references/scene-planning.md` for the comprehensive template.

### Step 2: Lock and align narration (narrated videos)

Generate or record the approved narration and lock the final audio before finalizing subtitle or animation timing. Transcribe and word/phrase-align that audio with available ASR/forced-alignment tooling; review the transcript against the audio and create one master timeline. When exact word alignment is unavailable, use the finest reliable phrase or sentence timing available from the final audio. If the audio changes, redo the dependent alignment and timing.

For videos without narration, skip this step and proceed with the visual plan.

### Step 3: Code (script.py)

One class per scene. Every scene is independently renderable. For narrated scenes, use the master timeline to coordinate voice, caption cues, drawing/reveals, and highlights.

```python
from manim import *

BG = "#1C1C1C"
PRIMARY = "#58C4DD"
SECONDARY = "#83C167"
ACCENT = "#FFFF00"
MONO = "Menlo"

class Scene1_Introduction(Scene):
    def construct(self):
        self.camera.background_color = BG
        title = Text("Why Does This Work?", font_size=48, color=PRIMARY, weight=BOLD, font=MONO)
        # API illustration only: in narrated work, cue text and duration come
        # from alignment against the final audio, never a manual estimate.
        self.add_subcaption("Why does this work?", duration=2)
        self.play(Write(title), run_time=1.5)
        self.wait(1.0)
        self.play(FadeOut(title), run_time=0.5)
```

Key patterns:
- **Captions** follow meaningful spoken phrases and are timed from the final-audio alignment; do not guess their timing or derive them independently from source text.
- **Synchronized visuals** reveal the concept at its spoken beat; do not draw the complete answer ahead of the explanation.
- **Shared color constants** at file top for cross-scene consistency
- **`self.camera.background_color`** set in every scene
- **Clean exits** — FadeOut all mobjects at scene end: `self.play(FadeOut(Group(*self.mobjects)))`

### Step 4: Render

```bash
manim -ql script.py Scene1_Introduction Scene2_CoreConcept  # draft
manim -qh script.py Scene1_Introduction Scene2_CoreConcept  # production
```

### Step 5: Stitch

```bash
cat > concat.txt << 'EOF'
file 'media/videos/script/480p15/Scene1_Introduction.mp4'
file 'media/videos/script/480p15/Scene2_CoreConcept.mp4'
EOF
ffmpeg -y -f concat -safe 0 -i concat.txt -c copy final.mp4
```

### Step 6: Review

```bash
manim -ql --format=png -s script.py Scene2_CoreConcept  # preview still
```

Review the complete rendered video at normal speed, not only still frames. Compare the actual audio, subtitles, and whiteboard/animation for every important idea; fix and re-render any wording, timing, number, terminology, or layout conflict.

## Critical Implementation Notes

### Raw Strings for LaTeX
```python
# WRONG: MathTex("\frac{1}{2}")
# RIGHT:
MathTex(r"\frac{1}{2}")
```

### buff >= 0.5 for Edge Text
```python
label.to_edge(DOWN, buff=0.5)  # never < 0.5
```

### FadeOut Before Replacing Text
```python
self.play(ReplacementTransform(note1, note2))  # not Write(note2) on top
```

### Never Animate Non-Added Mobjects
```python
self.play(Create(circle))  # must add first
self.play(circle.animate.set_color(RED))  # then animate
```

## Performance Targets

| Quality | Resolution | FPS | Speed |
|---------|-----------|-----|-------|
| `-ql` (draft) | 854x480 | 15 | 5-15s/scene |
| `-qm` (medium) | 1280x720 | 30 | 15-60s/scene |
| `-qh` (production) | 1920x1080 | 60 | 30-120s/scene |

Always iterate at `-ql`. Only render `-qh` for final output.

## References

| File | Contents |
|------|----------|
| `references/animations.md` | Core animations, rate functions, composition, `.animate` syntax, timing patterns |
| `references/mobjects.md` | Text, shapes, VGroup/Group, positioning, styling, custom mobjects |
| `references/visual-design.md` | 12 design principles, opacity layering, layout templates, color palettes |
| `references/equations.md` | LaTeX in Manim, TransformMatchingTex, derivation patterns |
| `references/graphs-and-data.md` | Axes, plotting, BarChart, animated data, algorithm visualization |
| `references/camera-and-3d.md` | MovingCameraScene, ThreeDScene, 3D surfaces, camera control |
| `references/scene-planning.md` | Narrative arcs, layout templates, scene transitions, planning template |
| `references/rendering.md` | CLI reference, quality presets, ffmpeg, voiceover workflow, GIF export |
| `references/troubleshooting.md` | LaTeX errors, animation errors, common mistakes, debugging |
| `references/animation-design-thinking.md` | When to animate vs show static, decomposition, pacing, narration sync |
| `references/updaters-and-trackers.md` | ValueTracker, add_updater, always_redraw, time-based updaters, patterns |
| `references/paper-explainer.md` | Turning research papers into animations — workflow, templates, domain patterns |
| `references/decorations.md` | SurroundingRectangle, Brace, arrows, DashedLine, Angle, annotation lifecycle |
| `references/production-quality.md` | Pre-code, pre-render, post-render checklists, spatial layout, color, tempo |

---

## Creative Divergence (use only when user requests experimental/creative/unique output)

If the user asks for creative, experimental, or unconventional explanatory approaches, select a strategy and reason through it BEFORE designing the animation.

- **SCAMPER** — when the user wants a fresh take on a standard explanation
- **Assumption Reversal** — when the user wants to challenge how something is typically taught

### SCAMPER Transformation
Take a standard mathematical/technical visualization and transform it:
- **Substitute**: replace the standard visual metaphor (number line → winding path, matrix → city grid)
- **Combine**: merge two explanation approaches (algebraic + geometric simultaneously)
- **Reverse**: derive backward — start from the result and deconstruct to axioms
- **Modify**: exaggerate a parameter to show why it matters (10x the learning rate, 1000x the sample size)
- **Eliminate**: remove all notation — explain purely through animation and spatial relationships

### Assumption Reversal
1. List what's "standard" about how this topic is visualized (left-to-right, 2D, discrete steps, formal notation)
2. Pick the most fundamental assumption
3. Reverse it (right-to-left derivation, 3D embedding of a 2D concept, continuous morphing instead of steps, zero notation)
4. Explore what the reversal reveals that the standard approach hides
