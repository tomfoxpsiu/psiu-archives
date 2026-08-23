#!/usr/bin/env python3
"""
Parse psiu.org's Notable Alumni page into structured person records.

Each entry on that page is a two-column block: a bold "Name, Chapter YEAR
(Institution)" line followed by a biography, and often a portrait beside it.
"""
import re, json, html, os, unicodedata, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(ROOT, "crawl", "site", "alumni_distinguished-alumni.html")
OUT  = os.path.join(ROOT, "data", "people.json")
IMG  = os.path.join(ROOT, "site", "assets", "people")
os.makedirs(IMG, exist_ok=True)

def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower())

def txt(s):
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", s)
    s = re.sub(r"(?i)<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = (s.replace("’", "'").replace("‘", "'").replace("“", '"')
          .replace("”", '"').replace("–", "-").replace("—", "-"))
    return re.sub(r"\s+", " ", s).strip()

def canon(u):
    u = html.unescape(u).split("?")[0]
    return re.sub(r"^https?://i[0-9]\.wp\.com/", "https://", u)

def grab(url, slug):
    ext = os.path.splitext(url)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        ext = ".jpg"
    dest = os.path.join(IMG, slug + ext)
    if not os.path.exists(dest):
        r = subprocess.run(["curl", "-sfL", "--max-time", "45",
                            "-A", "PsiU-Archives/1.0", url, "-o", dest])
        if r.returncode != 0 or os.path.getsize(dest) < 500:
            if os.path.exists(dest):
                os.remove(dest)
            return None
    return "assets/people/" + slug + ext

h = open(SRC, encoding="utf-8", errors="replace").read()
m = re.search(r'<div class="entry-content[^"]*"[^>]*>', h)
body = h[m.end():] if m else h
end = re.search(r'(?is)<(?:footer|/article|div[^>]*class="[^"]*(?:entry-footer|sharedaddy))', body)
if end:
    body = body[:end.start()]

# category headings are the gold-coloured paragraphs
CAT = re.compile(r'<p[^>]*color:#f2b300[^>]*>\s*<strong>(.*?)</strong>\s*</p>', re.S | re.I)
cats = [(m.start(), txt(m.group(1))) for m in CAT.finditer(body)]

def category_at(pos):
    cur = "Notable Alumni"
    for start, name in cats:
        if start <= pos:
            cur = name
        else:
            break
    return cur

# Entries read "Name, Chapter YEAR (Institution) - biography". Match against the
# paragraph's plain text; the markup varies but the sentence pattern doesn't.
LEAD = re.compile(
    r"^([A-Z][^,]{2,60}?),\s*"                                   # name
    r"([A-Z][A-Za-z]+(?:[\s-]+[A-Z][A-Za-z]+)?)\s*"              # chapter
    r"(?:['\u2019]\s*(\d{2})|(1[89]\d\d|20[0-2]\d))?\s*"       # class year
    r"(?:\(([^)]{2,90})\))?"                                    # institution
    r"\s*[-:]?\s*(.*)$", re.S)
SUFFIX = re.compile(r"^(Jr|Sr|II|III|IV)\.?$")

PARA = re.compile(r'<p class="wp-block-paragraph">\s*<strong>(.*?)</p>', re.S)
IMGRE = re.compile(r'<img[^>]+>')

def year_of(two, four):
    if four:
        return int(four)
    if two:
        n = int(two)
        return 2000 + n if n <= 26 else 1900 + n
    return None

people, seen = [], set()
paras = list(PARA.finditer(body))
for k, pm in enumerate(paras):
    plain = txt("<strong>" + pm.group(1))
    m = LEAD.match(plain)
    if m and SUFFIX.match(m.group(2)):
        # "Callaway, Jr, Beta 1912" — the suffix belongs to the name
        rest = plain[m.end(2):].lstrip(", ")
        m2 = LEAD.match(f"{m.group(1)}, {m.group(2)}, {rest}".replace(
            f"{m.group(1)}, {m.group(2)}, ", f"{m.group(1)} {m.group(2)}, ", 1))
        m = m2 or m
    if not m:
        continue
    name = m.group(1).strip()
    chapter = re.sub(r"\s+", " ", (m.group(2) or "").strip())
    year = year_of(m.group(3), m.group(4))
    inst = (m.group(5) or "").strip()
    bio = (m.group(6) or "").strip()
    if not name or len(name.split()) < 2 or SUFFIX.match(chapter):
        continue
    if len(bio) < 30:
        bio = plain

    # portrait: the first image between this entry and the next one
    stop = paras[k + 1].start() if k + 1 < len(paras) else len(body)
    im = IMGRE.search(body[pm.end(): min(stop + 400, len(body))])
    img = None
    if im:
        o = (re.search(r'data-orig-file="([^"]+)"', im.group(0))
             or re.search(r'src="([^"]+)"', im.group(0)))
        if o:
            img = grab(canon(o.group(1)), slugify(name))

    pid = slugify(name)
    if pid in seen:
        continue
    seen.add(pid)
    people.append(dict(id=pid, type="person", name=name, chapter=chapter,
                       year=year, institution=inst,
                       category=category_at(pm.start()), bio=bio,
                       portrait=img, links=[]))

people.sort(key=lambda p: (p["year"] or 9999, p["name"]))
json.dump(people, open(OUT, "w"), indent=1)
print(f"{len(people)} people -> {OUT}")
from collections import Counter
for c, n in Counter(p["category"] for p in people).most_common():
    print(f"  {n:3d}  {c}")
print(f"  portraits: {sum(1 for p in people if p['portrait'])}")
print(f"  missing chapter: {sum(1 for p in people if not p['chapter'])}, missing year: {sum(1 for p in people if not p['year'])}")
