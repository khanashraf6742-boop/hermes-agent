#!/usr/bin/env python3
"""Rendering engine: PIL 1920x1080 slides — title, tables, comparative
tables, flowcharts, bullets, code, closing. Hermes navy + gold theme.

Usage: python3 render_engine.py  (run from repo root)
"""
import json, os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "explainer_video", "script", "slides_spec.json")
OUT = os.path.join(ROOT, "explainer_video", "visuals")

W, H = 1920, 1080
M = 90  # side margin

FD = "/usr/share/fonts/truetype/dejavu"
F_SANS = f"{FD}/DejaVuSans.ttf"
F_BOLD = f"{FD}/DejaVuSans-Bold.ttf"
F_MONO = f"{FD}/DejaVuSansMono.ttf"
F_MONOB = f"{FD}/DejaVuSansMono-Bold.ttf"

SANITIZE = {"⟳": "", "▸": ">", "→": "->", "•": "-", "≈": "~", "…": "...",
            "“": '"', "”": '"', "‘": "'", "’": "'", "—": "-", "–": "-",
            "✓": "[x]", "☤": "+", "⚠": "!"}


def S(t):
    for a, b in SANITIZE.items():
        t = t.replace(a, b)
    return t


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, fnt, max_w):
    words, lines, cur = S(text).split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if draw.textlength(t, font=fnt) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines or [""]


