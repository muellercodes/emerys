"""
Brand logos.

One row per brand in the "Emery's Brands" database in Notion: a Name, a Logo file, and
a "Matches" field listing the text that shows up in a product's "Brand / source" field.
The build reads that database, downloads each logo once, and puts it on every product
whose source text contains one of the brand's match strings.

Nothing here is required. With no brands database set, the site builds exactly as before.
"""
import io
import os
import re
import sys

NOTION_VERSION = "2025-09-03"

# The one brand index for this build. build.py and beef.py both read it from here, so
# they see the same object no matter which of them imported the other first.
CURRENT = None

# Longest match wins, so "Herring Brothers Meats, Guilford ME" picks Herring Brothers and
# not some shorter brand whose name happens to appear inside it.
_MIN_NEEDLE = 3


# ---------- read from Notion ----------
def notion_brands(token, data_source):
    import requests
    url = f"https://api.notion.com/v1/data_sources/{data_source}/query"
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION,
               "Content-Type": "application/json"}
    out, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(url, headers=headers, json=body, timeout=60)
        r.raise_for_status()
        d = r.json()
        out += d["results"]
        if not d.get("has_more"):
            break
        cursor = d["next_cursor"]
    return [_normalize(p["properties"]) for p in out]


def _text(prop):
    t = prop.get("type")
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in prop.get(t, [])).strip()
    return ""


def _first_file(prop):
    for f in prop.get("files", []):
        u = f.get("file", {}).get("url") or f.get("external", {}).get("url")
        if u:
            return u
    return ""


def _normalize(P):
    g = lambda k: P.get(k, {})
    name = _text(g("Name"))
    matches = [m.strip() for m in _text(g("Matches")).split(",") if m.strip()]
    return {
        "name": name,
        "logo": _first_file(g("Logo")),
        "matches": matches or ([name] if name else []),
        "url": g("Website").get("url") or "",
        "show": bool(g("Show on site").get("checkbox")),
    }


# ---------- the placeholder logos used for local previews ----------
def _placeholder(name):
    """A marked-up box in the site's colours, so a preview shows the shape of the thing
    without anyone mistaking it for a real logo."""
    w = max(150, 13 * len(name) + 40)
    return ("data:image/svg+xml;utf8,"
            f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} 60'>"
            f"<rect x='1' y='1' width='{w-2}' height='58' fill='%23faf2f0' stroke='%23cdb9ab' stroke-dasharray='5 4'/>"
            f"<text x='{w//2}' y='30' text-anchor='middle' font-family='Georgia,serif' font-size='17' fill='%236b4031'>"
            f"{name}</text>"
            f"<text x='{w//2}' y='46' text-anchor='middle' font-family='Helvetica,Arial' font-size='9.5'"
            f" letter-spacing='1.4' fill='%23968175'>LOGO GOES HERE</text></svg>")


def demo_brands():
    """Used when there is no Notion access. Reads brands_data.py if it is there."""
    try:
        import brands_data
    except ImportError:
        return []
    out = []
    for b in brands_data.BRANDS:
        b = dict(b)
        b.setdefault("show", True)
        b.setdefault("url", "")
        b.setdefault("matches", [b["name"]])
        b["logo"] = b.get("logo") or _placeholder(b["name"])
        out.append(b)
    return out


# ---------- matching ----------
class Index:
    """Maps a product's "Brand / source" text to a brand row."""

    def __init__(self, brands, out_dir):
        self.out = out_dir
        self.brands = [b for b in brands if b.get("name")]
        self.needles = sorted(
            ((m.lower(), b) for b in self.brands for m in b["matches"] if len(m) >= _MIN_NEEDLE),
            key=lambda x: -len(x[0]))
        self.unmatched = {}     # source text -> how many products use it
        self.used = set()       # names of brands that reached the page
        self._files = {}

    def match(self, src):
        """Returns the brand row for this source text, or None."""
        if not src:
            return None
        s = src.lower()
        for needle, b in self.needles:
            if needle in s:
                return b
        return None

    def survey(self, rows):
        """Counts products whose source text hits no brand row. Called once, on the full
        list, so the numbers in the report are products and not page appearances."""
        for r in rows:
            src = (r.get("raw_src") or r.get("src") or "").strip()
            if not src or not r.get("src"):
                continue                      # no source, or one the page hides anyway
            if not self.match(src):
                self.unmatched[src] = self.unmatched.get(src, 0) + 1

    def logo(self, src):
        """Returns (path, name, url) for the logo to show next to a product, or None."""
        b = self.match(src)
        if not b or not b["logo"] or not b["show"]:
            return None
        path = self._logo_file(b)
        if not path:
            return None
        self.used.add(b["name"])
        return path, b["name"], b["url"]

    def all_logos(self):
        """Every brand with a usable logo, for the strip at the bottom of the page."""
        out = []
        for b in sorted(self.brands, key=lambda x: x["name"].lower()):
            if not b["logo"] or not b["show"]:
                continue
            path = self._logo_file(b)
            if path:
                out.append((path, b["name"], b["url"]))
        return out

    # Downloads once per brand, writes dist/brands/<name>.png at 2x the display height.
    def _logo_file(self, b):
        if b["name"] in self._files:
            return self._files[b["name"]]
        self._files[b["name"]] = path = self._write(b)
        return path

    def _write(self, b):
        src = b["logo"]
        if src.startswith("data:"):
            return src                      # placeholder, inline it as-is
        try:
            from PIL import Image
            import requests
            data = requests.get(src, timeout=60).content if src.startswith("http") else open(src, "rb").read()
            img = Image.open(io.BytesIO(data))
            img = img.convert("RGBA") if img.mode in ("RGBA", "LA", "P") else img.convert("RGB")
            img.thumbnail((520, 120))       # 2x the 60px display height
            os.makedirs(f"{self.out}/brands", exist_ok=True)
            name = re.sub(r"[^a-z0-9]+", "-", b["name"].lower()).strip("-")
            path = f"brands/{name}.png"
            img.save(f"{self.out}/{path}", "PNG", optimize=True)
            return path
        except Exception as e:
            print(f"  logo skipped for {b['name']}: {e}", file=sys.stderr)
            return None

    # ---------- the report ----------
    def report(self):
        lines = []
        if self.brands:
            missing = [b["name"] for b in self.brands if not b["logo"]]
            off = [b["name"] for b in self.brands if b["logo"] and not b["show"]]
            lines.append(f"{len(self.used)} of {len(self.brands)} brands showed a logo.")
            if missing:
                lines.append("No logo uploaded yet: " + ", ".join(sorted(missing)))
            if off:
                lines.append("Logo uploaded but Show on site is unticked: " + ", ".join(sorted(off)))
        if self.unmatched:
            lines.append("")
            lines.append("Product sources with no brand row (count, text). Add a row in the brands")
            lines.append("database for any of these worth a logo, and put the text in Matches:")
            for src, n in sorted(self.unmatched.items(), key=lambda x: -x[1]):
                lines.append(f"  {n:>4}  {src}")
        return "\n".join(lines)


def load(out_dir, token=None, data_source=None, placeholders=True):
    global CURRENT
    if token and data_source:
        rows = notion_brands(token, data_source)
        print(f"{len(rows)} brands")
    elif not placeholders:
        rows = []          # public build without Notion: no drawn stand-ins for real brands
    else:
        rows = demo_brands()
        if rows:
            print(f"{len(rows)} brands from brands_data.py (placeholder logos)")
    CURRENT = Index(rows, out_dir)
    return CURRENT
