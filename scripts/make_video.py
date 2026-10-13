"""Make a voiced, captioned 9:16 reel for one video in data/videos.json.

  python scripts/make_video.py <video id> <out dir>      → <out dir>/<id>.mp4 and <id>.txt (Instagram caption)

Script: data/videos.json → video["script"] (hook, per-listing lines, product, outro). Anything missing is filled
from the listings themselves (headline/detail, exact item, price), so every video group can be rendered.
Voice: Kokoro (free, open-source neural TTS; runs on GitHub Actions). Without it, a silent draft is made with
estimated timings so the layout can still be checked. Trending music is added in Instagram, not here.
"""
import json
import math
import os
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import make_reel as R
from common import ROOT, load_fits
from grade import graded_photo

W, H, FPS, SR = R.W, R.H, R.FPS, 24000
VOICE = os.environ.get("VIDEO_VOICE", "am_michael")          # Kokoro backup voice
SPEED = float(os.environ.get("VIDEO_SPEED", "1.08"))
EDGE_VOICE = os.environ.get("VIDEO_EDGE_VOICE", "en-US-AndrewMultilingualNeural")  # main voice (Microsoft neural)
EDGE_RATE = os.environ.get("VIDEO_EDGE_RATE", "+6%")
PAD = 0.18  # silence after each line


# ---------- script ----------

def price_of(it):
    return it.get("price") or it.get("price_auto") or ""


def money(p):
    m = re.search(r"[\d,.]+", p or "")
    return float(m.group().replace(",", "")) if m else None


def say_price(p):
    v = money(p)
    return f"{round(v)} dollars" if v else ""


def first_sentence(s, words=24):
    s = re.split(r"(?<=[.!?])\s", (s or "").strip())[0]
    w = s.split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


def build_script(v, fits):
    sc = v.get("script") or {}
    lines = sc.get("lines") or {}
    finds = [f for f in (sc.get("order") or v["finds"]) if f in fits]
    exact = {}
    for f in finds:
        its = [i for i in fits[f]["items"] if i.get("img")]
        exact[f] = next((i for i in its if i["label"] == "Exact"), its[0] if its else None)
    prices = [money(price_of(exact[f])) for f in finds if exact[f] and money(price_of(exact[f]))]
    low = f"${round(min(prices))}" if prices else ""
    segs = [{"kind": "hook", "finds": finds,
             "say": sc.get("hook_say") or f"{len(finds)} famous people. One affordable piece they all wear.",
             "text": sc.get("hook_text") or v["title"]}]
    for f in finds:
        fit, it = fits[f], exact[f]
        line = lines.get(f) or {}
        segs.append({"kind": "photo", "find": f,
                     "say": line.get("say") or first_sentence(fit.get("detail") or fit["headline"]),
                     "label": line.get("label") or fit["celeb"],
                     "sub": line.get("sub") or (price_of(it) if it else ""),
                     "crop": line.get("crop"), "focus": line.get("focus", [0.5, 0.45])})
    pf = sc.get("product_find") or next((f for f in finds if exact[f]), finds[0])
    pit = exact[pf]
    segs.append({"kind": "product", "find": pf,
                 "say": sc.get("product_say") or f"The {pit['brand']} {pit['name'].split('(')[0].strip()}. From {say_price(low)}.",
                 "title": sc.get("product_title") or f"{pit['brand']} {pit['name'].split('(')[0].strip()}",
                 "price": sc.get("product_price") or (f"From {low}" if low else "")})
    kw = sc.get("keyword") or "LINK"
    segs.append({"kind": "outro", "loop_find": finds[0], "keyword": kw,
                 "say": sc.get("outro_say") or f"Comment {kw.lower()}, and we'll send you every piece from this video."})
    first, last = finds[0], finds[-1]
    caption = sc.get("caption") or (f"{v['title']} 👀\nFind #{first}–#{last} on our site. Comment {kw} and we'll DM you every piece from this video.\n"
                                    "#celebstyle #fitcheck #copthefit")
    return segs, caption


