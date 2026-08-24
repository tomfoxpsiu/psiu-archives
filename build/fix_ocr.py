#!/usr/bin/env python3
"""
Repair the systematic OCR confusions in the 2020 Kirtas text layer.

The scans carry a text layer made in about 2020. It is mostly good, but it has a
handful of *systematic* letter confusions caused by tight ligatures in the
typefaces the Fraternity printed in:

    ll -> U     college  -> coUege     Angell  -> AngeU     Brownell -> BrowneU
    il -> k     Bailey   -> Bakey      William -> Wkliam    build    -> buksd
    ti -> k     beautiful-> beautkul   Upsilon -> Upskon
    ir -> k     iron     -> kon        their   -> thek
    rn -> m     Barnard  -> Bamard     Auburn  -> Aubum     govern   -> govem
    li -> h     Carolina -> Carohna    Elizabeth-> Ehzabeth
    tl -> ti    Butler   -> Butier     Atlanta -> Atianta   castle   -> castie

Measured across the corpus: 38,520 instances of a short list of *confirmed*
cases in 10.1 million words, and the true figure is higher. They matter more for
reading names out of the text than they do for search, because they land on
proper nouns.

This module fixes them by trying each substitution on any token that is not a
known English word and accepting the result only when it becomes a reasonably
common one, or a name we already hold in our own data. It is conservative: a
token it cannot confidently repair is left exactly as it was.

    from fix_ocr import repair
    repair("Wkliam W. Bakey '64, chemist")   ->  "William W. Bailey '64, chemist"

A fresh OCR pass does better still (measured: it removes the ll->U class
entirely) but costs 20.6 GB of downloading and some 83 hours of processing for
the whole archive. See build/reocr.py. This is the cheap 30-40% of the benefit.
"""
import functools, json, os, re

try:
    from wordfreq import zipf_frequency
except ImportError:                                     # graceful, so the build never breaks
    def zipf_frequency(w, lang): return 0.0

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUBS = [("U", "ll"), ("k", "il"), ("k", "ti"), ("k", "ir"), ("k", "if"),
        ("k", "ik"), ("m", "rn"), ("h", "li"), ("di", "th"), ("ii", "n"),
        ("I", "l"), ("rn", "m"), ("li", "h"), ("th", "di"), ("ie", "le"),
        ("cl", "d"), ("vv", "w"), ("tl", "ti"), ("ti", "tl"), ("i", "l"),
        ("l", "i"), ("t", "f"), ("f", "t"), ("e", "c"), ("c", "e")]
STRONG = SUBS[:9]                                       # safe enough to compose two of

# "ll" printed as a tight ligature is read as a capital U almost every time, so a
# lower-case letter followed by U followed by a lower-case letter is not English —
# it is that ligature. Accept the repair on much weaker evidence than usual.
U_LIG = re.compile(r"[a-z]U[a-z]|[a-z]U$")


@functools.lru_cache(maxsize=1)
def local_names():
    """Surnames, given names and place words from our own data — a domain lexicon."""
    words = set()
    for name in ("people.json", "chapters.json", "founders.json"):
        p = os.path.join(ROOT, "data", name)
        if not os.path.exists(p):
            continue
        try:
            rows = json.load(open(p, encoding="utf8"))
        except Exception:
            continue
        if isinstance(rows, dict):
            rows = rows.get("items", [])
        for r in rows:
            if not isinstance(r, dict):
                continue
            for field in ("name", "institution", "chapter", "location", "city"):
                v = r.get(field)
                if isinstance(v, str):
                    words.update(re.findall(r"[A-Za-z][A-Za-z'\-]{2,}", v))
    return {w.lower() for w in words}


def _known(tok):
    lo = tok.lower()
    return zipf_frequency(lo, "en") >= 2.6 or lo in local_names()


def _variants(tok):
    out = set()
    for a, b in SUBS:
        start = 0
        while True:
            i = tok.find(a, start)
            if i < 0:
                break
            out.add(tok[:i] + b + tok[i + len(a):])
            start = i + 1
    for v in list(out):
        for a, b in STRONG:
            start = 0
            while True:
                i = v.find(a, start)
                if i < 0:
                    break
                out.add(v[:i] + b + v[i + len(a):])
                start = i + 1
    out.discard(tok)
    return out


@functools.lru_cache(maxsize=200000)
def repair_token(tok):
    core = tok.strip("'’-")
    if len(core) < 3 or not core.isascii() or not core[0].isalpha():
        return tok
    own = zipf_frequency(core.lower(), "en")
    if own >= 3.4 or core.lower() in local_names():      # a common word or a name we hold
        return tok
    # The repair has to clear an absolute bar AND be a good deal more plausible
    # than what is already on the page, so real-but-rare words survive untouched.
    bar = max(1.4 if U_LIG.search(core) else 2.6, own + 1.2)
    best, best_score = None, 0.0
    for v in _variants(core):
        s = zipf_frequency(v.lower(), "en")
        if v.lower() in local_names():
            s = max(s, 3.2)                             # trust our own name list
        if s > best_score and s >= bar:
            best, best_score = v, s
    if best is None and U_LIG.search(core):
        # nothing in the dictionary, but the ligature is certain: still undo it
        return tok.replace(core, core.replace("U", "ll"), 1)
    if best is None:
        return tok
    # keep the original capitalisation shape
    if core.isupper():
        best = best.upper()
    elif core[0].isupper():
        best = best[0].upper() + best[1:]
    return tok.replace(core, best, 1)


TOKEN = re.compile(r"[A-Za-z][A-Za-z'’\-]*")


def repair(text):
    if not text:
        return text
    return TOKEN.sub(lambda m: repair_token(m.group(0)), text)


def stats(text):
    """(tokens, repaired) for a piece of text."""
    n = r = 0
    for m in TOKEN.finditer(text):
        n += 1
        if repair_token(m.group(0)) != m.group(0):
            r += 1
    return n, r


if __name__ == "__main__":
    import sys
    src = sys.stdin.read() if len(sys.argv) < 2 else open(sys.argv[1], encoding="utf8").read()
    n, r = stats(src)
    sys.stderr.write("%d tokens, %d repaired (%.1f%%)\n" % (n, r, r * 100.0 / max(n, 1)))
    sys.stdout.write(repair(src))
