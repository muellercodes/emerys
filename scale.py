"""
Builds the scale trainer for Emery's staff: dist/scale/index.html.

The keys come from scale/layout.json (what is printed on each key, in PLU order). Prices
come from the Notion catalogue: a row with a Scale and a PLU sets the price for that key.
A blank key in the layout that has a Notion row behind it gets filled in from the row.

The site is public, so the price list never ships readable. It is encrypted with the shop
code (the SHOP_CODE secret) and only opens on a phone where someone types the code.

Without Notion access the build falls back to scale/prices.locked.json, a sealed snapshot
made with:

    SHOP_CODE=... python scale.py --seal prices.json     (prices.json: {"scale:key": [price, flag]})
"""
import base64
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAYOUT = os.path.join(HERE, "scale", "layout.json")
TEMPLATE = os.path.join(HERE, "scale", "trainer.html")
SNAPSHOT = os.path.join(HERE, "scale", "prices.locked.json")
ITERATIONS = 310_000


def load_layout():
    with open(LAYOUT, encoding="utf-8") as f:
        return json.load(f)


# ---------- prices ----------
def _flag(r):
    """'cave' for a primal sheet price, 'check' for one read off a board that needs confirming."""
    notes = r.get("price_notes") or ""
    p = r.get("price")
    if p is not None and re.search(r"cave sheet", notes, re.I) and re.search(re.escape(f"${p:.2f}"), notes):
        return "cave"
    if re.search(r"confirm|sit a half|unconfirmed|\?", notes, re.I):
        return "check"
    return ""


def _five_lb(notes):
    m = re.search(r"5 (?:lb|lbs|pounds?) or more \$(\d+(?:\.\d+)?)", notes or "", re.I)
    return float(m.group(1)) if m else None


def _rows_by_key(rows, layout):
    names = [s["name"] for s in layout["scales"]]
    out = {}
    for r in rows:
        sc, plu = r.get("scale"), r.get("plu")
        if sc in names and plu:
            out[(names.index(sc), int(plu) - 1)] = r
    return out


def prices_from_rows(rows, layout):
    """{"scale:key": [price, flag]} for every key the catalogue has a price for."""
    by_key = _rows_by_key(rows, layout)
    prices = {}
    for si, s in enumerate(layout["scales"]):
        for ki, k in enumerate(s["keys"]):
            if k and k.get("five_lb_price_of"):
                base = by_key.get((si, k["five_lb_price_of"] - 1))
                p = _five_lb(base.get("price_notes")) if base else None
                if p is not None:
                    prices[f"{si}:{ki}"] = [p, ""]
                continue
            r = by_key.get((si, ki))
            if r and r.get("price") is not None:
                prices[f"{si}:{ki}"] = [r["price"], _flag(r)]
    return prices


def seal(obj, code):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=ITERATIONS).derive(code.strip().lower().encode())
    ct = AESGCM(key).encrypt(iv, json.dumps(obj, separators=(",", ":")).encode(), None)
    b = lambda x: base64.b64encode(x).decode()
    return {"v": 1, "iter": ITERATIONS, "salt": b(salt), "iv": b(iv), "ct": b(ct)}


# ---------- keys ----------
def _short_label(name):
    """Two short lines for a key the layout doesn't know yet, from the Notion name."""
    words = re.sub(r"\s*\([^)]*\)", "", name).split()
    a, b = "", ""
    for w in words:
        if len(a) + len(w) + (1 if a else 0) <= 9 and not b:
            a = (a + " " + w).strip()
        else:
            b = (b + " " + w).strip()
    return a if not b else a + "\n" + b[:9]


def page_layout(layout, rows):
    """The arrays the trainer expects: [{name, tint:[0-based], keys:[[label, name, each] | null]}]."""
    by_key = _rows_by_key(rows, layout)
    out = []
    for si, s in enumerate(layout["scales"]):
        keys = []
        for ki, k in enumerate(s["keys"]):
            if k:
                keys.append([k["label"], k["name"], 1 if k.get("each") else 0])
            elif (si, ki) in by_key and by_key[(si, ki)].get("name"):
                r = by_key[(si, ki)]
                nm = re.sub(r"\s*\([^)]*\)", "", r["name"]).strip()
                keys.append([_short_label(nm), nm, 1 if r.get("unit") == "each" else 0])
            else:
                keys.append(None)
        out.append({"name": s["name"], "tint": [t - 1 for t in s.get("tinted_keys", [])], "keys": keys})
    return out


# ---------- page ----------
def _js(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def build(out_dir, rows=None, code=None, built=""):
    """rows: catalogue rows from Notion, or None when the build has no Notion access."""
    layout = load_layout()
    locked, priced = None, 0
    if rows is not None and code:
        prices = prices_from_rows(rows, layout)
        locked, priced = seal(prices, code), len(prices)
        print(f"scale trainer: {priced} keys priced from Notion, sealed with the shop code")
    elif rows is not None:
        print("scale trainer: SHOP_CODE is not set, so it is built without prices", file=sys.stderr)
    elif os.path.exists(SNAPSHOT):
        with open(SNAPSHOT) as f:
            snap = json.load(f)
        locked, priced, built = snap["locked"], snap["priced"], f"snapshot from {snap['built']}"
        print(f"scale trainer: no Notion access, using the sealed snapshot ({priced} keys)")
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    for old, new in (("/*LAYOUT*/[]", _js(page_layout(layout, rows or []))),
                     ("/*PRICES*/null", _js(locked) if locked else "null"),
                     ("__BUILT__", built or "unknown"), ("__PRICED__", str(priced))):
        assert old in html, old
        html = html.replace(old, new)
    os.makedirs(f"{out_dir}/scale", exist_ok=True)
    with open(f"{out_dir}/scale/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {out_dir}/scale/index.html")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--seal":
        code = os.environ.get("SHOP_CODE")
        if not code:
            sys.exit("set SHOP_CODE")
        with open(sys.argv[2]) as f:
            prices = json.load(f)
        from datetime import date
        with open(SNAPSHOT, "w") as f:
            json.dump({"built": date.today().isoformat(), "priced": len(prices), "locked": seal(prices, code)}, f, indent=1)
            f.write("\n")
        print(f"sealed {len(prices)} prices into {SNAPSHOT}")
    else:
        sys.exit(__doc__)
