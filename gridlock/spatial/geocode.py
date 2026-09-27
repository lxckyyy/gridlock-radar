"""Turn location text into a project shape (a point or a line).

"A substation to B substation" becomes a line from A to B, in the order the text names them.
One named substation is a point. A county gives only its centroid; "near <place>" is a guess.
Each result carries a confidence that reflects which of those it was.

Real routes are not straight: swap in line shapes from a GIS dataset (e.g. HIFLD transmission
lines) when you have them, via data/lines.csv.
"""

from __future__ import annotations

import csv
import json
import re
from functools import lru_cache

from .. import config
from .geometry import line, point

CONF_SUBSTATION = 0.95
CONF_NEAR_PLACE = 0.70
CONF_COUNTY = 0.55
LINES_PATH = config.DATA_DIR / "lines.csv"


@lru_cache
def substations() -> dict[str, tuple[float, float]]:
    with open(config.SUBSTATIONS_PATH) as f:
        return {row["name"]: (float(row["lat"]), float(row["lon"])) for row in csv.DictReader(f)}


@lru_cache
def counties() -> dict[str, tuple[float, float]]:
    with open(config.COUNTIES_PATH) as f:
        return {row["county"]: (float(row["lat"]), float(row["lon"])) for row in csv.DictReader(f)}


@lru_cache
def known_lines() -> dict[frozenset, dict]:
    """Optional real routes: data/lines.csv with columns from,to,geojson (a LineString)."""
    if not LINES_PATH.exists():
        return {}
    with open(LINES_PATH) as f:
        return {frozenset((r["from"], r["to"])): json.loads(r["geojson"]) for r in csv.DictReader(f)}


def geocode(text: str | None) -> tuple[dict | None, float, str]:
    """Return (geometry or None, confidence, method)."""
    if not text:
        return None, 0.0, "no location text"

    hits = []  # (position in text, name, vague)
    remaining = text
    # Longest names first, blanking each match, so "Augusta" is not found inside "North Augusta".
    for name in sorted(substations(), key=len, reverse=True):
        m = re.search(rf"(near\s+)?\b{re.escape(name)}\b(?!\s+County)(\s+substation)?", remaining, re.I)
        if m:
            hits.append((m.start(), name, bool(m[1]) and not m[2]))
            remaining = remaining[: m.start()] + " " * len(m[0]) + remaining[m.end():]
    if hits:
        hits.sort()
        names = [h[1] for h in hits]
        conf, method = CONF_SUBSTATION, "substation match"
        if any(h[2] for h in hits):
            conf, method = CONF_NEAR_PLACE, "near a named place"
        if len(names) == 1:
            return point(*substations()[names[0]]), conf, method
        route = known_lines().get(frozenset(names[:2]))
        if route:
            return route, conf, "known line route"
        return line([substations()[n] for n in names]), conf, method + " (straight line between substations)"

    m = re.search(r"\b([A-Z][a-z]+)\s+County\b", text)
    if m and m[1] in counties():
        return point(*counties()[m[1]]), CONF_COUNTY, "county centroid"

    return None, 0.0, "no known place found"


def place_options() -> dict[str, tuple[float, float]]:
    """Every known place, for the reviewer's location picker."""
    options = {f"{name} substation": c for name, c in substations().items()}
    options.update({f"{name} County (centroid)": c for name, c in counties().items()})
    return dict(sorted(options.items()))
