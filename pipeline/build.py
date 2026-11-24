"""Build a finished 9:16 short from a JSON spec.

    python3 pipeline/build.py plan/<week>/<slug>.json            # full render -> videos/<file>.mp4
    python3 pipeline/build.py plan/<week>/<slug>.json --preview 1.0 4.2 9.8   # stills -> work/<slug>/prev_*.jpg

Spec (see plan/EXAMPLE_SPEC.json):
{
  "slug": "LOOT_VERLIEREN", "version": 1,
  "hook": {"lines": ["3 FEHLER,", "DIE DICH ARM MACHEN"], "accent": ["ARM"]},
  "keywords": {"GELD": "green", "ARM": "red"},          # caption word colours
  "beats": [
    {"text": "Spoken sentence(s).",                     # voice-over for this beat
     "header": "FEHLER 1", "progress": [1, 3],          # optional: new top title (+ progress pips)
     "shots": [{"clip": "raw/x.mp4", "in": 12.0, "focus": 0.5, "w": 1}],   # focus = horizontal crop centre 0..1
     "chip": {"text": "GELD SICHTBAR", "kind": "bad|good|info", "at": 0.2},  # optional label above gameplay
     "stamp": {"text": "EINBRUCH-ZIEL", "at": 1.0},       # optional stamp on gameplay (at = s after beat start)
     "cta": false}                                        # true on the last beat: follow button + title
  ]
}
Everything visual is soft and varied on purpose: no punch zooms, no shakes.
"""
import json, math, os, subprocess, sys, wave
import cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from motion import *          # noqa
from motion import _sc
from tts import make_voiceover

CARD_W, CARD_H, CARD_X, CARD_Y = 1080, 1000, 0, 430
HDR_Y, CHIP_Y, CAP_Y = 250, CARD_Y, CARD_Y + CARD_H - 92
# Looks that rotate between videos so the feed never looks the same.
THEMES = {"yellow": (255, 214, 10), "cyan": (40, 220, 255), "lime": (170, 255, 60), "orange": (255, 140, 30),
          "pink": (255, 70, 160), "white": (255, 255, 255)}
LAYOUTS = {"standard": (430, 1000), "tall": (380, 1140), "compact": (500, 900)}
ACC = (255, 214, 10)

def configure(spec):
    """Apply per-video look: spec["theme"] (accent colour) and spec["layout"]."""
    global CARD_Y, CARD_H, CHIP_Y, CAP_Y, HDR_Y, ACC, CAPBAND
    CARD_Y, CARD_H = LAYOUTS.get(spec.get("layout", "standard"), LAYOUTS["standard"])
    HDR_Y = CARD_Y - 180; CHIP_Y = CARD_Y; CAP_Y = CARD_Y + CARD_H - 92
    ACC = THEMES.get(spec.get("theme", "yellow"), THEMES["yellow"])
    r = np.arange(CARD_H, dtype=np.float32)
    CAPBAND = (1 - 0.45 * np.exp(-((r - (CAP_Y - CARD_Y)) / 62.0) ** 2))[:, None, None]
COLORS = {"accent": None, "green": GRN, "red": RED, "yellow": YEL, "purple": PUR, "gold": GLD, "white": WHT}
KIND = {"bad": (RED, "x"), "good": ((22, 170, 90), "check"), "info": ((200, 150, 0), "up"), "neutral": ((30, 30, 36), None)}
SR = None

def sr():
    global SR
    if SR is None:
        SR = cv2.dnn_superres.DnnSuperResImpl_create(); SR.readModel(os.path.join(HERE, "models", "FSRCNN_x2.pb")); SR.setModel("fsrcnn", 2)
    return SR

def clip_path(c): return c if os.path.isabs(c) else os.path.join(ROOT, c)

def probe(p):
    o = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", p], capture_output=True, text=True).stdout)
    v = next(s for s in o["streams"] if s["codec_type"] == "video")
    return v["width"], v["height"], float(o["format"]["duration"]), any(s["codec_type"] == "audio" for s in o["streams"])