class R:
    def __init__(self):
        spec = json.load(open(SPEC, encoding="utf-8"))
        self.slides = spec["slides"]
        self.st = spec["style"]
        os.makedirs(OUT, exist_ok=True)

    def base(self):
        img = Image.new("RGB", (W, H), self.st["bg"])
        d = ImageDraw.Draw(img)
        # subtle top glow bar
        d.rectangle([0, 0, W, 8], fill=self.st["accent"])
        return img, d

    def header(self, d, title, batch):
        f_t = font(F_BOLD, 56)
        f_b = font(F_SANS, 26)
        d.text((M, 52), S(title), font=f_t, fill=self.st["text"])
        bw = d.textlength(S(batch), font=f_b)
        d.text((W - M - bw, 66), S(batch), font=f_b, fill=self.st["accent"])
        d.line([(M, 140), (W - M, 140)], fill=self.st["accent"], width=3)

    def footer(self, d, text, sid):
        f = font(F_SANS, 24)
        ft = S(text or "Hermes Agent  -  detailed explainer")
        d.text((M, H - 62), ft, font=f, fill=self.st["muted"])
        tag = S(sid)
        tw = d.textlength(tag, font=f)
        d.text((W - M - tw, H - 62), tag, font=f, fill=self.st["muted"])

    def title_slide(self, sp):
        img, d = self.base()
        cx = W // 2
        f_k = font(F_BOLD, 34)
        f_t = font(F_BOLD, 150)
        f_s = font(F_SANS, 34)
        k = S(sp["kicker"])
        d.text((cx - d.textlength(k, font=f_k) / 2, 300), k, font=f_k, fill=self.st["accent"])
        t = S(sp["title"])
        d.text((cx - d.textlength(t, font=f_t) / 2, 370), t, font=f_t, fill=self.st["text"])
        d.line([(cx - 260, 580), (cx + 260, 580)], fill=self.st["accent"], width=4)
        y = 620
        for ln in wrap(d, sp["subtitle"], f_s, 1400):
            d.text((cx - d.textlength(ln, font=f_s) / 2, y), ln, font=f_s, fill=self.st["muted"])
            y += 52
        self.footer(d, sp.get("batch", ""), sp["id"])
        img.save(f"{OUT}/{sp['id']}.png")

    def closing_slide(self, sp):
        img, d = self.base()
        cx = W // 2
        f_k = font(F_BOLD, 36)
        f_t = font(F_BOLD, 110)
        f_b = font(F_SANS, 36)
        k = S(sp["kicker"])
        d.text((cx - d.textlength(k, font=f_k) / 2, 220), k, font=f_k, fill=self.st["accent"])
        t = S(sp["title"])
        d.text((cx - d.textlength(t, font=f_t) / 2, 290), t, font=f_t, fill=self.st["text"])
        d.line([(cx - 260, 450), (cx + 260, 450)], fill=self.st["accent"], width=4)
        y = 520
        for b in sp["bullets"]:
            lines = wrap(d, "-  " + b, f_b, 1300)
            for ln in lines:
                d.text((cx - 650, y), ln, font=f_b, fill=self.st["text"])
                y += 56
            y += 18
        self.footer(d, sp.get("footer", ""), sp["id"])
        img.save(f"{OUT}/{sp['id']}.png")

    def bullets_slide(self, sp):
        img, d = self.base()
        self.header(d, sp["title"], sp["batch"])
        f_b = font(F_SANS, 36)
        y = 230
        for b in sp["bullets"]:
            lines = wrap(d, b, f_b, 1500)
            d.ellipse([M, y + 12, M + 22, y + 34], fill=self.st["accent"])
            for j, ln in enumerate(lines):
                d.text((M + 48, y), ln, font=f_b, fill=self.st["text"])
                y += 54
            y += 34
        self.footer(d, sp.get("footer", ""), sp["id"])
        img.save(f"{OUT}/{sp['id']}.png")

    def table_slide(self, sp):
        img, d = self.base()
        self.header(d, sp["title"], sp["batch"])
        f_h = font(F_BOLD, 30)
        f_c = font(F_SANS, 28)
        f_c0 = font(F_BOLD, 28)
        widths = sp["widths"]
        tw = W - 2 * M
        cols = [int(tw * w_) for w_ in widths]
        cols[-1] = tw - sum(cols[:-1])
        xs = [M]
        for c in cols[:-1]:
            xs.append(xs[-1] + c)
        y = 190
        # header row
        d.rectangle([M, y, W - M, y + 62], fill=self.st["accent"])
        for x, hd, cw in zip(xs, sp["headers"], cols):
            t = S(hd)
            d.text((x + 20, y + 12), t, font=f_h, fill=self.st["bg"])
        y += 62
        for ri, row in enumerate(sp["rows"]):
            wrapped = []
            for cell, cw in zip(row, cols):
                f = f_c0 if len(sp["headers"]) > 1 and cell == row[0] else f_c
                wrapped.append((wrap(d, cell, f, cw - 40), f))
            rh = max(len(w_) for w_, _ in wrapped) * 42 + 30
            fill = self.st["card"] if ri % 2 == 0 else self.st["bg"]
            d.rectangle([M, y, W - M, y + rh], fill=fill, outline=self.st["grid"], width=2)
            for x, (lines, f), cw in zip(xs, wrapped, cols):
                for li, ln in enumerate(lines):
                    col = self.st["accent"] if f is f_c0 and len(sp["headers"]) > 1 else self.st["text"]
                    # first column in gold bold for 2-col tables
                    if len(sp["headers"]) == 2 and f is f_c0:
                        col = self.st["accent"]
                    d.text((x + 20, y + 14 + li * 42), ln, font=f, fill=col)
            # vertical dividers
            for x in xs[1:]:
                d.line([(x, y), (x, y + rh)], fill=self.st["grid"], width=2)
            y += rh
        self.footer(d, sp.get("footer", ""), sp["id"])
        img.save(f"{OUT}/{sp['id']}.png")

    def flow_slide(self, sp):
        img, d = self.base()
        self.header(d, sp["title"], sp["batch"])
        f_n = font(F_BOLD, 30)
        nodes = sp["nodes"]
        n = len(nodes)
        avail = H - 190 - 110
        gap = 34
        nh = min(118, (avail - gap * (n - 1)) // n)
        bw = 1500
        x0 = (W - bw) // 2
        y = 195
        for i, nd in enumerate(nodes):
            last = (i == n - 1)
            first = (i == 0)
            fill = self.st["card"]
            border = self.st["accent"]
            d.rounded_rectangle([x0, y, x0 + bw, y + nh], radius=18, fill=fill,
                                outline=border, width=3)
            t = S(nd)
            # shrink if too wide
            fs = 30
            while d.textlength(t, font=font(F_BOLD, fs)) > bw - 80 and fs > 20:
                fs -= 2
            f = font(F_BOLD, fs)
            tw_ = d.textlength(t, font=f)
            bb = d.textbbox((0, 0), t, font=f)
            th = bb[3] - bb[1]
            col = self.st["accent"] if (first or last) else self.st["text"]
            d.text((x0 + (bw - tw_) / 2, y + (nh - th) / 2 - bb[1]), t, font=f, fill=col)
            if i < n - 1:
                ax = W // 2
                y1 = y + nh + 6
                y2 = y + nh + gap - 6
                d.line([(ax, y1), (ax, y2)], fill=self.st["accent"], width=5)
                d.polygon([(ax - 12, y2 - 2), (ax + 12, y2 - 2), (ax, y2 + 14)],
                          fill=self.st["accent"])
            y += nh + gap
        self.footer(d, sp.get("footer", ""), sp["id"])
        img.save(f"{OUT}/{sp['id']}.png")

    def code_slide(self, sp):
        img, d = self.base()
        self.header(d, sp["title"], sp["batch"])
        f_m = font(F_MONO, 29)
        x0, y0 = M, 210
        cw_, ch = W - 2 * M, len(sp["lines"]) * 52 + 60
        d.rounded_rectangle([x0, y0, x0 + cw_, y0 + ch], radius=16, fill="#0A0F22",
                            outline=self.st["grid"], width=2)
        # traffic dots
        for i, c in enumerate(["#FF5F57", "#FEBC2E", "#28C840"]):
            d.ellipse([x0 + 28 + i * 34, y0 + 18, x0 + 48 + i * 34, y0 + 38], fill=c)
        y = y0 + 56
        for ln in sp["lines"]:
            t = S(ln) or " "
            col = self.st["muted"] if t.strip().startswith("#") else "#7DF9A4" \
                if not t.startswith(" ") and t.strip() else self.st["text"]
            if "hermes-agent.nousresearch" in t or "irm http" in t:
                col = self.st["accent"]
            d.text((x0 + 36, y), t, font=font(F_MONO, 29), fill=col)
            y += 52
        self.footer(d, sp.get("footer", ""), sp["id"])
        img.save(f"{OUT}/{sp['id']}.png")

    def run(self):
        kinds = {"title": self.title_slide, "closing": self.closing_slide,
                 "bullets": self.bullets_slide, "table": self.table_slide,
                 "flow": self.flow_slide, "code": self.code_slide}
        for sp in self.slides:
            kinds[sp["kind"]](sp)
            print(f"  rendered {sp['id']}.png ({sp['kind']})")
        print(f"RENDER OK: {len(self.slides)} slides -> {OUT}/")


if __name__ == "__main__":
    R().run()
