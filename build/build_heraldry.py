#!/usr/bin/env python3
"""Pull the heraldry narrative and the Fraternity-level images off psiu.org."""
import re, json, html, os, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(ROOT, "crawl", "site", "about_heraldry.html")
OUT  = os.path.join(ROOT, "data", "heraldry.json")
IMG  = os.path.join(ROOT, "site", "assets", "heraldry")
os.makedirs(IMG, exist_ok=True)

def txt(s):
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = (s.replace("’", "'").replace("‘", "'").replace("“", '"')
          .replace("”", '"').replace("–", "-").replace("—", "-"))
    return re.sub(r"[ \t]+", " ", s).strip()

def canon(u):
    return re.sub(r"^https?://i[0-9]\.wp\.com/", "https://", html.unescape(u).split("?")[0])

def grab(url, name):
    dest = os.path.join(IMG, name)
    if not os.path.exists(dest):
        r = subprocess.run(["curl", "-sfL", "--max-time", "45", "-A", "PsiU-Archives/1.0",
                            url, "-o", dest])
        if r.returncode != 0 or os.path.getsize(dest) < 400:
            if os.path.exists(dest):
                os.remove(dest)
            return None
    return "assets/heraldry/" + name

h = open(SRC, encoding="utf-8", errors="replace").read()
m = re.search(r'<div class="entry-content[^"]*"[^>]*>', h)
body = h[m.end():]
e = re.search(r'(?is)<(?:footer|/article|div[^>]*class="[^"]*'
              r'(?:entry-footer|sharedaddy|ast-single-related))', body)
if e:
    body = body[:e.start()]

# The page uses coloured or bold short paragraphs as section headings rather
# than real heading tags, so treat those as headings too.
blocks, cur = [], None
for m in re.finditer(r'<(h[12345])[^>]*>(.*?)</\1>|(<p[^>]*>)(.*?)</p>', body, re.S):
    if m.group(2) is not None:
        cur = dict(heading=txt(m.group(2)), paras=[])
        if cur["heading"]:
            blocks.append(cur)
        continue
    ptag, inner = m.group(3), m.group(4)
    t = txt(inner)
    looks_heading = (len(t) < 60 and t
                     and ("color:#" in ptag or "<strong>" in inner.lower())
                     and not t.endswith("."))
    if looks_heading:
        cur = dict(heading=t, paras=[])
        blocks.append(cur)
        continue
    if True:
        if len(t) < 8 or t.lower() in ("download", "popular searches:"):
            continue
        if cur is None:
            cur = dict(heading=None, paras=[])
            blocks.append(cur)
        cur["paras"].append(t)

# Fraternity-level artwork (not the per-chapter "_small" thumbnails)
wanted = {
    "Heraldry.png": ("arms", "The Fraternity coat of arms"),
    "psiu_19_about_convawards_garnetflag-1.png": ("flag", "The Fraternity flag"),
    "psiu_19_about_convaward_distgalumplaque-1.png": ("plaque", "The Distinguished Alumni plaque"),
    "psiu_19_alumni_ec-cofa-1.png": ("ec", "Arms of the Executive Council"),
    "psiu_19_about_convawards_diamondawardbadgecolor-1.png": ("diamond-badge", "The Diamond Award badge"),
    "psiu_19_about_convawards_distinctiocoatcolor-1.png": ("distinctio", "Arms of Distinctio"),
}
images = []
for u in {canon(x) for x in re.findall(r'data-orig-file="([^"]+)"', body)}:
    base = u.rsplit("/", 1)[-1]
    if base in wanted:
        slug, caption = wanted[base]
        path = grab(u, slug + os.path.splitext(base)[1])
        if path:
            images.append(dict(id=slug, caption=caption, src=path))
order = list(wanted.values())
images.sort(key=lambda i: [o[0] for o in order].index(i["id"]))

hi_res = None
for u in sorted(set(re.findall(r'https://psiu\.org/wp-content/uploads/[^"]+\.pdf', body))):
    if re.search(r"(?i)coat|arms|heraldry", u.rsplit("/", 1)[-1]):
        hi_res = u
        break

json.dump(dict(blocks=[b for b in blocks if b["paras"]], images=images,
               high_res_pdf=hi_res), open(OUT, "w"), indent=1)
print(f"  {len(blocks)} sections, {len(images)} images -> {OUT}")
for i in images:
    print("   ", i["id"], i["src"])
