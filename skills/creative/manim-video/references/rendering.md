# Rendering Reference

## Prerequisites

```bash
manim --version       # Manim CE
pdflatex --version    # LaTeX
ffmpeg -version       # ffmpeg
```

## CLI Reference

```bash
manim -ql script.py Scene1 Scene2    # draft (480p 15fps)
manim -qm script.py Scene1           # medium (720p 30fps)
manim -qh script.py Scene1           # production (1080p 60fps)
manim -ql --format=png -s script.py Scene1  # preview still (last frame)
manim -ql --format=gif script.py Scene1     # GIF output
```

## Quality Presets

| Flag | Resolution | FPS | Use case |
|------|-----------|-----|----------|
| `-ql` | 854x480 | 15 | Draft iteration (layout, timing) |
| `-qm` | 1280x720 | 30 | Preview (use for text-heavy scenes) |
| `-qh` | 1920x1080 | 60 | Production |

**Text rendering quality:** `-ql` (480p15) produces noticeably poor text kerning and readability. For scenes with significant text, preview stills at `-qm` to catch issues invisible at 480p. Use `-ql` only for testing layout and animation timing.

## Output Structure

```
media/videos/script/480p15/Scene1_Intro.mp4
media/images/script/Scene1_Intro.png  (from -s flag)
```

## Stitching with ffmpeg

```bash
cat > concat.txt << 'EOF'
file 'media/videos/script/480p15/Scene1_Intro.mp4'
file 'media/videos/script/480p15/Scene2_Core.mp4'
EOF
ffmpeg -y -f concat -safe 0 -i concat.txt -c copy final.mp4
```

## Add Voiceover

For narrated explainers, muxing happens after rendering, but narration planning does not: lock the final voice track and derive the shared subtitle/visual timeline **before** final scene timing. These examples assume that exact approved audio file; do not generate or replace narration after alignment without rebuilding dependent timing and re-rendering.

```bash
# Build/lock multi-part narration before aligning and timing scenes
cat > audio_concat.txt << 'EOF'
file 'audio/scene1.mp3'
file 'audio/scene2.mp3'
EOF
ffmpeg -y -f concat -safe 0 -i audio_concat.txt -c copy full_narration.mp3

# After rendering to the shared timeline, mux that exact locked narration
ffmpeg -y -i final.mp4 -i full_narration.mp3 -c:v copy -c:a aac -b:a 192k -shortest final_narrated.mp4
```

The `-shortest` mux option can truncate narration if scene timing is short. Confirm the rendered picture covers the complete locked voice track; never silently cut or speed up speech to make durations match. Re-time/re-render visuals and re-check the alignment instead.

## Add Background Music

```bash
ffmpeg -y -i final.mp4 -i music.mp3 \
  -filter_complex "[1:a]volume=0.15[bg];[0:a][bg]amix=inputs=2:duration=shortest" \
  -c:v copy final_with_music.mp4
```

## GIF Export

```bash
ffmpeg -y -i scene.mp4 \
  -vf "fps=15,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
  output.gif
```

## Aspect Ratios

```bash
manim -ql --resolution 1080,1920 script.py Scene  # 9:16 vertical
manim -ql --resolution 1080,1080 script.py Scene  # 1:1 square
```

## Render Workflow

For a narrated explainer, lock narration and derive its alignment/timeline before finalizing scene durations or event timing. Then:

1. Draft render scenes at `-ql`, following the shared final-audio timeline.
2. Preview stills at key moments (`-s`), including subtitle-safe placement.
3. Fix and re-render broken scenes; if voice changes, rebuild alignment first.
4. Production render at `-qh` and stitch with ffmpeg.
5. Mux the exact locked voice track and reviewed SRT; preserve the master duration.
6. Review the complete cut at normal speed for voice/subtitle/visual sync and repair/re-render any failure.

## manim.cfg — Project Configuration

Create `manim.cfg` in the project directory for per-project defaults:

```ini
[CLI]
quality = low_quality
preview = True
media_dir = ./media

[renderer]
background_color = #0D1117

[tex]
tex_template_file = custom_template.tex
```

This eliminates repetitive CLI flags and `self.camera.background_color` in every scene.

## Sections — Chapter Markers

Mark sections within a scene for organized output:

```python
class LongVideo(Scene):
    def construct(self):
        self.next_section("Introduction")
        # ... intro content ...

        self.next_section("Main Concept")
        # ... main content ...

        self.next_section("Conclusion")
        # ... closing ...
```

Render individual sections: `manim --save_sections script.py LongVideo`
This outputs separate video files per section — useful for long videos where you want to re-render only one part.

## manim-voiceover Plugin (Optional timing aid for Narrated Videos)

The official `manim-voiceover` plugin can schedule scene animations from voiceover duration and bookmarks. For a narrated explainer, first generate and lock the approved voice audio, transcribe/force-align that exact file, and then render against the same cached/consumed audio. Do not let final rendering silently generate a replacement voice track: any audio change invalidates the subtitle and visual timeline.

### Installation

```bash
pip install "manim-voiceover[elevenlabs]"
# Or for free/local TTS:
pip install "manim-voiceover[gtts]"    # Google TTS (free, lower quality)
pip install "manim-voiceover[azure]"   # Azure Cognitive Services
```

### Usage

The following is a timing-integration example, not permission to change narration during final rendering. If the service creates audio on its first run, perform that voice-only/preflight pass first, lock the exact output, review its alignment, and ensure final scene renders reuse it unchanged.

```python
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.elevenlabs import ElevenLabsService

class NarratedScene(VoiceoverScene):
    def construct(self):
        self.set_speech_service(ElevenLabsService(
            voice_name="Alice",
            model_id="eleven_multilingual_v2"
        ))

        # Use the exact cached audio from the approved/locked voice pass.
        # The tracker can schedule motion; separate final-audio alignment drives captions and beats.
        with self.voiceover(text="Here is a circle being drawn.") as tracker:
            self.play(Create(Circle()), run_time=tracker.duration)

        with self.voiceover(text="Now let's transform it into a square.") as tracker:
            self.play(Transform(circle, Square()), run_time=tracker.duration)
```

### Key Features

- `tracker.duration` — total voiceover duration in seconds
- `tracker.time_until_bookmark("mark1")` — sync specific animations to spoken anchors
- Can generate subtitle `.srt` files from the narration script
- Caches audio locally — re-renders don't re-generate TTS
- Works with: ElevenLabs, Azure, Google TTS, pyttsx3 (offline), and custom services

Treat generated captions as a draft unless they have been verified against the actual final audio. For narrated production, transcribe/force-align the final synthesized audio and use those word/phrase timestamps as the source of truth for subtitle and visual timing; script text or bookmarks alone do not replace that check.

### Bookmarks for Precise Sync

```python
with self.voiceover(text='This is a <bookmark mark="circle"/>circle.') as tracker:
    self.wait_until_bookmark("circle")
    self.play(Create(Circle()), run_time=tracker.time_until_bookmark("circle", limit=1))
```

Use the plugin as an optional timing aid, not as a source of truth for subtitle wording or forced alignment. The manual ffmpeg workflow remains appropriate for muxing the exact locked voice track, adding background music, or post-production mixing.
