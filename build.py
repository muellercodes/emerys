#!/usr/bin/env python3
"""
Builds the "What we carry" page for Emery's Meat & Produce, Brewer.

Source of truth is the Notion catalogue. With NOTION_TOKEN and NOTION_DATA_SOURCE_ID
set, rows and photos come from Notion. Without them it falls back to demo_data.py so the
page can be previewed anywhere.

    python build.py            -> dist/index.html, dist/photos/*.jpg

Rules the page follows (see README):
  - Prices, PLU, scale keys, nutrition estimates flagged as staff notes, and the Notes
    column never reach the page.
  - Rows with Status "Ask management" show the name only. Flip the status and the
    description appears on the next build.
  - Sentences written staff-to-staff are filtered out. A "Customer answer" column would
    be the proper fix.
"""
import os, re, io, json, html, sys

import brands

OUT = os.environ.get("OUT_DIR", "dist")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATA_SOURCE = os.environ.get("NOTION_DATA_SOURCE_ID")
BRANDS_SOURCE = os.environ.get("NOTION_BRANDS_DATA_SOURCE_ID")
SITE_DOMAIN = os.environ.get("SITE_DOMAIN", "")   # set it and the build writes a CNAME file
SHOP_CODE = os.environ.get("SHOP_CODE", "")       # unlocks prices on the scale trainer
# Search engines are kept off until the site is on the shop's own domain, so a trial copy on a
# github.io address never shows up in results for the shop.
ROBOTS = "" if SITE_DOMAIN else '<meta name="robots" content="noindex">\n'
NOTION_VERSION = "2025-09-03"

# ---------- read from Notion ----------
def notion_rows():
    import requests
    url = f"https://api.notion.com/v1/data_sources/{DATA_SOURCE}/query"
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": NOTION_VERSION, "Content-Type": "application/json"}
    pages, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(url, headers=headers, json=body, timeout=60)
        r.raise_for_status()
        d = r.json()
        pages += d["results"]
        if not d.get("has_more"):
            break
        cursor = d["next_cursor"]
    return [normalize(p["properties"]) for p in pages]

def _text(prop):
    t = prop.get("type")
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in prop.get(t, [])).strip()
    return ""

def _select(prop):
    v = prop.get("select")
    return v["name"] if v else ""

def _files(prop):
    out = []
    for f in prop.get("files", []):
        u = f.get("file", {}).get("url") or f.get("external", {}).get("url")
        if u:
            out.append(u)
    return out

def normalize(P):
    g = lambda k: P.get(k, {})
    return {
        "name": _text(g("Name")), "cat": _select(g("Category")), "aka": _text(g("Also called")),
        "src": _text(g("Brand / source")), "what": _text(g("What it is")), "how": _text(g("How to cook")),
        "taste": _text(g("Taste")), "ask": _text(g("Customer questions")), "fact": _text(g("Fact")),
        "try": _text(g("Recipe")), "status": _select(g("Status")),
        "price": g("Price").get("number"), "unit": _select(g("Unit")), "price_notes": _text(g("Price notes")),
        "nutrition": _text(g("Nutrition")), "nutrition_source": _select(g("Nutrition source")),
        "ingredients": _text(g("Ingredients & allergens")), "photos": _files(g("Photo")),
        "show_price": bool(g("Show price").get("checkbox")),
        "sale_price": g("Sale price").get("number"),
        "sale_until": ((g("Sale until").get("date") or {}).get("start") or "")[:10],
        "sale_note": _text(g("Sale note")),
        "scale": _select(g("Scale")), "plu": g("PLU").get("number"),   # scale trainer only
    }

# ---------- fallback: the snapshot in demo_data.py ----------
def demo_rows():
    from demo_data import ROWS, PRICES, NUTRITION
    out = []
    for r in ROWS:
        name = r["n"].replace(" (frozen bulk)", "")
        pr = PRICES.get(name)
        if pr and pr[2] == "bag" and r["c"] != "Frozen & bulk":
            pr = None
        row = {"name": r["n"], "cat": r["c"], "aka": r.get("a", ""), "src": r.get("s", ""), "what": r.get("w", ""),
               "how": r.get("h", ""), "taste": r.get("t", ""), "ask": r.get("q", ""), "fact": r.get("f", ""),
               "try": r.get("r", ""), "status": r.get("st", ""), "price": pr[0] if pr else None,
               "unit": ("bag" if pr and pr[2] == "bag" else "lb") if pr else "",
               "price_notes": (f"per {pr[1]}; {pr[3]}" if pr and pr[2] == "bag" else (f"bulk primal. {pr[3]}" if pr else "")),
               "nutrition": NUTRITION.get(name, ""), "nutrition_source": "USDA typical" if name in NUTRITION else "",
               "ingredients": "", "photos": [],
               "show_price": False, "sale_price": None, "sale_until": "", "sale_note": ""}
        out.append(row)
    return out

UNVERIFIED = ("Ask management",)   # rows with this status show the name only
# Shelf-survey rows that stand in for a product nobody could read yet ("Unread cut cheese
# wedges, Meat Cave dairy rack", "Chest 1: far-left basket, ..."). Staff bookkeeping, not
# products, so they stay off the site until the row is renamed to the real product.
PLACEHOLDER_ROW = re.compile(r"\bunread|^(chest|upright) \d", re.I)

# ---------- public filter ----------
STAFF = re.compile(r"\$|confirm|\bask\b|\bsell\b|steer|find out|if they|they want|they'll|\bscale\b|\bkey\b|cave sheet|primal sheet|handwritten|treat as|my reading|which\?|before promising|^see |case tag|\bcustomer\b", re.I)
PAREN = re.compile(r"\s*\([^)]*(\$|cave sheet|\bkey\b|\bscale\b|allergen|which\?|Sept 20\d\d)[^)]*\)", re.I)

def clean(text):
    if not text:
        return ""
    text = PAREN.sub("", text)
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(p for p in parts if p and not STAFF.search(p)).strip()

PRICE_STAFF = re.compile(r"confirm|\bask\b|\bsell\b|find out|\bkey\b|seems high|not yet recorded|which key", re.I)
def clean_sale_note(text):
    """Price notes legitimately contain dollar signs, so they get a lighter filter."""
    if not text:
        return ""
    text = PAREN.sub("", text)
    text = re.sub(r"(?i)^(cave sheet|primal sheet)\s*:\s*", "", text.strip())
    text = re.sub(r"(?i)\s+on the (cave|primal) sheet", "", text)
    parts = [p for p in re.split(r"(?<=[.!?;])\s+", text) if p and not PRICE_STAFF.search(p)]
    out = " ".join(parts).strip()
    return out[:1].upper() + out[1:] if out else ""

def source(s):
    if not s:
        return ""
    s = re.sub(r"\s*\([^)]*\)", "", s).strip()
    if "unknown" in s.lower() or "?" in s or "house name" in s.lower():
        return ""
    return s.replace("Emery's cut", "Cut in house").replace("Emery's house grind", "Ground in house").replace("Emery's house", "Made in house")

def today():
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date()
    except Exception:
        return datetime.now().date()

def sale_info(r):
    """Returns (sale price, unit, note, regular price or None) when a sale is on, else None."""
    if r.get("sale_price") is None:
        return None
    if r.get("sale_until") and r["sale_until"] < today().isoformat():
        return None
    unit = _unit(r)
    if unit == "bag":
        m = re.search(r"per ((?:\d+(?:\.\d+)? )?lb bag)", r["price_notes"] or "", re.I)
        unit = m.group(1) if m else "bag"
    was = r["price"] if (r["price"] is not None and r.get("show_price")) else None
    return (r["sale_price"], unit, clean_sale_note(r.get("sale_note", "")).rstrip("."), was)

