"""Render a 9:16 "N celebs who wear X" reel (MP4, no audio — add trending audio in Instagram).

  python scripts/make_reel.py reels/gshock.json out.mp4

The spec lists the hook, one beat per listing (Find #, overlay text, optional crop), the product and the CTA.
Photos come from images/photos/<find>.jpg (graded), products from the listing's cut-out image.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from common import ROOT, load_fits
from grade import graded_photo

W, H, FPS = 1080, 1920, 30
BG, INK, ACCENT, MUTED = (17, 18, 22), (240, 240, 244), (139, 147, 255), (160, 163, 175)
FONTS = Path(__file__).resolve().parent.parent / ".cache" / "fonts"


def font(name, size):
    return ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)


def ensure_fonts():
    FONTS.mkdir(parents=True, exist_ok=True)
    from fontTools.ttLib import TTFont
    for n in ("big-shoulders-display-latin-900-normal", "ibm-plex-mono-latin-500-normal", "instrument-sans-latin-600-normal"):
        out = FONTS / f"{n}.ttf"
        if not out.exists():
            f = TTFont(ROOT / "assets" / "fonts" / f"{n}.woff2")
            f.flavor = None
            f.save(out)


DISPLAY, MONO = "big-shoulders-display-latin-900-normal", "ibm-plex-mono-latin-500-normal"


def cover(img, box, t, zoom=(1.0, 1.12), focus=(0.5, 0.45)):
    """Crop-to-fill with a slow push-in toward `focus` (fractions of the image)."""
    bw, bh = box
    z = zoom[0] + (zoom[1] - zoom[0]) * t
    s = max(bw / img.width, bh / img.height) * z
    nw, nh = int(img.width * s), int(img.height * s)
    im = img.resize((nw, nh), Image.LANCZOS)
    fx, fy = focus
    x = min(max(int(fx * nw - bw / 2), 0), nw - bw)
    y = min(max(int(fy * nh - bh / 2), 0), nh - bh)
    return im.crop((x, y, x + bw, y + bh))


def wrap(draw, text, fnt, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= maxw:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def big_text(frame, text, y, size=150, color=INK, stroke=8, pop=1.0):
    d = ImageDraw.Draw(frame)
    fnt = font(DISPLAY, int(size * pop))
    lines = wrap(d, text.upper(), fnt, W - 120)
    lh = int(size * pop * 0.95)
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=fnt)
        d.text(((W - tw) / 2, y + i * lh), ln, font=fnt, fill=color, stroke_width=stroke, stroke_fill=(0, 0, 0))
    return y + len(lines) * lh


def chip(frame, text, x, y, size=40, fg=BG, bg=ACCENT):
    d = ImageDraw.Draw(frame)
    fnt = font(MONO, size)
    tw = d.textlength(text, font=fnt)
    d.rounded_rectangle((x, y, x + tw + 36, y + size + 28), radius=10, fill=bg)
    d.text((x + 18, y + 12), text, font=fnt, fill=fg)


def shade(frame):
    g = Image.new("L", (1, H))
    for yy in range(H):
        g.putpixel((0, yy), int(max(0, (yy - H * 0.45) / (H * 0.55)) * 215))
    black = Image.new("RGB", (W, H), (0, 0, 0))
    frame.paste(black, (0, 0), g.resize((W, H)))


def ease(t):
    return 1 - (1 - min(max(t, 0), 1)) ** 3


def render(spec, out):
    ensure_fonts()
    fits = {f["find"]: f for f in load_fits()["fits"]}
    segs = []  # (duration, draw(frame_index_in_seg, n_frames) -> Image)

    def photo_seg(find, dur, text, sub, crop=None, focus=(0.5, 0.45), hook=False):
        img = Image.open(graded_photo(find)).convert("RGB")
        if crop:
            img = img.crop(tuple(int(c * s) for c, s in zip(crop, (img.width, img.height, img.width, img.height))))
        bg = img.resize((W // 8, H // 8)).filter(ImageFilter.GaussianBlur(6)).resize((W, H))

        def draw(i, n):
            t = i / max(1, n - 1)
            fr = bg.copy()
            fr.paste(cover(img, (W, H), t, focus=focus), (0, 0))
            shade(fr)
            pop = 1.0 + 0.12 * (1 - ease(i / 6))
            if hook:
                big_text(fr, text, 260, size=170, pop=pop)
            else:
                y = big_text(fr, text, H - 560, size=130, pop=pop)
                if sub:
                    d = ImageDraw.Draw(fr)
                    fnt = font(MONO, 46)
                    tw = d.textlength(sub, font=fnt)
                    d.text(((W - tw) / 2, y + 20), sub, font=fnt, fill=ACCENT, stroke_width=3, stroke_fill=(0, 0, 0))
            chip(fr, f"FIND #{find}", 60, 90)
            return fr
        segs.append((dur, draw))

    def product_seg(find, dur, title, price):
        it = next(i for i in fits[find]["items"] if i.get("img"))
        prod = Image.open(ROOT / it["img"]).convert("RGBA")
        prod.thumbnail((860, 860))

        def draw(i, n):
            fr = Image.new("RGB", (W, H), BG)
            d = ImageDraw.Draw(fr)
            d.ellipse((W / 2 - 470, 560 - 470, W / 2 + 470, 560 + 470), fill=(28, 30, 38))
            s = 0.6 + 0.4 * ease(i / 9)
            p = prod.resize((int(prod.width * s), int(prod.height * s)), Image.LANCZOS)
            fr.paste(p, (int((W - p.width) / 2), int(560 - p.height / 2)), p)
            y = big_text(fr, title, 1150, size=120, stroke=0)
            big_text(fr, price, y + 30, size=170, color=ACCENT, stroke=0, pop=1.0 + 0.15 * (1 - ease((i - 8) / 6)) if i > 8 else 1.0)
            return fr
        segs.append((dur, draw))

    def cta_seg(dur, keyword, finds, loop_find):
        img = Image.open(graded_photo(loop_find)).convert("RGB")

        def draw(i, n):
            fr = cover(img, (W, H), 0.0).filter(ImageFilter.GaussianBlur(14))
            fr = Image.blend(fr, Image.new("RGB", (W, H), BG), 0.55)
            y = big_text(fr, f"Comment {keyword}", 620, size=190, color=ACCENT)
            y = big_text(fr, "for the link", y + 10, size=120)
            d = ImageDraw.Draw(fr)
            fnt = font(MONO, 48)
            for k, ln in enumerate([f"Find {finds}", "COP THE FIT"]):
                tw = d.textlength(ln, font=fnt)
                d.text(((W - tw) / 2, y + 90 + k * 80), ln, font=fnt, fill=INK if k else MUTED)
            return fr
        segs.append((dur, draw))

    for b in spec["beats"]:
        kind = b["kind"]
        if kind == "photo":
            photo_seg(b["find"], b["dur"], b["text"], b.get("sub", ""), b.get("crop"), tuple(b.get("focus", (0.5, 0.45))), b.get("hook", False))
        elif kind == "product":
            product_seg(b["find"], b["dur"], b["title"], b["price"])
        elif kind == "cta":
            cta_seg(b["dur"], b["keyword"], b["finds"], b["loop_find"])

    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                             "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
                            stdin=subprocess.PIPE)
    for dur, draw in segs:
        n = int(round(dur * FPS))
        for i in range(n):
            proc.stdin.write(draw(i, n).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    print("wrote", out, f"{sum(d for d, _ in segs):.1f}s")


if __name__ == "__main__":
    render(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
