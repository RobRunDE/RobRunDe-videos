"""Shared drawing helpers: fonts, easing, text/pill/stamp sprites and alpha blitting.
Canvas size is 1080x1920 (W, H). All sprites are RGBA numpy arrays."""
import cv2, math, os, numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
YEL = (255, 214, 10); RED = (255, 59, 59); GRN = (46, 214, 115); PUR = (178, 92, 255)
GLD = (255, 190, 40); WHT = (255, 255, 255); BLK = (0, 0, 0)

MONT = os.path.join(HERE, "fonts", "Montserrat.ttf")
ANTON = os.path.join(HERE, "fonts", "Anton.ttf")

_fc = {}
def font(kind, size):
    k = (kind, size)
    if k not in _fc:
        if kind == "anton":
            f = ImageFont.truetype(ANTON, size)
        else:
            f = ImageFont.truetype(MONT, size)
            f.set_variation_by_axes([900 if kind == "black" else 800])
        _fc[k] = f
    return _fc[k]

# ---------- easing ----------
def clamp(x, a=0, b=1): return max(a, min(b, x))
def eout(x): x = clamp(x); return 1 - (1 - x) ** 3
def eback(x):
    x = clamp(x); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
def ein(x): x = clamp(x); return x ** 3
def esin(x): x = clamp(x); return 0.5 - 0.5 * math.cos(math.pi * x)

# ---------- text sprites ----------
_sc = {}
def text_sprite(txt, kind, size, fill, stroke=0, stroke_fill=BLK, shadow=True):
    k = (txt, kind, size, fill, stroke, stroke_fill, shadow)
    if k in _sc: return _sc[k]
    f = font(kind, size)
    l, t, r, b = f.getbbox(txt, stroke_width=stroke)
    pad = 24
    w, h = r - l + pad * 2, b - t + pad * 2
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pad - l + 4, pad - t + 7), txt, font=f, fill=(0, 0, 0, 170), stroke_width=stroke, stroke_fill=(0, 0, 0, 170))
        a = cv2.GaussianBlur(np.array(sh), (0, 0), 5)
        im = Image.fromarray(a)
    ImageDraw.Draw(im).text((pad - l, pad - t), txt, font=f, fill=fill + (255,), stroke_width=stroke, stroke_fill=stroke_fill + (255,))
    arr = np.array(im)
    _sc[k] = arr
    return arr

def pill_sprite(txt, bg, fg=WHT, size=44, icon=None, kind="black", padx=34, pady=18, radius=None):
    k = ("pill", txt, bg, fg, size, icon, kind)
    if k in _sc: return _sc[k]
    f = font(kind, size)
    l, t, r, b = f.getbbox(txt)
    tw, th = r - l, b - t
    iw = int(th * 1.05) + 18 if icon else 0
    w, h = tw + iw + padx * 2, th + pady * 2
    rad = radius if radius is not None else h // 2
    m = 30
    im = Image.new("RGBA", (w + m * 2, h + m * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((m + 2, m + 10, m + w + 2, m + h + 10), rad, fill=(0, 0, 0, 150))
    im = Image.fromarray(cv2.GaussianBlur(np.array(sh), (0, 0), 9))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((m, m, m + w, m + h), rad, fill=bg + (255,))
    d.rounded_rectangle((m, m, m + w, m + h), rad, outline=(255, 255, 255, 70), width=3)
    x0 = m + padx
    if icon:
        s = th * 1.05; cy = m + h / 2; cx = x0 + s / 2
        d.ellipse((cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2), fill=(255, 255, 255, 255))
        lw = max(5, int(s * 0.14))
        if icon == "x":
            q = s * 0.22
            d.line((cx - q, cy - q, cx + q, cy + q), fill=bg + (255,), width=lw)
            d.line((cx - q, cy + q, cx + q, cy - q), fill=bg + (255,), width=lw)
        elif icon == "check":
            d.line((cx - s * .24, cy + s * .02, cx - s * .06, cy + s * .2, cx + s * .26, cy - s * .2), fill=bg + (255,), width=lw, joint="curve")
        elif icon == "up":
            d.polygon((cx, cy - s * .27, cx + s * .25, cy + s * .05, cx - s * .25, cy + s * .05), fill=bg + (255,))
            d.rectangle((cx - s * .09, cy, cx + s * .09, cy + s * .27), fill=bg + (255,))
        elif icon == "plus":
            q = s * 0.24
            d.line((cx - q, cy, cx + q, cy), fill=bg + (255,), width=lw)
            d.line((cx, cy - q, cx, cy + q), fill=bg + (255,), width=lw)
        x0 += iw
    d.text((x0 - l, m + pady - t), txt, font=f, fill=fg + (255,))
    arr = np.array(im)
    _sc[k] = arr
    return arr

def stamp_sprite(txt, col):
    k = ("stamp", txt, col)
    if k in _sc: return _sc[k]
    f = font("anton", 120)
    l, t, r, b = f.getbbox(txt)
    tw, th = r - l, b - t
    px, py, m = 40, 26, 30
    w, h = tw + px * 2, th + py * 2
    im = Image.new("RGBA", (w + m * 2, h + m * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((m, m, m + w, m + h), 18, fill=col + (235,))
    d.rounded_rectangle((m + 10, m + 10, m + w - 10, m + h - 10), 12, outline=(255, 255, 255, 255), width=6)
    d.text((m + px - l, m + py - t), txt, font=f, fill=(255, 255, 255, 255))
    _sc[k] = np.array(im)
    return _sc[k]

# ---------- blit ----------
def blit(canvas, spr, cx, cy, scale=1.0, alpha=1.0, angle=0.0, reveal=1.0, reveal_from='center'):
    if alpha <= 0.003 or scale <= 0.01 or reveal <= 0.003: return
    if reveal < 1.0:
        spr = spr.copy(); w0 = spr.shape[1]; keep = int(w0 * reveal)
        if reveal_from == 'left': spr[:, keep:, 3] = 0
        else:
            a0 = (w0 - keep) // 2; spr[:, :a0, 3] = 0; spr[:, a0 + keep:, 3] = 0
    h, w = spr.shape[:2]
    if scale != 1.0 or angle != 0.0:
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
        cos, sin = abs(M[0, 0]), abs(M[0, 1])
        nw, nh = int(h * sin + w * cos) + 2, int(h * cos + w * sin) + 2
        M[0, 2] += nw / 2 - w / 2; M[1, 2] += nh / 2 - h / 2
        spr = cv2.warpAffine(spr, M, (nw, nh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        h, w = nh, nw
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    sx0, sy0 = max(0, -x0), max(0, -y0)
    dx0, dy0 = max(0, x0), max(0, y0)
    dx1, dy1 = min(W, x0 + w), min(H, y0 + h)
    if dx1 <= dx0 or dy1 <= dy0: return
    s = spr[sy0:sy0 + dy1 - dy0, sx0:sx0 + dx1 - dx0].astype(np.float32)
    a = s[..., 3:4] / 255.0 * alpha
    reg = canvas[dy0:dy1, dx0:dx1].astype(np.float32)
    canvas[dy0:dy1, dx0:dx1] = (reg * (1 - a) + s[..., :3] * a).astype(np.uint8)