# Price notes are mostly staff bookkeeping: where a price was read ("Pork board, Sept 11
# 2026: ..."), doubts ("looks high", "mis-stickered"), cave sheet primal prices. Customers
# only get the parts that tell them something about buying: bag sizes, 5 lb tiers, per-unit.
PRICE_NOTE_PAREN = re.compile(r"\s*\([^)]*\)")
PRICE_NOTE_SOURCE = re.compile(r"^[^:]{0,60}\b(board|sign|sheet)\b[^:]*:\s*", re.I)
PRICE_NOTE_STAFF = re.compile(r"board|\bsign\b|\btags?\b|sticker|read off|looks high|seems high|lists one line|"
                              r"scale label|\bcave\b|primal|sheet|confirm|\bask\b|\bsell\b|find out|\bkey\b|"
                              r"not yet recorded|\bSept\b|\b20\d\d\b", re.I)
# A price staff weren't sure of stays off the site unless someone ticks Show price for it.
PRICE_UNSURE = re.compile(r"confirm|looks high|seems high|mis-?stick|sit a half|unconfirmed|\?", re.I)

def _unit(r):
    """Notion's Unit options ("per lb", "each", "per bag", "per case") as the page prints them."""
    return {"": "lb", "per lb": "lb", "per bag": "bag", "per case": "case"}.get(r.get("unit") or "", r.get("unit"))

def clean_price_note(text):
    if not text:
        return ""
    text = PRICE_NOTE_SOURCE.sub("", PRICE_NOTE_PAREN.sub("", text.strip()))
    parts = [p for p in re.split(r"(?<=[.!?;])\s+", text) if p and not PRICE_NOTE_STAFF.search(p)]
    out = " ".join(parts).strip()
    return out[:1].upper() + out[1:] if out else ""

def price_info(r, show_all=False):
    """Returns (amount, unit label, qualifier, public note) or None. Every recorded price goes in
    the page behind the Prices switch (show_all); Show price ticked means shown regardless."""
    if r["price"] is None or not (r.get("show_price") or show_all):
        return None
    notes = r["price_notes"] or ""
    if not r.get("show_price") and PRICE_UNSURE.search(notes):
        return None
    unit = _unit(r)
    qual = ""
    if unit == "bag":
        m = re.search(r"per ((?:\d+(?:\.\d+)? )?lb bag)", notes, re.I)
        unit = m.group(1) if m else "bag"
        m = re.search(r"\$\d+(?:\.\d+)?/lb", notes)
        qual = (m.group(0) + " by the pound") if m else ""
    elif re.search(r"primal|cave sheet", notes, re.I) and f"${r['price']:.2f}" in notes:
        qual = "whole primal price"
    return (r["price"], unit, qual, clean_price_note(notes))

ORDER = ["Beef","Pork","Chicken","Turkey","Lamb","Goat","Rabbit","Seafood","Ground & burgers","Sausage",
         "Bacon & smoked","Ham","Hot dogs","Marinated & prepared","Bones & broth","Frozen & bulk","Produce",
         "Packaged & shelf","Bakery","Dairy & cheese","Other"]

def public_rows(rows, show_all=False):
    out = []
    for r in rows:
        n = r["name"]
        if not n or "(pork scale)" in n or "(key " in n or "(or " in n or "unreadable" in n:
            continue
        n = re.sub(r"\s*\([^)]*\)", "", n).strip()
        if PLACEHOLDER_ROW.search(n):
            continue
        p = {"name": n, "cat": r["cat"] or "Other", "aka": r["aka"], "src": source(r["src"]),
             "raw_src": r["src"], "photos": r["photos"], "verified": r["status"] not in UNVERIFIED}
        if p["verified"]:
            for k in ("what", "how", "taste", "ask", "fact", "try"):
                v = clean(r[k])
                if v:
                    p[k] = v
            if r["ingredients"]:
                p["ingredients"] = r["ingredients"]
            if r["nutrition"]:
                p["nutrition"] = r["nutrition"]
                p["nutrition_source"] = r["nutrition_source"]
        pi = price_info(r, show_all)
        if pi:
            p["price"] = pi
            p["price_pub"] = bool(r.get("show_price"))
        si = sale_info(r)
        if si:
            p["sale"] = si
        out.append(p)
    return out

# ---------- where each beef cut comes from (for the Beef Cuts page) ----------
PRIMALS = {
 "chuck":   ("Chuck", "The shoulder. It works hard, so it's full of flavor and the kind of connective tissue that melts with slow cooking. Pot roast country, plus a few surprisingly tender steaks the butchers pull out of it.",
             ["Chuck roast","Chuck steak","Flat iron steak","Blade steak","Denver steak","Mock tender","Ground chuck 85%","Stew beef"]),
 "rib":     ("Rib", "Ribs 6 through 12. The most marbled, richest part of the animal: ribeyes, prime rib, and the bone-in showpieces.",
             ["Ribeye steak","Prime ribeye","Cowboy steak","Tomahawk steak","Bone-in rib roast","Boneless rib roast","Shaved ribeye"]),
 "loin":    ("Short loin", "Along the back behind the ribs. The tender, quick-cooking steaks: strip, T-bone, porterhouse, and the tenderloin tucked underneath.",
             ["Strip sirloin","Prime strip","Porterhouse","T-bone","Tenderloin steak","Tenderloin roast","CC tenderloin roast","Tenderloin tail"]),
 "sirloin": ("Sirloin", "Between the short loin and the round. Leaner than the loin, more tender than the round. Everyday steaks and a couple of great roasts.",
             ["NY sirloin","Picanha roast","Tri-tip","Sirloin tips"]),
 "round":   ("Round", "The hind leg. Lean, mild, and big. At its best sliced thin: roast beef, jerky, minute steak, London broil.",
             ["Top round roast","Top round steak","Bottom round roast","Bottom round steak","Eye round roast","Eye round steak","Rump roast","Cubed steak","Minute steak","Beef jerky meat","Ground round 90%"]),
 "brisket": ("Brisket", "The chest. Two muscles layered with fat and collagen. Smoke it, braise it, or cure it into corned beef.",
             ["Brisket"]),
 "plate":   ("Plate", "The belly behind the brisket. Skirt, hanger, and short ribs: the most flavor per bite on the animal.",
             ["Skirt steak","Hanger steak","Short ribs, bone-in","Short ribs, boneless","Korean style rib"]),
 "flank":   ("Flank", "The flat muscle below the loin, one per side. Lean and beefy, made for marinades and thin slicing across the grain.",
             ["Flank steak"]),
 "shank":   ("Shank and tail", "Bone, marrow, and slow-cooked meat. Oxtail and soup bones for the stockpot.",
             ["Oxtail","Beef bones"]),
}
PRIMAL_OF = {name: key for key, (_, _, names) in PRIMALS.items() for name in names}

# ---------- photos ----------
def slug(n): return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")

PLACEHOLDER = ("data:image/svg+xml;utf8," + "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 300'>"
    "<rect width='400' height='300' fill='%23f3ece5'/><rect x='0.5' y='0.5' width='399' height='299' fill='none' stroke='%23cdb9ab' stroke-dasharray='6 5'/>"
    "<text x='200' y='158' text-anchor='middle' font-family='Georgia,serif' font-size='22' fill='%236b4031'>Photo goes here</text></svg>")
DEMO_PHOTOS = {"Ribeye steak": [PLACEHOLDER, PLACEHOLDER]}   # local demo only, never published
DEMO_MODE = False

_PHOTO_CACHE = {}
def process_photos(p):
    """Downloads each photo, writes a 1200px gallery copy and a 200px square thumb into dist/photos.
    Returns (gallery paths, thumb path)."""
    if p["name"] in _PHOTO_CACHE:
        return _PHOTO_CACHE[p["name"]]
    r = _process_photos(p)
    _PHOTO_CACHE[p["name"]] = r
    return r

