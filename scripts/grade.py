"""One consistent, subtle look for every cover photo (site + Instagram).

The originals in images/photos/ are never changed: graded copies are made at build time in .cache/graded/.
The grade is deliberately gentle and never shifts hue, so product colors (a sneaker colorway) stay true:
  1. levels on brightness only (same curve on R, G and B, so no color cast is added or removed)
  2. brightness nudged toward a common midpoint (bounded gamma)
  3. a touch of contrast and saturation, then light sharpening
Set "photo_grade": false in config.json to turn it off.
"""
import math

from PIL import Image, ImageEnhance, ImageFilter

from common import ROOT, load_config, photo_path

CACHE = ROOT / ".cache" / "graded"
VERSION = "1"  # bump to regrade everything after changing the recipe


def _levels(im):
    hist = im.convert("L").histogram()
    total = sum(hist)
    lo_n, hi_n = total * 0.005, total * 0.995
    acc, lo, hi = 0, 0, 255
    for v, c in enumerate(hist):
        acc += c
        if acc >= lo_n and lo == 0:
            lo = v
        if acc >= hi_n:
            hi = v
            break
    lo, hi = min(lo, 40), max(hi, 215)  # never stretch harder than this
    lut = [max(0, min(255, round((v - lo) * 255 / max(1, hi - lo)))) for v in range(256)]
    return im.point(lut * 3)


def _gamma(im, target=118):
    hist = im.convert("L").histogram()
    mean = sum(v * c for v, c in enumerate(hist)) / max(1, sum(hist))
    if mean <= 1 or mean >= 254:
        return im
    g = max(0.85, min(1.18, math.log(target / 255) / math.log(mean / 255)))
    lut = [round(255 * (v / 255) ** g) for v in range(256)]
    return im.point(lut * 3)


def grade(src, dst):
    im = Image.open(src).convert("RGB")
    im = _gamma(_levels(im))
    im = ImageEnhance.Contrast(im).enhance(1.04)
    im = ImageEnhance.Color(im).enhance(1.04)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=35, threshold=3))
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, quality=88, optimize=True)


def graded_photo(find):
    """Path to the cover photo to publish: the graded copy (made if missing or stale), or the original if grading is off."""
    src = photo_path(find)
    if not src or load_config().get("photo_grade") is False:
        return src
    st = src.stat()  # key on the file itself, so a renumbered/replaced photo never reuses an old grade
    dst = CACHE / f"{find}-v{VERSION}-{st.st_size}-{int(st.st_mtime)}.jpg"
    if not dst.exists():
        grade(src, dst)
    return dst
