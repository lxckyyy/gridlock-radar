"""Confidence scoring and routing.

Each field's confidence starts from the extractor, then rule checks can only lower it.
A record is auto-approved only when every critical field clears the threshold and no
check failed; otherwise it goes to the human review queue with the reasons attached.
"""

from __future__ import annotations

from datetime import date

from . import config
from .spatial.geocode import geocode
from .spatial.geometry import latlon_path
from .models import Field, ProjectRecord

CONF_FAILED_CHECK = 0.30


def add_geometry(record: ProjectRecord) -> None:
    loc = record.fields.get("location_text", Field())
    geom, geo_conf, method = geocode(loc.value)
    record.fields["geometry"] = Field(
        geom,
        min(geo_conf, loc.confidence) if geom else 0.0,
        loc.quote,
        loc.page,
        method,
    )


def _cap(record: ProjectRecord, name: str, issue: str) -> None:
    f = record.fields.get(name)
    if f is not None:
        f.confidence = min(f.confidence, CONF_FAILED_CHECK)
    record.issues.append(issue)


def validate(record: ProjectRecord) -> None:
    """Run sanity checks; lower confidence and note an issue for each failure."""
    kv = record.value("voltage_kv")
    if kv is not None and kv not in config.STANDARD_KV:
        _cap(record, "voltage_kv", f"{kv} kV is not a standard transmission voltage")

    start, end = record.value("start_date"), record.value("end_date")
    if start and end:
        s, e = date.fromisoformat(start), date.fromisoformat(end)
        if e < s:
            _cap(record, "start_date", "end date is before start date")
            _cap(record, "end_date", "end date is before start date")
        lo, hi = config.PLAN_YEARS
        if not (lo <= s.year <= hi and lo <= e.year <= hi):
            _cap(record, "start_date", f"dates fall outside {lo}-{hi}")

    geom = record.geometry
    if geom:
        lats, lons = latlon_path(geom)
        lat_ok = all(config.SERVICE_BBOX["lat"][0] <= v <= config.SERVICE_BBOX["lat"][1] for v in lats)
        lon_ok = all(config.SERVICE_BBOX["lon"][0] <= v <= config.SERVICE_BBOX["lon"][1] for v in lons)
        if not (lat_ok and lon_ok):
            _cap(record, "geometry", "location falls outside the service territory")


def low_fields(record: ProjectRecord, threshold: float) -> list[str]:
    return [name for name in config.CRITICAL_FIELDS if record.confidence(name) < threshold]


def route(record: ProjectRecord, threshold: float = config.CONFIDENCE_THRESHOLD) -> str:
    return "needs_review" if low_fields(record, threshold) or record.issues else "auto_approved"


def score(record: ProjectRecord, threshold: float = config.CONFIDENCE_THRESHOLD) -> ProjectRecord:
    """Geocode, validate and route one freshly extracted record (mutates and returns it)."""
    add_geometry(record)
    validate(record)
    record.status = route(record, threshold)
    return record
