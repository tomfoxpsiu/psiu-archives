#!/usr/bin/env python3
"""
Print the text of scanned pages with the systematic OCR confusions repaired.

    python3 build/read_pages.py <volume-id> <pages>      e.g. 55-60  or  12,14,88
    python3 build/read_pages.py --founder <founder-id>   every page naming them
    python3 build/read_pages.py --list <pattern>         find a volume id
    python3 build/read_pages.py --where <founder-id>     which volumes and pages

Pages are 1-based scan pages, which for these volumes is often two printed pages
at once. Add --raw to see the text exactly as the OCR left it.
"""
import sys, os, json, re, argparse, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fix_ocr import repair

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT = os.path.join(ROOT, "data", "text")


def load(vid):
    p = os.path.join(TEXT, vid + ".json")
    if not os.path.exists(p):
        sys.exit("no such volume: " + vid + "   (try --list)")
    return json.load(open(p, encoding="utf8"))


def mentions():
    return json.load(open(os.path.join(ROOT, "data", "mentions.json"), encoding="utf8"))


def parse_pages(spec, n):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return [p for p in out if 1 <= p <= n]


def show(vid, pages, raw=False, limit=9000):
    d = load(vid)
    t = d.get("text") or []
    title = d.get("pdf_title") or vid
    for p in pages:
        if not (1 <= p <= len(t)):
            continue
        body = (t[p - 1] or "").strip()
        if not raw:
            body = repair(body)
        print("\n" + "=" * 78)
        print("### %s  [%s]  scan page %d of %d" % (title, vid, p, len(t)))
        print("=" * 78)
        print(body[:limit] if body else "(this page has no text)")


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("args", nargs="*")
    ap.add_argument("--founder"); ap.add_argument("--person")
    ap.add_argument("--where"); ap.add_argument("--list")
    ap.add_argument("--context", type=int, default=0)
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--limit", type=int, default=9000)
    ap.add_argument("-h", "--help", action="store_true")
    a = ap.parse_args()
    if a.help:
        print(__doc__); return

    if a.list:
        pat = a.list.lower()
        for p in sorted(glob.glob(os.path.join(TEXT, "*.json"))):
            vid = os.path.basename(p)[:-5]
            if pat in vid.lower():
                d = json.load(open(p, encoding="utf8"))
                print("%-62s %4s pages" % (vid, d.get("pages")))
        return

    who = a.where or a.founder or a.person
    if a.where:
        m = mentions()
        rec = m["founder"].get(who) or m["person"].get(who)
        if not rec:
            sys.exit("not found: " + who)
        print("%s — %d mentions across %d volumes" % (who, rec["total"], rec["volumes"]))
        for d in sorted(rec["docs"], key=lambda x: -x["count"]):
            print("  %3d  %-58s pages %s" % (d["count"], d["doc"],
                  ",".join(str(x) for x in d["pages"][:24])))
        return

    if a.founder or a.person:
        m = mentions()
        rec = m["founder"].get(who) or m["person"].get(who)
        if not rec:
            sys.exit("not found: " + who)
        for d in sorted(rec["docs"], key=lambda x: -x["count"]):
            pages = set()
            for p in d["pages"]:
                pages.update(range(p - a.context, p + a.context + 1))
            show(d["doc"], sorted(x for x in pages if x > 0), a.raw, a.limit)
        return

    if len(a.args) < 2:
        print(__doc__); sys.exit(1)
    vid = a.args[0]
    d = load(vid)
    pages = parse_pages(a.args[1], len(d.get("text") or []))
    show(vid, pages, a.raw, a.limit)


if __name__ == "__main__":
    main()