def _process_photos(p):
    if not p["photos"]:
        demo = DEMO_PHOTOS.get(p["name"]) if DEMO_MODE else None
        return (demo, demo[0]) if demo else ([], None)
    from PIL import Image, ImageOps
    try:
        import pillow_heif; pillow_heif.register_heif_opener()
    except ImportError:
        pass
    import requests
    os.makedirs(f"{OUT}/photos", exist_ok=True)
    gallery, thumb = [], None
    for i, u in enumerate(p["photos"]):
        try:
            data = requests.get(u, timeout=60).content if u.startswith("http") else open(u, "rb").read()
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        except Exception as e:
            print(f"  photo skipped for {p['name']}: {e}", file=sys.stderr)
            continue
        base = slug(p["name"]) + ("" if i == 0 else f"-{i+1}")
        g = img.copy(); g.thumbnail((1200, 1200))
        g.save(f"{OUT}/photos/{base}.jpg", "JPEG", quality=82, optimize=True, progressive=True)
        gallery.append(f"photos/{base}.jpg")
        if i == 0:
            ImageOps.fit(img, (200, 200)).save(f"{OUT}/photos/{base}-thumb.jpg", "JPEG", quality=80, optimize=True)
            thumb = f"photos/{base}-thumb.jpg"
    return gallery, thumb

# ---------- nutrition ----------
def nutrition_html(p):
    t = p.get("nutrition")
    if not t:
        return ""
    t = clean(t)
    if not t:
        return ""
    g = lambda pat: (re.search(pat, t) or [None, None])[1]
    cal, pro, fat, carb = g(r"(\d+)\s*cal"), g(r"(\d+)\s*g protein"), g(r"(\d+)\s*g fat"), g(r"(\d+)\s*carb")
    serving = (re.search(r"Per (.+?),\s*about", t) or [None, "serving"])[1]
    rest = re.split(r"(?<=\.)\s+", t, maxsplit=1)
    fine = rest[1] if len(rest) > 1 else ""
    src = "From the label." if p.get("nutrition_source") == "Label" else "Typical USDA values for this cut, not measured on this package."
    if not all([cal, pro, fat, carb]):
        return f"<h3>Nutrition</h3><p>{esc(t)}</p><p class='fine'>{esc(src)}</p>"
    return (f"<h3>Nutrition</h3><div class='nut'>"
            f"<span><b>{cal}</b>cal</span><span><b>{pro} g</b>protein</span><span><b>{fat} g</b>fat</span><span><b>{carb} g</b>carbs</span></div>"
            f"<p class='fine'>Per {esc(serving)}. {esc(src)} {esc(fine)}</p>")

# ---------- HTML ----------
LABELS = [("what","What it is"),("how","How to cook it"),("taste","What it tastes like"),("ask","People often ask"),("fact","Worth knowing"),("try","Try this")]

def esc(s): return html.escape(str(s), quote=True)

def price_html(p):
    if "sale" in p:
        amt, unit, note, was = p["sale"]
        return (f'<span class="price sale pub"><b>${amt:.2f}</b><span class="unit">/{esc(unit)}</span>'
                + (f'<s class="was">${was:.2f}</s>' if was is not None else "")
                + (f'<span class="qual">{esc(note)}</span>' if note else "") + "</span>")
    if "price" not in p:
        return ""
    amt, unit, qual, _ = p["price"]
    pub = " pub" if p.get("price_pub") else ""
    return (f'<span class="price{pub}"><b>${amt:.2f}</b><span class="unit">/{esc(unit)}</span>'
            + (f'<span class="qual">{esc(qual)}</span>' if qual else "") + "</span>")

def item_html(p, gallery, thumb, in_specials=False, id_prefix="", chart_link=True, extra=""):
    search = " ".join([p["name"], p["aka"], p["cat"], p.get("what",""), p.get("ask",""), p.get("how",""), p.get("try","")]).lower()
    if in_specials:
        search += " special sale"
    body = "".join(f"<h3>{esc(l)}</h3><p>{esc(p[k])}</p>" for k,l in LABELS if k in p)
    if p.get("ingredients"):
        body += f"<h3>Ingredients</h3><p>{esc(p['ingredients'])}</p>"
    body += nutrition_html(p)
    if gallery:
        imgs = "".join(f'<img src="{esc(u)}" alt="{esc(p["name"])}" loading="lazy">' for u in gallery)
        body = f'<div class="gallery{" one" if len(gallery)==1 else ""}">{imgs}</div>' + body
    if "price" in p and p["price"][3]:
        body += f'<div class="pnote{" pub" if p.get("price_pub") else ""}"><h3>Price</h3><p>{esc(p["price"][3])}</p></div>'
    if body and chart_link and p["name"] in PRIMAL_OF:
        pk = PRIMAL_OF[p["name"]]
        body += f'<p class="fine from"><a href="beef.html#{pk}">From the {esc(PRIMALS[pk][0].lower())}. See it on the chart.</a></p>'
    aka = (f'<span class="aka"><span class="catlabel">{esc(p["cat"])}</span>'
           + (f'<span class="akatxt">{esc(p["aka"])}</span>' if p["aka"] else "") + "</span>")
    # Match on what staff typed, but only ever print the public wording of it.
    raw = p.get("raw_src") or p["src"]
    logo = brands.CURRENT.logo(raw) if (brands.CURRENT and p["src"]) else None
    if logo:
        path, brand, _ = logo
        src = f'<img class="blogo" src="{esc(path)}" alt="{esc(brand)}" loading="lazy">'
        if body and p["src"].strip().lower() != brand.strip().lower():
            body += f'<p class="fine from">{esc(p["src"])}</p>'
    else:
        src = f'<span class="src">{esc(p["src"])}</span>' if p["src"] else ""
    right = f'<span class="right">{price_html(p)}{src}</span>'
    th = f'<img class="thumb" src="{esc(thumb)}" alt="" loading="lazy">' if thumb else ""
    left = f'{th}<span class="left"><span class="name">{esc(p["name"])}</span>{aka}</span>{right}'
    attrs = (f'id="{id_prefix}{slug(p["name"])}" {extra} data-cat="{esc(p["cat"])}" data-name="{esc(p["name"].lower())}" data-aka="{esc(p["aka"].lower())}" '
             f'data-search="{esc(search)}"' + (' data-special="1"' if in_specials else ""))
    if body:
        return f'<details class="item" {attrs}><summary>{left}</summary><div class="body">{body}</div></details>'
    return f'<div class="item plain" {attrs}>{left}</div>'

