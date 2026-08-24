#!/usr/bin/env python3
"""
Assemble data/timeline.json from two sources:

  data/timeline-core.json   hand-written events, each with its source
  data/chapters.json        one event per chapter chartered, and per closure

Edit timeline-core.json to add an event; the chapter events are derived.
"""
import json, os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

def load(name, default):
    fp = os.path.join(DATA, name)
    return json.load(open(fp)) if os.path.exists(fp) else default

core     = load("timeline-core.json", [])
chapters = load("chapters.json", [])

events = []
for e in core:
    e.setdefault("category", "founding")
    events.append(e)

ORD = {1: "st", 2: "nd", 3: "rd"}
def ordinal(n):
    suffix = "th" if 10 <= n % 100 <= 20 else ORD.get(n % 10, "th")
    return "%d%s" % (n, suffix)

for c in chapters:
    events.append(dict(
        year=c["founded"], category="expansion",
        title="The %s is chartered" % c["name"],
        text="Psi Upsilon's %s chapter, at %s." % (ordinal(c["position"]), c["institution"]),
        link="chapters/%s.html" % c["id"], link_label="The %s" % c["name"],
        thumb=c.get("arms")))
    if c.get("closed"):
        what = "becomes an Owl Club" if c["status"] == "owl club" else "goes inactive"
        events.append(dict(
            year=c["closed"], category="expansion",
            title="The %s %s" % (c["name"], what),
            text="After %d years at %s." % (c["closed"] - c["founded"], c["institution"]),
            link="chapters/%s.html" % c["id"], link_label="The %s" % c["name"],
            thumb=c.get("arms"), quiet=True))

events.sort(key=lambda e: (e["year"], 0 if e.get("feature") else 1, e["title"]))
json.dump(events, open(os.path.join(DATA, "timeline.json"), "w"), indent=1)

print("  %d events, %d-%d -> data/timeline.json"
      % (len(events), events[0]["year"], events[-1]["year"]))
for k, n in Counter(e["category"] for e in events).most_common():
    print("    %4d  %s" % (n, k))
