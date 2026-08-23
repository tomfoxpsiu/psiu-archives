#!/usr/bin/env python3
"""
Generate the static Psi Upsilon Digital Archives site from data/.

  site/                 <- everything you deploy
  build/index_html/     <- throwaway input for the Pagefind indexer

Run build/build.sh rather than calling this directly.
"""
import json, os, re, shutil, html, math, sys, urllib.parse
from collections import defaultdict

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA   = os.path.join(ROOT, "data")
SITE   = os.path.join(ROOT, "site")
IDXDIR = os.path.join(ROOT, "build", "index_html")

SITE_NAME = "Psi Upsilon Digital Archives"
# Set this once you know the public address (e.g. "https://archives.psiu.org/" or
# "https://psiu.org/archives/"). It only affects canonical links, social previews
# and sitemap.xml — the site itself works from anywhere without it.
SITE_URL  = (os.environ.get("PSIU_SITE_URL") or "").rstrip("/")
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

def slugify(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower())

# --------------------------------------------------------------------- data
d = json.load(open(os.path.join(DATA, "items.json")))
ITEMS = d["items"]
COLLS = {c["id"]: c for c in d["collections"]}
STORIES = json.load(open(os.path.join(DATA, "stories.json"))) if os.path.exists(os.path.join(DATA, "stories.json")) else []
MEDIA = json.load(open(os.path.join(DATA, "media.json"))) if os.path.exists(os.path.join(DATA, "media.json")) else []

def _load(name, default):
    fp = os.path.join(DATA, name)
    return json.load(open(fp)) if os.path.exists(fp) else default

PEOPLE   = _load("people.json", [])
CHAPTERS = _load("chapters.json", [])
SONGS    = _load("songs.json", [])
MENTIONS = _load("mentions.json", {})
HERALDRY = _load("heraldry.json", {"blocks": [], "images": []})

PEOPLE_BY_ID   = {p["id"]: p for p in PEOPLE}
CHAPTERS_BY_ID = {c["id"]: c for c in CHAPTERS}
CHAPTER_BY_NAME = {c["name"].lower(): c for c in CHAPTERS}

PERSON_CATS = ["Politics", "Business", "Entertainment", "Athletics",
               "Writers & Publishers", "Education"]

# The three non-paper item types. Each gets a listing page and a detail page;
# adding an entry to data/media.json is all it takes to fill one in.
MEDIA_KINDS = {
  "audio":  dict(slug="recordings", name="Song recordings", icon="audio",
                 blurb="Recordings of the Fraternity's songs and of voices from its history, "
                       "playable here beside the printed music they come from.",
                 empty="No recordings are online yet. If you are holding tapes, discs or digital "
                       "transfers of Psi Upsilon songs, the archive would like to hear from you."),
  "video":  dict(slug="video", name="Video", icon="video",
                 blurb="Convention films, interviews and chapter footage.",
                 empty="Video currently lives on the Fraternity's YouTube channel. Individual films "
                       "will be catalogued here as they are described."),
  "object": dict(slug="objects", name="Objects & artefacts", icon="object",
                 blurb="Badges, banners, gavels, convention souvenirs and other objects from the "
                       "Fraternity collection, photographed and catalogued.",
                 empty="Object records are not online yet. This is where photographs of badges, "
                       "banners and convention souvenirs will live, each with its provenance."),
}

COLL_ORDER = ["diamond", "convention", "annals", "histories", "review", "songbooks", "membered", "special"]

TEXTMETA = {}
for it in ITEMS:
    p = os.path.join(DATA, "text", it["id"] + ".json")
    if os.path.exists(p):
        try:
            j = json.load(open(p))
            TEXTMETA[it["id"]] = dict(pages=j.get("pages"), chars=j.get("chars"),
                                      bytes=j.get("pdf_bytes"), text=j.get("text"))
        except Exception:
            pass

def has_cover(i):  return os.path.exists(os.path.join(SITE, "assets", "covers", i["id"] + ".jpg"))

def _social_image():
    for pref in ("diamond-of-psi-upsilon-1931-4-vol018-num1-nov",
                 "diamond-of-psi-upsilon-1930-1-vol016-num2-jan"):
        if os.path.exists(os.path.join(SITE, "assets", "covers", pref + ".jpg")):
            return "assets/covers/%s.jpg" % pref
    return None
def decade(y):     return f"{(y // 10) * 10}s" if y else "Undated"

SOCIAL_IMAGE = None  # set after SITE/covers are known

INDEXED = [i for i in ITEMS if i["id"] in TEXTMETA]
TOTAL_PAGES = sum((TEXTMETA[i["id"]]["pages"] or 0) for i in INDEXED)
TOTAL_WORDS = sum((TEXTMETA[i["id"]]["chars"] or 0) for i in INDEXED) // 6
YEARS = sorted(i["year"] for i in ITEMS if i["year"])