def build(rows, demo=False):
    rows = public_rows(rows, show_all=True)
    specials = [r for r in rows if "sale" in r]
    regular = [r for r in rows if "sale" not in r]
    cats = [c for c in ORDER if any(r["cat"] == c for r in rows)]
    n = lambda k: f'<span class="n">{k}</span>'
    chips = f'<button type="button" aria-pressed="true" data-cat="">All{n(len(rows))}</button>'
    if specials:
        chips += f'<button type="button" aria-pressed="false" data-cat="__specials__">Specials{n(len(specials))}</button>'
    chips += "".join(f'<button type="button" aria-pressed="false" data-cat="{esc(c)}">{esc(c)}{n(sum(1 for r in rows if r["cat"] == c))}</button>' for c in cats)
    sections = ""
    if specials:
        items = ""
        for r in specials:
            gallery, thumb = process_photos(r)
            items += item_html(r, gallery, thumb, in_specials=True)
        sections += (f'<section class="cat specials" data-cat="__specials__"><h2><span class="tag">On special</span>'
                     f'<span class="count">{len(specials)}</span></h2>{items}</section>')
    for c in cats:
        rs = sorted((r for r in regular if r["cat"] == c), key=lambda r: r["name"].lower())
        if not rs:
            continue
        items = ""
        for r in rs:
            gallery, thumb = process_photos(r)
            items += item_html(r, gallery, thumb)
        sections += (f'<section class="cat" data-cat="{esc(c)}"><h2><span class="tag">{esc(c)}</span>'
                     f'<span class="count">{len(rs)}</span></h2>{items}</section>')
    brand_strip = ""
    if brands.CURRENT:
        strip = "".join(
            (f'<a href="{esc(url)}" rel="noopener"><img src="{esc(path)}" alt="{esc(name)}" loading="lazy"></a>'
             if url else f'<img src="{esc(path)}" alt="{esc(name)}" loading="lazy">')
            for path, name, url in brands.CURRENT.all_logos())
        if strip:
            brand_strip = f'<section class="brands in"><h2>Brands we carry</h2><div class="strip">{strip}</div></section>'
    switch = '<button type="button" class="switch" id="price-switch" role="switch" aria-checked="false"><span class="knob" aria-hidden="true"></span>Prices</button>'
    logo, ld = logo_and_ld(demo)
    return shell(title="What We Carry",
                 desc="Steaks, roasts, sausage, local pork, and more at Emery's Meat &amp; Produce in Brewer, Maine, with what each cut is and how to cook it.",
                 head_block=INDEX_HEAD, content=INDEX_CONTENT.replace("{{CHIPS}}", chips).replace("{{SECTIONS}}", sections)
                                                             .replace("{{SWITCH}}", switch).replace("{{BRANDS}}", brand_strip),
                 script=INDEX_SCRIPT, extra_css="", active="carry", logo=logo, ld=ld,
                 footnote=f"{len(rows)} products listed. Cuts and availability change with what comes in from the farms.",
                 bodyclass="")

def shell(title, desc, head_block, content, script, extra_css, active, logo, ld, footnote, bodyclass=""):
    cur = ' aria-current="page"'
    return (SHELL.replace("{{TITLE}}", title).replace("{{DESC}}", desc).replace("{{HEAD_BLOCK}}", head_block)
            .replace("{{CONTENT}}", content).replace("{{SCRIPT}}", script).replace("{{EXTRA_CSS}}", extra_css)
            .replace("{{CUR_CARRY}}", cur if active == "carry" else "").replace("{{CUR_BEEF}}", cur if active == "beef" else "")
            .replace("{{LOGO}}", logo).replace("{{LD}}", ld).replace("{{FOOTNOTE}}", footnote).replace("{{BODYCLASS}}", bodyclass).replace("{{ROBOTS}}", ROBOTS))

def logo_and_ld(demo):
    here = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(here, "assets", "logo.png")
    if demo:
        import base64
        logo = "data:image/png;base64," + base64.b64encode(open(logo_path, "rb").read()).decode()
    else:
        import shutil
        os.makedirs(f"{OUT}/assets", exist_ok=True)
        shutil.copy(logo_path, f"{OUT}/assets/logo.png")
        logo = "assets/logo.png"
    ld = json.dumps({"@context":"https://schema.org","@type":"Butcher","name":"Emery's Meat & Produce, Brewer",
        "telephone":"+1-207-922-2673","url":"https://emerysmeatbrewer.com/",
        "address":{"@type":"PostalAddress","streetAddress":"262 State Street","addressLocality":"Brewer","addressRegion":"ME","postalCode":"04412","addressCountry":"US"},
        "openingHours":["Mo-We 10:00-17:00","Th 10:00-18:00","Fr-Sa 10:00-17:00"]})
    return logo, ld

