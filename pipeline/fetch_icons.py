"""ROB RUN item icons (weapons, gear, keys, loot ...) with transparent background.

Source: the fan wiki robrun.info (not affiliated with Kefir). The icons are Kefir's game images,
so they are NOT committed to the public repo: they are downloaded per run into official/icons/.
Use them for short item cards / overlays only, never mass-republished.

    python3 pipeline/fetch_icons.py --catalog            # refresh knowledge/item_catalog.json (id, name, category, rarity)
    python3 pipeline/fetch_icons.py lmg_m2 "LM 249 Mk2"  # download icons by id or (part of) name -> official/icons/<id>.png
    python3 pipeline/fetch_icons.py --sheet weapons      # contact sheet of a category -> official/icons/sheet_weapons.jpg
"""
import html, io, json, os, re, sys, urllib.request
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAT = os.path.join(ROOT, "knowledge", "item_catalog.json")
OUT = os.path.join(ROOT, "official", "icons")
BASE = "https://robrun.info"
UA = {"User-Agent": "curl/8.5.0"}
CATS = {"weapons": "Waffe", "ammo": "Munition", "gear": "Ausrüstung", "tools": "Werkzeug/Schlüssel", "vehicles": "Fahrzeug",
        "base": "Basis", "valuables": "Wertsache", "contraband": "Schmuggelware"}

def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()

def catalog():
    s = fetch(f"{BASE}/items/").decode("utf-8", "ignore")
    items = []
    for m in re.finditer(r'<a class="tile" href="/items/([a-z0-9_]+)/" style="--rare:(#[0-9a-fA-F]{6})" data-g="([a-z]+)" data-r="(\d+)" data-q="([^"]*)".*?<img src="([^"]+)".*?<strong>([^<]*)</strong>', s, re.S):
        iid, col, g, r, q, img, name = m.groups()
        name = html.unescape(name)
        items.append({"id": iid, "name": name, "name_is_russian": bool(re.search("[\u0400-\u04ff]", name)), "img": img, "category": g, "category_de": CATS.get(g, g), "rarity": int(r), "rarity_color": col})
    json.dump({"source": BASE + "/items/", "note": "Namen/IDs aus Fan-Wiki; Icons © Kefir, nicht ins Repo.", "items": items},
              open(CAT, "w"), ensure_ascii=False, indent=0)
    print(len(items), "items")

def load():
    if not os.path.exists(CAT): catalog()
    return json.load(open(CAT))["items"]

def find(q, items):
    q = q.lower()
    return [i for i in items if i["id"] == q] or [i for i in items if q in i["name"].lower() ]

def _upscale(im, target=300):
    """Small icons (~120 px) are upscaled 2x with the FSRCNN model (colour) + smooth alpha, then lightly sharpened."""
    import cv2, numpy as np
    if max(im.size) >= target: return im
    a = np.array(im); rgb, al = a[..., :3], a[..., 3]
    sr = cv2.dnn_superres.DnnSuperResImpl_create(); sr.readModel(os.path.join(ROOT, "pipeline", "models", "FSRCNN_x2.pb")); sr.setModel("fsrcnn", 2)
    while max(rgb.shape[:2]) < target:
        rgb = sr.upsample(np.ascontiguousarray(rgb)); al = cv2.resize(al, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_CUBIC)
    rgb = cv2.addWeighted(rgb, 1.4, cv2.GaussianBlur(rgb, (0, 0), 1.0), -0.4, 0)
    return Image.fromarray(np.dstack([rgb, al]), "RGBA")

def icon(iid):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, iid + ".png")
    if not os.path.exists(p):
        it = next((i for i in load() if i["id"] == iid), {})
        im = Image.open(io.BytesIO(fetch(BASE + it.get("img", f"/shared/items/{iid}.webp")))).convert("RGBA")
        _upscale(im).save(p)
    return p

def sheet(cat, items):
    sel = [i for i in items if i["category"] == cat]
    fnt = ImageFont.truetype(os.path.join(ROOT, "pipeline", "fonts", "Montserrat.ttf"), 16)
    cols, cw, ch = 6, 260, 170; rows = (len(sel) + cols - 1) // cols
    sh = Image.new("RGB", (cols * cw, max(1, rows) * ch), (14, 14, 20)); d = ImageDraw.Draw(sh)
    for k, it in enumerate(sel):
        try: im = Image.open(icon(it["id"]))
        except Exception: continue
        im.thumbnail((cw - 20, ch - 50)); x, y = (k % cols) * cw, (k // cols) * ch
        sh.paste(im, (x + (cw - im.width) // 2, y + 8), im)
        d.text((x + 8, y + ch - 38), f'{it["name"]}\n{it["id"]}', font=fnt, fill=it["rarity_color"])
    p = os.path.join(OUT, f"sheet_{cat}.jpg"); sh.save(p, quality=82); print(p)

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == "--catalog": catalog()
    elif a[0] == "--sheet": sheet(a[1], load())
    else:
        items = load()
        for q in a:
            hits = find(q, items)
            if not hits: print("nicht gefunden:", q); continue
            for it in hits[:3]: print(it["id"], "|", it["name"], "|", it["category_de"], "->", icon(it["id"]))
