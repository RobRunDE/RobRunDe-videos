"""Index raw gameplay clips in raw/ into index/clips.json.

For every clip not yet indexed it stores technical data, detected shot cuts and
a contact sheet (index/sheets/<clip>.jpg, one frame every `step` seconds with
timestamps). The agent then LOOKS at each sheet and fills in "tags",
"summary" and "moments" (start/end/what/quality) by editing clips.json.

    python3 pipeline/index_clips.py            # index new clips
    python3 pipeline/index_clips.py --todo     # list clips still missing tags
"""
import cv2, json, os, subprocess, sys, numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, IDX = os.path.join(ROOT, "raw"), os.path.join(ROOT, "index")
FONT = os.path.join(ROOT, "pipeline", "fonts", "Montserrat.ttf")
DB = os.path.join(IDX, "clips.json")

def probe(p):
    o = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", p],
                                  capture_output=True, text=True).stdout)
    v = next(s for s in o["streams"] if s["codec_type"] == "video")
    n, d = v["r_frame_rate"].split("/")
    return {"duration": round(float(o["format"]["duration"]), 2), "width": v["width"], "height": v["height"],
            "fps": round(float(n) / float(d), 2), "has_audio": any(s["codec_type"] == "audio" for s in o["streams"])}

def cuts_and_sheet(p, name, step):
    cap = cv2.VideoCapture(p); fps = cap.get(cv2.CAP_PROP_FPS) or 30
    prev, diffs, thumbs, i = None, [], [], 0
    nextt = 0.0
    while True:
        ok, f = cap.read()
        if not ok: break
        t = i / fps
        g = cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (64, 36)).astype(np.float32)
        diffs.append(0 if prev is None else float(np.abs(g - prev).mean())); prev = g
        if t >= nextt:
            thumbs.append((t, cv2.cvtColor(cv2.resize(f, (320, int(320 * f.shape[0] / f.shape[1]))), cv2.COLOR_BGR2RGB)))
            nextt += step
        i += 1
    d = np.array(diffs); cuts = [0.0]
    for k in range(1, len(d)):
        if d[k] > 16 and d[k] > 3 * np.median(d[max(0, k - 10):k + 10]) and k / fps - cuts[-1] > 0.4:
            cuts.append(round(k / fps, 2))
    # contact sheet, 6 per row, with timestamps
    cols = 6; th = thumbs[0][1].shape[0] if thumbs else 180
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 320, max(1, rows) * (th + 26)), (15, 15, 15))
    dr = ImageDraw.Draw(sheet); fnt = ImageFont.truetype(FONT, 18)
    for k, (t, im) in enumerate(thumbs):
        x, y = (k % cols) * 320, (k // cols) * (th + 26)
        sheet.paste(Image.fromarray(im), (x, y + 26))
        dr.text((x + 6, y + 3), f"{name}  {t:.1f}s", font=fnt, fill=(255, 220, 0))
    os.makedirs(os.path.join(IDX, "sheets"), exist_ok=True)
    out = os.path.join(IDX, "sheets", name + ".jpg")
    sheet.save(out, quality=80)
    return cuts, os.path.relpath(out, ROOT)

def main():
    db = json.load(open(DB)) if os.path.exists(DB) else {}
    if "--todo" in sys.argv:
        for k, v in db.items():
            if not v.get("tags"): print(k, v["sheet"])
        return
    for fn in sorted(os.listdir(RAW)):
        if not fn.lower().endswith((".mp4", ".mov", ".mkv", ".webm")) or fn in db: continue
        p = os.path.join(RAW, fn)
        meta = probe(p)
        step = 1.0 if meta["duration"] <= 60 else 2.0
        cuts, sheet = cuts_and_sheet(p, fn, step)
        db[fn] = {**meta, "path": f"raw/{fn}", "cuts": cuts, "sheet": sheet, "sheet_step_s": step,
                  "tags": [], "summary": "", "moments": [], "used_in": []}
        print("indexed", fn, meta)
    json.dump(db, open(DB, "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
