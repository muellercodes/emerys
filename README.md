# Emery's Meat & Produce, Brewer: website pages and scale trainer

Three pages built from the "Emery's Product Catalogue" and "Emery's Brands" databases in
Notion and published with GitHub Pages. Staff edit Notion. Nothing else needs touching.

| Page | Address | For |
| --- | --- | --- |
| What we carry | https://muellercodes.github.io/emerys/ | customers |
| Beef cuts | https://muellercodes.github.io/emerys/beef.html | customers |
| Scale trainer | https://muellercodes.github.io/emerys/scale/ | staff (prices need the shop code) |

## How it works

    Notion catalogue  -->  GitHub Action  -->  GitHub Pages
    Notion brands          runs build.py      muellercodes.github.io/emerys
    (staff edit here)      nightly, on push,  (later carry.emerysmeatbrewer.com)
                           or on demand

- `build.py` reads every row from Notion, filters out anything internal, downloads and
  resizes photos, and writes `dist/index.html` (What we carry) plus `dist/photos/`.
- `beef.py` writes `dist/beef.html` (Beef Cuts): the chart, the "what are you cooking"
  picker, the compare-two-cuts tool, and the basics. It uses the same rows, so it only
  ever shows cuts the shop carries. Which cut belongs to which part of the animal is the
  `PRIMALS` table in `build.py`; the cooking scenarios and the basics are plain lists at
  the top of `beef.py`. A new beef product in Notion shows up on the chart once its name
  is added to `PRIMALS`.
- `brands.py` reads the brands database, downloads each logo once, and puts it on every
  product whose "Brand / source" text mentions that brand.
- `scale.py` writes `dist/scale/index.html`, the scale trainer (see below).
- Both customer pages share one header, menu, and footer (`SHELL` in `build.py`). They
  are mobile first and open out to two or three columns above 1000px.
- `.github/workflows/build.yml` runs the build at 4am Eastern, on every push to `main`,
  and from the Run workflow button. `gh workflow run build.yml -R muellercodes/emerys`
  does the same from a terminal, which is how a catalogue batch gets published right away.
- Until `SITE_DOMAIN` is set, every page carries `noindex`, so the trial copy on
  github.io never shows up in search results for the shop.

## This repository is public

Free GitHub Pages only publishes from a public repository, so anyone can read every file
and every past commit here. The rules that follow from that:

- Never commit a price list, the Notes column, or a raw Notion export. The build reads
  Notion at run time and publishes only the filtered pages.
- `demo_data.py` is an old snapshot (Sept 6, 2026) that has already been through the
  public filter and has no prices. It is only used when the build can't reach Notion.
- Scale prices are sealed with the shop code before they leave the build (below).
  `scale/prices.locked.json` is a sealed snapshot, unreadable without the code.
- Secrets live in Settings > Secrets and variables > Actions, never in a file.

The other way to keep the code private is GitHub Pro, or Cloudflare Pages from a private
repo. The Cloudflare workflow is parked at `docs/cloudflare-deploy.yml`.

## The scale trainer

A practice copy of the four counter scales: sell by weight or PLU, tare, the price-change
and label procedures, a key quiz that brings back the keys you miss, and a 60 second
rush mode. Scores live on each phone.

- **Keys** come from `scale/layout.json`: what is printed on each key, in PLU order (row
  1 is PLU 1 to 9, each row adds 9). When a scale gets relabeled, edit that file. A blank
  key that has a Notion row with that Scale and PLU fills itself in from the row.
- **Prices** come from Notion: any catalogue row with a **Scale** and a **PLU** prices
  that key, on every build. The 5 lb+ keys read "5 lb or more $X" from the Price notes of
  the key they belong to. Price notes that mention confirming, or a cave sheet price,
  show as unconfirmed or cave sheet in the trainer.
- **Shop code.** Prices ship encrypted with the `SHOP_CODE` secret. Staff type the code
  once on their phone; it is remembered there. To change it:
  `gh secret set SHOP_CODE -R muellercodes/emerys`, then run the workflow. Old phones
  ask for the new code. The sealed snapshot in `scale/prices.locked.json` only matters
  when the build has no Notion access; reseal it with `SHOP_CODE=... python scale.py
  --seal prices.json` if the code changes before then.

## What reaches the page, and what doesn't

Shown: name, category, also called, brand or source, brand logo, what it is, how to
cook, taste, common question, fact, recipe, ingredients, nutrition, photos, price (only
when Show price is ticked), and specials.

Never shown: PLU, scale keys, the Notes column, and any sentence written staff to staff
("ask which cut", "sell the porterhouse"). That filter is a word list and not perfect;
the proper fix is a "Customer answer" column written for the public.

Rows with Status **Ask management** show the name only. Change the status and the full
entry appears on the next build.

Nutrition shows "Typical USDA values" unless the row's Nutrition source is **Label**.
Ingredients only show if the column is filled in from the actual label.

## Daily use (any staff member, on the phone)

- **New product:** open the catalogue in the Notion app, add a row, fill in Name and
  Category. Everything else is optional and can come later.
