#!/usr/bin/env python3
"""Rohmaterial anonymisieren: Spielername, Chat (fremde Namen) und Build-Nummer unkenntlich machen.

  python3 pipeline/anonymize.py <input> <raw/ausgabe_basis> [--max-mb 95] [--fps 30]

- Feste Bereiche (in 1920x1080-Koordinaten): Chat unten links, Spielername über der Lebensleiste, Build-Nummer oben links.
- Bewegliche Namensfelder (z. B. Besitzer unten in Kisten-/Lager-Panels) per Template-Matching.
  Templates liegen in work/private/*.png (NICHT im Repo – sie zeigen den Namen).
- Ausgabe: H.264 1080p, aufgeteilt in Teile < max-mb (raw/<basis>_p1.mp4 …).
- Danach Stichprobe per OCR (tesseract) auf Namensreste; Begriffe aus ROBRUN_HIDE_NAMES (kommagetrennt, Umgebung).
"""
import argparse, glob, os, subprocess, sys, json
import cv2, numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1920, 1080
FIXED = [  # x0, y0, x1, y1
    (0, 700, 440, 935),     # Chat (fremde Spielernamen, wächst nach oben)
    (55, 974, 330, 1005),   # eigener Spielername über der Lebensleiste
    (0, 0, 150, 20),        # Build-/Versionsnummer
]


def pixelate(img, x0, y0, x1, y1):
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.shape[1], x1), min(img.shape[0], y1)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return
    roi = img[y0:y1, x0:x1]
    small = cv2.resize(roi, (max(1, (x1 - x0) // 14), max(1, (y1 - y0) // 14)), interpolation=cv2.INTER_AREA)
    roi = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
    roi = cv2.GaussianBlur(roi, (0, 0), 6)
    img[y0:y1, x0:x1] = (roi * 0.75).astype(np.uint8)


def load_templates():
    ts = []
    for p in sorted(glob.glob(os.path.join(ROOT, "work", "private", "*.png"))):
        t = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if t is not None:
            ts.append(t)
    return ts


def process(inp, tmp_out, fps):
    ts = load_templates()
    print(f"{len(ts)} Namens-Templates", file=sys.stderr)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", inp, "-vf", f"scale={W}:{H}:flags=lanczos,fps={fps}",
                            "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-i", inp, "-map", "0:v", "-map", "1:a?",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", tmp_out],
                           stdin=subprocess.PIPE)
    hold = []  # [x0,y0,x1,y1,ttl]
    n = hits = 0
    fb = W * H * 3
    while True:
        buf = dec.stdout.read(fb)
        if len(buf) < fb:
            break
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
        if ts:
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            for t in ts:
                r = cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED)
                ys, xs = np.where(r >= 0.78)
                for y, x in list(zip(ys, xs))[:6]:
                    hold.append([x - 6, y - 4, x + t.shape[1] + 30, y + t.shape[0] + 4, int(fps * 0.4)])
                    hits += 1
        for b in hold:
            pixelate(img, *b[:4])
            b[4] -= 1
        hold = [b for b in hold if b[4] > 0][-40:]
        for b in FIXED:
            pixelate(img, *b)
        enc.stdin.write(img.tobytes())
        n += 1
    enc.stdin.close(); enc.wait(); dec.wait()
    print(f"{n} Frames, {hits} Namens-Treffer", file=sys.stderr)


def split(tmp_out, base, max_mb):
    size = os.path.getsize(tmp_out) / 1e6
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                         "-of", "csv=p=0", tmp_out]).decode())
    parts = max(1, int(np.ceil(size / (max_mb * 0.92))))
    outs = []
    if parts == 1:
        out = f"{base}.mp4"; os.replace(tmp_out, out); return [out]
    seg = dur / parts
    for i in range(parts):
        out = f"{base}_p{i+1}.mp4"
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-ss", f"{i*seg:.3f}", "-i", tmp_out, "-t", f"{seg:.3f}",
                               "-c", "copy", "-movflags", "+faststart", out])
        outs.append(out)
    os.remove(tmp_out)
    return outs


def ocr_check(path, step=2.0):
    names = [s.strip().lower() for s in os.environ.get("ROBRUN_HIDE_NAMES", "").split(",") if s.strip()]
    if not names:
        return []
    found = []
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                         "-of", "csv=p=0", path]).decode())
    t = 0.5
    while t < dur:
        png = "/tmp/_anon_chk.png"
        subprocess.call(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", png])
        txt = subprocess.run(["tesseract", png, "-", "--psm", "11"], capture_output=True, text=True).stdout.lower()
        for nm in names:
            if nm in txt.replace(" ", ""):
                found.append(round(t, 1))
        t += step
    return found


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("base")
    ap.add_argument("--max-mb", type=float, default=95); ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    tmp = a.base + ".part.mp4"
    process(a.inp, tmp, a.fps)
    outs = split(tmp, a.base, a.max_mb)
    for o in outs:
        bad = ocr_check(o)
        print(json.dumps({"file": os.path.relpath(o, ROOT), "mb": round(os.path.getsize(o) / 1e6, 1),
                          "name_seen_at": bad}))
