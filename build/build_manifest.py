#!/usr/bin/env python3
"""Parse the crawled WordPress archive pages into a structured item manifest."""
import re, json, html, glob, os, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CRAWL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "crawl")
OUT   = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "data", "items.json")

# WordPress has shipped at least two markup variants for the file block:
#   <div class="wp-block-file"><a href="…pdf">Label</a><a …>Download</a></div>
#   <div data-wp-interactive="core/file" class="wp-block-file"><object …/><a href="…pdf">Label</a>…
# Find the block first, then the first real link inside it.
BLOCK_RE = re.compile(r'<div[^>]*class="[^"]*wp-block-file[^"]*"[^>]*>', re.I)
LINK_RE  = re.compile(r'<a[^>]*href="(https://psiu\.org/wp-content/uploads/[^"]+?\.(?:pdf|pptx))(?:\?[^"]*)?"[^>]*>(.*?)</a>',
                      re.S | re.I)

def find_files(h):
    """Yield (pdf_url, label) for every file block on the page."""
    out = []
    for m in BLOCK_RE.finditer(h):
        chunk = h[m.end(): m.end() + 4000]
        end = chunk.find("</div>")
        if end > 0: chunk = chunk[:end + 6]
        for url, label in LINK_RE.findall(chunk):
            txt_label = re.sub(r"<[^>]+>", "", label).strip()
            if txt_label.lower() in ("download", ""):
                continue
            out.append((url, label))
            break
    return out

H_RE = re.compile(r'<h([12])[^>]*>(.*?)</h\1>', re.S | re.I)
INTRO_RE = re.compile(r'<h1 class="wp-block-heading">(.*?)</h1>\s*(?:<p class="wp-block-paragraph">(.*?)</p>)?', re.S)

MONTHS = {'jan':'January','feb':'February','mar':'March','apr':'April','may':'May','jun':'June',
          'jul':'July','aug':'August','sep':'September','oct':'October','nov':'November','dec':'December',
          'win':'Winter','spr':'Spring','sum':'Summer','aut':'Autumn','fal':'Fall'}

def txt(s):
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s).replace('–','-').replace('—','-').replace(' ',' ')
    return re.sub(r'\s+', ' ', s).strip()

SOURCE_URLS = {
    "diamond":    "https://psiu.org/about/history/archives-diamond-of-psi-upsilon/",
    "convention": "https://psiu.org/about/history/archives-convention-records",
    "annals":     "https://psiu.org/archives-annals-of-psi-upsilon/",
    "histories":  "https://psiu.org/about/history/archives-printed-histories/",
    "review":     "https://psiu.org/about/history/archives-the-review-original-run/",
    "songbooks":  "https://psiu.org/about/history/archives-songbooks/",
    "membered":   "https://psiu.org/about/history/archives-member-education-guides/",
    "special":    "https://psiu.org/about/history/archives-special-collections/",
}

def source_url(path, coll):
    """The psiu.org page this record was read from."""
    base = os.path.basename(path)
    m = re.match(r"archives-(\d{4})-diamond\.html$", base)
    if m:
        return "https://psiu.org/archives-%s-diamond/" % m.group(1)
    return SOURCE_URLS.get(coll["id"])

