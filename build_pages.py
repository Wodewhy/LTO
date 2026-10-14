#!/usr/bin/env python3
"""Build static, search-friendly pages from lto.json.

Writes one page per item (items/<slug>/), one page per chain (chains/<slug>/),
plus sitemap.xml, robots.txt and site.css. Run after collector.py:

    python build_pages.py

Public address: set SITE_URL (env) or site_url (config.yaml). Defaults to the GitHub Pages URL.
"""
import html
import json
import os
import re
import shutil
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).parent
_cfg_path = ROOT / "config.yaml"
CFG = (yaml.safe_load(_cfg_path.read_text()) or {}) if _cfg_path.exists() else {}
SITE = (os.environ.get("SITE_URL") or CFG.get("site_url") or "https://wodewhy.github.io/LTO").rstrip("/")
NAME = CFG.get("site_name") or "LTO Tracker"
CONTACT = str(CFG.get("contact_url") or "https://github.com/Wodewhy/LTO/issues")
if not CONTACT.startswith(("https://", "mailto:")):
    CONTACT = "https://github.com/Wodewhy/LTO/issues"
# US Pacific date, so an offer isn't marked "ended" while the last day is still running out west.
TODAY = datetime.now(ZoneInfo("America/Los_Angeles")).date()
UP = "../../"  # every generated page lives two folders deep
SLUG_OK = re.compile(r"[a-z0-9-]+")

CSS = """:root{--bg:#faf7f2;--card:#fff;--ink:#1d1b19;--mute:#6b645c;--line:#e6dfd5;--accent:#d93a1f;--soon:#b45309;--soonbg:#fef3c7;--ok:#166534;--okbg:#dcfce7;--na:#475569;--nabg:#e2e8f0;--nw:#1d4ed8;--nwbg:#dbeafe;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#171513;--card:#211e1b;--ink:#f3eee7;--mute:#a69d92;--line:#37322c;--accent:#ff6a4d;--soon:#fcd34d;--soonbg:#4a3508;--ok:#86efac;--okbg:#14351f;--na:#cbd5e1;--nabg:#2b3340;--nw:#93c5fd;--nwbg:#172554;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:20px 16px 56px}
a{color:var(--accent)}
.top{margin-bottom:18px;font-weight:700}
.top a{text-decoration:none;color:var(--ink)}.top span{color:var(--accent)}
.crumbs{font-size:.88rem;color:var(--mute);margin-bottom:14px}
h1{font-size:clamp(1.6rem,5vw,2.2rem);line-height:1.2;margin:4px 0 10px;letter-spacing:-.02em}
h2{font-size:1.15rem;margin:28px 0 8px}
.chain{font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;color:var(--accent);font-weight:700;margin:0}
.hero{display:block;width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:14px;background:var(--line);margin-bottom:14px}
.pill{display:inline-block;border-radius:999px;padding:2px 12px;font-weight:600;font-size:.85rem;white-space:nowrap}
.p-ok{background:var(--okbg);color:var(--ok)}.p-soon{background:var(--soonbg);color:var(--soon)}.p-na{background:var(--nabg);color:var(--na)}.p-new{background:var(--nwbg);color:var(--nw)}
.lead{font-size:1.08rem}
.tile{display:grid;place-items:center;aspect-ratio:16/7;border-radius:14px;font-size:3.6rem;margin-bottom:14px;background:hsl(var(--h) 75% 91%)}
@media (prefers-color-scheme:dark){.tile{background:hsl(var(--h) 30% 22%)}}
.facts{display:grid;grid-template-columns:max-content 1fr;gap:6px 16px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:16px 0}
.facts dt{color:var(--mute)}.facts dd{margin:0}
.list{list-style:none;padding:0;margin:0;display:grid;gap:8px}
.list li{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}
.list a{font-weight:600;text-decoration:none;color:var(--ink)}
.note{margin-top:28px;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--mute);font-size:.86rem}
"""


# ----------------------------------------------------------------------------
def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def d(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except (ValueError, TypeError):
        return None


def fmt(x):
    return f"{x:%a, %b} {x.day}, {x.year}"


def long(x):
    return f"{x:%B} {x.day}, {x.year}"


def short(x):
    return f"{x:%b} {x.day}"


def slugify(s):
    s = s.lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:80].strip("-") or "item"