# ---------- voice ----------

_PIPE = None
USED = set()  # which voice engine actually spoke (recorded next to the video)
EDGE_ERR = []  # why the neural voice failed, if it did


def tts(text):
    """→ (float32 audio @24kHz, [(word, start_s, end_s)]). Microsoft neural voice first, then Kokoro, then silence."""
    try:
        return tts_edge(text)
    except Exception as e:  # noqa: BLE001 (no network / package missing → fall back)
        print("edge voice unavailable:", str(e)[:120], file=sys.stderr)
        EDGE_ERR.append(f"{type(e).__name__}: {str(e)[:100]}")
    return tts_kokoro(text)


def tts_edge(text):
    import asyncio
    import edge_tts

    async def run():
        audio, words = bytearray(), []
        try:
            com = edge_tts.Communicate(text, EDGE_VOICE, rate=EDGE_RATE, boundary="WordBoundary")
        except TypeError:  # older edge-tts: word boundaries are the default
            com = edge_tts.Communicate(text, EDGE_VOICE, rate=EDGE_RATE)
        async for ch in com.stream():
            if ch["type"] == "audio":
                audio += ch["data"]
            elif ch["type"] == "WordBoundary":
                st = ch["offset"] / 1e7
                words.append((ch["text"], st, st + ch["duration"] / 1e7))
        return bytes(audio), words

    mp3, words = asyncio.run(run())
    if not mp3:
        raise RuntimeError("no audio returned")
    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "-", "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         input=mp3, capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    USED.add(f"neural ({EDGE_VOICE})")
    return audio, words or _even(text, len(audio) / SR)


def tts_kokoro(text):
    global _PIPE
    try:
        if _PIPE is None:
            from kokoro import KPipeline
            _PIPE = KPipeline(lang_code="a")
        chunks, words, off = [], [], 0.0
        for r in _PIPE(text, voice=VOICE, speed=SPEED):
            a = r.audio.detach().cpu().numpy() if hasattr(r.audio, "detach") else np.asarray(r.audio)
            for t in r.tokens or []:
                if getattr(t, "start_ts", None) is not None and re.search(r"\w", t.text or ""):
                    words.append((t.text, off + t.start_ts, off + (t.end_ts or t.start_ts + 0.3)))
            chunks.append(a.astype(np.float32))
            off += len(a) / SR
        audio = np.concatenate(chunks) if chunks else np.zeros(int(SR * 0.5), np.float32)
        if not words:
            words = _even(text, len(audio) / SR)
        USED.add("kokoro")
        return audio, words
    except ImportError:
        USED.add("silent draft")
        n = len(text.split())
        dur = 0.3 + n * 0.34
        return np.zeros(int(SR * dur), np.float32), _even(text, dur)


def _even(text, dur):
    w = text.split()
    step = dur / max(1, len(w))
    return [(x, i * step, (i + 1) * step) for i, x in enumerate(w)]


# ---------- sound effects (synthesised, so there's nothing to license) ----------

def whoosh(dur=0.32, vol=0.07):
    n = int(SR * dur)
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(n)
    k = np.linspace(40, 4, n).astype(int)  # smoothing shrinks → pitch rises
    out = np.empty(n)
    acc = 0.0
    for i in range(n):
        a = 1.0 / k[i]
        acc += a * (noise[i] - acc)
        out[i] = acc
    env = np.sin(np.linspace(0, math.pi, n)) ** 2
    out = out * env
    return (out / (np.abs(out).max() or 1) * vol).astype(np.float32)


def kaching(vol=0.13):
    n = int(SR * 0.7)
    t = np.arange(n) / SR
    bell = sum(np.sin(2 * math.pi * f * t) * np.exp(-t * d) for f, d in ((1568, 6), (2093, 7), (3136, 9), (4186, 11)))
    click = np.random.default_rng(3).standard_normal(n) * np.exp(-t * 90) * 0.6
    out = bell * (t > 0.06) + click
    return (out / np.abs(out).max() * vol).astype(np.float32)


