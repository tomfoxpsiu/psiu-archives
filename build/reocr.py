#!/usr/bin/env python3
"""
Re-read the scans with modern OCR — TESTED, AND NOT RECOMMENDED WHOLESALE.

This script works, but the measurement that prompted it did not hold up. On a
73-page 1936 Diamond, against the OCR that came with the scans in about 2020:

    original 2020 text layer   21,237 word-like tokens   99.8% look like words
    ocrmypdf --force-ocr       21,399 word-like tokens   99.6% look like words
    ocrmypdf --redo-ocr        42,653 word-like tokens   but 19% of them are
                               duplicates — it leaves the old layer in place
                               and adds a second one. Never use --redo-ocr.

So a clean re-OCR gains under one per cent, makes the file about nine per cent
larger, and takes roughly eight minutes a volume — some sixty hours across the
whole archive. The scans we have were OCR'd well.

What actually caused the garbled search results was not the OCR but the text
*extraction*: `pdftotext -layout` interleaves multi-column pages — rosters,
chapter letters, In Memoriam lists — into unreadable rows. build/extract.py now
extracts each volume both ways and keeps the better, which fixed it for nothing.

Keep this script for the cases where it is genuinely the right tool:

  * a volume whose text layer really is poor or missing (--find-bad lists them)
  * making smaller web copies of the largest scans (--no-ocr --derivatives web/)

For each volume it downloads the PDF, optionally re-OCRs it with --force-ocr
(never --redo-ocr), optionally writes a smaller greyscale copy, re-extracts the
text, regenerates the cover, and deletes the download. Nothing is overwritten
unless the new text is at least as good. Progress is kept in
data/reocr-state.json, so it can be stopped and restarted.

    ./build/reocr.py --find-bad                  which volumes have weak text
    ./build/reocr.py --ids one-volume-id         try a single volume
    ./build/reocr.py --no-ocr --derivatives web  smaller copies, no re-OCR
    ./build/reocr.py --report                    what has been done

Needs: ocrmypdf, tesseract-ocr, ghostscript, poppler-utils.
    sudo apt install ocrmypdf tesseract-ocr ghostscript poppler-utils
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time

ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA  = os.path.join(ROOT, "data")
TEXT  = os.path.join(DATA, "text")
COVER = os.path.join(ROOT, "site", "assets", "covers")
STATE = os.path.join(DATA, "reocr-state.json")
UA    = "Mozilla/5.0 (compatible; PsiUpsilonArchives/1.0; +https://psiu.org)"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import clean, fetch          # same cleanup and download as the first pass


def need(tool):
    if shutil.which(tool) is None:
        sys.exit(f"{tool} is not installed. See the note at the top of this script.")


def run(cmd, timeout=3600):
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def page_text(pdf):
    raw = run(["pdftotext", "-layout", "-enc", "UTF-8", pdf, "-"]).stdout.decode("utf8", "replace")
    pages = [clean(p) for p in raw.split("\f")]
    while pages and not pages[-1]:
        pages.pop()
    return pages


def cover(pdf, dest):
    """Best of the first four pages, so a blank flyleaf isn't the cover."""
    with tempfile.TemporaryDirectory() as td:
        try:
            run(["pdftoppm", "-jpeg", "-jpegopt", "quality=70", "-scale-to-x", "420",
                 "-scale-to-y", "-1", "-f", "1", "-l", "4", pdf, os.path.join(td, "c")],
                timeout=300)
            from PIL import Image, ImageStat
            best, score = None, -1
            for f in sorted(x for x in os.listdir(td) if x.endswith(".jpg")):
                fp = os.path.join(td, f)
                im = Image.open(fp).convert("L")
                ink = sum(1 for px in im.resize((84, 110)).getdata() if px < 205) / (84 * 110)
                s = ImageStat.Stat(im).stddev[0] * min(ink * 8, 1.0)
                if s > score:
                    best, score = fp, s
            if best:
                shutil.move(best, dest)
                return True
        except Exception:
            pass
    return False


