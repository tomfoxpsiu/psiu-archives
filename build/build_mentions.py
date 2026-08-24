#!/usr/bin/env python3
"""
Find where people, chapters and songs are mentioned across the archive.

Strategy: tokenise each page once into a set of words, use that set as a cheap
prefilter, and only run exact verification on the handful of candidates a page
could possibly match. A single big regex alternation over 64 MB of OCR text
takes about fifteen minutes in Python; this takes about a minute.

Matching rules
  People    a surname only counts as a mention when it is actually attached to
            the person's given name — "Jay Berwanger", "Berwanger, Jay",
            "W. H. Taft" — not merely on the same page as it. A page mentioning
            "Brown" and, separately, some other Dan is not a Dan Brown mention.
            Mentions are also floored at the person's class year less six, since
            a brother initiated in 1986 cannot appear in a 1921 Diamond. Names
            do repeat down the generations, so the pages are offered as likely
            mentions rather than certainties.
  Chapters  "<Name> Chapter" is captured with up to three leading capitalised
            words and credited to the longest chapter name that matches, so
            "Epsilon Phi Chapter" is not filed under Phi. The institution name
            counts as a mention too.
  Songs     the printed title, with or without a leading article.

Output: data/mentions.json
"""
import json, os, re, sys, time, unicodedata
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
WINDOW = 70

def load(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p)) if os.path.exists(p) else default

items    = load("items.json", {"items": []})["items"]
people   = load("people.json", [])
chapters = load("chapters.json", [])
songs    = load("songs.json", [])
founders = load("founders.json", [])

STOP = {"de", "la", "van", "von", "der", "jr", "sr", "ii", "iii", "iv"}
WORD = re.compile(r"[a-z][a-z']+")
CH_ANY = re.compile(r"(?<!\w)((?:[A-Z][a-z]+[ \t]+){0,2}[A-Z][a-z]+)[ \t]+Chapter(?!\w)")