- **Photo:** open the product row, tap the Photo property, add from camera. Keep it
  under 5 MB (a normal phone photo is fine). The first photo is the thumbnail.
- **Price:** fill in Price and Unit, then tick **Show price**. Unticked, the price
  stays off the site. Anything in Price notes that isn't for the public gets filtered,
  but keep it short.
- **Special:** put the sale price in **Sale price**, the last day in **Sale until**,
  and a short line for customers in **Sale note** ("Through Sunday"). The product moves
  to an "On special" section at the top of the page and comes up first in search. The
  day after Sale until, it drops back into its category by itself. If Show price is also
  ticked, the regular price shows crossed out next to the sale.
- **Publish:** it goes live at 4am. For right now: GitHub > Actions > Build and deploy >
  Run workflow.

## Brand logos

One row per brand in the **Emery's Brands** database. The product rows are not touched.

- **Name** is what shows in the logo's alt text, so write it the way customers say it.
- **Logo** is the image. PNG with a transparent or white background is best. It gets
  resized to 60px tall on a listing and 46px in the strip at the bottom of the page.
- **Matches** is the part that does the work. Put in the text that shows up in a
  product's "Brand / source" field, comma separated, and any product whose source
  mentions it gets the logo. `Herring Brothers` catches both "Herring Brothers Meats"
  and "Herring Brothers Meats, Guilford ME". Longest match wins, so a specific line
  beats a general one. Blank means match on the Name.
- **Show on site** unticked keeps the logo off the site without deleting the row. Use
  this for the house label unless you want the same mark on all 60 house items.
- **Website** is optional; the logo in the bottom strip links there.
- **Notes** never reaches the site. Use it for where the file came from.

Matching runs against the raw Notion text, but the page only ever prints the public
wording, so a row that says "Emery's cut" still reads "Cut in house" to a customer.

Every build writes a report of source texts with no brand row, sorted by how many
products use them, so you know which rows are worth creating. It is attached to the
Actions run as **brand-report**, not published to the site. Locally it is
`dist/brands-todo.txt`.

Get logos from the brand's own media or press kit, or ask the rep for a file. Don't pull
them off a search page.

## Setup on GitHub

Settings > Secrets and variables > Actions:

| Name | Kind | Value |
| --- | --- | --- |
| `NOTION_TOKEN` | secret | the "Website build" integration's secret (below) |
| `NOTION_DATA_SOURCE_ID` | secret | `e29f1c60-ad30-40b7-8ea2-75eeb62239c5` (catalogue) |
| `NOTION_BRANDS_DATA_SOURCE_ID` | secret | `97701d74-b39b-4387-846c-15c71ae7ee25` (brands) |
| `SHOP_CODE` | secret | the code staff type to see scale prices |
| `SITE_DOMAIN` | variable | `carry.emerysmeatbrewer.com`, only once the DNS record exists |

Settings > Pages > Source is **GitHub Actions**.

**The Notion token.** notion.so/profile/integrations > New integration, named "Website
build", internal, capabilities **Read content** only. Copy the secret into
`NOTION_TOKEN`. Then on each database (catalogue and brands): ... menu > Connections >
add "Website build". Connecting one database does not connect the other, and a missing
brands connection fails quietly: a green build with no logos.

Without `NOTION_TOKEN` the build still publishes, from the old snapshot and the sealed
scale prices, so the pages never go blank.

## Moving to the shop's domain and accounts

The trial runs on Andrew's GitHub and Notion. Do it in this order so nothing goes down.

1. **Notion.** In the shop's workspace, duplicate both databases. Create the "Website
   build" integration there, connect it to both, and update the three Notion secrets.
2. **GitHub.** Settings > Danger Zone > Transfer ownership > the shop's account.
   Secrets and variables do not transfer: add them again, and set Pages to GitHub
   Actions again. The address becomes `<account>.github.io/emerys/`.
3. **DNS** (GoDaddy): CNAME record, name `carry`, value `<account>.github.io`. Then add
   `SITE_DOMAIN` = `carry.emerysmeatbrewer.com` as an Actions variable and run the
   workflow. That writes the CNAME file and lets search engines in. Add a "What We
   Carry" link in the GoDaddy site menu pointing at it.
4. Remove Andrew as a collaborator and a Notion guest when ready.

## If it stops updating

Nothing breaks. The site keeps showing the last good build. Check GitHub > Actions for
the red run and read the last few lines. The usual causes: the Notion token was revoked,
the integration lost access to one of the databases, or a photo in Notion is corrupt (a
bad photo is skipped with a warning, it does not stop the build).

GitHub pauses scheduled runs on repos with no commits for 60 days. The workflow commits
`last-build.txt` once a month to prevent that. If it ever does pause, the Actions tab
shows an "Enable workflow" button.

## Local preview

    pip install -r requirements.txt
    python build.py          # uses demo_data.py and brands_data.py if NOTION_TOKEN is not set
    open dist/index.html

`dist/demo.html` is both customer pages in one file with a prices toggle, for showing
around without hosting anything. `PUBLIC=1 python build.py` builds exactly what GitHub
publishes when it has no Notion access.