def squash(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


PHOTO_OK = {squash(x) for x in (CFG.get("photo_permission") or [])}  # chains with written photo permission

# Original, brand-free tiles: (emoji, hue). First matching rule wins; the third value means "match the name only".
ICONS = {
    "burger": ("\U0001F354", 28), "chicken": ("\U0001F357", 38), "taco": ("\U0001F32E", 48),
    "pizza": ("\U0001F355", 8), "sandwich": ("\U0001F96A", 85), "coffee": ("\u2615", 25),
    "bakery": ("\U0001F369", 330), "icecream": ("\U0001F366", 200), "drink": ("\U0001F964", 185),
    "sauce": ("\U0001F336\uFE0F", 355), "meal": ("\U0001F37D\uFE0F", 260),
}
RULES = [
    ("sauce", r"\bsauces?\b|\bdips?\b", True),
    ("coffee", r"coffee|latte|espresso|cold brew|frapp|macchiato|cold foam|cappuccino|mocha", False),
    ("icecream", r"ice cream|blizzard|sundae|soft serve|gelato|\bshakes?\b|\bcones?\b|mochi", False),
    ("bakery", r"donut|doughnut|dozen|cookie|\bcakes?\b|pastry|bakery|muffin|croissant|\bpie\b|brownie", False),
    ("pizza", r"pizza|pepperoni", False),
    ("taco", r"taco|burrito|quesadilla|chalupa|crunchwrap|empanada|tostada", False),
    ("sandwich", r"sandwich|\bsubs?\b|cheesesteak|hoagie|\bwraps?\b|panini", False),
    ("burger", r"burger|whopper|big mac|patty|patties|smash", False),
    ("chicken", r"chicken|\bwings?\b|nuggets|tenders|drumstick|popcorn", False),
    ("drink", r"drink|soda|sprite|refresher|lemonade|slush|smoothie|sparkler|punch|beverage|\btea\b|\bcola\b", False),
]
_DEFAULTS = {
    "burger": ["McDonald's", "Burger King", "Wendy's", "Sonic", "Jack in the Box", "Carl's Jr.", "Hardee's",
               "Whataburger", "Culver's", "Shake Shack", "Five Guys", "White Castle", "Steak 'n Shake",
               "Checkers & Rally's", "Krystal"],
    "chicken": ["KFC", "Popeyes", "Chick-fil-A", "Raising Cane's", "Zaxby's", "Bojangles", "Church's Texas Chicken",
                "El Pollo Loco", "Wingstop", "Buffalo Wild Wings", "Dave's Hot Chicken"],
    "taco": ["Taco Bell", "Del Taco", "Chipotle", "Qdoba", "Moe's Southwest Grill"],
    "pizza": ["Domino's", "Pizza Hut", "Papa Johns", "Little Caesars", "Marco's Pizza", "Papa Murphy's"],
    "sandwich": ["Subway", "Arby's", "Jimmy John's", "Jersey Mike's", "Firehouse Subs", "Panera Bread"],
    "coffee": ["Starbucks", "Dunkin'", "Tim Hortons", "Dutch Bros"],
    "bakery": ["Krispy Kreme", "Crumbl"],
    "icecream": ["Dairy Queen", "Baskin-Robbins", "Cold Stone Creamery"],
    "drink": ["Smoothie King", "Tropical Smoothie Cafe"],
}
CHAIN_DEFAULT = {squash(n): cat for cat, names in _DEFAULTS.items() for n in names}


def category(i):
    name = i["name"].lower()
    both = f'{i["name"]} {i.get("desc") or ""}'.lower()
    for cat, rx, name_only in RULES:
        if re.search(rx, name if name_only else both):
            return cat
    return CHAIN_DEFAULT.get(squash(i["chain"]), "meal")


def label(i):
    """'Wingstop Sour Patch Kids Wicked Punch', without doubling the chain name."""
    c, n = i["chain"], i["name"]
    return n if squash(n).startswith(squash(c)) else f"{c} {n}"


def state(i):
    s, e = d(i.get("start")), d(i.get("end"))
    if s and e and s > e:
        s = None
    if e and e < TODAY:
        return "ended", s, e
    if s and s > TODAY:
        return "upcoming", s, e
    return "live", s, e


def pill(st, s, e):
    if st == "ended":
        return "Ended", "p-na"
    if st == "upcoming":
        return f"Starts {short(s)}", "p-new"
    if e:
        return f"Ends {short(e)}", ("p-soon" if (e - TODAY).days <= 7 else "p-ok")
    return "No end date announced", "p-na"


def sentence(i, st, s, e):
    c, n = i["chain"], i["name"]
    if st == "ended":
        return f"{n} at {c} ended on {fmt(e)}."
    if st == "upcoming":
        out = f"{n} arrives at {c} on {fmt(s)}"
        out += f" and is available through {fmt(e)}." if e else f". {c} hasn't announced an end date."
    elif e:
        out = f"{n} is available at {c} through {fmt(e)}."
        if s:
            out += f" It started {fmt(s)}."
    else:
        out = (f"{n} is a limited-time item at {c}. {c} hasn't announced an end date, "
               "and many limited-time items run until supplies last.")
    return out + " Availability and prices can vary by location."


def title_for(i, st, s, e):
    base = label(i)
    if st == "ended":
        t = f"{base} – Ended {long(e)}"
    elif st == "upcoming":
        t = f"{base} – Starts {long(s)}"
    elif e:
        t = f"{base} – Ends {long(e)}"
    else:
        t = f"{base} – Limited-Time Item"
    return f"{t} | {NAME}"


def shell(title, desc, canonical, body, image="", noindex=False):
    og = f'<meta property="og:image" content="{esc(image)}">' if image else ""
    robots = '<meta name="robots" content="noindex,follow">' if noindex else ""
    card = "summary_large_image" if image else "summary"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">{robots}
<meta property="og:type" content="website"><meta property="og:site_name" content="{esc(NAME)}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{esc(canonical)}">{og}
<meta name="twitter:card" content="{card}">
<link rel="stylesheet" href="{UP}site.css">
</head><body><div class="wrap">
<div class="top"><a href="{UP}">&#127828; LTO <span>Tracker</span></a></div>
{body}
<div class="note">Dates come from each chain's announcements and press coverage and can vary by location. Last updated {esc(fmt(TODAY))}. This site is not affiliated with or endorsed by any restaurant; names are trademarks of their owners. Questions or removal requests: <a href="{esc(CONTACT)}">contact us</a>. <a href="{UP}">See all current limited-time offers</a>.</div>
</div></body></html>
"""


def write(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# ----------------------------------------------------------------------------
def main():
    path = ROOT / "lto.json"
    raw = path.read_text()
    data = json.loads(raw)
    items = [i for i in data.get("items", []) if i.get("chain") and i.get("name")]
    data["items"] = items

    # Stable slugs: assigned once, saved back to lto.json, never changed afterwards.
    used = {i["slug"] for i in items if SLUG_OK.fullmatch(i.get("slug") or "")}
    for i in items:
        if not SLUG_OK.fullmatch(i.get("slug") or ""):
            base = slugify(label(i))
            slug, n = base, 2
            while slug in used:
                slug, n = f"{base}-{n}", n + 1
            i["slug"] = slug
            used.add(slug)
    for i in items:
        cat = category(i)
        i["cat"] = cat
        i["icon"], i["hue"] = ICONS[cat]
        i["photo_ok"] = squash(i["chain"]) in PHOTO_OK
        if not i["photo_ok"]:  # no third-party photos without written permission
            i.pop("image", None)
            i.pop("img_checked", None)
    data["contact"] = CONTACT
    new_raw = json.dumps(data, indent=1, ensure_ascii=False)
    if new_raw != raw:
        path.write_text(new_raw)

    info = [state(i) for i in items]
    for sub in ("items", "chains"):
        shutil.rmtree(ROOT / sub, ignore_errors=True)
        (ROOT / sub).mkdir()

    def li(k):
        i = items[k]
        text, cls = pill(*info[k])
        return (f'<li><a href="{UP}items/{i["slug"]}/">{esc(label(i))}</a>'
                f'<span class="pill {cls}">{esc(text)}</span></li>')

    chains = {}
    for k, i in enumerate(items):
        if info[k][0] != "ended":
            chains.setdefault(i["chain"], []).append(k)
    chain_slug = {c: slugify(c) for c in chains}

    # ---- item pages
    for k, i in enumerate(items):
        st, s, e = info[k]
        chain = i["chain"]
        text, cls = pill(st, s, e)
        img = str(i.get("image") or "") if i.get("photo_ok") else ""
        img = img if img.startswith("https://") else ""
        url = str(i.get("url") or "")
        src = esc(i.get("src") or "the original post")
        src_html = (f'<a href="{esc(url)}" rel="noopener noreferrer" target="_blank">{src}</a>'
                    if url.startswith(("http://", "https://")) else src)
        facts = ""
        if s:
            facts += f"<dt>Starts</dt><dd>{esc(fmt(s))}</dd>"
        facts += f"<dt>Ends</dt><dd>{esc(fmt(e)) if e else 'Not announced'}</dd>"
        facts += f"<dt>Source</dt><dd>{src_html}</dd>"
        lead = sentence(i, st, s, e)
        tile_html = (f'<div class="tile" style="--h:{int(i.get("hue", 30))}" aria-hidden="true">'
                     f'<span>{esc(i.get("icon", "\U0001F37D"))}</span></div>')
        hero = (f'<img class="hero" src="{esc(img)}" alt="{esc(label(i))}" referrerpolicy="no-referrer" '
                f'onerror="this.remove()">')
        desc = (i.get("desc") or "").strip()
        about = f"<h2>About this item</h2><p>{esc(desc)}</p>" if desc else ""
        same = [j for j in chains.get(chain, []) if j != k][:8]
        soon = sorted((j for j, x in enumerate(items)
                       if j != k and x["chain"] != chain and info[j][0] == "live" and info[j][2]),
                      key=lambda j: info[j][2])[:6]
        more = ""
        if same:
            more += (f'<h2>More limited-time items at {esc(chain)}</h2><ul class="list">'
                     + "".join(li(j) for j in same) + "</ul>")
        if soon:
            more += ('<h2>Other offers ending soon</h2><ul class="list">'
                     + "".join(li(j) for j in soon) + "</ul>")
        crumb_chain = (f' &rsaquo; <a href="{UP}chains/{chain_slug[chain]}/">{esc(chain)}</a>'
                       if chain in chain_slug else f" &rsaquo; {esc(chain)}")
        body = (f'<div class="crumbs"><a href="{UP}">All offers</a>{crumb_chain}</div><article>'
                + (hero if img else tile_html)
                + f'<p class="chain">{esc(chain)}</p><h1>{esc(i["name"])}</h1>'
                + f'<p><span class="pill {cls}">{esc(text)}</span></p>'
                + f'<p class="lead">{esc(lead)}</p><dl class="facts">{facts}</dl>{about}</article>{more}')
        write(f"items/{i['slug']}/index.html",
              shell(title_for(i, st, s, e), lead, f"{SITE}/items/{i['slug']}/", body, img,
                    noindex=(st == "ended")))

    # ---- chain pages
    for chain, ks in chains.items():
        ks = sorted(ks, key=lambda j: (info[j][0] == "upcoming", info[j][2] or date.max))
        n = len(ks)
        desc = (f"{n} current limited-time item{'s' if n != 1 else ''} at {chain}, "
                "with start and end dates where announced.")
        body = (f'<div class="crumbs"><a href="{UP}">All offers</a> &rsaquo; {esc(chain)}</div>'
                f'<p class="chain">Limited-time menu items</p><h1>{esc(chain)} limited-time offers</h1>'
                f'<p class="lead">{esc(desc)}</p><ul class="list">' + "".join(li(j) for j in ks) + "</ul>")
        write(f"chains/{chain_slug[chain]}/index.html",
              shell(f"{chain} Limited-Time Offers and End Dates | {NAME}", desc,
                    f"{SITE}/chains/{chain_slug[chain]}/", body))

    # ---- sitemap, robots, css
    urls = [(f"{SITE}/", TODAY)]
    urls += [(f"{SITE}/chains/{chain_slug[c]}/", TODAY) for c in chains]
    urls += [(f"{SITE}/items/{i['slug']}/", d(i.get("last_post")) or TODAY)
             for k, i in enumerate(items) if info[k][0] != "ended"]
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "".join(f"<url><loc>{esc(u)}</loc><lastmod>{m.isoformat()}</lastmod></url>\n" for u, m in urls)
           + "</urlset>\n")
    write("sitemap.xml", xml)
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    write("site.css", CSS)
    print(f"built {len(items)} item pages, {len(chains)} chain pages, {len(urls)} sitemap URLs")


if __name__ == "__main__":
    main()
