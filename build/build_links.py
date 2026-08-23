#!/usr/bin/env python3
"""
Attach an external reference link to each person.

Wikipedia article titles come from Wikipedia's own "List of Psi Upsilon
members" (read off that page, not guessed) plus a few verified by search, kept
in data/wikipedia-titles.txt as "Display Name|/wiki/Article_Title".

Anyone we can't match confidently gets a Wikipedia search link instead — always
valid, and it lands on the article if there is one. Nothing is invented.
"""
import json, os, re, unicodedata, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r'"[^"]*"', " ", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", " ", s)
    s = re.sub(r"[^a-z ]", " ", s)
    return " ".join(s.split())

def key(s):
    t = norm(s).split()
    return (t[0], t[-1]) if len(t) > 1 else None

titles = {}
for line in open(os.path.join(DATA, "wikipedia-titles.txt")):
    line = line.strip()
    if not line or "|" not in line:
        continue
    disp, path = line.split("|", 1)
    titles[norm(disp)] = (disp.strip(), path.strip())

# also index by (first, last) so "William S. Cohen" matches "William Cohen"
by_fl = {}
for n, v in titles.items():
    k = key(n)
    if k:
        by_fl.setdefault(k, v)

people = json.load(open(os.path.join(DATA, "people.json")))
exact = fuzzy = search = 0
for p in people:
    links = []
    n = norm(p["name"])
    hit = titles.get(n)
    if hit:
        exact += 1
    else:
        # try the printed name, then the nickname form ("Jay" Berwanger -> Jay Berwanger)
        cands = [key(p["name"])]
        nick = re.search(r'"([^"]+)"', p["name"])
        if nick:
            parts = norm(p["name"]).split()
            cands.append((norm(nick.group(1)), parts[-1]) if parts else None)
        for c in cands:
            if c and c in by_fl:
                hit = by_fl[c]
                fuzzy += 1
                break
    if hit:
        links.append(dict(label="Wikipedia", url="https://en.wikipedia.org" + hit[1],
                          verified=True))
    else:
        q = re.sub(r'\s*"[^"]*"\s*', " ", p["name"]).strip()
        links.append(dict(label="Look up on Wikipedia",
                          url="https://en.wikipedia.org/w/index.php?search="
                              + urllib.parse.quote(q + " Psi Upsilon"),
                          verified=False))
        search += 1
    p["links"] = links

json.dump(people, open(os.path.join(DATA, "people.json"), "w"), indent=1)
print(f"  {exact} exact + {fuzzy} matched by first/last = {exact+fuzzy} verified articles; "
      f"{search} fall back to a Wikipedia search link")
print("  no article found for: " + ", ".join(
    p["name"] for p in people if not p["links"][0]["verified"])[:600])
