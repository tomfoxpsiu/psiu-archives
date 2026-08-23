#!/usr/bin/env python3
"""
Re-read the existing WordPress archive pages so build_manifest.py can pick up
documents that have been added there since the last run.

Writes raw HTML into crawl/ ; nothing else touches the network.
"""
import os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

CRAWL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crawl")
CRAWL = os.path.abspath(os.environ.get("PSIU_CRAWL_DIR", CRAWL))
UA = "Mozilla/5.0 (compatible; PsiUpsilonArchives/1.0)"

INDEX_PAGES = {
    "raw_fd5236d4.html": "https://psiu.org/about/history/archives-home/",
    "raw_fbae9ccc.html": "https://psiu.org/archives-annals-of-psi-upsilon/",
    "raw_70fbe905.html": "https://psiu.org/about/history/archives-convention-records",
    "raw_5f70ba2c.html": "https://psiu.org/about/history/archives-diamond-of-psi-upsilon/",
    "raw_96a17a21.html": "https://psiu.org/about/history/archives-member-education-guides/",
    "raw_40db17fa.html": "https://psiu.org/about/history/archives-printed-histories/",
    "raw_1f7ca0a2.html": "https://psiu.org/about/history/archives-the-review-original-run/",
    "raw_d6fd98d4.html": "https://psiu.org/about/history/archives-songbooks/",
    "raw_97980ee7.html": "https://psiu.org/about/history/archives-special-collections/",
}

def get(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    subprocess.run(["curl", "-sfL", "--max-time", "90", "-A", UA, url, "-o", dest], check=False)

os.makedirs(CRAWL, exist_ok=True)
with ThreadPoolExecutor(8) as ex:
    list(ex.map(lambda kv: get(kv[1], os.path.join(CRAWL, kv[0])), INDEX_PAGES.items()))

# Every per-year Diamond page. The Diamond index on psiu.org has a handful of
# wrong links (1954 points at 1934, 2009 at 1939, and so on), so trusting it
# silently loses whole years. Probe every plausible year directly instead and
# keep whatever answers 200.
def diamond_year(y):
    u = f"https://psiu.org/archives-{y}-diamond/"
    dest = os.path.join(CRAWL, "pages", f"archives-{y}-diamond.html")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    r = subprocess.run(["curl", "-sL", "--max-time", "60", "-A", UA, "-o", dest,
                        "-w", "%{http_code}", u], capture_output=True, text=True)
    if r.stdout.strip() != "200" or not os.path.exists(dest) or os.path.getsize(dest) < 2000:
        if os.path.exists(dest): os.remove(dest)
        return None
    return y

with ThreadPoolExecutor(10) as ex:
    years = [y for y in ex.map(diamond_year, range(1878, 2026)) if y]

# the From the Archives article index and its articles
for n in (1, 2, 3, 4):
    get(f"https://psiu.org/category/from-the-archives/page/{n}/",
        os.path.join(CRAWL, "stories", f"cat{n}.html"))
import glob
blob = "".join(open(f, encoding="utf-8", errors="replace").read()
               for f in glob.glob(os.path.join(CRAWL, "stories", "cat*.html")))
arts = sorted({u for u in re.findall(r'https://psiu\.org/from-the-archives-[a-z0-9-]+/', blob)})
def art(u):
    slug = u.replace("https://psiu.org/", "").rstrip("/")
    get(u, os.path.join(CRAWL, "stories", slug + ".html"))
with ThreadPoolExecutor(6) as ex:
    list(ex.map(art, arts))

print(f"crawled {len(INDEX_PAGES)} index pages, {len(years)} Diamond years, {len(arts)} articles "
      f"into {CRAWL}")