def slugify(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+','-', s).strip('-').lower()
    return re.sub(r'-{2,}','-', s)

# ---- collection definitions -------------------------------------------------
COLLECTIONS = [
    dict(id="diamond",   name="The Diamond",              source="pages/archives-*-diamond.html",
         blurb="The Fraternity's magazine, published 1878-1887 and again from 1920 to 2015. The single richest record of Psi Upsilon life: chapter letters, alumni notes, obituaries, convention coverage and photographs."),
    dict(id="convention", name="Convention Records",       source="raw_70fbe905.html",
         blurb="Official proceedings of the annual Convention, 1872 to 1972. Delegate rolls, reports, resolutions and addresses."),
    dict(id="annals",     name="Annals of Psi Upsilon",    source="raw_fbae9ccc.html",
         blurb="The 1941 centennial history of the Fraternity, issued in twelve parts."),
    dict(id="histories",  name="Printed Histories",        source="raw_40db17fa.html",
         blurb="Book-length histories of the Fraternity and of individual chapters, from 1883 onward."),
    dict(id="review",     name="The Review",               source="raw_1f7ca0a2.html",
         blurb="A short-lived newsletter published by The Psi Upsilon Review Company of Detroit, 1895-1896."),
    dict(id="songbooks",  name="Songbooks",                source="raw_d6fd98d4.html",
         blurb="Psi Upsilon printed its first songbook in 1849. These are the bound editions published by the Executive Council."),
    dict(id="membered",   name="Member Education",         source="raw_96a17a21.html",
         blurb="Pledge manuals and editions of the College Tablet used to teach new members."),
    dict(id="special",    name="Special Collections",      source="raw_97980ee7.html",
         blurb="Material that doesn't fit the serial runs: committee presentations, one-off documents and curiosities."),
]

def parse_title(raw, coll):
    """Return (display_title, year, sort_key_extra, subtitle)."""
    t = txt(raw)
    year, sub = None, None
    m = re.search(r'(?<![0-9])(1[78]\d\d|19\d\d|20[0-2]\d)(?![0-9])', t.replace('_',' '))
    if m: year = int(m.group(1))

    if coll == "diamond":
        # "Diamond of Psi Upsilon 1930 1. Vol016 Num2 Jan" / "... 2007 1. Vol092 1-2 Spr"
        mm = re.match(r'Diamond of Psi Upsilon\s+(\d{4})\s*[-\s]*(\d+)?\.?\s*(?:Vol0*(\d+))?\s*(?:Num\s*0*([\d-]+)|(?<=\s)([\d]+-[\d]+))?\s*([A-Za-z]+)?\s*$', t)
        if mm:
            year = int(mm.group(1)); seq = mm.group(2); vol = mm.group(3)
            num = mm.group(4) or mm.group(5); per = mm.group(6)
            period = MONTHS.get((per or '').lower()[:3], per or '')
            label = f"{period} {year}".strip() if period else str(year)
            bits = []
            if vol: bits.append(f"Vol. {int(vol)}")
            if num: bits.append(f"No. {num}")
            sub = ", ".join(bits) or None
            return f"The Diamond - {label}", year, int(seq or 0), sub

    if coll == "convention":
        if year: return f"{year} Convention Records", year, 0, None

    if coll == "annals":
        mm = re.match(r'Annals of Psi Upsilon Pt\s*(\d+)\s*(.*)', t)
        if mm:
            return f"Annals, Part {int(mm.group(1))} - {mm.group(2)}", 1941, int(mm.group(1)), None

    if coll == "review":
        mm = re.search(r'Vol[_ ]*(\d+)[_ ]*Num[_ ]*(\d+)[_ ]*(\d{4})', t)
        if mm:
            vol, num, yr = int(mm.group(1)), int(mm.group(2)), int(mm.group(3))
            return f"The Review - No. {num} ({yr})", yr, num, f"Vol. {vol}, No. {num}"

    if coll == "songbooks":
        mm = re.match(r'Songs of the Psi Upsilon Fraternity\s*(\d{4})\s*-?\s*(\d+)(?:st|nd|rd|th)?\s*ed', t, re.I)
        if mm:
            yr, ed = int(mm.group(1)), int(mm.group(2))
            suf = {1:'st',2:'nd',3:'rd'}.get(ed if ed<20 else ed%10, 'th')
            return f"Songs of Psi Upsilon - {ed}{suf} edition ({yr})", yr, ed, "Executive Council edition"

    return t, year, 0, sub

items, collections_out = [], []
seen = set()

for c in COLLECTIONS:
    files = sorted(glob.glob(os.path.join(CRAWL, c["source"])))
    count = 0
    for f in files:
        h = open(f, encoding="utf-8", errors="replace").read()
        # section headings (h2) to group within a collection
        for pdf, raw in find_files(h):
            if 'General-Terms' in pdf: continue
            if pdf.startswith('blob:'): continue   # broken upload on the source site
            if pdf in seen: continue
            seen.add(pdf)
            title, year, seq, sub = parse_title(raw, c["id"])
            fname = pdf.rsplit('/',1)[-1]
            fmt = fname.rsplit('.', 1)[-1].lower()
            items.append(dict(
                id=slugify(os.path.splitext(fname)[0]),
                type="document",
                format=fmt,
                title=title,
                subtitle=sub,
                collection=c["id"],
                year=year,
                seq=seq,
                pdf=pdf,
                source_page=source_url(f, c),
                original_label=txt(raw),
            ))
            count += 1
    collections_out.append(dict(id=c["id"], name=c["name"], blurb=c["blurb"], count=count))
    print(f"{count:5d}  {c['name']}")

# A few volumes carry identical volume/number labels on psiu.org (e.g. two 1878
# issues both marked Vol. 2 No. 1). Number them so they can be told apart.
from collections import defaultdict as _dd
_groups = _dd(list)
for _i in items:
    _groups[(_i["title"], _i.get("subtitle"))].append(_i)
for _k, _v in _groups.items():
    if len(_v) > 1:
        _v.sort(key=lambda x: (x["seq"], x["id"]))
        for _n, _i in enumerate(_v, 1):
            _i["subtitle"] = ((_i.get("subtitle") + " ") if _i.get("subtitle") else "") \
                             + f"({_n} of {len(_v)} so labelled)"

items.sort(key=lambda i: (i["collection"], i["year"] or 0, i["seq"], i["title"]))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(dict(collections=collections_out, items=items), open(OUT,"w"), indent=1)
print(f"\nTOTAL {len(items)} documents -> {OUT}")
yrs = [i['year'] for i in items if i['year']]
print("year range", min(yrs), max(yrs), "| missing year:", sum(1 for i in items if not i['year']))
