"""Rule-based extractor: works offline, no API key needed.

It reads "Project <ID>: <name>" blocks followed by "Key: value" lines, which is how the
sample plans (and many real utility slide decks) are laid out.
"""

from __future__ import annotations

import re
from datetime import timedelta

from .dates import parse_window
from ..models import Field, ProjectRecord

PROJECT_HEAD = re.compile(r"^\s*Project\s+([A-Z]{2,5}-\d{4}-\d{2,3})\s*[:\-–]\s*(.+?)\s*$", re.M)
KEY_VALUE = re.compile(r"^\s*([A-Za-z][A-Za-z .\-]{1,30}?)\s*:\s*(.+?)\s*$", re.M)
VOLTAGE = re.compile(r"(\d{2,3})(?:/\d{2,3})?\s*kV", re.I)

LOCATION_KEYS = ("location", "site", "where", "route")
CONSTRUCTION_KEYS = ("construction", "construction window", "est. construction", "schedule", "timing")
IN_SERVICE_KEYS = ("in-service", "in service", "planned in-service")
SCOPE_KEYS = ("scope", "description")

TYPE_PATTERNS = {
    "transformer": r"transformer",
    "substation_equipment": r"breaker|relay|switchgear",
    "substation": r"new\s+(?:\d+\s*kV\s+)?substation|substation\s+expansion",
    "new_line": r"new\s+(?:\d+\s*kV\s+)?line|line\s+extension",
    "line_rebuild": r"rebuild|reconductor",
}
# If only an in-service date is given, assume construction runs this long before it.
ASSUMED_BUILD_DAYS = 365
CONF_ASSUMED_START = 0.50


def _blocks(pages: list[str]):
    """Yield (page_number, project_id, name, block_text) for every project block."""
    for page_no, text in enumerate(pages, start=1):
        heads = list(PROJECT_HEAD.finditer(text))
        for i, head in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            yield page_no, head[1], head[2], text[head.start() : end]


def _key_values(block: str) -> dict[str, tuple[str, str]]:
    """Map lower-cased key -> (value, full source line)."""
    return {m[1].strip().lower(): (m[2], m[0].strip()) for m in KEY_VALUE.finditer(block)}


def _first(kv: dict, keys: tuple[str, ...]):
    for key in keys:
        if key in kv:
            return key, kv[key]
    return None, None


def _classify(text: str) -> tuple[str, float]:
    matches = [t for t, pattern in TYPE_PATTERNS.items() if re.search(pattern, text, re.I)]
    if not matches:
        return "other", 0.30
    return matches[0], 0.90 if len(matches) == 1 else 0.60


def extract(pages: list[str], utility: str, document: str) -> list[ProjectRecord]:
    records = []
    for page, project_id, name, block in _blocks(pages):
        kv = _key_values(block)
        head_line = block.splitlines()[0].strip()
        f: dict[str, Field] = {"project_name": Field(name, 0.95, head_line, page)}

        _, scope = _first(kv, SCOPE_KEYS)
        scope_text, scope_line = scope if scope else ("", "")

        ptype, conf = _classify(f"{name} {scope_text}")
        f["project_type"] = Field(ptype, conf, f"{head_line} {scope_line}".strip(), page)

        kv_match = VOLTAGE.search(name) or VOLTAGE.search(scope_text)
        if kv_match:
            in_name = VOLTAGE.search(name) is not None
            f["voltage_kv"] = Field(int(kv_match[1]), 0.95 if in_name else 0.85, head_line if in_name else scope_line, page)
        else:
            f["voltage_kv"] = Field(None, 0.0, "", page, "no voltage found")

        _, loc = _first(kv, LOCATION_KEYS)
        f["location_text"] = Field(loc[0], 0.90, loc[1], page) if loc else Field(None, 0.0, "", page, "no location line")

        _, sched = _first(kv, CONSTRUCTION_KEYS)
        window = parse_window(sched[0]) if sched else None
        if window:
            start, end, conf = window
            f["start_date"] = Field(start.isoformat(), conf, sched[1], page)
            f["end_date"] = Field(end.isoformat(), conf, sched[1], page)
        else:
            _, isd = _first(kv, IN_SERVICE_KEYS)
            window = parse_window(isd[0]) if isd else None
            if window:
                end = window[1]
                start = end - timedelta(days=ASSUMED_BUILD_DAYS)
                f["start_date"] = Field(start.isoformat(), CONF_ASSUMED_START, isd[1], page, "assumed 12 months before in-service")
                f["end_date"] = Field(end.isoformat(), window[2], isd[1], page, "in-service date")
            else:
                f["start_date"] = Field(None, 0.0, "", page, "no schedule found")
                f["end_date"] = Field(None, 0.0, "", page, "no schedule found")

        status = kv.get("status")
        f["status"] = Field(status[0].lower(), 0.95, status[1], page) if status else Field(None, 0.0, "", page)

        records.append(ProjectRecord(project_id, utility, document, f, extractor="rules"))
    return records
