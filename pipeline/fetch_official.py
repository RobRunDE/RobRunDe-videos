"""Fetch official ROB RUN store media from Steam (app 4262460, Kefir) into official/ (git-ignored).

    python3 pipeline/fetch_official.py            # screenshots + header + trailers, contact sheet
    python3 pipeline/fetch_official.py --no-video # images only

Rights stay with Kefir: these files are NOT committed to the public repo, only downloaded per run.
Use them as supporting material (max ~20 % of a video), never instead of own gameplay, and never
in a way that makes @robrun_de look like the official channel.
Result: official/index.json with every file and its kind; official/sheet.jpg to look at.
"""
import json, os, subprocess, sys, urllib.request
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "official")
APP = "4262460"
UA = {"User-Agent": "curl/8.5.0"}

def get(url, path):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r, open(path, "wb") as f:
        f.write(r.read())

def main():
    os.makedirs(OUT, exist_ok=True)
    d = json.loads(urllib.request.urlopen(urllib.request.Request(
        f"https://store.steampowered.com/api/appdetails?appids={APP}&l=german", headers=UA), timeout=60).read())[APP]["data"]
    items = []
    get(d["header_image"], os.path.join(OUT, "header.jpg")); items.append({"file": "official/header.jpg", "kind": "key_art"})
    for i, s in enumerate(d.get("screenshots", []), 1):
        fn = f"screenshot_{i:02d}.jpg"; get(s["path_full"], os.path.join(OUT, fn))
        items.append({"file": f"official/{fn}", "kind": "screenshot"})
    if "--no-video" not in sys.argv:
        for i, m in enumerate(d.get("movies", []), 1):
            src = m.get("hls_h264") or m.get("dash_h264")
            if not src: continue
            fn = f"trailer_{i:02d}.mp4"
            r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-user_agent", UA["User-Agent"], "-i", src, "-map", "0:v:0", "-map", "0:a:0?",
                                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-vf", "scale=-2:1080", "-c:a", "aac", fn],
                               cwd=OUT, capture_output=True, text=True)
            if r.returncode == 0:
                items.append({"file": f"official/{fn}", "kind": "trailer", "name": m.get("name")})
            else:
                print("trailer failed:", m.get("name"), r.stderr[-300:])
    json.dump({"source": f"https://store.steampowered.com/app/{APP}/", "rights": "© Kefir – nur unterstützend, nicht ins Repo",
               "description": d.get("short_description"), "items": items}, open(os.path.join(OUT, "index.json"), "w"), ensure_ascii=False, indent=1)
    # contact sheet of the stills
    stills = [i for i in items if i["kind"] != "trailer"]
    W = 480; ims = []
    fnt = ImageFont.truetype(os.path.join(ROOT, "pipeline", "fonts", "Montserrat.ttf"), 22)
    for it in stills:
        im = Image.open(os.path.join(ROOT, it["file"])).convert("RGB"); im = im.resize((W, int(W * im.height / im.width)))
        ImageDraw.Draw(im).text((8, 6), os.path.basename(it["file"]), font=fnt, fill=(255, 220, 0), stroke_width=3, stroke_fill=(0, 0, 0))
        ims.append(im)
    cols = 3; h = max(i.height for i in ims); rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (W * cols, h * rows), (10, 10, 10))
    for k, im in enumerate(ims): sheet.paste(im, ((k % cols) * W, (k // cols) * h))
    sheet.save(os.path.join(OUT, "sheet.jpg"), quality=82)
    print(json.dumps(items, ensure_ascii=False))

if __name__ == "__main__":
    main()