def shrink(src, dest, dpi, quality):
    """Greyscale web copy. The OCR text layer survives this untouched."""
    r = run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pdfwrite",
             "-dPDFSETTINGS=/ebook", "-dCompatibilityLevel=1.5",
             "-dDetectDuplicateImages=true", "-dFastWebView=true",
             "-dColorConversionStrategy=/Gray", "-dProcessColorModel=/DeviceGray",
             "-dDownsampleGrayImages=true", "-dDownsampleColorImages=true",
             "-dGrayImageDownsampleType=/Bicubic", "-dColorImageDownsampleType=/Bicubic",
             f"-dGrayImageResolution={dpi}", f"-dColorImageResolution={dpi}",
             f"-dJPEGQ={quality}", f"-sOutputFile={dest}", src])
    return r.returncode == 0 and os.path.exists(dest) and os.path.getsize(dest) > 10240


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="one or more collection ids, comma separated")
    ap.add_argument("--ids", help="specific document ids, comma separated")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dpi", type=int, default=200, help="web copy resolution (default 200)")
    ap.add_argument("--quality", type=int, default=60, help="web copy JPEG quality (default 60)")
    ap.add_argument("--jobs", type=int, default=4, help="OCR threads per volume")
    ap.add_argument("--derivatives", help="keep the smaller web copies in this folder")
    ap.add_argument("--no-shrink", action="store_true", help="re-OCR only, no web copy")
    ap.add_argument("--force", action="store_true", help="redo volumes already done")
    ap.add_argument("--min-ratio", type=float, default=0.6,
                    help="reject the new text if it is below this fraction of the old (default 0.6)")
    ap.add_argument("--report", action="store_true", help="print what has been done and stop")
    ap.add_argument("--no-ocr", action="store_true",
                    help="skip OCR entirely — just make the smaller web copies")
    ap.add_argument("--find-bad", action="store_true",
                    help="list the volumes whose text layer looks weakest, and stop")
    a = ap.parse_args()

    state = json.load(open(STATE)) if os.path.exists(STATE) else {}

    if a.report:
        if not state:
            print("Nothing re-read yet.")
            return
        ok = [v for v in state.values() if v.get("status") == "ok"]
        print(f"{len(state)} volumes attempted, {len(ok)} replaced")
        if ok:
            ob = sum(v["old_bytes"] for v in ok); nb = sum(v["new_bytes"] for v in ok)
            oc = sum(v["old_chars"] for v in ok); nc = sum(v["new_chars"] for v in ok)
            print(f"  size  {ob/1073741824:.2f} GB -> {nb/1073741824:.2f} GB "
                  f"({ob/max(nb,1):.1f}x smaller)")
            print(f"  text  {oc/1e6:.1f}M chars -> {nc/1e6:.1f}M chars "
                  f"({(nc-oc)/max(oc,1)*100:+.0f}%)")
        for k, v in sorted(state.items(), key=lambda kv: kv[1].get("delta_pct", 0))[:8]:
            if v.get("status") != "ok":
                print(f"  ! {k}: {v.get('status')}")
        return

    if a.find_bad:
        rows = []
        for it in json.load(open(os.path.join(DATA, "items.json")))["items"]:
            fp = os.path.join(TEXT, it["id"] + ".json")
            if not os.path.exists(fp):
                continue
            j = json.load(open(fp))
            pages = j.get("pages") or 1
            rows.append(((j.get("chars") or 0) / pages, it["title"], it["id"], pages))
        rows.sort()
        print("Volumes with the least text per page — the ones worth re-OCRing:\n")
        print(f"{'chars/page':>10}  {'pages':>5}  volume")
        for cpp, title, tid, pages in rows[:25]:
            print(f"{cpp:10.0f}  {pages:5d}  {title[:56]}")
        print("\nRe-OCR one of them with:  ./build/reocr.py --ids <id>")
        return

    if not a.no_ocr:
        need("ocrmypdf")
    need("pdftotext")
    if not a.no_shrink:
        need("gs")
    if a.derivatives:
        os.makedirs(a.derivatives, exist_ok=True)

    items = [i for i in json.load(open(os.path.join(DATA, "items.json")))["items"]
             if i["type"] == "document" and i.get("format", "pdf") == "pdf"]
    if a.only:
        keep = set(a.only.split(",")); items = [i for i in items if i["collection"] in keep]
    if a.ids:
        keep = set(a.ids.split(",")); items = [i for i in items if i["id"] in keep]
    todo = [i for i in items if a.force or state.get(i["id"], {}).get("status") != "ok"]
    if a.limit:
        todo = todo[: a.limit]

    print(f"{len(todo)} of {len(items)} volumes to re-read")
    t0 = time.time()
    for n, it in enumerate(todo, 1):
        tid = it["id"]
        tpath = os.path.join(TEXT, tid + ".json")
        old = json.load(open(tpath)) if os.path.exists(tpath) else {"chars": 0, "pdf_bytes": 0}
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "in.pdf")
            if not fetch(it["pdf"], src):
                state[tid] = {"status": "download-failed"}
                print(f"[{n}/{len(todo)}] download failed   {it['title'][:50]}")
                continue
            old_bytes = os.path.getsize(src)
            ocr = os.path.join(td, "ocr.pdf")
            if a.no_ocr:
                shutil.copyfile(src, ocr)
                r = subprocess.CompletedProcess([], 0, b"", b"")
            else:
                # --force-ocr, never --redo-ocr: redo-ocr leaves the old text
                # layer in place and adds a second one on top of it
                r = run(["ocrmypdf", "--force-ocr", "--language", "eng",
                         "--jobs", str(a.jobs), "--optimize", "1",
                         "--output-type", "pdf", src, ocr])
            if r.returncode != 0 or not os.path.exists(ocr):
                msg = r.stderr.decode("utf8", "replace").strip().splitlines()[-1:] or ["failed"]
                state[tid] = {"status": "ocr-failed: " + msg[0][:120]}
                print(f"[{n}/{len(todo)}] OCR failed        {it['title'][:50]}")
                continue

            web = ocr
            if not a.no_shrink:
                small = os.path.join(td, "web.pdf")
                if shrink(ocr, small, a.dpi, a.quality):
                    web = small

            pages = page_text(ocr)          # read the text from the full-resolution file
            new_chars = sum(len(p) for p in pages)
            ratio = new_chars / max(old.get("chars") or 1, 1)
            if ratio < a.min_ratio:
                state[tid] = {"status": f"rejected: new text only {ratio*100:.0f}% of old",
                              "old_chars": old.get("chars", 0), "new_chars": new_chars}
                print(f"[{n}/{len(todo)}] rejected {ratio*100:3.0f}%     {it['title'][:50]}")
                continue

            new_bytes = os.path.getsize(web)
            json.dump({"id": tid, "pdf": it["pdf"], "pdf_bytes": new_bytes,
                       "pages": len(pages), "chars": new_chars, "format": "pdf",
                       "pdf_title": old.get("pdf_title"), "creator": "tesseract (re-read)",
                       "text": pages}, open(tpath, "w"))
            cover(ocr, os.path.join(COVER, tid + ".jpg"))
            if a.derivatives and web != ocr:
                shutil.copyfile(web, os.path.join(a.derivatives,
                                                  it["pdf"].rsplit("/", 1)[-1]))
            state[tid] = {"status": "ok", "old_bytes": old_bytes, "new_bytes": new_bytes,
                          "old_chars": old.get("chars", 0), "new_chars": new_chars,
                          "delta_pct": round((new_chars - old.get("chars", 1))
                                             / max(old.get("chars", 1), 1) * 100, 1)}
            print(f"[{n}/{len(todo)}] ok  text {state[tid]['delta_pct']:+6.1f}%  "
                  f"size {old_bytes/1048576:5.0f} -> {new_bytes/1048576:4.0f} MB  "
                  f"{(time.time()-t0)/60:5.1f}m  {it['title'][:44]}")
        json.dump(state, open(STATE, "w"), indent=1)

    json.dump(state, open(STATE, "w"), indent=1)
    done = [v for v in state.values() if v.get("status") == "ok"]
    print(f"\n{len(done)} volumes replaced in {(time.time()-t0)/60:.1f} minutes")
    print("Now run ./build/build.sh to rebuild the site with the improved text.")
    if a.derivatives:
        print(f"Web copies are in {a.derivatives}/ — upload them to psiu.org in place of the "
              f"current files, keeping the same names, and nothing will break.")


if __name__ == "__main__":
    main()
