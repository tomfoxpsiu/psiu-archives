#!/usr/bin/env python3
"""
Build the chapter roll from psiu.org: one record per chapter with its Greek-letter
name, institution, founding year and status, plus its coat of arms (from the
Heraldry page) and its house photograph (from the Chapter Roll page).
"""
import re, json, html, os, unicodedata, subprocess

ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRAWL = os.path.join(ROOT, "crawl", "site")
OUT   = os.path.join(ROOT, "data", "chapters.json")
ARMS  = os.path.join(ROOT, "site", "assets", "arms")
HOUSE = os.path.join(ROOT, "site", "assets", "houses")
for d in (ARMS, HOUSE):
    os.makedirs(d, exist_ok=True)

def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower())

def txt(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ").replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()

def canon(u):
    u = html.unescape(u).split("?")[0]
    return re.sub(r"^https?://i[0-9]\.wp\.com/", "https://", u)

def grab(url, dest):
    if os.path.exists(dest):
        return True
    r = subprocess.run(["curl", "-sfL", "--max-time", "45",
                        "-A", "PsiU-Archives/1.0", url, "-o", dest])
    if r.returncode != 0 or os.path.getsize(dest) < 400:
        if os.path.exists(dest):
            os.remove(dest)
        return False
    return True

def content(name):
    h = open(os.path.join(CRAWL, name), encoding="utf-8", errors="replace").read()
    m = re.search(r'<div class="entry-content[^"]*"[^>]*>', h)
    body = h[m.end():] if m else h
    e = re.search(r'(?is)<(?:footer|/article|div[^>]*class="[^"]*'
                  r'(?:entry-footer|sharedaddy|ast-single-related))', body)
    return body[:e.start()] if e else body

# ------------------------------------------------------------------ the roll
roll_body = content("chapter-roll.html")
flat = txt(roll_body)
ROLL = re.compile(
    r"(\d{1,2})\.\s*"                               # position on the roll
    r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s*,\s*"  # chapter
    r"([^(]{4,70}?)\s*"                             # institution
    r"\((\d{4})([^)]*)\)")                          # founded + status note
chapters = []
for m in ROLL.finditer(flat):
    pos, name, inst, founded, note = m.groups()
    note = note.strip(" ,")
    status, closed, owl = "active", None, False
    nm = re.search(r"(?i)inactive(?:\s+since)?\s*(\d{4})?", note)
    if nm:
        status = "inactive"
        closed = int(nm.group(1)) if nm.group(1) else None
    if re.search(r"(?i)owl club", note):
        status, owl = "owl club", True
        cm = re.search(r"(\d{4})", note)
        closed = int(cm.group(1)) if cm else None
    chapters.append(dict(
        id=slugify(name), type="chapter", position=int(pos), name=name.strip(),
        institution=txt(inst), founded=int(founded), status=status,
        closed=closed, note=note, arms=None, arms_pdf=None, house=None))

# ------------------------------------------------------- arms from Heraldry
her_body = content("about_heraldry.html")
arms_img = {}
for u in re.findall(r'data-orig-file="([^"]+)"', her_body):
    u = canon(u)
    base = u.rsplit("/", 1)[-1]
    # filenames are inconsistent: theta_small.png, betabeta_small-1.png,
    # theta_pi_small.jpg, Delta-Omicron_Small.jpg, crop-0-0-61-90-0-theta_small.png
    m = re.search(r"([A-Za-z_-]+?)_small(?:-\d+)?\.(png|jpg|jpeg)$", base, re.I)
    if m:
        key = re.sub(r"[^a-z]", "", m.group(1).lower())
        key = re.sub(r"^crop\d*", "", key)
        arms_img.setdefault(key, u)
arms_pdf = {}
for u in sorted(set(re.findall(r'https://psiu\.org/wp-content/uploads/[^"]+\.pdf', her_body))):
    base = u.rsplit("/", 1)[-1][:-4]
    arms_pdf[slugify(base).replace("-", "")] = u

# ---------------------------------------------- house photos from the roll
houses = {}
for fig in re.finditer(r"<figure[^>]*>(.*?)</figure>", roll_body, re.S):
    block = fig.group(1)
    cap = re.search(r"<figcaption[^>]*>(.*?)</figcaption>", block, re.S)
    o = re.search(r'data-orig-file="([^"]+)"', block)
    if cap and o:
        houses[slugify(txt(cap.group(1)))] = canon(o.group(1))

# ------------------------------------------------------------- attach media
for c in chapters:
    key = c["id"].replace("-", "")
    if key in arms_img:
        ext = os.path.splitext(arms_img[key])[1] or ".png"
        dest = os.path.join(ARMS, c["id"] + ext)
        if grab(arms_img[key], dest):
            c["arms"] = "assets/arms/" + os.path.basename(dest)
    if key in arms_pdf:
        c["arms_pdf"] = arms_pdf[key]
    if c["id"] in houses:
        ext = os.path.splitext(houses[c["id"]])[1] or ".jpg"
        dest = os.path.join(HOUSE, c["id"] + ext)
        if grab(houses[c["id"]], dest):
            c["house"] = "assets/houses/" + os.path.basename(dest)

chapters.sort(key=lambda c: c["position"])
json.dump(chapters, open(OUT, "w"), indent=1)
print(f"{len(chapters)} chapters -> {OUT}")
print(f"  active {sum(1 for c in chapters if c['status']=='active')}, "
      f"inactive {sum(1 for c in chapters if c['status']=='inactive')}, "
      f"owl club {sum(1 for c in chapters if c['status']=='owl club')}")
print(f"  arms images {sum(1 for c in chapters if c['arms'])}, "
      f"arms PDFs {sum(1 for c in chapters if c['arms_pdf'])}, "
      f"house photos {sum(1 for c in chapters if c['house'])}")
missing = [c["name"] for c in chapters if not c["arms"]]
if missing:
    print("  no arms image:", ", ".join(missing))