# ---------------------------------------------------------------- timeline
def plan_timeline(spec, workdir):
    vo = make_voiceover([b["text"] for b in spec["beats"]], os.path.join(workdir, "vo.wav"))
    dur = vo["duration"] + 0.6
    shots, events = [], []
    for i, (b, bi) in enumerate(zip(spec["beats"], vo["beats"])):
        a = bi["start"] if i else 0.0
        e = vo["beats"][i + 1]["start"] if i + 1 < len(vo["beats"]) else dur
        ws = [s.get("w", 1) for s in b["shots"]]; tot = sum(ws); t = a
        for s, w in zip(b["shots"], ws):
            d = (e - a) * w / tot
            shots.append({**s, "t0": t, "t1": t + d}); t += d
        b["_t0"], b["_t1"] = a, e
    return vo, dur, shots

# ---------------------------------------------------------------- frames
class ShotReader:
    """Streams frames of one shot, cropped to the card aspect around `focus`."""
    def __init__(self, shot, idx):
        p = clip_path(shot["clip"]); w, h, d, _ = probe(p)
        ar = CARD_W / CARD_H
        ch = h; cw = int(round(ch * ar))
        if cw > w: cw = w; ch = int(round(cw / ar))
        fx = shot.get("focus", 0.5); x0 = int(clamp(fx * w - cw / 2, 0, w - cw)); y0 = (h - ch) // 2
        self.cw, self.ch = cw - cw % 2, ch - ch % 2
        self.n = self.cw * self.ch * 3
        tin = min(shot.get("in", 0.0), max(0, d - (shot["t1"] - shot["t0"]) - 0.05))
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{tin:.3f}", "-i", p, "-vf",
                                   f"crop={self.cw}:{self.ch}:{x0}:{y0},fps={FPS}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                  stdout=subprocess.PIPE)
        self.last = None; self.style = idx % 4
        self.up = self.cw < CARD_W * 0.8
    def next(self):
        b = self.p.stdout.read(self.n)
        if len(b) == self.n: self.last = np.frombuffer(b, np.uint8).reshape(self.ch, self.cw, 3)
        return self.last
    def close(self):
        try: self.p.kill()
        except Exception: pass

def camera(style, u):
    u = esin(u)
    if style == 0: return 1.0 + 0.035 * u, 0.0
    if style == 1: return 1.035 - 0.035 * u, 0.0
    if style == 2: return 1.035, -14 + 28 * u
    return 1.0, 0.0

yy, xx = np.mgrid[0:H, 0:W]
VIGN = (1 - 0.55 * np.clip(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2, 0, 1)).astype(np.float32)[..., None]
_r = np.arange(CARD_H, dtype=np.float32)
CAPBAND = (1 - 0.45 * np.exp(-((_r - (CAP_Y - CARD_Y)) / 62.0) ** 2))[:, None, None]