def strip_accents(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()

def surname_of(name):
    n = re.sub(r'"[^"]*"', " ", strip_accents(name))
    n = re.sub(r"[^A-Za-z .\-']", " ", n)
    toks = [t.strip(".") for t in n.split() if len(t.strip(".")) > 1]
    toks = [t for t in toks if t.lower() not in STOP]
    return (toks[-1], toks[:-1]) if toks else (None, [])

# ------------------------------------------------------------------ people
# For each person: the surname (a cheap word-set prefilter) plus a verification
# regex that requires the given name, or the person's own initials, adjacent to
# the surname.
def person_pattern(first_names, last):
    firsts = [re.escape(f) for f in first_names if len(f) > 2]
    inits = [f[0] for f in first_names if f]
    L = re.escape(last)
    alts = []
    if firsts:
        joined = "|".join(firsts)
        # "William Howard Taft", "William H. Taft", "William Taft"
        alts.append(r"(?:%s)(?:\s+[A-Za-z]{1,12}\.?){0,2}\s+%s" % (joined, L))
        # "Taft, William"
        alts.append(r"%s\s*,\s*(?:%s)" % (L, joined))
    if len(inits) >= 2:
        alts.append(r"%s\.?\s*%s\.?\s*%s" % (re.escape(inits[0]), re.escape(inits[1]), L))
    if not alts:
        return None
    return re.compile(r"(?<!\w)(?:%s)(?!\w)" % "|".join(alts), re.I)

by_surname = defaultdict(list)       # surname -> [(id, verifier, year floor, kind)]
for p in people:
    last, first = surname_of(p["name"])
    if not last:
        continue
    rx = person_pattern(first, last)
    if rx is not None:
        floor = (p["year"] - 6) if p.get("year") else None
        by_surname[last.lower()].append((p["id"], rx, floor, "person"))

# the seven founders are matched the same way, but filed separately
for f in founders:
    last, first = surname_of(f["name"])
    rx = person_pattern(first, last) if last else None
    if rx is not None:
        by_surname[last.lower()].append((f["id"], rx, None, "founder"))
SURNAMES = set(by_surname)

# How many volumes contain each surname at all? A rare surname ("Berwanger",
# "Barthelmess") is unambiguous enough to count on its own; a common one
# ("Brown", "Ford", "Clark") only counts with the given name attached.
def surname_frequency():
    freq = defaultdict(int)
    for it in items:
        fp = os.path.join(DATA, "text", it["id"] + ".json")
        if not os.path.exists(fp):
            continue
        seen = set()
        for raw in json.load(open(fp))["text"]:
            if raw:
                seen |= SURNAMES & set(WORD.findall(raw.lower()))
        for s_ in seen:
            freq[s_] += 1
    return freq

FREQ = surname_frequency()
RARE_MAX = 120           # volumes
rare = {s_ for s_, n in FREQ.items() if n <= RARE_MAX}
print(f"  {len(rare)} of {len(SURNAMES)} surnames are distinctive enough to count alone")

# ---------------------------------------------------------------- chapters
chap_by_name = {c["name"].lower(): c["id"] for c in chapters}
chap_first_word = defaultdict(set)   # first word of chapter name -> ids
for c in chapters:
    chap_first_word[c["name"].split()[0].lower()].add(c["id"])

inst_by_token = defaultdict(list)    # distinctive token -> [(id, phrase)]
GENERIC = {"university", "college", "of", "the", "institute", "state", "and",
           "polytechnic", "school", "technology"}
for c in chapters:
    phrase = re.sub(r"^the\s+", "", c["institution"].lower()).strip()
    toks = [t for t in WORD.findall(phrase) if t not in GENERIC]
    if toks:
        inst_by_token[min(toks, key=len) if len(toks) == 1 else toks[0]].append((c["id"], phrase))

# ------------------------------------------------------------------- songs
song_by_token = defaultdict(list)
SONG_GENERIC = {"the", "a", "of", "psi", "upsilon", "song", "old", "and", "young", "dear"}
for s_ in songs:
    phrase = s_["title"].lower()
    variants = {phrase, re.sub(r"^(the|a) ", "", phrase)}
    toks = [t for t in WORD.findall(phrase) if t not in SONG_GENERIC]
    key = max(toks, key=len) if toks else None
    if key:
        song_by_token[key].append((s_["id"], sorted(variants)))

print(f"  {len(founders)} founders, {len(people)} people, {len(chapters)} chapters, {len(songs)} songs")

def snippet(text, idx, term_len, width=150):
    s = max(0, idx - width // 2)
    e = min(len(text), idx + term_len + width)
    return ("…" if s else "") + re.sub(r"\s+", " ", text[s:e]).strip() + ("…" if e < len(text) else "")

hits = defaultdict(lambda: defaultdict(list))
t0 = time.time()
scanned = 0

for it in items:
    fp = os.path.join(DATA, "text", it["id"] + ".json")
    if not os.path.exists(fp):
        continue
    pages = json.load(open(fp))["text"]
    doc_id = it["id"]
    scanned += 1
    for pno, raw in enumerate(pages, 1):
        if not raw:
            continue
        low = raw.lower()
        words = set(WORD.findall(low))

        # --- people
        for sur in SURNAMES & words:
            bare = sur in rare
            for pid, rx, floor, kind in by_surname[sur]:
                if floor and (it["year"] or 0) < floor:
                    continue
                m = rx.search(raw)
                if m is None and bare and len(by_surname[sur]) == 1:
                    i = low.find(sur)
                    if i >= 0:
                        hits[(kind, pid)][doc_id].append(
                            (pno, snippet(raw, i, len(sur))))
                    continue
                if m:
                    hits[(kind, pid)][doc_id].append(
                        (pno, snippet(raw, m.start(), len(m.group(0)))))

        # --- chapters, by "<Name> Chapter"
        if "chapter" in words:
            for m in CH_ANY.finditer(raw):
                phrase = re.sub(r"\s+", " ", m.group(1)).lower()
                parts = phrase.split()
                for n in (3, 2, 1):
                    cand = " ".join(parts[-n:])
                    if cand in chap_by_name:
                        hits[("chapter", chap_by_name[cand])][doc_id].append(
                            (pno, snippet(raw, m.start(), len(m.group(0)))))
                        break

        # --- chapters, by institution name
        for tok in set(inst_by_token) & words:
            for cid, phrase in inst_by_token[tok]:
                i = low.find(phrase)
                if i >= 0:
                    hits[("chapter", cid)][doc_id].append((pno, snippet(raw, i, len(phrase))))

        # --- songs
        for tok in set(song_by_token) & words:
            for sid, variants in song_by_token[tok]:
                for v in variants:
                    i = low.find(v)
                    if i >= 0:
                        hits[("song", sid)][doc_id].append((pno, snippet(raw, i, len(v))))
                        break

print(f"  scanned {scanned} volumes in {time.time()-t0:.0f}s")

by_item = {it["id"]: it for it in items}
out = {}
for (kind, eid), docs in hits.items():
    recs = []
    for doc_id, pl in docs.items():
        if not pl:
            continue
        it = by_item[doc_id]
        seen, pages_u = set(), []
        for p, _ in pl:
            if p not in seen:
                seen.add(p); pages_u.append(p)
        recs.append(dict(doc=doc_id, title=it["title"], collection=it["collection"],
                         year=it["year"], pages=pages_u[:40], count=len(pages_u),
                         snippet=pl[0][1]))
    recs.sort(key=lambda r: (r["year"] or 0))
    out.setdefault(kind, {})[eid] = dict(
        total=sum(r["count"] for r in recs), volumes=len(recs), docs=recs[:200])

json.dump(out, open(os.path.join(DATA, "mentions.json"), "w"))
for kind in ("founder", "person", "chapter", "song"):
    d = out.get(kind, {})
    if not d:
        continue
    top = sorted(d.items(), key=lambda kv: -kv[1]["volumes"])[:6]
    print(f"  {kind}: {len(d)} with hits; busiest -> " +
          ", ".join(f"{k} ({v['volumes']})" for k, v in top))