SHELL = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}} | Emery's Meat &amp; Produce, Brewer</title>
<meta name="description" content="{{DESC}}">
{{ROBOTS}}<meta name="theme-color" content="#6b4031">
<meta name="color-scheme" content="light only">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;600&family=Playfair+Display&display=swap" rel="stylesheet">
<script type="application/ld+json">{{LD}}</script>
<style>
:root{--brown:#6b4031;--brown-dk:#4f2e23;--ink:#151515;--muted:#666362;--line:#e6dfda;--card:#faf2f0;--tint:#faf2f0;--sans:"Open Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;--serif:"Playfair Display",Georgia,"Times New Roman",serif}
*{box-sizing:border-box}
[hidden]{display:none!important}
html{background:#fff;color-scheme:light only}
body{margin:0;background:#fff;color:var(--ink);font:16px/1.5 var(--sans)}
a{color:var(--brown)}
.page{background:#fff;color:var(--ink);min-height:100vh;position:relative}
.in{max-width:640px;margin:0 auto}
/* site header, matching emerysmeatbrewer.com */
.site{background:#fff;text-align:center;padding:22px 16px 10px}
.site .phone{display:block;color:var(--brown);text-decoration:none;font:400 24px/1.2 var(--sans);letter-spacing:.01em}
.site .bar{position:relative;display:flex;justify-content:center;align-items:center;margin-top:22px;min-height:96px}
.site .logo img{display:block;height:96px;width:auto}
.burger{position:absolute;left:0;top:50%;transform:translateY(-50%);width:44px;height:44px;border:0;background:none;padding:0;cursor:pointer;-webkit-tap-highlight-color:transparent}
.burger span{display:block;width:26px;height:3px;background:var(--brown);margin:5px auto;border-radius:1px}
.burger:focus-visible{outline:3px solid var(--brown);outline-offset:2px;border-radius:4px}
.site nav.desk{display:none}
/* full-screen menu, like the site's */
.menu{position:absolute;top:0;left:0;right:0;min-height:100vh;z-index:20;background:#faf2f0;padding:24px 24px 60px 40px;display:block}
.menu .close{position:absolute;top:22px;right:22px;width:44px;height:44px;border:0;background:none;font:300 40px/1 var(--sans);color:var(--ink);cursor:pointer}
.menu ul{list-style:none;margin:80px 0 0;padding:0;display:block}
.menu li{display:block;margin:0 0 34px;padding:0}
.menu a{display:inline-block;color:var(--ink);text-decoration:none;font:400 20px/1.3 var(--sans);text-transform:uppercase;letter-spacing:.1em}
.menu a[aria-current=page]{font-weight:600}
.menu a:focus-visible,.menu .close:focus-visible{outline:3px solid var(--brown);outline-offset:4px}
/* page head, in the site's hero style */
.head{background:var(--tint);text-align:center}
.head .in{padding:40px 24px 34px}
.eyebrow{margin:0 0 14px;color:var(--brown);font:400 13px/1.6 var(--sans);text-transform:uppercase;letter-spacing:.2em}
h1{margin:0 0 14px;font:400 38px/1.15 var(--serif);color:var(--ink)}
.lede{margin:0 auto;max-width:30em;font-size:16.5px;line-height:1.6;color:var(--muted)}
@media(min-width:768px){
  .site{padding:26px 24px 0}
  .site .phone{font-size:22px}
  .burger{display:none}
  .site nav.desk{display:flex;justify-content:center;gap:34px;margin:18px 0 0;padding:16px 0 14px;border-top:1px solid var(--line)}
  .site nav.desk a{color:var(--ink);text-decoration:none;font:400 13px/1 var(--sans);text-transform:uppercase;letter-spacing:.18em;padding:6px 0;border-bottom:2px solid transparent}
  .site nav.desk a[aria-current=page]{font-weight:600;border-bottom-color:var(--brown)}
  h1{font-size:48px}
}
/* tools */
.tools{position:sticky;top:0;z-index:2;background:#fff;border-bottom:1px solid var(--line)}
.tools .in{padding:12px 16px 6px}
.row{display:flex;gap:10px;align-items:center}
.search{flex:1}
.search input{width:100%;padding:11px 13px;border:1.5px solid #b9a79b;border-radius:6px;background:#fff;font:inherit;font-size:16px;color:var(--ink);-webkit-appearance:none}
.search input:focus{outline:3px solid var(--brown);outline-offset:1px;border-color:var(--brown)}
.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
/* price switch */
.switch{display:flex;align-items:center;gap:7px;font:inherit;font-size:13px;color:var(--muted);cursor:pointer;white-space:nowrap;border:0;background:none;padding:6px 2px;margin:0;-webkit-tap-highlight-color:transparent;touch-action:manipulation}
.knob{position:relative;width:34px;height:20px;border-radius:10px;background:#c9bdb4;transition:background .15s}
.knob::after{content:"";position:absolute;top:3px;left:3px;width:14px;height:14px;border-radius:50%;background:#fff;transition:transform .15s}
.switch[aria-checked=true] .knob{background:var(--brown)}
.switch[aria-checked=true] .knob::after{transform:translateX(14px)}
.switch:focus-visible{outline:3px solid var(--brown);outline-offset:2px;border-radius:4px}
@media(prefers-reduced-motion:reduce){.knob,.knob::after{transition:none}}
.chips{display:flex;gap:6px;overflow-x:auto;padding:10px 0 6px;scrollbar-width:none}
.chips::-webkit-scrollbar{display:none}
.chips button{flex:0 0 auto;padding:6px 12px;border:1px solid var(--brown);background:#fff;color:var(--brown);font:600 13px var(--sans);letter-spacing:.02em;border-radius:4px;cursor:pointer}
.chips button[aria-pressed=true]{background:var(--brown);color:#fff}
.chips button:focus-visible{outline:3px solid var(--brown);outline-offset:2px}
.pricenote{margin:6px 0 0;font-size:13px;color:var(--muted)}
/* list */
main{padding:6px 16px 30px}
.cat{margin:24px 0 8px}
.cat h2{margin:0 0 6px;font:400 22px/1 var(--serif);display:flex;align-items:baseline}
.tag{display:inline-block;background:var(--tint);color:var(--brown);border:1px solid #cdb9ab;padding:5px 12px 6px;border-radius:2px;transform:rotate(-1.2deg);transform-origin:left bottom}
.count{font:13px var(--sans);color:var(--muted);margin-left:10px}
.item{border-bottom:1px solid var(--line)}
.item summary,.item.plain{list-style:none;padding:12px 2px;display:grid;grid-template-columns:1fr auto;gap:1px 12px;align-items:start}
.item summary:has(.thumb),.item.plain:has(.thumb){grid-template-columns:auto 1fr auto}
.thumb{width:52px;height:52px;object-fit:cover;border-radius:4px;border:1px solid var(--line);background:var(--tint)}
.gallery{display:flex;gap:8px;overflow-x:auto;margin:10px -14px 4px;padding:0 14px;scrollbar-width:none}
.gallery::-webkit-scrollbar{display:none}
.gallery img{flex:0 0 78%;aspect-ratio:4/3;object-fit:cover;border-radius:4px;border:1px solid var(--line);background:var(--tint)}
.gallery.one img{flex-basis:100%}
.nut{display:flex;gap:6px;margin:4px 0 4px}
.nut span{flex:1;background:#fff;border:1px solid var(--line);border-radius:4px;padding:6px 4px;text-align:center;font-size:12px;color:var(--muted);line-height:1.2}
.nut b{display:block;font-size:16px;color:var(--ink);font-weight:600}
.fine{font-size:12.5px;color:var(--muted);line-height:1.4}
.from{margin-top:10px}
.body p.fine{font-size:12.5px}
.item summary{cursor:pointer}
.item summary::-webkit-details-marker{display:none}
.item summary:focus-visible{outline:3px solid var(--brown);outline-offset:-3px}
.name{font-weight:600;font-size:17px;padding-top:1px}
.item.plain .name{font-weight:500}
.right{display:flex;flex-direction:column;align-items:flex-end;gap:2px}
.src{font-size:12.5px;color:var(--muted);text-align:right;max-width:13em;overflow-wrap:anywhere}
.left{display:flex;flex-direction:column;gap:1px;min-width:0}
.aka{font-size:13.5px;color:var(--muted)}
.aka:empty{display:none}
.catlabel{display:none}
.specials .catlabel,#results .catlabel{display:inline}
.specials .catlabel+.akatxt::before,#results .catlabel+.akatxt::before{content:", "}
#results{margin-top:8px}
.item[open] summary .name{color:var(--brown)}
.price{display:none;text-align:right;line-height:1.15}
.price b{font-size:17px;font-weight:600;color:var(--ink)}
.price .unit{font-size:12.5px;color:var(--muted);margin-left:1px}
.price .qual{display:block;font-size:11.5px;color:var(--muted);white-space:nowrap}
.pnote{display:none}
#blist .price,#blist .pnote{display:none}
body.prices #blist .price{display:inline-block}
body.prices #blist .pnote{display:block}
.price.sale b{color:var(--brown);font-size:18px}
.price .was{display:none;font-size:12.5px;color:var(--muted)}
body.prices .price .was{display:block}
.specials .tag{background:var(--brown);color:#fff;border-color:var(--brown)}
body.prices .price,body.prices .pnote{display:block}
body.prices .price{display:inline-block}
.price.pub,#blist .price.pub{display:inline-block}
.pnote.pub,#blist .pnote.pub{display:block}
.body{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:4px 14px 12px;margin:0 0 14px}
.body h3{margin:12px 0 2px;font:600 13px/1.3 inherit;font-family:inherit;color:var(--muted)}
.body p{margin:0;font-size:15px;line-height:1.5}
.empty{margin:30px auto;padding:0 16px;color:var(--muted)}
/* site footer */
.foot{background:var(--tint);margin-top:20px}
.foot .in{padding:22px 16px 40px;font-size:14px;color:var(--muted);line-height:1.6}
.foot h2{margin:0 0 10px;font:400 26px var(--serif);color:var(--ink)}
.foot{text-align:center}
.foot p{margin:0 0 10px}
.foot a{color:var(--brown)}
@media(min-width:640px){h1{font-size:42px}.site .brand{font-size:20px}}
/* brand logos */
.blogo{display:block;height:26px;width:auto;max-width:118px;object-fit:contain;object-position:right center}
.brands{padding:26px 16px 6px;text-align:center;border-top:1px solid var(--line);margin-top:26px}
.brands h2{margin:0 0 16px;font:400 22px/1 var(--serif)}
.strip{display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:18px 26px}
.strip img{height:38px;width:auto;max-width:150px;object-fit:contain}
.strip a{display:block}
.chips button .n{display:none}
/* ---------- desktop (1024px and up) ----------
   The header and footer copy emerysmeatbrewer.com (200px centered logo, phone on the right,
   spaced-capital nav with a brown underline, Playfair titles, spaced-capital footer). The
   catalogue itself is laid out for shopping: a sticky sidebar with search, the Prices
   switch and the categories with counts; compact product cards that line up in even rows;
   and the details opening in a panel from the right instead of stretching the grid.
   Below 1024px none of this applies and the approved phone layout is untouched. */
@media(min-width:1024px){
  .in{max-width:1160px}
  /* header, as on the original site */
  .site{max-width:1160px;margin:0 auto;padding:56px 24px 16px;position:relative}
  .site .phone{position:absolute;right:24px;top:141px;font:400 22px/33px var(--sans);letter-spacing:0}
  .site .bar{margin-top:0;min-height:200px}
  .site .logo img{height:200px;width:auto}
  .site nav.desk{border-top:0;margin:18px 0 0;padding:0;gap:32px}
  .site nav.desk a{font:400 14px/24px var(--sans);letter-spacing:.214em;color:#151515;padding:0 0 4px;border-bottom:1px solid transparent}
  .site nav.desk a[aria-current=page]{font-weight:400;border-bottom-color:var(--brown)}
  .site nav.desk a:hover{border-bottom-color:#cdb9ab}
  /* page title */
  .head{background:#fff;text-align:left}
  .head .in{max-width:1160px;padding:40px 24px 0}
  .eyebrow{display:none}
  h1{margin:0 0 12px;font:400 44px/1.2 var(--serif);letter-spacing:.023em;color:#1b1b1b}
  .lede{margin:0;max-width:40em;font-size:17px;line-height:27px;color:#5e5e5e}
  .lede a{color:var(--brown)}
  /* catalogue: sidebar + list */
  .catalog{display:grid;grid-template-columns:248px minmax(0,1fr);gap:0 56px;max-width:1160px;margin:0 auto;padding:0 24px;align-items:start}
  .tools{grid-column:1;grid-row:1/span 3;position:sticky;top:0;align-self:start;background:#fff;border:0;box-shadow:none;max-height:100vh;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#e6dcd6 transparent}
  .tools .in{max-width:none;margin:0;padding:30px 0 24px}
  .tools .row{display:flex;flex-direction:column;align-items:stretch;gap:12px;max-width:none}
  .tools .search{flex:none}
  .search input{border:1px solid #d3cac5;border-radius:4px;padding:11px 12px;font-size:14.5px;background:#fff}
  .search input:focus{outline:2px solid var(--brown);outline-offset:0;border-color:var(--brown)}
  .switch{margin:0;align-self:flex-start;padding:4px 0;font:400 14px/1 var(--sans);letter-spacing:0;text-transform:none;color:#5e5e5e}
  .chips{display:flex;flex-direction:column;flex-wrap:nowrap;gap:1px;padding:14px 0 0;overflow:visible;border-top:1px solid var(--line);margin-top:14px}
  .chips button{display:flex;justify-content:space-between;align-items:baseline;gap:10px;width:100%;text-align:left;border:0;border-radius:4px;background:none;color:#2b2b2b;padding:5px 10px;font:400 14.5px/1.3 var(--sans);letter-spacing:0;text-transform:none}
  .chips button .n{display:inline;font-size:12.5px;color:#9b928d}
  .chips button:hover{background:#f8f1ee}
  .chips button[aria-pressed=true]{background:var(--tint);color:var(--brown);font-weight:600;box-shadow:inset 3px 0 0 var(--brown)}
  .chips button[aria-pressed=true] .n{color:var(--brown)}
  .pricenote{margin:16px 0 0;font-size:12.5px;line-height:1.5}
  main.in{grid-column:2;max-width:none;margin:0;padding:36px 0 24px}
  .catalog .empty{grid-column:2;max-width:none;margin:36px 0;padding:0;font-size:16px}
  /* sections and cards */
  .cat,#results{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px;margin:0 0 52px}
  #results{margin-top:0}
  .cat h2,#results h2{grid-column:1/-1;display:flex;align-items:baseline;gap:12px;margin:0 0 6px;font:400 30px/1.25 var(--serif);letter-spacing:.01em;color:#1b1b1b}
  .tag{display:inline;background:none;border:0;padding:0;transform:none;color:inherit;border-radius:0}
  .specials .tag{background:none;color:var(--brown)}
  .count{font:400 13px var(--sans);color:#9b928d;margin:0}
  .item{background:#fff;border:1px solid #e9e1dc;border-radius:4px;transition:border-color .15s,box-shadow .15s}
  details.item:hover{border-color:#c9b4a8;box-shadow:0 6px 18px rgba(79,46,35,.08)}
  /* card: name and other names on the left, price on the right; source and "Details" underneath */
  .item summary,.item.plain{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px 14px;align-items:start;padding:16px 18px 15px;text-align:left}
  .item summary:has(.thumb),.item.plain:has(.thumb){grid-template-columns:60px minmax(0,1fr) auto}
  .thumb{grid-column:1;grid-row:1/span 2;width:60px;height:60px;border-radius:3px}
  .left{grid-column:-3/-2;grid-row:1;gap:3px;align-items:flex-start}
  .right{display:contents}
  .right .price{grid-column:-2/-1;grid-row:1;justify-self:end}
  .right .src,.right .blogo{grid-column:-3/-2;grid-row:2;align-self:center;justify-self:start}
  .name,.item.plain .name{font:600 16.5px/1.35 var(--sans);letter-spacing:0;color:#1b1b1b;padding:0}
  .item[open] summary .name{color:#1b1b1b}
  .aka{font-size:14px;line-height:1.45;color:#706a67}
  .right{align-items:flex-end;gap:6px;margin:0}
  .src{max-width:none;text-align:left;font-size:10.5px;line-height:1.45;letter-spacing:.13em;text-transform:uppercase;color:var(--brown)}
  .blogo{height:26px;max-width:110px;object-position:left center}
  .price{text-align:right}
  .price b{font-size:16.5px}
  .price .qual{font-size:11px}
  details.item summary::after{content:"Details \2192";grid-column:-2/-1;grid-row:2;align-self:center;justify-self:end;white-space:nowrap;font:600 12px/1 var(--sans);letter-spacing:.04em;color:#b29a8d;transition:color .15s}
  details.item:hover summary::after{color:var(--brown)}
  .item summary:focus-visible{outline:2px solid var(--brown);outline-offset:2px;border-radius:4px}
  .cat .item .body,#results .item .body{display:none}
  .brands{max-width:1160px;padding:40px 24px 8px;margin-top:24px;text-align:left;border-top:1px solid var(--line)}
  .brands h2{font:400 16px/1.4 var(--sans);letter-spacing:.125em;text-transform:uppercase;color:var(--brown);margin:0 0 24px}
  .strip{justify-content:flex-start}
  .strip img{height:46px;max-width:180px}
  /* footer, as on the original site */
  .foot{background:#fff;margin-top:24px;text-align:left;border-top:1px solid var(--line)}
  .foot .in{max-width:1160px;padding:40px 24px 56px;display:grid;grid-template-columns:1fr 1fr;gap:0 24px;font-size:12px}
  .foot h2{grid-column:1/-1;margin:0 0 24px;font:400 16px/22px var(--sans);letter-spacing:.125em;text-transform:uppercase;color:var(--brown)}
  .foot .social{grid-column:1/-1;text-align:center;margin:0 0 56px}
  .foot .social a{display:inline-block;margin:0 8px;padding:11px 22px;border:1px solid var(--brown);color:var(--brown);text-decoration:none;font:700 12px/1 var(--sans);letter-spacing:.214em;text-transform:uppercase}
  .foot .social a:hover{background:var(--brown);color:#fff}
  .foot .copy{grid-column:1;grid-row:3;margin:0;font:400 12px/18px var(--sans);letter-spacing:.083em;text-transform:uppercase;color:#595959}
  .foot .addr{grid-column:2;grid-row:3;margin:0;text-align:right;font:400 12px/18px var(--sans);letter-spacing:.083em;text-transform:uppercase;color:#595959}
  .foot .addr .fn{display:block;margin-top:6px;text-transform:none;letter-spacing:0;color:#767676}
}
/* details panel (opens on desktop only) */
.drawer{position:fixed;inset:0;z-index:50}
.drawer .scrim{position:absolute;inset:0;background:rgba(21,21,21,.36);opacity:0;transition:opacity .18s}
.dpanel{position:absolute;top:0;right:0;bottom:0;width:min(540px,100vw);background:#fff;box-shadow:-14px 0 44px rgba(0,0,0,.14);transform:translateX(28px);opacity:0;transition:transform .2s,opacity .2s;overflow-y:auto;overscroll-behavior:contain}
.drawer.on .scrim{opacity:1}
.drawer.on .dpanel{transform:none;opacity:1}
.dclose{position:sticky;top:0;float:right;margin:10px 10px 0 0;width:44px;height:44px;border:0;border-radius:50%;background:#fff;font:300 32px/1 var(--sans);color:#151515;cursor:pointer;z-index:1}
.dclose:hover{background:#f6efec}
.dclose:focus-visible{outline:2px solid var(--brown);outline-offset:1px}
#dbody{padding:40px 44px 56px}
.dcat{margin:0 0 10px;font:400 12px/1.4 var(--sans);letter-spacing:.18em;text-transform:uppercase;color:var(--brown)}
.dtop h2{margin:0 0 6px;font:400 36px/1.15 var(--serif);color:#1b1b1b}
.daka{margin:0 0 4px;font-size:16px;line-height:1.5;color:#5e5e5e}
.dmeta{display:flex;flex-direction:row;align-items:center;justify-content:space-between;gap:16px;margin:18px 0 8px;padding:14px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.dmeta .price{text-align:left}
.dmeta .price b{font-size:22px}
.dmeta .src{max-width:none;font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--brown)}
.dmeta .blogo{height:34px;max-width:160px}
.dcontent{background:none;border:0;padding:0;margin:0}
.dcontent h3{margin:24px 0 6px;font:400 12px/1.4 var(--sans);letter-spacing:.18em;text-transform:uppercase;color:var(--brown)}
.dcontent p{margin:0;font-size:16px;line-height:1.65;color:#333}
.dcontent .fine{font-size:13.5px;color:#767676}
.dcontent .from{margin-top:26px}
.dcontent .gallery{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:8px 0 6px;padding:0;overflow:visible}
.dcontent .gallery.one{grid-template-columns:1fr}
.dcontent .gallery img{width:100%;flex:none;border-radius:3px}
.dcontent .nut{margin:6px 0}
html.dopen{overflow:hidden}
@media(max-width:1023px){.drawer{display:none!important}}
@media(prefers-reduced-motion:reduce){.drawer .scrim,.dpanel{transition:none}}
{{EXTRA_CSS}}
</style>
</head>
<body class="{{BODYCLASS}}"><div class="page">
<header class="site">
<a class="phone" href="tel:2079222673">(207) 922-2673</a>
<div class="bar">
<button type="button" class="burger" id="burger" aria-label="Menu" aria-expanded="false" aria-controls="menu"><span></span><span></span><span></span></button>
<a class="logo" href="https://emerysmeatbrewer.com/"><img src="{{LOGO}}" alt="Emery's Meat &amp; Produce, Brewer" width="96" height="96"></a>
</div>
<nav class="desk" aria-label="Site">
<a href="https://emerysmeatbrewer.com/">Home</a>
<a href="https://emerysmeatbrewer.com/about-us">About Us</a>
<a href="https://emerysmeatbrewer.com/meats-and-produce">Meats and Produce</a>
<a href="https://emerysmeatbrewer.com/freezer-packs">Freezer Packs</a>
<a href="index.html"{{CUR_CARRY}}>What We Carry</a>
<a href="beef.html"{{CUR_BEEF}}>Beef Cuts</a>
</nav>
</header>
<nav class="menu" id="menu" aria-label="Site" hidden>
<button type="button" class="close" id="closemenu" aria-label="Close menu">&times;</button>
<ul>
<li><a href="https://emerysmeatbrewer.com/">Home</a></li>
<li><a href="https://emerysmeatbrewer.com/about-us">About Us</a></li>
<li><a href="https://emerysmeatbrewer.com/meats-and-produce">Meats and Produce</a></li>
<li><a href="https://emerysmeatbrewer.com/freezer-packs">Freezer Packs</a></li>
<li><a href="index.html"{{CUR_CARRY}}>What We Carry</a></li>
<li><a href="beef.html"{{CUR_BEEF}}>Beef Cuts</a></li>
</ul>
</nav>
{{HEAD_BLOCK}}
{{CONTENT}}
<footer class="foot"><div class="in">
<h2>Connect With Us</h2>
<p class="social"><a href="https://www.facebook.com/EmerysMeatAndProduceBrewer/">Facebook</a> &nbsp; <a href="https://www.yelp.com/biz/suLFSAX7XvzPG4EKU0USgg">Yelp</a></p>
<p class="addr"><span class="street">262 State Street, Brewer, Maine 04412.</span> <span class="fn">{{FOOTNOTE}}</span></p>
<p class="copy">Copyright © Emery's Meat &amp; Produce Brewer - All Rights Reserved.</p>
</div></footer>
<div class="drawer" id="drawer" hidden>
<div class="scrim" data-close></div>
<div class="dpanel" role="dialog" aria-modal="true" aria-labelledby="dtitle">
<button type="button" class="dclose" data-close aria-label="Close">&times;</button>
<div id="dbody"></div>
</div>
</div>
</div>
<script>
(function(){
var burger=document.getElementById('burger'),menu=document.getElementById('menu'),closeBtn=document.getElementById('closemenu');
function openMenu(o){menu.hidden=!o;burger.setAttribute('aria-expanded',o?'true':'false');document.body.style.overflow=o?'hidden':'';if(o)window.scrollTo(0,0);try{(o?closeBtn:burger).focus({preventScroll:true});}catch(e){}}
burger.addEventListener('click',function(){openMenu(true);});
closeBtn.addEventListener('click',function(){openMenu(false);});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!menu.hidden)openMenu(false);});
/* On desktop a product's details open in a panel from the right; on phones they open in place. */
var drawer=document.getElementById('drawer'),dbody=document.getElementById('dbody'),dlast=null;
var wide=window.matchMedia?window.matchMedia('(min-width:1024px)'):{matches:false};
function openDrawer(item){
  var body=item&&item.querySelector('.body');if(!drawer||!body)return false;
  dbody.innerHTML='';
  var top=document.createElement('div');top.className='dtop';
  var c=document.createElement('p');c.className='dcat';c.textContent=item.getAttribute('data-cat')||'';top.appendChild(c);
  var h=document.createElement('h2');h.id='dtitle';h.textContent=item.querySelector('.name').textContent;top.appendChild(h);
  var aka=item.querySelector('.akatxt');if(aka){var a=document.createElement('p');a.className='daka';a.textContent=aka.textContent;top.appendChild(a);}
  var right=item.querySelector('.right');if(right&&right.children.length){var m=right.cloneNode(true);m.className='dmeta';top.appendChild(m);}
  dbody.appendChild(top);
  var b=body.cloneNode(true);b.className='dcontent';dbody.appendChild(b);
  drawer.hidden=false;document.documentElement.classList.add('dopen');
  drawer.querySelector('.dpanel').scrollTop=0;
  requestAnimationFrame(function(){requestAnimationFrame(function(){drawer.classList.add('on');});});
  dlast=item.querySelector('summary');
  try{drawer.querySelector('.dclose').focus({preventScroll:true});}catch(e){}
  return true;
}
function closeDrawer(){
  if(!drawer||drawer.hidden)return;
  drawer.classList.remove('on');document.documentElement.classList.remove('dopen');
  setTimeout(function(){drawer.hidden=true;},200);
  if(dlast){try{dlast.focus({preventScroll:true});}catch(e){}}
}
document.addEventListener('click',function(e){
  var s=e.target.closest('details.item>summary');
  if(s&&wide.matches&&!e.target.closest('a')){e.preventDefault();openDrawer(s.parentNode);return;}
  if(e.target.closest('[data-close]')){closeDrawer();}
});
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'&&drawer&&!drawer.hidden){closeDrawer();return;}
  if(e.key==='Tab'&&drawer&&!drawer.hidden){
    var f=[].slice.call(drawer.querySelectorAll('button,a[href],[tabindex="0"]'));if(!f.length)return;
    if(e.shiftKey&&document.activeElement===f[0]){e.preventDefault();f[f.length-1].focus();}
    else if(!e.shiftKey&&document.activeElement===f[f.length-1]){e.preventDefault();f[0].focus();}
  }
});
{{SCRIPT}}
})();
</script>
</body>
</html>"""

INDEX_HEAD = r"""<div class="head"><div class="in">
<p class="eyebrow">Emery's Meat &amp; Produce, Brewer</p>
<h1>What We Carry</h1>
<p class="lede">Typical products, and what to do with them. Not everything is in every day. Call <a href="tel:2079222673">(207) 922-2673</a> to check on something specific.</p>
</div></div>"""

INDEX_CONTENT = r"""<div class="catalog">
<div class="tools"><div class="in">
<div class="row">
<label class="search"><span class="vh">Search products</span><input type="search" id="q" placeholder="Search a cut, like porterhouse" autocomplete="off"></label>
{{SWITCH}}
</div>
<div class="chips" id="chips">{{CHIPS}}</div>
<p class="pricenote" id="pricenote" hidden>Per pound unless noted. Prices change with the market; call to confirm.</p>
</div></div>
<main class="in" id="list">{{SECTIONS}}<section id="results" hidden></section></main>
<p class="empty in" id="empty" hidden>Nothing matches that. Try another word, or call the shop at (207) 922-2673.</p>
</div>
{{BRANDS}}"""

INDEX_SCRIPT = r"""var q=document.getElementById('q'),chips=document.getElementById('chips'),empty=document.getElementById('empty');
var sws=[].slice.call(document.querySelectorAll('.switch[role=switch]')),sw=sws[0],note=document.getElementById('pricenote');
var demo=!!sw;
var items=[].slice.call(document.querySelectorAll('.item')),cats=[].slice.call(document.querySelectorAll('.cat'));
var results=document.getElementById('results');
function norm(t){return t.replace(/-/g,' ').replace(/\s+/g,' ');}
items.forEach(function(el,i){el._home=el.parentNode;el._idx=i;el._n=norm(el.dataset.name);el._a=norm(el.dataset.aka);el._all=norm(el.dataset.search);});
var cat='';
function score(el,s,words){
  var n=el._n,a=el._a,c=el.dataset.cat.toLowerCase(),all=el._all;
  for(var i=0;i<words.length;i++){if(all.indexOf(words[i])<0)return 0;}
  var sc;
  if(n===s)sc=100;
  else if(n.indexOf(s)===0)sc=90;
  else if((' '+n).indexOf(' '+s)>-1)sc=80;
  else if(n.indexOf(s)>-1)sc=70;
  else{
    var hits=0;words.forEach(function(w){if((' '+n).indexOf(' '+w)>-1)hits++;});
    if(hits===words.length)sc=65;
    else if(a.indexOf(s)>-1||words.every(function(w){return a.indexOf(w)>-1;}))sc=50;
    else if(c.indexOf(s)>-1)sc=40;
    else sc=10+hits*5;
  }
  if(el.dataset.special)sc+=200;
  return sc;
}
function inCat(el){return !cat||el.dataset.cat===cat||(cat==='__specials__'&&el.dataset.special);}
function apply(){
  var s=norm(q.value.trim().toLowerCase()),n=0;
  if(!s){
    items.forEach(function(el){el._home.appendChild(el);el.hidden=!inCat(el);if(!el.hidden)n++;});
    cats.forEach(function(c){c.hidden=!c.querySelector('.item:not([hidden])');});
    results.hidden=true;
  }else{
    var words=s.split(/\s+/);
    var ranked=items.map(function(el){return {el:el,sc:inCat(el)?score(el,s,words):0};})
      .filter(function(x){return x.sc>0;})
      .sort(function(a,b){return b.sc-a.sc||a.el._idx-b.el._idx;});
    items.forEach(function(el){el.hidden=true;});
    ranked.forEach(function(x){results.appendChild(x.el);x.el.hidden=false;n++;});
    cats.forEach(function(c){c.hidden=true;});
    results.hidden=n===0;
    if(n<=3){ranked.forEach(function(x){if(x.el.tagName==='DETAILS')x.el.open=true;});}
  }
  empty.hidden=n>0;
}
var PKEY='emerys.prices';
function setPrices(on,fromUser){
  sws.forEach(function(b){b.setAttribute('aria-checked',on?'true':'false');}); document.body.classList.toggle('prices',on);
  note.hidden=!(on||document.querySelector('.price.pub:not(.sale)'));
  if(fromUser){try{localStorage.setItem(PKEY,on?'1':'0');}catch(e){}}
}
if(!document.querySelector('.price')){sws.forEach(function(b){b.hidden=true;});}
q.addEventListener('input',function(){if(cat&&q.value.trim()){cat='';[].forEach.call(chips.children,function(x){x.setAttribute('aria-pressed',x.getAttribute('data-cat')===''?'true':'false');});}apply();});
chips.addEventListener('click',function(e){
  var b=e.target.closest('button'); if(!b)return;
  cat=b.dataset.cat;
  [].forEach.call(chips.children,function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});
  apply();
  var cl=document.querySelector('.catalog'),y=cl?cl.getBoundingClientRect().top+window.pageYOffset:0;
  if(wide.matches){if(window.pageYOffset>y)window.scrollTo({top:y});}else{window.scrollTo({top:0});}
});
sws.forEach(function(b){b.addEventListener('click',function(){setPrices(b.getAttribute('aria-checked')!=='true',true);});});
var hash=''; try{hash=location.hash;}catch(e){}
var savedPrices=null; try{savedPrices=localStorage.getItem(PKEY);}catch(e){}
setPrices(hash==='#prices'||savedPrices==='1');
function openItem(id){var t=document.getElementById(id);if(t&&t.classList.contains('item')){if(wide.matches&&openDrawer(t))return;if(t.tagName==='DETAILS')t.open=true;setTimeout(function(){t.scrollIntoView({block:'start'});window.scrollBy(0,-130);},50);}}
try{var h=hash.slice(1);if(h&&h!=='prices'&&h.indexOf('/')<0)openItem(h);}catch(e){}"""


if __name__ == "__main__":
    live = bool(NOTION_TOKEN and DATA_SOURCE)
    # On GitHub (or with PUBLIC=1) a build without Notion still publishes, from the snapshot,
    # but with no price switch, no placeholder logos and no demo file. Locally it is the full demo.
    public = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("PUBLIC") == "1"
    demo = not live and not public
    DEMO_MODE = demo
    if live:
        print("Reading catalogue from Notion")
        rows = notion_rows()
    else:
        print("NOTION_TOKEN not set; using the demo_data.py snapshot")
        rows = demo_rows()
    print(f"{len(rows)} rows")
    os.makedirs(OUT, exist_ok=True)

    brands.load(OUT, token=NOTION_TOKEN if live else None,
                data_source=BRANDS_SOURCE if live else None, placeholders=demo)

    index_html = build(rows, demo=demo)
    with open(f"{OUT}/index.html", "w") as f:
        f.write(index_html)
    from beef import build_beef, build_demo
    beef_html = build_beef(rows, demo=demo)
    with open(f"{OUT}/beef.html", "w") as f:
        f.write(beef_html)
    print(f"wrote {OUT}/index.html and {OUT}/beef.html")
    if demo:
        with open(f"{OUT}/demo.html", "w") as f:
            f.write(build_demo(rows, index_html, beef_html))
        print(f"wrote {OUT}/demo.html (both pages in one file, for showing around)")

    import scale
    from datetime import datetime, timezone
    scale.build(OUT, rows=rows if live else None, code=SHOP_CODE,
                built=datetime.now(timezone.utc).strftime("%b %-d, %Y"))

    brands.CURRENT.survey(public_rows(rows, show_all=demo))
    report = brands.CURRENT.report()
    if report:
        with open(f"{OUT}/brands-todo.txt", "w") as f:
            f.write(report + "\n")
        if not public:
            print("\n" + report)

    if SITE_DOMAIN:
        with open(f"{OUT}/CNAME", "w") as f:
            f.write(SITE_DOMAIN + "\n")
    with open(f"{OUT}/.nojekyll", "w") as f:
        pass
