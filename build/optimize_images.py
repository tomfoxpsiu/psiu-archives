#!/usr/bin/env python3
"""
Shrink the images the site ships: cover thumbnails and story illustrations.
Converts PNGs to progressive JPEG and rewrites data/stories.json to match.
Safe to run repeatedly.
"""
import json, os, glob
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def shrink(path, maxw, q):
    im = Image.open(path)
    if im.mode in ("P", "RGBA", "LA"): im = im.convert("RGB")
    if im.width > maxw:
        im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    out = os.path.splitext(path)[0] + ".jpg"
    im.save(out, "JPEG", quality=q, optimize=True, progressive=True)
    if out != path: os.remove(path)
    return out

def sweep(pattern, maxw, q):
    before = after = 0; renames = {}
    for f in glob.glob(os.path.join(ROOT, pattern)):
        before += os.path.getsize(f)
        try:
            out = shrink(f, maxw, q)
            after += os.path.getsize(out)
            if out != f:
                renames[os.path.relpath(f, os.path.join(ROOT, "site"))] = \
                    os.path.relpath(out, os.path.join(ROOT, "site"))
        except Exception as e:
            after += os.path.getsize(f); print("  skip", os.path.basename(f), e)
    print(f"  {pattern}: {before/1048576:.1f}MB -> {after/1048576:.1f}MB")
    return renames

renames = {}
renames.update(sweep("site/assets/covers/*.jpg", 420, 68))
renames.update(sweep("site/assets/covers/*.png", 420, 68))
renames.update(sweep("site/assets/stories/*.png", 1200, 78))
renames.update(sweep("site/assets/stories/*.jpg", 1200, 78))
renames.update(sweep("site/assets/objects/*.png", 1400, 80))
renames.update(sweep("site/assets/people/*.jpg", 600, 78))
renames.update(sweep("site/assets/people/*.png", 600, 78))
renames.update(sweep("site/assets/houses/*.jpg", 800, 78))

def retarget(fname, single_keys=(), list_keys=()):
    """Point a data file at the converted image names."""
    fp = os.path.join(ROOT, "data", fname)
    if not renames or not os.path.exists(fp):
        return
    rows = json.load(open(fp))
    n = 0
    for r in rows:
        for k in list_keys:
            if r.get(k):
                new = [renames.get(u, u) for u in r[k]]
                n += sum(1 for a, b in zip(r[k], new) if a != b)
                r[k] = new
        for k in single_keys:
            if r.get(k) and r[k] in renames:
                r[k] = renames[r[k]]
                n += 1
    json.dump(rows, open(fp, "w"), indent=1)
    if n:
        print(f"  repointed {n} image path(s) in data/{fname}")

retarget("stories.json", single_keys=("cover",), list_keys=("images",))
retarget("people.json", single_keys=("portrait",))
retarget("chapters.json", single_keys=("arms", "house"))