def compose_card(src, style, u, reader):
    z, dx = camera(style, u)
    img = sr().upsample(src) if reader.up else src
    if reader.up: img = cv2.addWeighted(img, 1.5, cv2.GaussianBlur(img, (0, 0), 1.1), -0.5, 0)
    ih, iw = img.shape[:2]; cw, ch = iw / z, ih / z
    cx = clamp(iw / 2 + dx * iw / CARD_W, cw / 2, iw - cw / 2); cy = ih / 2
    sx, sy = CARD_W / cw, CARD_H / ch
    M = np.float32([[sx, 0, -(cx - cw / 2) * sx], [0, sy, -(cy - ch / 2) * sy]])
    card = cv2.warpAffine(img, M, (CARD_W, CARD_H), flags=cv2.INTER_AREA if sx < 1 else cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    return card

def background(card):
    small = cv2.resize(card, (68, 63), interpolation=cv2.INTER_AREA)
    bg = cv2.resize(cv2.GaussianBlur(cv2.resize(small, (W // 8, H // 8)), (0, 0), 3), (W, H)).astype(np.float32)
    return (bg * 0.22 * VIGN).astype(np.uint8)

# ---------------------------------------------------------------- overlays
class Overlay:
    def __init__(self, spec, vo, dur):
        self.spec, self.vo, self.dur = spec, vo, dur
        kw = {k.upper(): (COLORS.get(v) or ACC) for k, v in spec.get("keywords", {}).items()}
        self.kw = kw
        # caption groups
        groups, cur = [], []
        for w in vo["words"]:
            cur.append(w); txt = " ".join(self.clean(x[2]) for x in cur)
            if w[2][-1] in ".,?!:;" or len(cur) >= 3 or len(txt) >= 14: groups.append(cur); cur = []
        if cur: groups.append(cur)
        self.G = []
        for i, g in enumerate(groups):
            nxt = groups[i + 1][0][0] if i + 1 < len(groups) else dur
            self.G.append((g[0][0], min(nxt, g[-1][1] + 0.45), g))
        # headers
        self.headers = [(0.0, "hook", None)]
        for b in spec["beats"]:
            if b.get("cta"): self.headers.append((b["_t0"], "cta", None))
            elif b.get("header"): self.headers.append((b["_t0"], b["header"], b.get("progress")))
        self.chips, self.stamps = [], []
        for b in spec["beats"]:
            if b.get("chip"):
                c = b["chip"]; self.chips.append((c["text"], c.get("kind", "info"), b["_t0"] + c.get("at", 0.15), b["_t1"] - 0.1))
            if b.get("stamp"):
                s = b["stamp"]; t = b["_t0"] + s.get("at", 0.4); self.stamps.append((s["text"], t, min(t + 1.3, b["_t1"])))
        self.cta_t = next((b["_t0"] for b in spec["beats"] if b.get("cta")), None)

    @staticmethod
    def clean(t): return t.upper().strip(".,!?:;\"'()")

    def header_at(self, t):
        cur, idx = self.headers[0], 0
        for i, h in enumerate(self.headers):
            if t >= h[0]: cur, idx = h, i
        return cur, idx

    def draw(self, cv, t):
        self.draw_header(cv, t); self.draw_stamps(cv, t); self.draw_chips(cv, t); self.draw_cta(cv, t); self.draw_caps(cv, t)

    def dim(self, t):
        for st, kind, _ in self.headers[1:]:
            dt = t - st
            if kind != "cta" and 0 <= dt < 0.75: return 0.4 * esin(dt / 0.15) * (1 - esin((dt - 0.4) / 0.35))
        return 0.0

    def draw_header(self, cv, t):
        (st, kind, prog), idx = self.header_at(t)
        if kind == "hook":
            lines = self.spec.get("hook", {}).get("lines", [])
            acc = {a.upper() for a in self.spec.get("hook", {}).get("accent", [])}
            if not lines: return
            tt = t + 0.25; a1 = eout(tt / 0.4)
            blit(cv, text_sprite(lines[0], "anton", 150 if len(lines[0]) < 14 else 112, ACC), W / 2, HDR_Y - 45 - 30 * (1 - a1), alpha=clamp(tt / 0.25))
            if len(lines) > 1:
                parts = lines[1].split(); sprs = [text_sprite(p, "anton", 88 if len(lines[1]) < 22 else 70, RED if self.clean(p) in acc else WHT) for p in parts]
                gap = -22; tot = sum(s.shape[1] for s in sprs) + gap * (len(sprs) - 1); x = W / 2 - tot / 2
                for k, s in enumerate(sprs):
                    ts = 0.35 + 0.12 * k; a = eout((tt - ts) / 0.3)
                    blit(cv, s, x + s.shape[1] / 2, HDR_Y + 75 + 20 * (1 - a), alpha=clamp((tt - ts) / 0.2))
                    x += s.shape[1] + gap
            return
        if kind == "cta":
            a = eout((t - st) / 0.45)
            blit(cv, text_sprite(self.spec.get("cta_title", "FOLG FÜR MEHR"), "anton", 140 if len(self.spec.get("cta_title", "FOLG FÜR MEHR")) < 15 else 100, ACC), W / 2, HDR_Y, alpha=a, reveal=a)
            return
        spr = text_sprite(kind, "anton", 150 if len(kind) < 12 else 110, ACC)
        dt = t - st; style = idx % 3
        if dt < 0.75:
            mv = esin((dt - 0.42) / 0.33); cy = 900 + (HDR_Y - 900) * mv; sc = 1.3 - 0.3 * mv
            if style == 1: blit(cv, spr, W / 2, cy, scale=sc, reveal=eout(dt / 0.3), reveal_from='left')
            elif style == 2: blit(cv, spr, W / 2 + 260 * (1 - eout(dt / 0.32)), cy, scale=sc, alpha=clamp(dt / 0.2))
            else: blit(cv, spr, W / 2, cy, scale=sc, reveal=eout(dt / 0.32))
        else:
            blit(cv, spr, W / 2, HDR_Y, scale=1.0)
        if prog:
            n, tot = prog
            for i in range(tot):
                k = ("pip", i < n, ACC)
                if k not in _sc:
                    im = Image.new("RGBA", (70, 30), (0, 0, 0, 0))
                    ImageDraw.Draw(im).rounded_rectangle((6, 7, 64, 23), 8, fill=(ACC + (255,)) if i < n else (255, 255, 255, 70))
                    _sc[k] = np.array(im)
                blit(cv, _sc[k], W / 2 + (i - (tot - 1) / 2) * 70, HDR_Y + 105, alpha=eout((dt - 0.5 - i * 0.05) / 0.25))

    def draw_chips(self, cv, t):
        for txt, kind, ti, to in self.chips:
            if not (ti <= t < to): continue
            col, ic = KIND.get(kind, KIND["info"])
            a = eout((t - ti) / 0.32); out = esin((t - (to - 0.22)) / 0.22); al = clamp((t - ti) / 0.15) * (1 - out)
            spr = pill_sprite(txt, col, icon=ic, size=44)
            if kind == "bad": blit(cv, spr, W / 2 - 140 * (1 - a), CHIP_Y, alpha=al)
            elif kind == "good": blit(cv, spr, W / 2, CHIP_Y, alpha=al, reveal=a)
            else: blit(cv, spr, W / 2, CHIP_Y + 26 * (1 - a), alpha=al)

    def draw_stamps(self, cv, t):
        for i, (txt, ti, to) in enumerate(self.stamps):
            if not (ti <= t < to): continue
            dt = t - ti; a = eout(dt / 0.3); out = esin((t - (to - 0.2)) / 0.2); ang = -5 if i % 2 == 0 else 5
            blit(cv, stamp_sprite(txt, RED), W / 2, CARD_Y + CARD_H * 0.45 - 30 * (1 - a), scale=1.08 - 0.08 * a, alpha=clamp(dt / 0.18) * (1 - out), angle=ang * a)

    def draw_cta(self, cv, t):
        if self.cta_t is None or t < self.cta_t + 0.25: return
        t0 = self.cta_t + 0.25; a = eout((t - t0) / 0.4)
        br = 1 + 0.025 * math.sin((t - t0) * 4) * clamp((t - t0 - 0.4) / 0.4)
        blit(cv, pill_sprite(self.spec.get("cta_button", "FOLGEN"), (255, 44, 85), icon="plus", size=58, padx=44, pady=22), W / 2, CHIP_Y + 20 * (1 - a), scale=br, alpha=a)
        q = self.spec.get("cta_prompt")      # e.g. "SCHREIB DEINEN FEHLER IN DIE KOMMENTARE"
        if q and t >= t0 + 0.6:
            b = eout((t - t0 - 0.6) / 0.4)
            blit(cv, pill_sprite(q, (24, 24, 30), fg=ACC, size=36, padx=26, pady=14), W / 2, CARD_Y + CARD_H * 0.3 + 24 * (1 - b), alpha=b)

    def draw_caps(self, cv, t):
        for gi, (st, en, g) in enumerate(self.G):
            if not (st - 0.02 <= t < en): continue
            style = gi % 3
            rise = 22 * (1 - eout((t - st) / 0.22)) if style == 0 else 0
            fade = clamp((t - st) / 0.14) * (1 - clamp((t - (en - 0.08)) / 0.08))
            sprs = []
            for s, e, wd in g:
                c = self.clean(wd); active = s <= t < max(e, s + 0.12)
                col = self.kw.get(c, ACC if active else WHT)
                sprs.append((text_sprite(c, "black", 80, col, stroke=9), active, s))
            gap = -36; tot = sum(s.shape[1] for s, _, _ in sprs) + gap * (len(sprs) - 1)
            sc0 = min(1.0, 820 / tot); x = W / 2 - tot * sc0 / 2
            for wi, (spr, active, s) in enumerate(sprs):
                wd = spr.shape[1] * sc0
                wa = fade * (0.25 + 0.75 * eout((t - s + 0.04) / 0.14)) if style == 1 else fade
                lift = 5 * eout((t - s) / 0.12) if active else 0
                if style == 2:
                    rv = eout((t - st) / 0.28)
                    blit(cv, spr, x + wd / 2, CAP_Y - lift, scale=sc0, alpha=wa, reveal=clamp(rv * len(sprs) - wi), reveal_from='left')
                else:
                    blit(cv, spr, x + wd / 2, CAP_Y - lift + rise, scale=sc0, alpha=wa)
                x += wd + gap * sc0
            break

# ---------------------------------------------------------------- audio
def synth_sfx(events, dur, out):
    srate = 48000; n = int(srate * dur); bus = np.zeros(n, np.float32); rng = np.random.default_rng(3)
    def add(sig, t, g):
        i = int(t * srate); j = min(n, i + len(sig))
        if 0 <= i < n: bus[i:j] += sig[:j - i] * g
    def pop(f0, f1, d=0.07):
        m = int(srate * d); tt = np.arange(m) / srate; ph = 2 * np.pi * np.cumsum(np.linspace(f0, f1, m)) / srate
        return (np.sin(ph) * np.exp(-tt * 45)).astype(np.float32)
    def whoosh(d=0.5):
        m = int(srate * d); x = rng.standard_normal(m).astype(np.float32)
        sp = np.fft.rfft(x); f = np.fft.rfftfreq(m, 1 / srate); sp *= np.exp(-((f - 1800) / 1400) ** 2); y = np.fft.irfft(sp, m)
        env = np.sin(np.pi * np.linspace(0, 1, m)) ** 2; y = y * env; return (y / (np.abs(y).max() + 1e-9)).astype(np.float32)
    def thump(d=0.35):
        m = int(srate * d); tt = np.arange(m) / srate; ph = 2 * np.pi * np.cumsum(70 * np.exp(-tt * 5) + 45) / srate
        return (np.sin(ph) * np.exp(-tt * 9)).astype(np.float32)
    for kind, t in events:
        if kind == "whoosh": add(whoosh(), t - 0.2, 0.16)
        elif kind == "pop": add(pop(520, 820), t, 0.22)
        elif kind == "pop_good": add(pop(660, 990), t, 0.2)
        elif kind == "stamp": add(thump(), t, 0.35)
        elif kind == "cta": add(pop(600, 1200, 0.1), t, 0.22)
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(srate); w.writeframes((np.clip(bus, -1, 1) * 32767).astype(np.int16).tobytes())

def game_audio(shots, dur, out):
    """Gameplay sound under the voice, from the same moments that are on screen."""
    args, filt = [], []
    for k, s in enumerate(shots):
        p = clip_path(s["clip"]); has_a = probe(p)[3]; d = s["t1"] - s["t0"]
        if has_a:
            args += ["-ss", f"{s.get('in', 0):.3f}", "-t", f"{d:.3f}", "-i", p]
        else:
            args += ["-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        filt.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={d:.3f},atrim=0:{d:.3f}[a{k}]")
    filt.append("".join(f"[a{k}]" for k in range(len(shots))) + f"concat=n={len(shots)}:v=0:a=1,apad=whole_dur={dur:.3f}[g]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", ";".join(filt), "-map", "[g]", "-t", f"{dur:.3f}", out], check=True)

# ---------------------------------------------------------------- main
def build(spec_path, preview=None):
    spec = json.load(open(spec_path))
    configure(spec)
    slug = spec["slug"]; ver = spec.get("version", 1)
    wd = os.path.join(ROOT, "work", slug); os.makedirs(wd, exist_ok=True)
    vo, dur, shots = plan_timeline(spec, wd)
    ov = Overlay(spec, vo, dur)
    nf = int(dur * FPS)
    out_v = os.path.join(wd, "video_tmp.mp4")
    enc = None
    if not preview:
        enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out_v], stdin=subprocess.PIPE)
    want = sorted(preview or [])
    si, rd = 0, None
    for fi in range(nf):
        t = fi / FPS
        while si < len(shots) - 1 and t >= shots[si]["t1"]: si += 1
        if rd is None or rd.idx != si:
            if rd: rd.close()
            rd = ShotReader(shots[si], si); rd.idx = si
        src = rd.next()
        if preview and not any(abs(t - w) < 0.5 / FPS for w in want):
            continue
        s = shots[si]; u = (t - s["t0"]) / max(0.3, s["t1"] - s["t0"])
        card = compose_card(src, rd.style, u, rd).astype(np.float32)
        card = np.clip((card - 128) * 1.06 + 130, 0, 255) * CAPBAND
        d = ov.dim(t)
        if d: card *= (1 - d)
        cv = background(card.astype(np.uint8))
        cv[CARD_Y:CARD_Y + CARD_H] = card.astype(np.uint8)
        ov.draw(cv, t)
        if preview:
            Image.fromarray(cv).save(os.path.join(wd, f"prev_{t:05.2f}.jpg"), quality=88)
            if t > want[-1]: break
        else:
            enc.stdin.write(cv.tobytes())
    if rd: rd.close()
    if preview: return None
    enc.stdin.close(); enc.wait()
    assert enc.returncode == 0
    # audio: voice + quiet gameplay + soft sfx
    ev = [("whoosh", h[0]) for h in ov.headers[1:]] + [("pop" if c[1] == "bad" else "pop_good", c[2]) for c in ov.chips] + [("stamp", s[1]) for s in ov.stamps]
    if ov.cta_t is not None: ev.append(("cta", ov.cta_t + 0.25))
    synth_sfx(ev, dur, os.path.join(wd, "sfx.wav")); game_audio(shots, dur, os.path.join(wd, "game.wav"))
    mix = os.path.join(wd, "mix.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(wd, "vo.wav"), "-i", os.path.join(wd, "game.wav"), "-i", os.path.join(wd, "sfx.wav"),
                    "-filter_complex", "[0:a]aresample=48000,aformat=channel_layouts=stereo,apad[v];[1:a]volume=0.13[g];[2:a]aformat=channel_layouts=stereo[s];"
                    "[v][g][s]amix=inputs=3:normalize=0:duration=first,loudnorm=I=-14:TP=-2:LRA=11,aresample=48000[a]",
                    "-map", "[a]", "-t", f"{dur:.3f}", mix], check=True)
    os.makedirs(os.path.join(ROOT, "videos"), exist_ok=True)
    final = os.path.join(ROOT, "videos", f"ROB_RUN_{slug}_v{ver:02d}.mp4")
    tmp = final.replace(".mp4", ".part.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out_v, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-ar", "48000", "-shortest", "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, final)
    return final

if __name__ == "__main__":
    a = sys.argv[1:]
    if "--preview" in a:
        i = a.index("--preview"); build(a[0], [float(x) for x in a[i + 1:]]); print("previews in work/")
    else:
        print(build(a[0]))