def add(track, clip, at):
    i = int(at * SR)
    j = min(len(track), i + len(clip))
    if i < len(track):
        track[i:j] += clip[: j - i]


# ---------- picture ----------

def zoom_cover(img, z, focus):
    s = max(W / img.width, H / img.height) * z
    nw, nh = int(img.width * s), int(img.height * s)
    im = img.resize((nw, nh), Image.BILINEAR)
    x = min(max(int(focus[0] * nw - W / 2), 0), nw - W)
    y = min(max(int(focus[1] * nh - H / 2), 0), nh - H)
    return im.crop((x, y, x + W, y + H))


def punch(t):
    """zoom: quick punch-in on the cut, then slow drift"""
    return 1.22 - 0.16 * R.ease(t / 0.25) - 0.06 * min(1, t / 3)


def captions(fr, words, t, y=1240):
    """Word-by-word captions: groups of 3, current word highlighted."""
    if not words:
        return
    k = max([i for i, w in enumerate(words) if w[1] <= t] or [0])
    g = k // 3
    group = words[g * 3: g * 3 + 3]
    d = ImageDraw.Draw(fr)
    fnt = R.font(R.DISPLAY, 112)
    parts = [re.sub(r"[^\w$'’.,!?%-]", "", w[0]).upper() for w in group]
    widths = [d.textlength(p, font=fnt) for p in parts]
    gap = 28
    total = sum(widths) + gap * (len(parts) - 1)
    if total > W - 80:  # too wide: scale down
        fnt = R.font(R.DISPLAY, int(112 * (W - 80) / total))
        widths = [d.textlength(p, font=fnt) for p in parts]
        total = sum(widths) + gap * (len(parts) - 1)
    x = (W - total) / 2
    for i, p in enumerate(parts):
        cur = g * 3 + i == k
        d.text((x, y), p, font=fnt, fill=R.ACCENT if cur else R.INK, stroke_width=9, stroke_fill=(0, 0, 0))
        x += widths[i] + gap


def label(fr, text, sub, find):
    d = ImageDraw.Draw(fr)
    R.chip(fr, f"FIND #{find}", 60, 90)
    fnt = R.font(R.DISPLAY, 96)
    tw = d.textlength(text.upper(), font=fnt)
    d.text(((W - tw) / 2, 230), text.upper(), font=fnt, fill=R.INK, stroke_width=7, stroke_fill=(0, 0, 0))
    if sub:
        fnt2 = R.font(R.MONO, 50)
        tw = d.textlength(sub, font=fnt2)
        d.rounded_rectangle(((W - tw) / 2 - 24, 350, (W + tw) / 2 + 24, 420), radius=12, fill=R.ACCENT)
        d.text(((W - tw) / 2, 358), sub, font=fnt2, fill=R.BG)


def top_shade(fr):
    g = Image.new("L", (1, H))
    for yy in range(H):
        top = max(0, 1 - yy / 560) * 170
        bot = max(0, (yy - H * 0.55) / (H * 0.45)) * 200
        g.putpixel((0, yy), int(min(230, top + bot)))
    fr.paste(Image.new("RGB", (W, H), (0, 0, 0)), (0, 0), g.resize((W, H)))


def load_photo(find, crop=None):
    im = Image.open(graded_photo(find)).convert("RGB")
    if crop:
        im = im.crop(tuple(int(c * s) for c, s in zip(crop, (im.width, im.height, im.width, im.height))))
    return im


# ---------- background music (synthesised lo-fi bed, so there's nothing to license) ----------

