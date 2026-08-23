#!/usr/bin/env bash
# Rebuild the whole site from data/. Safe to run any time.
#
#   ./build/build.sh            regenerate pages + search index
#   ./build/build.sh --pull     also re-read psiu.org for new PDFs first
#   ./build/build.sh --serve    build, then serve at http://localhost:8000
set -euo pipefail
cd "$(dirname "$0")/.."

PULL=0; SERVE=0
for a in "$@"; do
  [ "$a" = "--pull" ]  && PULL=1
  [ "$a" = "--serve" ] && SERVE=1
done

if [ "$PULL" = 1 ]; then
  echo "== crawling psiu.org for the document list =="
  python3 build/crawl_source.py
  python3 build/build_manifest.py
  python3 build/build_stories.py
  python3 build/build_people.py
  python3 build/build_chapters.py
  python3 build/build_heraldry.py
  python3 build/build_links.py
fi

echo "== optimising images =="
python3 build/optimize_images.py

echo "== extracting text for anything new (downloads, reads, discards) =="
python3 build/extract.py

echo "== working out who and what is mentioned where =="
python3 build/build_mentions.py

echo "== generating pages =="
python3 build/gen_site.py

echo "== building the search index =="
npx --yes pagefind@1 --site build/index_html \
    --output-path "$(pwd)/site/pagefind" --root-selector main

echo
echo "Done. Deploy the contents of ./site"
du -sh site

if [ "$SERVE" = 1 ]; then
  echo "Serving http://localhost:8000 — Ctrl-C to stop"
  python3 -m http.server 8000 --directory site
fi
