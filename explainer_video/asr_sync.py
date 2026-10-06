#!/usr/bin/env python3
"""ASR-sync engine: sentence/sub-sentence timing from real audio duration,
VAD snap-to-silence via ffmpeg silencedetect, SRT + segment manifests.

Usage: python3 asr_sync.py  (run from repo root)
"""
import json, os, re, subprocess

from mutagen.mp3 import MP3
import imageio_ffmpeg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "explainer_video", "script", "script_batches.json")
ADIR = os.path.join(ROOT, "explainer_video", "audio")
SDIR = os.path.join(ROOT, "explainer_video", "subs")
FF = imageio_ffmpeg.get_ffmpeg_exe()

HEAD, TAIL = 0.7, 0.8  # lead-in / lead-out seconds per batch


def split_subs(s):
    parts = re.split(r"(?<=[.!?])\s+", s.strip())
    return [p.strip() for p in parts if p.strip()]


def srt_time(t):
    t = max(0, t)
    h, rem = divmod(t, 3600)
    m, rem = divmod(rem, 60)
    s = int(rem)
    ms = int(round((rem - s) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{int(h):02d}:{int(m):02d}:{s:02d},{ms:03d}"


def wrap_cue(text, width=44):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if len(t) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    # rebalance to max 2 even lines
    if len(lines) > 2:
        words = text.split()
        best, bi = None, 0
        for i in range(1, len(words)):
            l1, l2 = " ".join(words[:i]), " ".join(words[i:])
            score = abs(len(l1) - len(l2)) + max(0, len(l1) - 46) * 4 + max(0, len(l2) - 46) * 4
            if best is None or score < best:
                best, bi = score, i
        return " ".join(words[:bi]) + "\n" + " ".join(words[bi:])
    return "\n".join(lines)


def detect_silences(mp3):
    """Return [(start,end),...] of silences via ffmpeg silencedetect."""
    cmd = [FF, "-hide_banner", "-i", mp3, "-af",
           "silencedetect=noise=-38dB:d=0.25", "-f", "null", "-"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    starts, sil = [], []
    for line in p.stderr.splitlines():
        m1 = re.search(r"silence_start:\s*([\d.]+)", line)
        m2 = re.search(r"silence_end:\s*([\d.]+)", line)
        if m1:
            starts.append(float(m1.group(1)))
        if m2 and starts:
            sil.append((starts.pop(-1), float(m2.group(1))))
    return sil


def main():
    os.makedirs(SDIR, exist_ok=True)
    batches = json.load(open(SCRIPT, encoding="utf-8"))["batches"]
    manifest = {}
    for b in batches:
        mp3 = os.path.join(ADIR, f"batch_{b['id']}.mp3")
        dur = MP3(mp3).info.length
        total = HEAD + dur + TAIL
        # sub-sentence units inherit parent slide
        units = []
        for si, sent in enumerate(b["sentences"]):
            for sub in split_subs(sent):
                units.append({"text": sub, "slide": b["slides"][b["sent_slide"][si]]})
        weights = [max(len(u["text"]), 10) for u in units]
        tot = sum(weights)
        # raw boundaries over [HEAD, HEAD+dur]
        bounds = [HEAD]
        acc = HEAD
        for w_ in weights[:-1]:
            acc += dur * w_ / tot
            bounds.append(acc)
        bounds.append(HEAD + dur)
        # VAD snap internal boundaries to silence midpoints
        try:
            sil = [(s + HEAD, e + HEAD) for s, e in detect_silences(mp3)]
        except Exception as e:
            print(f"  {b['id']}: VAD unavailable ({e}), using proportional timing")
            sil = []
        snapped = [bounds[0]]
        for x in bounds[1:-1]:
            best, bd = x, 0.9
            for s, e in sil:
                mid = (s + e) / 2
                if abs(mid - x) < bd:
                    best, bd = mid, abs(mid - x)
            snapped.append(best)
        snapped.append(bounds[-1])
        snapped = sorted(snapped)
        # min cue length 0.5s
        for i in range(1, len(snapped) - 1):
            if snapped[i] - snapped[i - 1] < 0.5:
                snapped[i] = snapped[i - 1] + 0.5
        # build cues + segments
        cues, segs = [], []
        for i, u in enumerate(units):
            st, en = round(snapped[i], 3), round(snapped[i + 1], 3)
            cues.append({"i": i + 1, "start": st, "end": en, "text": u["text"]})
            segs.append({"cue": i + 1, "slide": u["slide"], "start": st, "end": en,
                         "dur": round(en - st, 3)})
        # SRT
        with open(os.path.join(SDIR, f"batch_{b['id']}.srt"), "w", encoding="utf-8") as f:
            for c in cues:
                f.write(f"{c['i']}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n"
                        f"{wrap_cue(c['text'])}\n\n")
        with open(os.path.join(SDIR, f"segments_{b['id']}.json"), "w", encoding="utf-8") as f:
            json.dump({"batch": b["id"], "audio": mp3, "audio_dur": round(dur, 3),
                       "total": round(total, 3), "head": HEAD, "tail": TAIL,
                       "units": len(units), "segments": segs}, f, indent=1)
        manifest[b["id"]] = {"total": round(total, 3), "cues": len(cues)}
        print(f"  {b['id']}: audio {dur:.2f}s -> video {total:.2f}s, {len(cues)} cues, "
              f"{len(sil)} silences used")
    json.dump(manifest, open(os.path.join(SDIR, "manifest.json"), "w"), indent=1)
    print(f"SYNC OK: {len(batches)} batches -> {SDIR}/")


if __name__ == "__main__":
    main()