def lofi(dur, bpm=86, vol=0.055):
    """Soft Rhodes-style chords + kick/hat + vinyl hiss. Quiet enough to sit under the voice."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    out = np.zeros(n)
    beat = 60 / bpm
    bar = beat * 4
    chords = [(57, 60, 64, 67), (53, 57, 60, 64), (48, 52, 55, 59), (55, 59, 62, 65)]  # Am7 Fmaj7 Cmaj7 G7
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    for b in range(int(dur / bar) + 1):
        st = b * bar
        i0, i1 = int(st * SR), min(n, int((st + bar) * SR))
        if i0 >= n:
            break
        tt = t[i0:i1] - st
        env = (1 - np.exp(-tt * 18)) * np.exp(-tt * 0.9)
        for m in chords[b % 4]:
            f = hz(m)
            out[i0:i1] += (np.sin(2 * math.pi * f * tt) + 0.3 * np.sin(4 * math.pi * f * tt) * np.exp(-tt * 3)) * env * 0.18
        f = hz(chords[b % 4][0] - 12)  # bass
        out[i0:i1] += np.sin(2 * math.pi * f * tt) * np.exp(-tt * 1.2) * 0.35
    rng = np.random.default_rng(11)
    for k in range(int(dur / beat) + 1):
        st = k * beat
        i0 = int(st * SR)
        if i0 >= n:
            break
        if k % 2 == 0:  # kick on 1 and 3
            m = min(n - i0, int(SR * 0.25))
            tt = np.arange(m) / SR
            out[i0:i0 + m] += np.sin(2 * math.pi * (50 + 70 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 14) * 0.9
        for h in (0, 0.5):  # soft hats on eighths
            j0 = int((st + h * beat) * SR)
            m = min(n - j0, int(SR * 0.05))
            if m > 0:
                out[j0:j0 + m] += rng.standard_normal(m) * np.exp(-np.arange(m) / SR * 90) * 0.12
    out += rng.standard_normal(n) * 0.01  # vinyl hiss
    fade = np.minimum(1, np.minimum(t / 0.6, (dur - t) / 1.2))
    out *= np.clip(fade, 0, 1)
    return (out / (np.abs(out).max() or 1) * vol).astype(np.float32)


def thud(vol=0.22):
    n = int(SR * 0.35)
    tt = np.arange(n) / SR
    out = np.sin(2 * math.pi * (45 + 60 * np.exp(-tt * 25)) * tt) * np.exp(-tt * 9)
    out += np.random.default_rng(5).standard_normal(n) * np.exp(-tt * 60) * 0.4
    return (out / np.abs(out).max() * vol).astype(np.float32)


# ---------- "story" videos: one listing told in beats, each with its own image ----------

def story_image(vid, fits, ref):
    """asset:<name> → reels/<vid>/assets/<name>.jpg · photo:<find> → cover photo · product:<find> → product cut-out on white"""
    kind, _, name = ref.partition(":")
    if kind == "asset":
        return Image.open(ROOT / "reels" / vid / "assets" / f"{name}.jpg").convert("RGB")
    if kind == "photo":
        return load_photo(name)
    it = next(i for i in fits[name]["items"] if i.get("img"))
    prod = Image.open(ROOT / it["img"]).convert("RGBA")
    bg = Image.new("RGBA", (int(prod.width * 1.6), int(prod.height * 1.6)), (243, 241, 238, 255))
    bg.alpha_composite(prod, ((bg.width - prod.width) // 2, (bg.height - prod.height) // 2))
    return bg.convert("RGB")


def fit_frame(img, z, focus, fit):
    """Fill 9:16. fit=True: whole image centred over a blurred copy of itself (for wide shots)."""
    if not fit:
        return zoom_cover(img, z, focus)
    bg = zoom_cover(img, 1.0, (0.5, 0.5)).resize((W // 12, H // 12)).filter(ImageFilter.GaussianBlur(3)).resize((W, H))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.35)
    s = W / img.width * z
    im = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    x = int((W - im.width) * focus[0])
    bg.paste(im, (x, int((H - im.height) / 2)))
    return bg


def stamp(fr, text, k):
    """Rubber-stamp text slamming in (k: 0→1)."""
    sc = 1.0 + 1.2 * (1 - R.ease(k))
    fnt = R.font(R.DISPLAY, int(200 * sc))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    tw = d.textlength(text, font=fnt)
    x, y = (W - tw) / 2, H * 0.42 - 100 * sc
    d.rounded_rectangle((x - 40, y - 10, x + tw + 40, y + 230 * sc), radius=18, outline=(235, 52, 52, 255), width=int(14 * sc))
    d.text((x, y), text, font=fnt, fill=(235, 52, 52, 255))
    lay = lay.rotate(-11, resample=Image.BICUBIC, center=(W / 2, H * 0.45))
    a = int(255 * min(1, k * 3))
    lay.putalpha(lay.getchannel("A").point(lambda v: v * a // 255))
    fr.paste(lay, (0, 0), lay)


def make_story(v, fits, out_dir):
    vid, sc = v["id"], v["script"]
    beats = list(sc["beats"])
    pf = sc.get("product_find") or v["finds"][0]
    beats.append({"kind": "product", "say": sc["product_say"], "title": sc["product_title"], "price": sc["product_price"], "find": pf})
    kw = sc.get("keyword") or "LINK"
    beats.append({"kind": "outro", "say": sc.get("outro_say") or f"Comment {kw.lower()}, and we'll send you the link.",
                  "keyword": kw, "img": sc.get("outro_img") or beats[0]["img"]})

    t0, track, timeline = 0.0, [], []
    for b in beats:
        audio, words = tts(b["say"])
        dur = max(len(audio) / SR + PAD, b.get("min", 1.2))
        timeline.append((b, t0, dur, words))
        track.append(np.concatenate([audio, np.zeros(int(SR * dur) - len(audio), np.float32)]))
        t0 += dur
    mix = np.concatenate(track)
    for b, start, dur, words in timeline:
        if start > 0:
            add(mix, whoosh(), max(0, start - 0.12))
        if b.get("stamp"):
            trig = b.get("stamp_on", "sold").lower()
            b["_stamp_at"] = next((w[1] for w in words if w[0].lower().strip(".,!?") == trig), dur * 0.5)
            add(mix, thud(), start + b["_stamp_at"])
        if b.get("kind") == "product":
            b["_price_at"] = next((w[1] for w in words if re.search(r"\d|dollar|hundred", w[0], re.I)), 0.5)
            add(mix, kaching(), start + b["_price_at"])
    if sc.get("music", True):
        mix = mix + lofi(len(mix) / SR)
    peak = np.abs(mix).max() or 1
    mix = mix / peak * 0.95 if peak > 0.95 else mix
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / f"{vid}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    mp4 = out_dir / f"{vid}.mp4"
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                             "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                             "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(mp4)], stdin=subprocess.PIPE)
    prev, XF = None, 7  # crossfade frames
    for b, start, dur, words in timeline:
        n = int(round(dur * FPS))
        kind = b.get("kind", "photo")
        if kind == "product":
            it = next(i for i in fits[b["find"]]["items"] if i.get("img"))
            prod = Image.open(ROOT / it["img"]).convert("RGBA")
            prod = prod.crop(prod.getchannel("A").getbbox() or (0, 0, prod.width, prod.height))
            prod.thumbnail((760, 760))
            if prod.width < 760 and prod.height < 760:
                k_ = 760 / max(prod.size)
                prod = prod.resize((int(prod.width * k_), int(prod.height * k_)), Image.LANCZOS)
        else:
            img = story_image(vid, fits, b["img"])
            if b.get("crop"):
                c = b["crop"]
                img = img.crop((int(c[0] * img.width), int(c[1] * img.height), int(c[2] * img.width), int(c[3] * img.height)))
            z0, z1 = b.get("zoom", [1.04, 1.16])
            if kind == "outro":
                bgo = Image.blend(fit_frame(img, 1.0, b.get("focus", [0.5, 0.45]), False).filter(ImageFilter.GaussianBlur(16)), Image.new("RGB", (W, H), R.BG), 0.55)
        for i in range(n):
            t = i / FPS
            if kind == "product":
                fr = Image.new("RGB", (W, H), R.BG)
                d = ImageDraw.Draw(fr)
                d.ellipse((W / 2 - 460, 620 - 460, W / 2 + 460, 620 + 460), fill=(28, 30, 38))
                s_ = 0.55 + 0.45 * R.ease(t / 0.35)
                p = prod.resize((int(prod.width * s_), int(prod.height * s_)), Image.LANCZOS)
                fr.paste(p, (int((W - p.width) / 2), int(620 - p.height / 2 + math.sin(t * 3) * 10)), p)
                y = R.big_text(fr, b["title"], 1130, size=100, stroke=0)
                if t >= b["_price_at"]:
                    R.big_text(fr, b["price"], y + 20, size=170, color=R.ACCENT, stroke=0, pop=1.0 + 0.2 * (1 - R.ease((t - b["_price_at"]) / 0.2)))
                captions(fr, words, t, y=1620)
            elif kind == "outro":
                fr = bgo.copy()
                y = R.big_text(fr, f"Comment {b['keyword']}", 560, size=190, color=R.ACCENT)
                R.big_text(fr, "for the link", y + 10, size=110)
                captions(fr, words, t, y=1400)
            else:
                z = z0 + (z1 - z0) * (t / max(dur, 0.1))
                fr = fit_frame(img, z, b.get("focus", [0.5, 0.45]), b.get("fit", False))
                top_shade(fr)
                if b.get("text"):
                    pop = 1.0 + 0.14 * (1 - R.ease(t / 0.2))
                    y = R.big_text(fr, b["text"], 210, size=b.get("size", 130), pop=pop)
                    if b.get("sub"):
                        fnt2 = R.font(R.MONO, 46)
                        d = ImageDraw.Draw(fr)
                        tw = d.textlength(b["sub"], font=fnt2)
                        d.rounded_rectangle(((W - tw) / 2 - 22, y + 18, (W + tw) / 2 + 22, y + 86), radius=12, fill=R.ACCENT)
                        d.text(((W - tw) / 2, y + 26), b["sub"], font=fnt2, fill=R.BG)
                if b.get("stamp") and t >= b["_stamp_at"]:
                    stamp(fr, b["stamp"], (t - b["_stamp_at"]) / 0.18)
                captions(fr, words, t)
            if prev is not None and i < XF:  # crossfade from the last frame of the previous beat
                fr = Image.blend(prev, fr, (i + 1) / (XF + 1))
            proc.stdin.write(fr.tobytes())
        prev = fr
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    caption = sc.get("caption") or v["title"]
    (out_dir / f"{vid}.txt").write_text(caption)
    (out_dir / f"{vid}.voice").write_text(", ".join(sorted(USED)) + (" + music" if sc.get("music", True) else "") + (f" (neural failed: {EDGE_ERR[0]})" if EDGE_ERR and not any(u.startswith("neural") for u in USED) else ""))
    print(f"wrote {mp4} ({t0:.1f}s)")
    return mp4, caption, round(t0, 1)


def make(vid, out_dir):
    R.ensure_fonts()
    fits = {f["find"]: f for f in load_fits()["fits"]}
    vids = json.loads((ROOT / "data" / "videos.json").read_text())["videos"]
    v = next(x for x in vids if x["id"] == vid)
    if v.get("format") == "story":
        return make_story(v, fits, out_dir)
    segs, caption = build_script(v, fits)

    # voice first: it sets the timing
    t0, track, timeline = 0.0, [], []
    for s in segs:
        audio, words = tts(s["say"])
        dur = max(len(audio) / SR + PAD, 1.6 if s["kind"] == "hook" else 1.2)
        timeline.append((s, t0, dur, words))
        track.append(np.concatenate([audio, np.zeros(int(SR * dur) - len(audio), np.float32)]))
        t0 += dur
    mix = np.concatenate(track)
    for s, start, dur, words in timeline:
        if s["kind"] != "hook":
            add(mix, whoosh(), max(0, start - 0.12))
        if s["kind"] == "product":
            at = next((w[1] for w in words if re.search(r"\d|dollar", w[0], re.I)), 0.5)
            s["_price_at"] = at
            add(mix, kaching(), start + at)
    peak = np.abs(mix).max() or 1
    mix = mix / peak * 0.95 if peak > 0.95 else mix
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / f"{vid}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())

    mp4 = out_dir / f"{vid}.mp4"
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                             "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                             "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(mp4)], stdin=subprocess.PIPE)
    for s, start, dur, words in timeline:
        n = int(round(dur * FPS))
        k = s["kind"]
        if k == "hook":
            imgs = [load_photo(f, (segs_line_crop(v, f))) for f in s["finds"]]
        elif k == "photo":
            img = load_photo(s["find"], s.get("crop"))
            blur = img.resize((W // 10, H // 10)).filter(ImageFilter.GaussianBlur(4)).resize((W, H))
        elif k == "product":
            it = next(i for i in fits[s["find"]]["items"] if i.get("img"))
            prod = Image.open(ROOT / it["img"]).convert("RGBA")
            prod.thumbnail((820, 820))
        else:
            loop = load_photo(s["loop_find"], segs_line_crop(v, s["loop_find"]))
            bg = zoom_cover(loop, 1.0, (0.5, 0.45)).filter(ImageFilter.GaussianBlur(16))
            bg = Image.blend(bg, Image.new("RGB", (W, H), R.BG), 0.55)
        for i in range(n):
            t = i / FPS
            if k == "hook":
                per = max(1, n // len(imgs))
                im = imgs[min(i // per, len(imgs) - 1)]
                fr = zoom_cover(im, 1.18 - 0.14 * ((i % per) / per), (0.5, 0.42))
                fr = Image.blend(fr, Image.new("RGB", (W, H), (0, 0, 0)), 0.38)
                pop = 1.0 + 0.16 * (1 - R.ease(i / 5))
                R.big_text(fr, s["text"], 330, size=150, pop=pop)
                captions(fr, words, t, y=1300)
            elif k == "photo":
                fr = blur.copy()
                fr.paste(zoom_cover(img, punch(t), s["focus"]), (0, 0))
                top_shade(fr)
                label(fr, s["label"], s["sub"], s["find"])
                captions(fr, words, t)
                if i < 3:  # cut flash + shake
                    fr = Image.blend(fr, Image.new("RGB", (W, H), (255, 255, 255)), 0.25 * (3 - i) / 3)
            elif k == "product":
                fr = Image.new("RGB", (W, H), R.BG)
                d = ImageDraw.Draw(fr)
                d.ellipse((W / 2 - 460, 620 - 460, W / 2 + 460, 620 + 460), fill=(28, 30, 38))
                sc = 0.55 + 0.45 * R.ease(t / 0.35)
                bob = math.sin(t * 3) * 10
                p = prod.resize((int(prod.width * sc), int(prod.height * sc)), Image.LANCZOS)
                fr.paste(p, (int((W - p.width) / 2), int(620 - p.height / 2 + bob)), p)
                y = R.big_text(fr, s["title"], 1130, size=100, stroke=0)
                at = s.get("_price_at", 0.5)
                if t >= at and s["price"]:
                    R.big_text(fr, s["price"], y + 20, size=170, color=R.ACCENT, stroke=0, pop=1.0 + 0.2 * (1 - R.ease((t - at) / 0.2)))
                captions(fr, words, t, y=1620)
            else:
                fr = bg.copy()
                y = R.big_text(fr, f"Comment {s['keyword']}", 560, size=190, color=R.ACCENT)
                R.big_text(fr, "for the link", y + 10, size=110)
                captions(fr, words, t, y=1400)
            proc.stdin.write(fr.tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    (out_dir / f"{vid}.txt").write_text(caption)
    (out_dir / f"{vid}.voice").write_text(", ".join(sorted(USED)))
    print(f"wrote {mp4} ({t0:.1f}s)")
    return mp4, caption, round(t0, 1)


def segs_line_crop(v, find):
    return (((v.get("script") or {}).get("lines") or {}).get(find) or {}).get("crop")


if __name__ == "__main__":
    make(sys.argv[1], sys.argv[2])