def human(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M".replace(".0M", "M")
    if n >= 10_000:    return f"{round(n/1000)},000" if n >= 100_000 else f"{n/1000:.0f},000"
    if n >= 1000:      return f"{n:,}"
    return str(n)

def fmt_bytes(n):
    if not n: return ""
    return f"{n/1048576:.0f} MB" if n > 10485760 else f"{n/1048576:.1f} MB"

# --------------------------------------------------------------- chrome
NAV = [("", "index.html", "Search"), ("", "browse.html", "Browse"),
       ("", "collections.html", "Collections"), ("", "people.html", "People"),
       ("", "chapters.html", "Chapters"), ("", "stories/index.html", "Stories"),
       ("", "about.html", "About")]

ICONS = {
 "search": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/></svg>',
 "audio":  '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M9 18V7l10-2v11"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="16.5" cy="16" r="2.5"/></svg>',
 "video":  '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="5" width="18" height="14" rx="3"/><path d="m10 9.5 5 2.5-5 2.5z"/></svg>',
 "object": '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12 4 7.5"/></svg>',
 "photo":  '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="9" cy="10" r="2"/><path d="m4 18 5-4 4 3 3-2.5 4 3.5"/></svg>',
 "story":  '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M5 4h9a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M8 8.5h6M8 12h6M8 15.5h4"/></svg>',
}

def shell(base, title, desc, body, page_js=(), current="", page_url=None, og_image=None):
    cur = ' aria-current="page"'
    nav = "".join(
        '<a href="%s%s"%s>%s</a>' % (base, href, cur if href == current else "", label)
        for _, href, label in NAV)
    scripts = "".join('<script src="%sassets/js/%s" type="module"></script>' % (base, x) for x in page_js)
    canon = ('<link rel="canonical" href="%s/%s">' % (SITE_URL, page_url)) if (SITE_URL and page_url) else ""
    ogurl = ('<meta property="og:url" content="%s/%s">' % (SITE_URL, page_url)) if (SITE_URL and page_url) else ""
    ogimg = ""
    if og_image:
        src = ("%s/%s" % (SITE_URL, og_image)) if SITE_URL else (base + og_image)
        ogimg = '<meta property="og:image" content="%s">' % src
    quick = "" if current == "index.html" else (
        '<form class="topsearch" action="%sindex.html" method="get" role="search">'
        '<label class="sr" for="tq">Search the archives</label>'
        '<input id="tq" name="q" type="search" placeholder="Search the archives\u2026" autocomplete="off">'
        '</form>' % base)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:site_name" content="{E(SITE_NAME)}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
{canon}{ogurl}{ogimg}
<link rel="stylesheet" href="{base}assets/css/site.css">
<link rel="icon" href="{base}assets/favicon.svg" type="image/svg+xml">
<script>window.PSIU_BASE={json.dumps(base)};</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="masthead">
  <div class="wrap masthead-in">
    <a class="brand" href="{base}index.html">
      <span class="mono" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><path d="M6.5 5v5.2a5.5 5.5 0 0 0 11 0V5"/><path d="M12 4.4V20M8.6 20h6.8"/></svg></span>
      <span><b>Psi Upsilon</b><span>Digital Archives</span></span>
    </a>
    {quick}
    <button class="burger" aria-expanded="false" aria-controls="nav">Menu</button>
    <nav class="nav" id="nav" aria-label="Main">{nav}
      <a class="out" href="https://psiu.org/">psiu.org &#8599;</a>
    </nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site">
  <div class="wrap">
    <div class="foot-grid">
      <div>
        <h4>About the archive</h4>
        <p style="margin:0;max-width:44ch">The Psi Upsilon Digital Archives make a selection of the
        Fraternity's records and heritage materials freely available in support of its educational
        mission. Assembled by the History &amp; Archives Committee and the International Office.</p>
      </div>
      <div>
        <h4>Collections</h4>
        <ul>{"".join(f'<li><a href="{base}collections/{c}.html">{E(COLLS[c]["name"])}</a></li>' for c in COLL_ORDER if COLLS.get(c) and COLLS[c]["count"])}</ul>
      </div>
      <div>
        <h4>Elsewhere</h4>
        <ul>
          <li><a href="{base}recordings.html">Song recordings</a></li>
          <li><a href="{base}objects.html">Objects &amp; artefacts</a></li>
          <li><a href="https://www.flickr.com/photos/psiupsilon/albums">Photo galleries (Flickr)</a></li>
          <li><a href="https://www.youtube.com/user/PsiUpsilon">Video (YouTube)</a></li>
          <li><a href="https://issuu.com/psiupsilon">Recent publications (Issuu)</a></li>
          <li><a href="https://necrology.psiu.org/">Necrology</a></li>
          <li><a href="{base}about.html">Contact the archives</a></li>
        </ul>
      </div>
    </div>
    <div class="rule"></div>
    <div class="credit">
      <span>&copy; Psi Upsilon Fraternity. Materials provided for research and educational use.</span>
      <span><a href="{base}about.html#advisory">Content advisory</a></span>
    </div>
  </div>
</footer>
<script src="{base}assets/js/site.js"></script>
{scripts}
</body>
</html>"""

def write(relpath, content):
    p = os.path.join(SITE, relpath)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(content)

# ------------------------------------------------------- shared fragments
def search_panel(base):
    return f"""
<div id="results">
  <div class="wrap">
    <div class="res-top">
      <div><div class="res-count" data-count></div>
        <div class="res-count" style="font-size:12.5px;margin-top:3px;opacity:.8">
          Words are matched separately. Wrap a phrase in <code>&quot;quotes&quot;</code> to require it exactly.
        </div></div>
      <label class="sans" style="font-size:13.5px;color:var(--ink-3)">Order
        <select data-sort style="font:inherit;margin-left:6px;padding:7px 10px;border-radius:6px;border:1px solid var(--line-2);background:var(--card);color:var(--ink)">
          <option value="">Best match</option>
          <option value="year_asc">Oldest first</option>
          <option value="year_desc">Newest first</option>
        </select></label>
    </div>
    <div class="facets" data-facets></div>
    <div data-list></div>
    <button class="btn ghost" data-more style="display:none;width:auto;margin:16px auto 0">Show more</button>
  </div>
</div>"""

def doc_card(i, base):
    tm = TEXTMETA.get(i["id"], {})
    cover = f'{base}assets/covers/{i["id"]}.jpg' if has_cover(i) else None
    inner = (f'<img src="{cover}" alt="Cover of {E(i["title"])}" loading="lazy">'
             if cover else '<div class="ph">no scan preview</div>')
    bits = []
    if i.get("subtitle"): bits.append(E(i["subtitle"]))
    if tm.get("pages"):   bits.append(f'{tm["pages"]} {"slides" if i.get("format") == "pptx" else "pages"}')
    return f"""<a class="doc" href="{base}documents/{i["id"]}.html"
   data-coll="{i['collection']}" data-decade="{decade(i['year'])}" data-year="{i['year'] or 0}"
   data-seq="{i.get('seq') or 0}" data-title="{E(i['title'])}"
   data-search="{E((i['title'] + ' ' + (i.get('subtitle') or '') + ' ' + (i.get('original_label') or '')).lower())}">
  <div class="thumb">{inner}</div>
  <b>{E(i["title"])}</b><span>{" · ".join(bits)}</span></a>"""

# --------------------------------------------------------------- home page
def build_home():
    dec = defaultdict(int)
    for i in ITEMS:
        if i["year"]: dec[(i["year"] // 10) * 10] += 1
    decs = sorted(dec)
    top = max(dec.values())
    tl = "".join(
        f'<a href="browse.html?decade={y}s" title="{dec[y]} items from the {y}s">'
        f'<div class="bar" style="height:{max(6, round(dec[y]/top*104))}px"></div>'
        f'<b>{y}s</b>{dec[y]}</a>' for y in decs)

    cards = []
    for cid in COLL_ORDER:
        c = COLLS.get(cid)
        if not c or not c["count"]: continue
        mine = [i for i in ITEMS if i["collection"] == cid]
        yrs = [i["year"] for i in mine if i["year"]]
        covers = [i for i in mine if has_cover(i)][:3]
        stack = "".join(f'<img src="assets/covers/{i["id"]}.jpg" alt="" loading="lazy">' for i in covers) \
                or '<div class="ph"></div>'
        span = f"{min(yrs)}&ndash;{max(yrs)}" if yrs and min(yrs) != max(yrs) else (str(yrs[0]) if yrs else "")
        cards.append(f"""<a class="card" href="collections/{cid}.html">
  <div class="stack">{stack}</div>
  <div class="card-body">
    <h3>{E(c["name"])}</h3>
    <p>{E(c["blurb"])}</p>
    <div class="foot"><span class="pill">{c["count"]} volumes</span><span>{span}</span></div>
  </div></a>""")

    st = sorted([s for s in STORIES if s.get("cover")], key=lambda s: -(s.get("words") or 0))[:3]
    story_cards = "".join(f"""<a class="card" href="stories/{s['id']}.html">
  <div class="story-img"><img src="{E(s['cover'])}" alt="" loading="lazy"></div>
  <div class="card-body"><h3>{E(s['title'])}</h3><p>{E((s.get('lead') or '')[:150])}…</p>
  <div class="foot"><span class="pill">From the Archives</span>{f"<span>{s['year']}</span>" if s.get('year') else ""}</div>
  </div></a>""" for s in st)

    top_people = sorted(
        [p for p in PEOPLE if mention_data("person", p["id"])],
        key=lambda p: -mention_data("person", p["id"])["volumes"])[:10]
    people_cards = "".join(person_card(p, "") for p in top_people)
    people_vols = sum(mention_data("person", p["id"])["volumes"]
                      for p in PEOPLE if mention_data("person", p["id"]))

    active = [c for c in CHAPTERS if c["status"] == "active"]
    chap_strip = "".join(
        '<a class="armscell" href="chapters/%s.html"><img src="%s" alt="Arms of the %s Chapter" '
        'loading="lazy"><span>%s</span></a>' % (c["id"], E(c["arms"]), E(c["name"]), E(c["name"]))
        for c in CHAPTERS if c.get("arms"))[:100000]

    soon = f"""
  <a class="soon live" href="https://www.flickr.com/photos/psiupsilon/albums">
    <div class="ico">{ICONS['photo']}</div><h3>Photographs</h3>
    <p>Thousands of scanned photographs, currently hosted on Flickr.</p>
    <span class="tag">Live · off-site</span></a>
  <a class="soon live" href="https://www.youtube.com/user/PsiUpsilon">
    <div class="ico">{ICONS['video']}</div><h3>Video</h3>
    <p>Convention footage, interviews and chapter films on the Fraternity's YouTube channel.</p>
    <span class="tag">Live · off-site</span></a>
  <a class="soon{' live' if SONGS else ''}" href="recordings.html">
    <div class="ico">{ICONS['audio']}</div><h3>Song recordings</h3>
    <p>The Fraternity's songs, playable in the browser and cross-referenced against the printed
    music in the songbooks.</p>
    <span class="tag">{f"Live &middot; {len(SONGS)} recordings" if SONGS else 'Section ready'}</span></a>
  <a class="soon live" href="heraldry.html">
    <div class="ico">{ICONS['object']}</div><h3>Heraldry</h3>
    <p>The coat of arms, badge, flag and founders' plaque, with all fifty chapter shields.</p>
    <span class="tag">Live &middot; {len([c for c in CHAPTERS if c.get('arms')])} chapter arms</span></a>
  <a class="soon{' live' if media_of('object') else ''}" href="objects.html">
    <div class="ico">{ICONS['object']}</div><h3>Objects &amp; artefacts</h3>
    <p>Badges, banners, gavels and convention souvenirs, photographed and catalogued with their
    provenance.</p>
    <span class="tag">{f"{len(media_of('object'))} objects" if media_of('object') else 'Section ready · no content yet'}</span></a>"""

    body = f"""
<div class="hero">
  <div class="wrap"><div class="hero-in">
    <p class="eyebrow">The Digital Archives of Psi Upsilon &middot; founded 1833</p>
    <h1>Search <em>{human(TOTAL_PAGES)} pages</em> of Psi Upsilon history.</h1>
    <p class="lede">Every scanned volume in the archive &mdash; the Diamond, the Convention Records,
      the Annals, the printed histories &mdash; read as full text. Search once and see the exact page
      your words appear on.</p>
    <div class="searchbox">
      {ICONS['search']}
      <label class="sr" for="q">Search the archives</label>
      <input id="q" type="search" autocomplete="off" spellcheck="false"
             placeholder="A name, a chapter, a place, a year&hellip;">
    </div>
    <div class="chips"><span>Try:</span>
      <button class="chip" data-suggest="Yule Log">Yule Log</button>
      <button class="chip" data-suggest="Berwanger">Berwanger</button>
      <button class="chip" data-suggest="Ann Arbor">Ann Arbor</button>
      <button class="chip" data-suggest="sweetheart">sweetheart</button>
      <button class="chip" data-suggest="Taft">Taft</button>
    </div>
    <div class="stats">
      <div><b>{len(ITEMS)}</b>volumes online</div>
      <div><b>{human(TOTAL_PAGES)}</b>pages of searchable text</div>
      <div><b>{YEARS[0]}&ndash;{YEARS[-1]}</b>years covered</div>
      <div><b>{human(TOTAL_WORDS)}</b>words indexed</div>
    </div>
  </div></div>
</div>

{search_panel('')}

<section class="band" data-hide-on-search>
  <div class="wrap">
    <div class="sec-head">
      <div><p class="eyebrow">Browse</p><h2>The collections</h2>
        <p>Eight runs of material, from the first convention minutes of 1872 to the last printed Diamond.</p></div>
      <a class="more" href="collections.html">All collections</a>
    </div>
    <div class="grid g-coll">{"".join(cards)}</div>
  </div>
</section>

<section class="band alt" data-hide-on-search>
  <div class="wrap">
    <div class="sec-head">
      <div><p class="eyebrow">By era</p><h2>A century and a half, decade by decade</h2>
      <p>How much of the archive comes from each decade. Pick one to see what survives from it.</p></div>
      <a class="more" href="browse.html">Browse everything</a>
    </div>
    <div class="tl">{tl}</div>
  </div>
</section>

<section class="band alt" data-hide-on-search>
  <div class="wrap">
    <div class="sec-head">
      <div><p class="eyebrow">The brothers</p><h2>People, and the pages that name them</h2>
      <p>Notable alumni tied straight to the primary sources &mdash; {people_vols:,} volume
      appearances found so far across {len(PEOPLE)} men.</p></div>
      <a class="more" href="people.html">All {len(PEOPLE)} people</a>
    </div>
    <div class="grid g-people">{people_cards}</div>
  </div>
</section>

<section class="band" data-hide-on-search>
  <div class="wrap">
    <div class="sec-head">
      <div><p class="eyebrow">The roll</p><h2>Fifty chapters, {min(c["founded"] for c in CHAPTERS) if CHAPTERS else 1833}&ndash;{max(c["founded"] for c in CHAPTERS) if CHAPTERS else 1992}</h2>
      <p>{len(active)} active today. Each shield leads to the chapter's own page: its dates, its
      printed history, its brothers, and every mention of it in the archive.</p></div>
      <a class="more" href="chapters.html">All chapters</a>
    </div>
    <div class="armsgrid">{chap_strip}</div>
  </div>
</section>

<section class="band alt" data-hide-on-search>
  <div class="wrap">
    <div class="sec-head">
      <div><p class="eyebrow">From the Archives</p><h2>Stories out of the collection</h2>
      <p>Short pieces written from the material in these volumes.</p></div>
      <a class="more" href="stories/index.html">All {len(STORIES)} stories</a>
    </div>
    <div class="grid g-story">{story_cards}</div>
  </div>
</section>

<section class="band" data-hide-on-search>
  <div class="wrap">
    <div class="sec-head">
      <div><p class="eyebrow">Also in the archives</p><h2>Beyond the printed page</h2>
      <p>The archive is more than paper. These sections are built and waiting for their content.</p></div>
    </div>
    <div class="grid g-soon">{soon}</div>
  </div>
</section>

<section class="band" data-hide-on-search>
  <div class="wrap narrow">
    <div class="notice" id="advisory">
      <b>A note on historical material.</b> These documents are reproduced as they were printed.
      Some contain language and cultural depictions that are outdated and that do not reflect the
      values Psi Upsilon holds today. They are preserved unaltered because the historical record is
      only useful if it is honest.
    </div>
  </div>
</section>"""
    write("index.html", shell("", f"{SITE_NAME} — search 190 years of Psi Upsilon history",
        f"Full-text search across {len(ITEMS)} scanned volumes of Psi Upsilon publications, "
        f"{human(TOTAL_PAGES)} pages covering {YEARS[0]}–{YEARS[-1]}.",
        body, page_js=["search.js"], current="index.html", page_url="index.html",
        og_image=SOCIAL_IMAGE))

# ------------------------------------------------------------- collections
def build_collections():
    cards = []
    for cid in COLL_ORDER:
        c = COLLS.get(cid)
        if not c or not c["count"]: continue
        mine = [i for i in ITEMS if i["collection"] == cid]
        yrs = [i["year"] for i in mine if i["year"]]
        pages = sum((TEXTMETA.get(i["id"], {}).get("pages") or 0) for i in mine)
        stack = "".join(f'<img src="assets/covers/{i["id"]}.jpg" alt="" loading="lazy">'
                        for i in [x for x in mine if has_cover(x)][:3])
        cards.append(f"""<a class="card" href="collections/{cid}.html">
  <div class="stack">{stack}</div>
  <div class="card-body"><h3>{E(c['name'])}</h3><p>{E(c['blurb'])}</p>
  <div class="foot"><span class="pill">{c['count']} volumes</span>
  <span>{min(yrs)}&ndash;{max(yrs)}</span>{f'<span>{pages:,} pages</span>' if pages else ''}</div>
  </div></a>""")
    body = f"""<div class="wrap"><div class="crumb"><a href="index.html">Archives</a> / Collections</div>
<div class="doc-head"><p class="eyebrow">Browse</p><h1>Collections</h1>
<p class="muted" style="max-width:62ch">Everything in the archive belongs to one of these runs.
Each collection page lists its volumes oldest first, with the number of pages we hold for each.</p></div></div>
<section class="band"><div class="wrap"><div class="grid g-coll">{"".join(cards)}</div></div></section>"""
    write("collections.html", shell("", f"Collections — {SITE_NAME}",
        "The eight collections that make up the Psi Upsilon Digital Archives.", body,
        current="collections.html"))

    for cid in COLL_ORDER:
        c = COLLS.get(cid)
        if not c or not c["count"]: continue
        mine = sorted([i for i in ITEMS if i["collection"] == cid],
                      key=lambda i: (i["year"] or 0, i.get("seq") or 0, i["title"]))
        yrs = [i["year"] for i in mine if i["year"]]
        pages = sum((TEXTMETA.get(i["id"], {}).get("pages") or 0) for i in mine)
        grid = "".join(doc_card(i, "../") for i in mine)
        body = f"""<div class="wrap">
<div class="crumb"><a href="../index.html">Archives</a> / <a href="../collections.html">Collections</a> / {E(c['name'])}</div>
<div class="doc-head"><p class="eyebrow">Collection</p><h1>{E(c['name'])}</h1>
<p style="max-width:66ch;color:var(--ink-2);margin:0 0 14px">{E(c['blurb'])}</p>
<div class="sub"><span class="pill">{c['count']} volumes</span>
  <span>{min(yrs)}&ndash;{max(yrs)}</span>{f'<span>{pages:,} pages of text</span>' if pages else ''}
  <span><a href="../index.html">Search inside this collection →</a></span></div></div></div>
<section class="band"><div class="wrap"><div class="grid g-doc">{grid}</div></div></section>"""
        write(f"collections/{cid}.html", shell("../", f"{c['name']} — {SITE_NAME}", c["blurb"], body,
              page_url=f"collections/{cid}.html", og_image=SOCIAL_IMAGE))

# ------------------------------------------------------------------ browse
def build_browse():
    items = sorted(ITEMS, key=lambda i: (i["year"] or 0, i.get("seq") or 0))
    decs = sorted({decade(i["year"]) for i in ITEMS if i["year"]})
    opt_c = "".join(f'<option value="{c}">{E(COLLS[c]["name"])}</option>'
                    for c in COLL_ORDER if COLLS.get(c) and COLLS[c]["count"])
    opt_d = "".join(f'<option value="{x}">{x}</option>' for x in decs)
    grid = "".join(doc_card(i, "") for i in items)
    body = f"""<div class="wrap"><div class="crumb"><a href="index.html">Archives</a> / Browse</div>
<div class="doc-head"><p class="eyebrow">Everything</p><h1>Browse the archive</h1>
<p class="muted" style="max-width:60ch">All {len(ITEMS)} volumes. Filter by collection or decade, or
type to narrow by title. To search <em>inside</em> the documents, use the
<a href="index.html">main search</a>.</p></div>
<div class="toolbar" style="margin-top:24px">
  <select id="f-coll" aria-label="Collection"><option value="">All collections</option>{opt_c}</select>
  <select id="f-dec" aria-label="Decade"><option value="">All decades</option>{opt_d}</select>
  <select id="f-sort" aria-label="Sort"><option value="old">Oldest first</option>
    <option value="new">Newest first</option><option value="title">By title</option></select>
  <input id="f-q" type="search" placeholder="Filter titles…" aria-label="Filter titles">
  <span id="gridcount" class="muted" style="margin-left:auto"></span>
</div></div>
<section class="band" style="padding-top:8px"><div class="wrap">
  <div class="grid g-doc" id="grid">{grid}</div></div></section>"""
    write("browse.html", shell("", f"Browse — {SITE_NAME}",
        f"All {len(ITEMS)} volumes in the Psi Upsilon Digital Archives.", body,
        page_js=["browse.js"], current="browse.html"))

# --------------------------------------------------------------- documents
def _reverse_index():
    """doc id -> the people and chapters named in it, most-mentioned first."""
    rev = {}
    for kind, key in (("person", "people"), ("chapter", "chapters")):
        for eid, m in (MENTIONS.get(kind) or {}).items():
            for d in m["docs"]:
                rev.setdefault(d["doc"], {}).setdefault(key, []).append((d["count"], eid))
    for doc in rev.values():
        for k in doc:
            doc[k].sort(key=lambda t: -t[0])
    return rev

REVERSE = None

def build_documents():
    global REVERSE
    REVERSE = _reverse_index()
    by_coll = defaultdict(list)
    for i in ITEMS:
        by_coll[i["collection"]].append(i)
    for v in by_coll.values():
        v.sort(key=lambda i: (i["year"] or 0, i.get("seq") or 0, i["title"]))

    for i in ITEMS:
        tm = TEXTMETA.get(i["id"], {})
        c  = COLLS[i["collection"]]
        sibs = by_coll[i["collection"]]
        k = sibs.index(i)
        prev, nxt = (sibs[k-1] if k else None), (sibs[k+1] if k+1 < len(sibs) else None)
        cover = f'../assets/covers/{i["id"]}.jpg' if has_cover(i) else None
        pages = tm.get("pages")
        has_text = bool(tm.get("text"))
        fmt = i.get("format", "pdf")
        unit = "slides" if fmt == "pptx" else "pages"

        kv = [("Collection", f'<a href="../collections/{i["collection"]}.html">{E(c["name"])}</a>'),
              ("Year", E(i["year"]) if i["year"] else "&mdash;")]
        if i.get("subtitle"): kv.append(("Issue", E(i["subtitle"])))
        if pages: kv.append((unit.title(), f"{pages:,}"))
        if tm.get("bytes"): kv.append(("File size", fmt_bytes(tm["bytes"])))
        if tm.get("chars"): kv.append(("Words of text", f"{tm['chars']//6:,}"))
        kv.append(("Format", "PowerPoint" if fmt == "pptx" else "PDF, scanned"))
        kv.append(("Text", ("slide text, searchable" if fmt == "pptx" else "OCR, searchable")
                   if has_text else "not yet extracted"))
        if i.get("source_page"):
            kv.append(("On psiu.org", f'<a href="{E(i["source_page"])}">source page</a>'))

        if fmt != "pdf":
            slides = "".join(
                f'<div class="tpage"><h4>Slide {n}</h4><pre>{E(t)}</pre></div>'
                for n, t in enumerate(tm.get("text") or [], 1) if t)
            reader = f"""
<div class="notice">
  <b>This item is a PowerPoint presentation, not a scan.</b> There is no page-by-page
  reader for it, but its slide text is indexed and searchable, and it is reproduced below.
  <div style="margin-top:12px"><a class="btn" style="width:auto;display:inline-flex"
     href="{E(i['pdf'])}">Download the presentation</a></div>
</div>
<details class="transcript" open><summary>Slide text ({pages} slides)</summary>{slides}</details>"""
        else:
            reader = f"""
<div class="reader" id="reader" data-pdf="{E(i['pdf'])}" data-id="{i['id']}"
     data-pages="{pages or 0}" data-title="{E(i['title'])}">
  <div class="reader-bar" data-bar style="display:none">
    <button data-prev title="Previous page">&larr;</button>
    <span class="muted">Page</span>
    <input data-num type="number" min="1" value="1" aria-label="Page number">
    <span class="muted">of <span data-total>?</span></span>
    <button data-next title="Next page">&rarr;</button>
    <span class="markchip" data-mark></span>
    <span style="margin-left:auto;display:flex;gap:8px">
      <button data-zout title="Zoom out">&minus;</button>
      <button data-zin title="Zoom in">+</button>
      <a class="btn ghost" style="width:auto;margin:0;padding:6px 11px" target="_blank"
         rel="noopener" href="{E(i['pdf'])}">Open PDF ↗</a>
    </span>
  </div>
  <div class="reader-stage" data-stage>
    <div class="reader-msg">
      <p style="font-size:16px;color:var(--ink-2);margin-top:0">Read this volume here, a page at a time.</p>
      <p style="max-width:44ch;margin:0 auto 18px">The scan stays on psiu.org &mdash; only the pages
        you actually turn to are downloaded, so a {fmt_bytes(tm.get('bytes')) or 'large'} volume opens
        in a moment.</p>
      <button class="btn" data-open style="width:auto;display:inline-flex">Open the reader</button>
    </div>
  </div>
</div>

<div class="inpage">
  <h2 style="font-size:21px;margin-bottom:4px">Search inside this volume</h2>
  <p class="muted sans" style="font-size:13.5px;margin:0 0 12px">
    {'Finds every page of this volume that mentions your words, then jumps the reader there.'
      if has_text else 'The text layer for this volume has not been extracted yet.'}</p>
  <div class="searchbox" style="max-width:520px">
    <input id="inq" type="search" placeholder="e.g. a surname, a chapter, a city"
      {'' if has_text else 'disabled'}
      style="padding-left:19px;box-shadow:var(--shadow-sm);border-color:var(--line-2)">
  </div>
  <div class="inpage-hits" id="inhits"></div>
</div>"""

        rev = (REVERSE or {}).get(i["id"], {})
        named = ""
        pp = [PEOPLE_BY_ID[e] for _, e in rev.get("people", []) if e in PEOPLE_BY_ID][:12]
        cc = [CHAPTERS_BY_ID[e] for _, e in rev.get("chapters", []) if e in CHAPTERS_BY_ID][:14]
        if pp or cc:
            bits = []
            if pp:
                bits.append('<div><h3 style="font-size:15px;font-family:var(--sans);'
                            'letter-spacing:.04em;text-transform:uppercase;color:var(--ink-3);'
                            'margin-bottom:10px">Brothers named in this volume</h3>'
                            '<div class="grid g-people">%s</div></div>'
                            % "".join(person_card(p, "../") for p in pp))
            if cc:
                bits.append('<div style="margin-top:24px"><h3 style="font-size:15px;'
                            'font-family:var(--sans);letter-spacing:.04em;text-transform:uppercase;'
                            'color:var(--ink-3);margin-bottom:10px">Chapters named in this volume'
                            '</h3><div class="chiprow">%s</div></div>'
                            % "".join('<a href="../chapters/%s.html">%s</a>' % (c["id"], E(c["name"]))
                                      for c in cc))
            named = ('<div style="margin-top:44px;padding-top:26px;border-top:1px solid var(--line)">'
                     '%s</div>' % "".join(bits))

        nav_links = " ".join(filter(None, [
            f'<a href="{prev["id"]}.html">&larr; {E(prev["title"])}</a>' if prev else "",
            f'<a href="{nxt["id"]}.html" style="margin-left:auto">{E(nxt["title"])} &rarr;</a>' if nxt else ""]))

        body = f"""<div class="wrap">
<div class="crumb"><a href="../index.html">Archives</a> /
  <a href="../collections/{i['collection']}.html">{E(c['name'])}</a> / {E(i['title'])}</div>
<div class="doc-head">
  <p class="eyebrow">{E(c['name'])}</p>
  <h1>{E(i['title'])}</h1>
  <div class="sub">{f'<span class="pill">{E(i["subtitle"])}</span>' if i.get('subtitle') else ''}
    {f'<span>{pages:,} {unit}</span>' if pages else ''}
    {f'<span>{fmt_bytes(tm["bytes"])}</span>' if tm.get('bytes') else ''}
    <span>{E(i['year']) if i['year'] else ''}</span></div>
</div>
<div class="split">
  <div class="aside">
    {f'<img class="cover" src="{cover}" alt="First page of {E(i["title"])}">' if cover else ''}
    <a class="btn" href="{E(i['pdf'])}" target="_blank" rel="noopener">{"Download the presentation" if fmt != "pdf" else "Download the PDF"}</a>
    <a class="btn ghost" href="../collections/{i['collection']}.html">All of {E(c['name'])}</a>
    <ul class="kv">{"".join(f'<li><span>{k}</span><b>{v}</b></li>' for k, v in kv)}</ul>
  </div>
  <div>{reader}
    {named}
    <div class="sans" style="display:flex;gap:18px;margin-top:38px;padding-top:18px;
         border-top:1px solid var(--line);font-size:13.5px">{nav_links}</div>
  </div>
</div></div>"""
        write(f"documents/{i['id']}.html",
              shell("../", f"{i['title']} — {SITE_NAME}",
                    f"{i['title']}. {c['name']}, Psi Upsilon Digital Archives."
                    + (f" {pages} pages, full text searchable." if pages else ""),
                    body, page_js=(["reader.js"] if fmt == "pdf" else []),
                    page_url=f"documents/{i['id']}.html",
                    og_image=(f"assets/covers/{i['id']}.jpg" if cover else SOCIAL_IMAGE)))

# ----------------------------------------------------------------- stories
def build_stories():
    if not STORIES: return
    cards = "".join(f"""<a class="card" href="{s['id']}.html">
  {f'<div class="story-img"><img src="../{E(s["cover"])}" alt="" loading="lazy"></div>' if s.get('cover') else ''}
  <div class="card-body"><h3>{E(s['title'])}</h3>
  <p>{E((s.get('lead') or 'A gallery of scanned pages from the collection.')[:170])}…</p>
  <div class="foot"><span class="pill">From the Archives</span>
  {f"<span>{s['year']}</span>" if s.get('year') else ''}
  {f"<span>{s['words']} words</span>" if s.get('words') else ''}</div></div></a>"""
        for s in STORIES)
    body = f"""<div class="wrap"><div class="crumb"><a href="../index.html">Archives</a> / Stories</div>
<div class="doc-head"><p class="eyebrow">From the Archives</p><h1>Stories out of the collection</h1>
<p class="muted" style="max-width:64ch">Short pieces drawn from the material in these volumes &mdash;
a founder's letter, a Convention special train, a brother who went to Hollywood. Originally published
on psiu.org and gathered here beside the documents they came from.</p></div></div>
<section class="band"><div class="wrap"><div class="grid g-story">{cards}</div></div></section>"""
    write("stories/index.html", shell("../", f"From the Archives — {SITE_NAME}",
        "Short stories written from the Psi Upsilon archival collection.", body,
        current="stories/index.html"))

    for n, s in enumerate(STORIES):
        paras = [p for p in (s.get("body") or "").split("\n\n") if p.strip()]
        out, imgs = [], list(s.get("images") or [])
        lead = imgs.pop(0) if imgs else None
        for k, p in enumerate(paras):
            if p.startswith("[caption]"):
                out.append(f'<p class="muted sans" style="font-size:13.5px">{E(p[9:].strip())}</p>')
            else:
                out.append(f"<p>{E(p)}</p>")
            if imgs and k and k % 3 == 0:
                out.append(f'<figure><img src="../{E(imgs.pop(0))}" alt="" loading="lazy"></figure>')
        for im in imgs:
            out.append(f'<figure><img src="../{E(im)}" alt="" loading="lazy"></figure>')
        if not paras and not out:
            out.append('<p class="muted">This piece is a gallery of scanned pages.</p>')
        nxt = STORIES[(n + 1) % len(STORIES)]
        body = f"""<div class="wrap narrow">
<div class="crumb"><a href="../index.html">Archives</a> / <a href="index.html">Stories</a> / {E(s['title'])}</div>
<div class="doc-head"><p class="eyebrow">From the Archives{f" &middot; {s['year']}" if s.get('year') else ""}</p>
<h1>{E(s['title'])}</h1></div>
{f'<figure style="margin:26px 0"><img src="../{E(lead)}" alt="" style="border-radius:10px;box-shadow:var(--shadow-md)"></figure>' if lead else ''}
<div class="prose" style="padding-bottom:40px">{"".join(out)}</div>
<div class="sans" style="border-top:1px solid var(--line);padding:18px 0 70px;font-size:13.5px;
  display:flex;gap:18px;flex-wrap:wrap">
  <a href="{E(s['url'])}" target="_blank" rel="noopener">Originally published on psiu.org ↗</a>
  <a href="{nxt['id']}.html" style="margin-left:auto">Next story: {E(nxt['title'])} &rarr;</a>
</div></div>"""
        write(f"stories/{s['id']}.html", shell("../", f"{s['title']} — From the Archives",
            (s.get("lead") or s["title"])[:180], body))

# --------------------------------------------------- shared: mention blocks
def mention_data(kind, eid):
    return (MENTIONS.get(kind) or {}).get(eid)

def mention_block(kind, eid, base, term, label_one="volume", show=10):
    """The list of volumes and pages in the archive that mention this thing."""
    m = mention_data(kind, eid)
    if not m or not m["docs"]:
        return ('<p class="muted" style="font-size:15.5px">No mentions found in the scanned '
                'volumes yet. The text layer is machine-read, so a name can be missed where '
                'the print is faint &mdash; the <a href="%sindex.html">main search</a> may '
                'still turn something up.</p>' % base)
    q = "&q=" + urllib.parse.quote(term) if term else ""
    rows = []
    for n, d in enumerate(m["docs"]):
        pages = "".join(
            '<a href="%sdocuments/%s.html#page-%d%s">%d</a>' % (base, d["doc"], pg, q, pg)
            for pg in d["pages"][:12])
        more = ('<span>+%d more</span>' % (d["count"] - 12)) if d["count"] > 12 else ""
        rows.append(
            '<li%s><div class="mrow"><a class="mtitle" href="%sdocuments/%s.html">%s</a>'
            '<span class="myear">%s</span></div>'
            '<p class="msnip">%s</p>'
            '<div class="alsopages"><span>Page%s</span>%s%s</div></li>'
            % (' class="mhide"' if n >= show else "", base, d["doc"], E(d["title"]),
               E(d["year"] or ""), E(d["snippet"]), "s" if len(d["pages"]) > 1 else "",
               pages, more))
    extra = ""
    if len(m["docs"]) > show:
        extra = ('<button class="btn ghost mmore" style="width:auto;margin-top:14px">'
                 'Show the other %d %ss</button>' % (len(m["docs"]) - show, label_one))
    return ('<p class="mcount">Named on <b>%d page%s</b> across <b>%d %s%s</b> of the archive.</p>'
            '<ul class="mlist">%s</ul>%s'
            % (m["total"], "" if m["total"] == 1 else "s", m["volumes"], label_one,
               "" if m["volumes"] == 1 else "s", "".join(rows), extra))

# --------------------------------------------------------------- the people
def person_card(p, base):
    portrait = ('<div class="pface"><img src="%s%s" alt="%s" loading="lazy"></div>'
                % (base, E(p["portrait"]), E(p["name"]))
                if p.get("portrait") else '<div class="pface pinitial">%s</div>'
                % E("".join(w[0] for w in p["name"].split()[:2] if w[0].isalpha())))
    m = mention_data("person", p["id"])
    tag = ('<span class="pill">%d volumes</span>' % m["volumes"]) if m else ""
    return ('<a class="pcard" href="%speople/%s.html">%s<div class="pmeta"><b>%s</b>'
            '<span>%s %s &middot; %s</span>%s</div></a>'
            % (base, p["id"], portrait, E(p["name"]), E(p["chapter"]),
               E(p["year"] or ""), E(p["institution"] or ""), tag))

def build_people():
    if not PEOPLE:
        return
    total_v = sum((mention_data("person", p["id"]) or {}).get("volumes", 0) for p in PEOPLE)
    withhits = sum(1 for p in PEOPLE if mention_data("person", p["id"]))
    sections = []
    for cat in PERSON_CATS + sorted({p["category"] for p in PEOPLE} - set(PERSON_CATS)):
        mine = [p for p in PEOPLE if p["category"] == cat]
        if not mine:
            continue
        mine.sort(key=lambda p: (p["year"] or 9999))
        sections.append('<h2 id="%s">%s <span class="muted sans" style="font-size:14px;'
                        'font-weight:400">%d</span></h2><div class="grid g-people">%s</div>'
                        % (slugify(cat), E(cat), len(mine),
                           "".join(person_card(p, "") for p in mine)))
    jump = " ".join('<a href="#%s">%s</a>' % (slugify(c), E(c))
                    for c in PERSON_CATS if any(p["category"] == c for p in PEOPLE))
    body = ('<div class="wrap"><div class="crumb"><a href="index.html">Archives</a> / People</div>'
            '<div class="doc-head"><p class="eyebrow">The brothers</p><h1>People</h1>'
            '<p class="muted" style="max-width:64ch">The Fraternity\'s notable alumni, each one '
            'linked to every page of the archive that names him. %d of the %d have been found in '
            'the scanned volumes so far, across %s volume appearances in all.</p>'
            '<div class="sans" style="display:flex;gap:14px;flex-wrap:wrap;font-size:13.5px;'
            'margin-top:14px">%s</div></div></div>'
            '<section class="band">%s<div class="wrap">%s</div></section>'
            % (withhits, len(PEOPLE), f"{total_v:,}", jump, "", "".join(sections)))
    write("people.html", shell("", "People — " + SITE_NAME,
          "Psi Upsilon's notable alumni, each linked to every page of the archive that names him.",
          body, current="people.html", page_url="people.html", og_image=SOCIAL_IMAGE))

    for p in PEOPLE:
        last = p["name"].split()[-1]
        ch = CHAPTER_BY_NAME.get(p["chapter"].lower())
        links = "".join(
            '<a class="btn %s" href="%s" target="_blank" rel="noopener">%s &#8599;</a>'
            % ("" if l.get("verified") else "ghost", E(l["url"]), E(l["label"]))
            for l in (p.get("links") or []))
        kv = [("Chapter", ('<a href="../chapters/%s.html">%s</a>' % (ch["id"], E(ch["name"])))
                          if ch else E(p["chapter"])),
              ("Class of", E(p["year"] or "&mdash;")),
              ("Institution", E(p["institution"] or "&mdash;")),
              ("Field", E(p["category"]))]
        portrait = ('<img class="cover" src="../%s" alt="%s">' % (E(p["portrait"]), E(p["name"]))
                    if p.get("portrait") else "")
        body = ('<div class="wrap"><div class="crumb"><a href="../index.html">Archives</a> / '
                '<a href="../people.html">People</a> / %s</div>'
                '<div class="doc-head"><p class="eyebrow">%s &middot; %s %s</p><h1>%s</h1></div>'
                '<div class="split"><div class="aside">%s%s<ul class="kv">%s</ul></div><div>'
                '<div class="prose" style="max-width:66ch"><p>%s</p></div>'
                '<div class="inpage" style="margin-top:34px">'
                '<h2 style="font-size:22px;margin-bottom:4px">In the archive</h2>'
                '<p class="muted sans" style="font-size:13.5px;margin:0 0 14px">Every page of the '
                'scanned volumes that names him. Click a page number to open the scan there with '
                'the name highlighted. Names repeat down the generations, so an occasional page '
                'may be a different brother of the same name.</p>%s</div></div></div></div>'
                % (E(p["name"]), E(p["category"]), E(p["chapter"]), E(p["year"] or ""),
                   E(p["name"]), portrait, links, "".join(
                       "<li><span>%s</span><b>%s</b></li>" % kv_ for kv_ in kv),
                   E(p["bio"]), mention_block("person", p["id"], "../", last)))
        write("people/%s.html" % p["id"],
              shell("../", "%s — %s" % (p["name"], SITE_NAME),
                    (p["bio"] or p["name"])[:180], body, page_js=["mentions.js"],
                    page_url="people/%s.html" % p["id"],
                    og_image=(p["portrait"] if p.get("portrait") else SOCIAL_IMAGE)))

# ------------------------------------------------------------- the chapters
def build_chapter_pages():
    if not CHAPTERS:
        return
    def card(c):
        m = mention_data("chapter", c["id"])
        arms = ('<img src="%s" alt="Arms of the %s Chapter" loading="lazy">' % (E(c["arms"]), E(c["name"]))
                if c.get("arms") else "")
        status = ("Active" if c["status"] == "active"
                  else ("Owl Club" if c["status"] == "owl club" else "Inactive"))
        return ('<a class="chcard %s" href="chapters/%s.html"><div class="charms">%s</div>'
                '<div class="chmeta"><b>%s</b><span>%s</span>'
                '<span class="chfoot"><span class="pill">%s</span>%s%s</span></div></a>'
                % (c["status"].replace(" ", "-"), c["id"], arms, E(c["name"]),
                   E(c["institution"]), c["founded"],
                   '<span class="chstat">%s</span>' % status,
                   ('<span>%d vols</span>' % m["volumes"]) if m else ""))
    act = [c for c in CHAPTERS if c["status"] == "active"]
    rest = [c for c in CHAPTERS if c["status"] != "active"]
    body = ('<div class="wrap"><div class="crumb"><a href="index.html">Archives</a> / Chapters</div>'
            '<div class="doc-head"><p class="eyebrow">The roll</p><h1>Chapters</h1>'
            '<p class="muted" style="max-width:64ch">Fifty chapters chartered since 1833, in the '
            'order they joined the roll. Each has its coat of arms, its place in the roll, and '
            'every mention of it across the scanned volumes.</p>'
            '<div class="sub" style="margin-top:14px"><span class="pill">%d active</span>'
            '<span>%d inactive</span><span>1833&ndash;%d</span></div></div></div>'
            '<section class="band"><div class="wrap">'
            '<h2 style="font-size:24px">Active chapters</h2><div class="grid g-chapters">%s</div>'
            '<h2 style="font-size:24px;margin-top:52px">Chapters no longer active</h2>'
            '<div class="grid g-chapters">%s</div></div></section>'
            % (len(act), len(rest), max(c["founded"] for c in CHAPTERS),
               "".join(card(c) for c in act), "".join(card(c) for c in rest)))
    write("chapters.html", shell("", "Chapters — " + SITE_NAME,
          "All fifty Psi Upsilon chapters, with their arms, their dates, and every mention "
          "in the archive.", body, current="chapters.html", page_url="chapters.html",
          og_image=SOCIAL_IMAGE))

    # "1905 - History of the Phi of Psi Upsilon" -> the Phi; try the two-word
    # chapter names first so "Beta Beta" beats "Beta".
    hist_by_chapter = {}
    for i in ITEMS:
        if i["collection"] != "histories":
            continue
        mm = re.search(r"(?i)history of the\s+((?:\w+\s+){0,2}\w+)", i["title"])
        if not mm:
            continue
        words = mm.group(1).split()
        for n in (2, 1):
            cand = " ".join(words[:n]).lower()
            if cand in CHAPTER_BY_NAME:
                hist_by_chapter.setdefault(cand, []).append(i)
                break

    for n, c in enumerate(CHAPTERS):
        prev = CHAPTERS[n - 1] if n else None
        nxt = CHAPTERS[n + 1] if n + 1 < len(CHAPTERS) else None
        people_here = [p for p in PEOPLE if p["chapter"].lower() == c["name"].lower()]
        hists = hist_by_chapter.get(c["name"].lower(), [])
        status = ("Active since %d" % c["founded"] if c["status"] == "active"
                  else ("Owl Club since %s" % (c["closed"] or "") if c["status"] == "owl club"
                        else "Inactive%s" % (" since %d" % c["closed"] if c["closed"] else "")))
        kv = [("Position on the roll", "#%d" % c["position"]),
              ("Institution", E(c["institution"])),
              ("Chartered", str(c["founded"])),
              ("Status", E(status))]
        if c.get("arms_pdf"):
            kv.append(("Coat of arms", '<a href="%s">full-size PDF</a>' % E(c["arms_pdf"])))
        aside = ""
        if c.get("arms"):
            aside += ('<img class="cover" style="background:var(--card);padding:14px" src="../%s" '
                      'alt="Arms of the %s Chapter">' % (E(c["arms"]), E(c["name"])))
        if c.get("house"):
            aside += ('<figure style="margin:16px 0 0"><img src="../%s" alt="The %s chapter house" '
                      'style="border-radius:6px;border:1px solid var(--line-2)">'
                      '<figcaption class="muted sans" style="font-size:12.5px;margin-top:6px">'
                      'The chapter house</figcaption></figure>' % (E(c["house"]), E(c["name"])))
        blocks = []
        if hists:
            blocks.append('<div style="margin-bottom:30px">'
                          '<h2 style="font-size:22px">Its printed history</h2>'
                          '<div class="grid g-doc" style="margin-top:14px">%s</div></div>'
                          % "".join(doc_card(i, "../") for i in hists))
        if people_here:
            blocks.append('<div style="margin-bottom:30px"><h2 style="font-size:22px">'
                          'Notable brothers of the %s</h2><div class="grid g-people" '
                          'style="margin-top:14px">%s</div></div>'
                          % (E(c["name"]), "".join(person_card(p, "../") for p in people_here)))
        nav = " ".join(x for x in [
            ('<a href="%s.html">&larr; %s</a>' % (prev["id"], E(prev["name"]))) if prev else "",
            ('<a href="%s.html" style="margin-left:auto">%s &rarr;</a>'
             % (nxt["id"], E(nxt["name"]))) if nxt else ""] if x)
        body = ('<div class="wrap"><div class="crumb"><a href="../index.html">Archives</a> / '
                '<a href="../chapters.html">Chapters</a> / %s</div>'
                '<div class="doc-head"><p class="eyebrow">Chapter %d on the roll</p>'
                '<h1>The %s</h1><div class="sub"><span class="pill">%s</span>'
                '<span>%s</span><span>Chartered %d</span></div></div>'
                '<div class="split"><div class="aside">%s<ul class="kv">%s</ul></div><div>%s'
                '<div class="inpage"><h2 style="font-size:22px;margin-bottom:4px">In the archive</h2>'
                '<p class="muted sans" style="font-size:13.5px;margin:0 0 14px">Pages that name the '
                '%s Chapter or its institution.</p>%s</div>'
                '<div class="sans" style="display:flex;gap:18px;margin-top:38px;padding-top:18px;'
                'border-top:1px solid var(--line);font-size:13.5px">%s</div>'
                '</div></div></div>'
                % (E(c["name"]), c["position"], E(c["name"]), E(status), E(c["institution"]),
                   c["founded"], aside,
                   "".join("<li><span>%s</span><b>%s</b></li>" % kv_ for kv_ in kv),
                   "".join(blocks), E(c["name"]),
                   mention_block("chapter", c["id"], "../", c["name"] + " Chapter", "volume"),
                   nav))
        write("chapters/%s.html" % c["id"],
              shell("../", "The %s Chapter — %s" % (c["name"], SITE_NAME),
                    "The %s Chapter of Psi Upsilon at %s, chartered %d."
                    % (c["name"], c["institution"], c["founded"]),
                    body, page_js=["mentions.js"],
                    page_url="chapters/%s.html" % c["id"],
                    og_image=(c["arms"] if c.get("arms") else SOCIAL_IMAGE)))

# ------------------------------------------------------------- recordings
def build_recordings():
    songbooks = [i for i in ITEMS if i["collection"] == "songbooks"]
    annals5 = [i for i in ITEMS if "Songs of Psi Upsilon" in i["title"]]
    if not SONGS:
        return False
    cards = []
    for s_ in SONGS:
        m = mention_data("song", s_["id"])
        cards.append(
            '<article class="song"><div class="shead"><h3>%s</h3>%s</div>'
            '<audio controls preload="none" src="%s"></audio>'
            '<div class="sfoot"><a href="media/%s.html">Where it appears in print &rarr;</a>'
            '<a href="%s" download>Download the recording</a></div></article>'
            % (E(s_["title"]),
               ('<span class="pill">printed in %d volumes</span>' % m["volumes"]) if m else "",
               E(s_["audio"]), s_["id"], E(s_["audio"])))
    intro = ('<p>Ten recordings of the Fraternity\'s songs, made available by the International '
             'Office. Every title is also cross-referenced against the printed songbooks and the '
             'century of Diamonds in this archive, so you can read the music and the chapter '
             'reports of the nights it was sung.</p>'
             '<p class="muted" style="font-size:15.5px">Two lines have appeared in every printed '
             'Psi U songbook since the first in 1849 &mdash; one from <em>The Merchant of '
             'Venice</em>, and one by Francis M. Finch, Beta 1849: &ldquo;Until the sands of life '
             'are run, we\'ll sing to thee, Psi Upsilon.&rdquo;</p>')
    extra = ""
    if songbooks:
        extra = ('<h2 style="font-size:24px;margin-top:54px">The printed songbooks</h2>'
                 '<div class="grid g-doc" style="margin-top:16px">%s</div>'
                 % "".join(doc_card(i, "") for i in songbooks + annals5))
    body = ('<div class="wrap"><div class="crumb"><a href="index.html">Archives</a> / '
            'Song recordings</div><div class="doc-head">'
            '<p class="eyebrow">Beyond the printed page</p><h1>Song recordings</h1>'
            '<div class="prose" style="max-width:66ch">%s</div></div></div>'
            '<section class="band"><div class="wrap"><div class="grid g-songs">%s</div>%s'
            '</div></section>' % (intro, "".join(cards), extra))
    write("recordings.html", shell("", "Song recordings — " + SITE_NAME,
          "Recordings of the songs of Psi Upsilon, cross-referenced against the printed "
          "songbooks and a century of the Diamond.", body,
          page_url="recordings.html", og_image=SOCIAL_IMAGE))

    for s_ in SONGS:
        body = ('<div class="wrap narrow"><div class="crumb"><a href="../index.html">Archives</a> / '
                '<a href="../recordings.html">Song recordings</a> / %s</div>'
                '<div class="doc-head"><p class="eyebrow">Song recording</p><h1>%s</h1></div>'
                '<audio controls preload="none" style="width:100%%;margin:20px 0" src="%s"></audio>'
                '<div class="inpage"><h2 style="font-size:22px;margin-bottom:4px">In the archive</h2>'
                '<p class="muted sans" style="font-size:13.5px;margin:0 0 14px">Where this song is '
                'printed or mentioned in the scanned volumes.</p>%s</div>'
                '<div style="height:60px"></div></div>'
                % (E(s_["title"]), E(s_["title"]), E(s_["audio"]),
                   mention_block("song", s_["id"], "../", s_["title"], "volume")))
        write("media/%s.html" % s_["id"],
              shell("../", "%s — %s" % (s_["title"], SITE_NAME),
                    "A recording of %s, with every appearance of the song in the archive."
                    % s_["title"], body, page_js=["mentions.js"]))
    return True

# --------------------------------------------------------------- heraldry
def build_heraldry_page():
    if not HERALDRY.get("blocks"):
        return
    imgs = {i["id"]: i for i in HERALDRY.get("images", [])}
    def fig(key, cls=""):
        i = imgs.get(key)
        return ('<figure class="hfig %s"><img src="%s" alt="%s" loading="lazy">'
                '<figcaption>%s</figcaption></figure>' % (cls, E(i["src"]), E(i["caption"]),
                                                          E(i["caption"]))) if i else ""
    parts = []
    for b in HERALDRY["blocks"]:
        head = ('<h2>%s</h2>' % E(b["heading"])) if b["heading"] else ""
        paras = "".join("<p>%s</p>" % E(x) for x in b["paras"])
        art = ""
        if b["heading"] == "Fraternity Coat-of-Arms":
            art = fig("arms")
        elif b["heading"] == "Official Flag":
            art = fig("flag")
        elif b["heading"] == "Seal of the Executive Council":
            art = fig("ec")
        parts.append('<section class="hblock">%s<div class="prose">%s</div>%s</section>'
                     % (head, paras, art))
    others = [i for i in HERALDRY.get("images", []) if i["id"] in ("plaque", "diamond-badge", "distinctio")]
    if others:
        parts.append('<section class="hblock"><h2>Other insignia</h2>'
                     '<div class="insignia">%s</div></section>'
                     % "".join('<figure><img src="%s" alt="%s" loading="lazy">'
                               '<figcaption>%s</figcaption></figure>'
                               % (E(i["src"]), E(i["caption"]), E(i["caption"])) for i in others))

    arms_grid = "".join(
        '<a class="armscell" href="chapters/%s.html"><img src="%s" alt="Arms of the %s Chapter" '
        'loading="lazy"><span>%s</span></a>' % (c["id"], E(c["arms"]), E(c["name"]), E(c["name"]))
        for c in CHAPTERS if c.get("arms"))
    body = ('<div class="wrap"><div class="crumb"><a href="index.html">Archives</a> / Heraldry</div>'
            '<div class="doc-head"><p class="eyebrow">Exhibit</p><h1>Heraldry</h1>'
            '<p class="muted" style="max-width:64ch">The system of arms adopted at the Convention '
            'of 1894, and the fifty chapter shields drawn under it.</p></div></div>'
            '<section class="band"><div class="wrap"><div style="max-width:70ch">%s</div></div></section>'
            '<section class="band alt"><div class="wrap"><div class="sec-head"><div>'
            '<p class="eyebrow">All fifty</p><h2>The chapter arms</h2>'
            '<p>Every chapter bears the Fraternity arms differenced by its own charges. '
            'Follow one through to its chapter page.</p></div></div>'
            '<div class="armsgrid">%s</div></div></section>' % ("".join(parts), arms_grid))
    write("heraldry.html", shell("", "Heraldry — " + SITE_NAME,
          "The Psi Upsilon coat of arms, badge, flag and the fifty chapter shields.",
          body, page_url="heraldry.html", og_image=SOCIAL_IMAGE))

# ------------------------------------------------------------------- media
def media_of(kind):
    return sorted([m for m in MEDIA if m.get("type") == kind], key=lambda m: (m.get("year") or 0))

def build_media(skip_audio=False):
    for kind, spec in MEDIA_KINDS.items():
        if kind == "audio" and skip_audio:
            continue
        mine = media_of(kind)
        if mine:
            cards = []
            for m in mine:
                first = (m.get("images") or [None])[0]
                thumb = ('<div class="story-img"><img src="%s" alt="" loading="lazy"></div>'
                         % E(first)) if first else ""
                yr = ("<span>%s</span>" % m["year"]) if m.get("year") else ""
                cards.append(
                    '<a class="card" href="media/%s.html">%s<div class="card-body"><h3>%s</h3>'
                    '<p>%s</p><div class="foot"><span class="pill">%s</span>%s</div></div></a>'
                    % (m["id"], thumb, E(m["title"]), E((m.get("description") or "")[:170]),
                       E(spec["name"]), yr))
            inner = '<div class="grid g-story">%s</div>' % "".join(cards)
        else:
            inner = ('<div class="notice" style="max-width:62ch">%s'
                     '<div style="margin-top:12px"><a href="about.html">'
                     'How to contribute to the archive &rarr;</a></div></div>' % E(spec["empty"]))
        body = ('<div class="wrap"><div class="crumb"><a href="index.html">Archives</a> / %s</div>'
                '<div class="doc-head"><p class="eyebrow">Beyond the printed page</p><h1>%s</h1>'
                '<p class="muted" style="max-width:64ch">%s</p></div></div>'
                '<section class="band"><div class="wrap">%s</div></section>'
                % (E(spec["name"]), E(spec["name"]), E(spec["blurb"]), inner))
        write(spec["slug"] + ".html",
              shell("", "%s — %s" % (spec["name"], SITE_NAME), spec["blurb"], body))

    for m in MEDIA:
        spec = MEDIA_KINDS.get(m.get("type"))
        if not spec:
            continue
        rel = [i for i in ITEMS if i["id"] in (m.get("related") or [])]
        player = ""
        if m.get("type") == "audio" and m.get("audio"):
            player = ('<audio controls preload="none" style="width:100%%;margin:22px 0" '
                      'src="../%s"></audio>' % E(m["audio"]))
        if m.get("type") == "video" and m.get("youtube"):
            player = ('<div style="position:relative;padding-top:56.25%%;margin:22px 0;'
                      'border-radius:10px;overflow:hidden"><iframe loading="lazy" allowfullscreen '
                      'title="%s" style="position:absolute;inset:0;width:100%%;height:100%%;border:0" '
                      'src="https://www.youtube-nocookie.com/embed/%s"></iframe></div>'
                      % (E(m["title"]), E(m["youtube"])))
        for u in (m.get("images") or []):
            player += '<figure><img src="../%s" alt="" loading="lazy"></figure>' % E(u)

        facts = [(k.replace("_", " ").title(), E(m[k])) for k in
                 ("year", "performer", "dimensions", "location", "credit") if m.get(k)]
        kv = ('<ul class="kv" style="max-width:430px">%s</ul>'
              % "".join("<li><span>%s</span><b>%s</b></li>" % kvp for kvp in facts)) if facts else ""
        tr = ('<p class="muted" style="font-size:15px">%s</p>' % E(m["transcript"])) if m.get("transcript") else ""
        relblk = ('<div style="margin-top:34px"><h2 style="font-size:20px">In the documents</h2>'
                  '<div class="grid g-doc" style="margin-top:14px">%s</div></div>'
                  % "".join(doc_card(i, "../") for i in rel)) if rel else ""
        body = ('<div class="wrap narrow"><div class="crumb"><a href="../index.html">Archives</a> / '
                '<a href="../%s.html">%s</a> / %s</div>'
                '<div class="doc-head"><p class="eyebrow">%s</p><h1>%s</h1></div>%s'
                '<div class="prose" style="padding:10px 0 26px"><p>%s</p>%s</div>%s%s'
                '<div style="height:60px"></div></div>'
                % (spec["slug"], E(spec["name"]), E(m["title"]), E(spec["name"]), E(m["title"]),
                   player, E(m.get("description") or ""), tr, kv, relblk))
        write("media/%s.html" % m["id"],
              shell("../", "%s — %s" % (m["title"], SITE_NAME),
                    (m.get("description") or m["title"])[:180], body))

# ------------------------------------------------------------------- about
def build_about():
    body = f"""<div class="wrap narrow">
<div class="crumb"><a href="index.html">Archives</a> / About</div>
<div class="doc-head"><p class="eyebrow">About</p><h1>About the Digital Archives</h1></div>
<div class="prose" style="padding:8px 0 40px">
<p>The Psi Upsilon Digital Archives make a selection of the records and heritage materials of the
Fraternity archives freely available in support of Psi Upsilon's educational mission. The work is
carried out by the History &amp; Archives Committee together with the International Office.</p>

<h2>What is here</h2>
<p>{len(ITEMS)} volumes, {human(TOTAL_PAGES)} scanned pages, spanning {YEARS[0]} to {YEARS[-1]}:
the complete run of the Convention Records, the Diamond from its first number in 1878 to the last
printed issue in 2015, the twelve parts of the Annals, the printed chapter histories, the Review,
the Executive Council songbooks and the member education manuals.</p>

<h2>People and chapters</h2>
<p>Alongside the documents, {len(PEOPLE)} notable alumni and all {len(CHAPTERS)} chapters have
their own pages. Each lists every page of the archive that names them &mdash; worked out by
matching the printed name against the machine-read text, so a brother counts only where his given
name sits beside his surname. Because names repeat down the generations, an occasional page will be
a different brother of the same name; the lists are offered as likely mentions rather than
certainties. Where an outside reference exists it is linked, so a visitor who has never heard of
Amos Alonzo Stagg can read about him before reading him.</p>

<h2>How the search works</h2>
<p>Every volume has been passed through optical character recognition, page by page. Searching looks
inside all of that text at once and reports not just which volume mentions your words but which
page. Clicking a page opens the scan at that page with your words highlighted on it.</p>
<p>Words in a query are matched separately, so <em>Ann Arbor</em> finds pages containing either.
Wrap a phrase in double quotes &mdash; <em>&ldquo;Ann Arbor&rdquo;</em> &mdash; to require it exactly.
Results can be narrowed to one collection or one decade, and ordered oldest or newest first.
Every document page also has its own search box that lists every page of that single volume
mentioning your words.</p>
<p>Because it is machine-read text from old print, the transcription is imperfect &mdash; broken
type, foxed paper and tight gutters all confuse OCR. If a search comes up empty, try a shorter word,
a surname on its own, or an alternative spelling. Searching for a person is usually more reliable
than searching for a phrase.</p>

<h2 id="advisory">A note on historical material</h2>
<div class="notice"><b>These documents are reproduced as they were printed.</b> Some contain
language and cultural depictions that are outdated and that do not reflect the values Psi Upsilon
holds today. They are preserved unaltered because a historical record is only useful if it is
honest.</div>

<h2>Rights and use</h2>
<p>Materials are provided for research, teaching and private study. Psi Upsilon retains rights in its own
publications; please credit the Psi Upsilon Digital Archives when quoting from them, and contact the
International Office before reproducing material commercially.</p>

<h2>Corrections and contributions</h2>
<p>Gaps in the run, misdated issues, missing volumes and OCR errors are all worth reporting &mdash;
so are documents, photographs, recordings and objects you may be holding. The archive grows almost
entirely through what members send in. Write to the International Office at
<a href="mailto:psiu@psiu.org">psiu@psiu.org</a>.</p>

<h2>Elsewhere</h2>
<p><a href="https://www.flickr.com/photos/psiupsilon/albums">Photograph galleries on Flickr</a> &middot;
<a href="https://www.youtube.com/user/PsiUpsilon">Video on YouTube</a> &middot;
<a href="https://issuu.com/psiupsilon">Recent publications on Issuu</a> &middot;
<a href="https://necrology.psiu.org/">Necrology</a></p>
</div></div>"""
    write("about.html", shell("", f"About — {SITE_NAME}",
        "How the Psi Upsilon Digital Archives are built, how the search works, and how to contribute.",
        body, current="about.html"))

# ---------------------------------------------------------- pagefind input
def build_index_input():
    # left in place between runs; each file is rewritten when its content changes
    n = 0
    for i in ITEMS:
        tm = TEXTMETA.get(i["id"])
        if not tm or not tm.get("text"): continue
        c = COLLS[i["collection"]]
        attrs = (f'data-pagefind-filter="collection[data-coll], decade[data-dec]" '
                 f'data-pagefind-meta="title[data-title], collection_name[data-coll], '
                 f'collection_id[data-cid], year[data-year], pagecount[data-pages], cover[data-cover]" '
                 f'data-pagefind-sort="year[data-year]" '
                 f'data-coll="{E(c["name"])}" data-dec="{decade(i["year"])}" '
                 f'data-title="{E(i["title"])}" data-cid="{i["collection"]}" '
                 f'data-year="{i["year"] or 0}" data-pages="{tm.get("pages") or 0}" '
                 f'data-cover="{"assets/covers/" + i["id"] + ".jpg" if has_cover(i) else ""}"')
        parts = [f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>{E(i['title'])}</title></head><body><main data-pagefind-body {attrs}>
<h1 data-pagefind-weight="7">{E(i['title'])}</h1>"""]
        for pn, t in enumerate(tm["text"], 1):
            if not t or len(t) < 12: continue
            parts.append(f'<h3 id="page-{pn}" data-pagefind-weight="0">Page {pn}</h3><p>{E(t)}</p>')
        parts.append("</main></body></html>")
        p = os.path.join(IDXDIR, "documents", i["id"] + ".html")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        blob = "\n".join(parts)
        if not (os.path.exists(p) and os.path.getsize(p) == len(blob.encode("utf-8"))):
            open(p, "w", encoding="utf-8").write(blob)
        n += 1
    # stories are searchable too
    for s in STORIES:
        p = os.path.join(IDXDIR, "stories", s["id"] + ".html")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        sattrs = (f'data-pagefind-filter="collection[data-coll], decade[data-dec]" '
                  f'data-pagefind-meta="title[data-title], collection_name[data-coll], '
                  f'year[data-year], cover[data-cover]" data-pagefind-sort="year[data-year]" '
                  f'data-coll="From the Archives" data-dec="{decade(s.get("year"))}" '
                  f'data-title="{E(s["title"])}" data-year="{s.get("year") or 0}" '
                  f'data-cover="{E(s.get("cover") or "")}"')
        open(p, "w", encoding="utf-8").write(f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><title>{E(s['title'])}</title></head><body><main data-pagefind-body {sattrs}>
<h1 data-pagefind-weight="7">{E(s['title'])}</h1>
<p>{E(s.get('body') or '')}</p></main></body></html>""")
    # audio / video / object records are searchable too
    for m in MEDIA:
        spec = MEDIA_KINDS.get(m.get("type"))
        if not spec: continue
        p = os.path.join(IDXDIR, "media", m["id"] + ".html")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        blob = " ".join(str(m.get(k) or "") for k in
                        ("description", "transcript", "performer", "credit", "location", "dimensions"))
        mattrs = ('data-pagefind-filter="collection[data-coll], decade[data-dec]" '
                  'data-pagefind-meta="title[data-title], collection_name[data-coll], '
                  'year[data-year], cover[data-cover]" data-pagefind-sort="year[data-year]" '
                  'data-coll="%s" data-dec="%s" data-title="%s" data-year="%s" data-cover="%s"'
                  % (E(spec["name"]), decade(m.get("year")), E(m["title"]),
                     m.get("year") or 0, E((m.get("images") or [""])[0])))
        open(p, "w", encoding="utf-8").write(
            '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>%s</title></head>'
            '<body><main data-pagefind-body %s><h1 data-pagefind-weight="7">%s</h1><p>%s</p>'
            '</main></body></html>' % (E(m["title"]), mattrs, E(m["title"]), E(blob)))

    # people, chapters and song records are searchable alongside the scans
    def idx_page(path, title, coll, year, cover, blob, extra_dec=""):
        fp = os.path.join(IDXDIR, path)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        attrs = ('data-pagefind-filter="collection[data-coll], decade[data-dec]" '
                 'data-pagefind-meta="title[data-title], collection_name[data-coll], '
                 'year[data-year], cover[data-cover]" data-pagefind-sort="year[data-year]" '
                 'data-coll="%s" data-dec="%s" data-title="%s" data-year="%s" data-cover="%s"'
                 % (E(coll), extra_dec or decade(year), E(title), year or 0, E(cover or "")))
        open(fp, "w", encoding="utf-8").write(
            '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>%s</title></head>'
            '<body><main data-pagefind-body %s><h1 data-pagefind-weight="8">%s</h1><p>%s</p>'
            '</main></body></html>' % (E(title), attrs, E(title), E(blob)))

    for p_ in PEOPLE:
        idx_page("people/%s.html" % p_["id"], p_["name"], "People", p_.get("year"),
                 p_.get("portrait"),
                 " ".join([p_["bio"], p_["chapter"] + " Chapter", p_.get("institution") or "",
                           p_.get("category") or "", "Psi Upsilon notable alumnus"]))
    for c_ in CHAPTERS:
        idx_page("chapters/%s.html" % c_["id"], "The %s Chapter" % c_["name"], "Chapters",
                 c_["founded"], c_.get("arms"),
                 " ".join([c_["name"] + " Chapter", c_["institution"], c_.get("note") or "",
                           "chartered %d" % c_["founded"], c_["status"]]))
    for s_ in SONGS:
        idx_page("media/%s.html" % s_["id"], s_["title"], "Song recordings", None, None,
                 "Psi Upsilon song recording. " + s_["title"], extra_dec="Undated")

    print(f"  index input: {n} documents + {len(STORIES)} stories + {len(MEDIA)} media"
          f" + {len(PEOPLE)} people + {len(CHAPTERS)} chapters + {len(SONGS)} songs")

# ------------------------------------------------------------------- misc
def build_misc():
    os.makedirs(os.path.join(SITE, "text"), exist_ok=True)
    kept = 0
    for i in ITEMS:
        src = os.path.join(DATA, "text", i["id"] + ".json")
        if not os.path.exists(src):
            continue
        dst = os.path.join(SITE, "text", i["id"] + ".json")
        # skip the copy when it is already there and the same size — makes
        # rebuilds fast, and matters a lot on network or bridged filesystems
        if not (os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src)):
            shutil.copyfile(src, dst)
        kept += 1
    os.makedirs(os.path.join(SITE, "data"), exist_ok=True)
    shutil.copyfile(os.path.join(DATA, "items.json"), os.path.join(SITE, "data", "items.json"))
    write("assets/favicon.svg", """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="12" fill="#571220"/>
<text x="32" y="45" font-family="Georgia,serif" font-size="38" font-weight="bold"
 text-anchor="middle" fill="#e2c684">&#936;</text></svg>""")
    write("robots.txt", "User-agent: *\nAllow: /\n")
    write("404.html", shell("", "Not found — " + SITE_NAME, "That page isn't here.",
        '''<section class="band"><div class="wrap narrow" style="text-align:center;padding:40px 0 80px">
        <p class="eyebrow">404</p>
        <h1 style="font-size:38px">That page isn't in the archive</h1>
        <p class="muted" style="max-width:44ch;margin:0 auto 26px">The link may be old, or the
        volume may have been renamed. The search will almost certainly find it.</p>
        <a class="btn" style="width:auto;display:inline-flex" href="index.html">Search the archive</a>
        </div></section>'''))
    urls = ["index.html", "browse.html", "collections.html", "about.html", "stories/index.html"] \
         + [f"collections/{c}.html" for c in COLL_ORDER if COLLS.get(c) and COLLS[c]["count"]] \
         + [f"documents/{i['id']}.html" for i in ITEMS] \
         + [f"stories/{s['id']}.html" for s in STORIES]
    write("sitemap.txt", "\n".join(urls) + "\n")
    if SITE_URL:
        xml = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for u in urls:
            xml.append("  <url><loc>%s/%s</loc></url>" % (SITE_URL, u))
        xml.append("</urlset>")
        write("sitemap.xml", "\n".join(xml) + "\n")
        write("robots.txt", "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % SITE_URL)
    print(f"  transcripts shipped: {kept}")

def clean_generated():
    """
    Remove previously generated pages so renamed or removed items don't linger.

    Best-effort: some mounts (network shares, the Claude desktop workspace) forbid
    deletion. Every generated file is rewritten in place anyway, so a failure here
    only means stale leftovers from items that no longer exist.
    """
    blocked = 0
    for d in ("documents", "collections", "stories", "media", "text", "pagefind"):
        try:
            shutil.rmtree(os.path.join(SITE, d))
        except FileNotFoundError:
            pass
        except OSError:
            blocked += 1
    for f in ("index.html", "browse.html", "collections.html", "about.html", "404.html",
              "recordings.html", "video.html", "objects.html", "sitemap.txt", "sitemap.xml"):
        try:
            os.remove(os.path.join(SITE, f))
        except FileNotFoundError:
            pass
        except OSError:
            blocked += 1
    if blocked:
        print(f"  note: couldn't clear {blocked} old path(s) — this filesystem forbids delete."
              f" Files are rewritten in place; only orphans from removed items would linger.")

if __name__ == "__main__":
    clean_generated()
    globals()["SOCIAL_IMAGE"] = _social_image()
    print(f"generating site: {len(ITEMS)} items, {len(TEXTMETA)} with text, {len(STORIES)} stories")
    build_home(); build_collections(); build_browse(); build_documents()
    build_stories(); build_people(); build_chapter_pages(); build_heraldry_page()
    have_songs = build_recordings()
    build_media(skip_audio=have_songs); build_about(); build_misc(); build_index_input()
    print("  done")
