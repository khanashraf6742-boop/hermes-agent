#!/usr/bin/env python3
"""Assembler: segments -> batch MP4s (slides + audio + burned subs) -> full MP4.

Usage: python3 assemble.py  (run from repo root)
"""
import glob, json, os, re, subprocess

import imageio_ffmpeg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV = os.path.join(ROOT, "explainer_video")
VDIR, SDIR, ADIR, FDIR = (os.path.join(EV, x) for x in ("visuals", "subs", "audio", "final"))
TMP = os.path.join(EV, ".asm_tmp")
FF = imageio_ffmpeg.get_ffmpeg_exe()
FPS = 30


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if p.returncode != 0:
        print("CMD:", " ".join(cmd))
        print(p.stderr[-3000:])
        raise SystemExit("ffmpeg failed")
    return p


def probe_dur(path):
    p = subprocess.run([FF, "-hide_banner", "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", p.stderr)
    h, mnt, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mnt * 60 + s


def build_batch(bid):
    seg = json.load(open(os.path.join(SDIR, f"segments_{bid}.json"), encoding="utf-8"))
    total = seg["total"]
    # 1) per-segment silent clips from slides
    parts = []
    for i, s in enumerate(seg["segments"]):
        img = os.path.join(VDIR, f"{s['slide']}.png")
        out = os.path.join(TMP, f"{bid}_{i:03d}.mp4")
        frames = max(1, round(s["dur"] * FPS))
        run([FF, "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", img,
             "-frames:v", str(frames),
             "-vf", f"scale=1920:1080,format=yuv420p",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
             "-r", str(FPS), out])
        parts.append(out)
    # head/tail stills (first/last slide)
    first_slide = os.path.join(VDIR, f"{seg['segments'][0]['slide']}.png")
    last_slide = os.path.join(VDIR, f"{seg['segments'][-1]['slide']}.png")
    head = os.path.join(TMP, f"{bid}_head.mp4")
    tail = os.path.join(TMP, f"{bid}_tail.mp4")
    for path, img, dd in ((head, first_slide, seg["head"]), (tail, last_slide, seg["tail"])):
        run([FF, "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", img,
             "-frames:v", str(max(1, round(dd * FPS))),
             "-vf", "scale=1920:1080,format=yuv420p",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-r", str(FPS), path])
    # 2) concat: head + segments + tail
    lst = os.path.join(TMP, f"{bid}_list.txt")
    with open(lst, "w") as f:
        for p in [head] + parts + [tail]:
            f.write(f"file '{p}'\n")
    silent = os.path.join(TMP, f"{bid}_silent.mp4")
    run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
         "-c", "copy", silent])
    # 3) mux audio (offset by head) + fades + burned subtitles
    audio = os.path.join(ADIR, f"batch_{bid}.mp3")
    srt = os.path.join(SDIR, f"batch_{bid}.srt")
    out = os.path.join(FDIR, f"hermes_explainer_{bid}.mp4")
    style = ("PlayResX=1920,PlayResY=1080,FontName=DejaVu Sans,FontSize=44,"
             "PrimaryColour=&HFFFFFF&,OutlineColour=&H80000000&,"
             "BackColour=&HCC000000&,BorderStyle=4,"
             "Outline=1,Shadow=0,Alignment=2,MarginV=60")
    srt_esc = srt.replace(":", "\\:").replace("'", "\\'")
    vf = (f"subtitles='{srt_esc}':fontsdir='/usr/share/fonts':force_style='{style}',"
          f"fade=t=in:st=0:d=0.4,fade=t=out:st={total - 0.4:.3f}:d=0.4,format=yuv420p")
    run([FF, "-y", "-v", "error", "-i", silent, "-itsoffset", str(seg["head"]), "-i", audio,
         "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
         "-t", f"{total:.3f}", "-movflags", "+faststart", out])
    got = probe_dur(out)
    print(f"  {bid}: {out}  target={total:.2f}s actual={got:.2f}s")
    return out, got


def main():
    os.makedirs(FDIR, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    batches = json.load(open(os.path.join(EV, "script", "script_batches.json"),
                             encoding="utf-8"))["batches"]
    outs, durs = [], []
    for b in batches:
        o, d = build_batch(b["id"])
        outs.append(o)
        durs.append(d)
    # full concat
    lst = os.path.join(TMP, "full_list.txt")
    with open(lst, "w") as f:
        for p in outs:
            f.write(f"file '{p}'\n")
    full = os.path.join(FDIR, "hermes_explainer_FULL.mp4")
    run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
         "-c", "copy", "-movflags", "+faststart", full])
    # full SRT with offsets
    off, idx, cues = 0.0, 1, []
    for b, d in zip(batches, durs):
        txt = open(os.path.join(SDIR, f"batch_{b['id']}.srt"), encoding="utf-8").read().strip()
        for blk in txt.split("\n\n"):
            lines = blk.splitlines()
            m = re.match(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", lines[1])
            g = list(map(int, m.groups()))
            t1 = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000 + off
            t2 = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000 + off

            def ts(t):
                h, r = divmod(t, 3600)
                mnt, r = divmod(r, 60)
                s = int(r)
                ms = int(round((r - s) * 1000))
                return f"{int(h):02d}:{int(mnt):02d}:{s:02d},{ms:03d}"
            cues.append(f"{idx}\n{ts(t1)} --> {ts(t2)}\n" + "\n".join(lines[2:]))
            idx += 1
        off += d
    open(os.path.join(FDIR, "hermes_explainer_FULL.srt"), "w", encoding="utf-8").write(
        "\n\n".join(cues) + "\n")
    # thumbnail = title slide
    import shutil
    shutil.copy(os.path.join(VDIR, "S01.png"), os.path.join(FDIR, "thumbnail.png"))
    print(f"ASSEMBLE OK: 6 batch MP4s + FULL ({off:.1f}s, {idx - 1} cues) -> {FDIR}/")
    for p in outs + [full]:
        print(f"   {os.path.getsize(p) / 1e6:.1f} MB  {os.path.basename(p)}")


if __name__ == "__main__":
    main()
