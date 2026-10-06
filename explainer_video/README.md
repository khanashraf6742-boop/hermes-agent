# Hermes Agent — Detailed Explainer Video (Indian-accent, batched)

Full video: `final/hermes_explainer_FULL.mp4` — **5:19, 1920x1080, 30fps, H.264 + AAC**,
Indian-English voiceover, burned subtitles + sidecar SRT, 15 slides (tables,
comparative tables, flowcharts, code cards).

## Batches (rendered to avoid overload — 6 standalone MP4s + 1 full cut)

| Batch | Title | Duration | Slides | MP4 |
|---|---|---|---|---|
| B1 | What is Hermes Agent? | 0:50 | S01 title, S02 glance table, S03 any-model bullets | `final/hermes_explainer_B1.mp4` |
| B2 | Architecture: three layers | 1:00 | S04 architecture flowchart, S05 runtime table, S06 state table | `final/hermes_explainer_B2.mp4` |
| B3 | The closed learning loop | 0:58 | S07 loop flowchart, S08 memory-vs-skills comparative table | `final/hermes_explainer_B3.mp4` |
| B4 | Lives anywhere, runs anywhere | 0:49 | S09 platforms table, S10 7-backends comparative table | `final/hermes_explainer_B4.mp4` |
| B5 | Delegation, automation, research | 0:51 | S11 delegation flowchart, S12 automations table | `final/hermes_explainer_B5.mp4` |
| B6 | Install + quickstart + closing | 0:51 | S13 install code card, S14 commands table, S15 closing | `final/hermes_explainer_B6.mp4` |

Sidecars: `final/hermes_explainer_FULL.srt` (64 cues), `final/thumbnail.png`,
per-batch `subs/batch_B*.srt`.

## Pipeline (all in-repo, reproducible)

1. **RAG grounding** — `rag_ingest.py`: chunks README/SOUL/AGENTS/COMPAT/CONTRIBUTING +
   curated FACTS into 98 chunks, TF-IDF retrieval per batch →
   `evidence/evidence_B*.json`, `evidence/EVIDENCE_INDEX.md`; claim check **20/20 grounded**.
2. **Voiceover** — 6 batches, en-IN voice (`voice-00`), every batch < 1500 chars →
   `audio/batch_B*.mp3`.
3. **Rendering engine** — `render_engine.py` (PIL, 1920x1080, navy `#0B1020` + gold
   `#FFD700`, DejaVu): kinds `title/table/bullets/flow/code/closing`; spec in
   `script/slides_spec.json` → `visuals/S01..S15.png`.
4. **ASR-sync engine** — `asr_sync.py`: real MP3 durations (mutagen) → proportional
   sub-sentence timing → VAD snap-to-silence via ffmpeg `silencedetect`
   (102 silences used) → `subs/batch_B*.srt` + `subs/segments_B*.json`.
   Slide cuts and cues share one clock — sync is exact by construction.
5. **Assembler** — `assemble.py` (static ffmpeg 7.0.2, libx264 + libass): per-cue slide
   segments → batch concat → audio mux (0.7s lead-in) → fades → burned subtitles
   (PlayRes 1920x1080) → full concat + offset master SRT.

## Rebuild

```bash
pip install pillow numpy mutagen imageio imageio-ffmpeg
python3 explainer_video/rag_ingest.py
python3 explainer_video/render_engine.py
python3 explainer_video/asr_sync.py
python3 explainer_video/assemble.py
```

## Sync verification

- Batch video durations match audio-derived targets within **±0.03s**.
- 64/64 cues inside audio ranges; frame-spot-checks passed (table + code + flowchart
  slides with correct narration-matched subtitles).
- Streams verified: H.264 High yuv420p + AAC 44.1kHz stereo, `+faststart`.
