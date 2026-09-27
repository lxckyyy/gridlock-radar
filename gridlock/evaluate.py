"""Measure extraction against the hand-labeled answer key in data/labels.csv."""

from __future__ import annotations

import csv
from datetime import date

from . import config
from .confidence import route
from .spatial.geometry import distance_km, point, representative_latlon
from .models import ProjectRecord

CHECKED_FIELDS = ("geometry", "start_date", "end_date", "project_type", "voltage_kv")


def load_labels(path=config.LABELS_PATH) -> dict[str, dict]:
    with open(path) as f:
        return {row["project_id"]: row for row in csv.DictReader(f)}


def field_correct(record: ProjectRecord, label: dict, name: str) -> bool:
    value = record.value(name)
    if value is None:
        return False
    if name == "geometry":
        # The label stores one representative point (a line's midpoint); compare against ours.
        lat, lon = representative_latlon(value)
        return distance_km(point(lat, lon), point(float(label["lat"]), float(label["lon"]))) <= config.EVAL_KM
    if name in ("start_date", "end_date"):
        return abs((date.fromisoformat(value) - date.fromisoformat(label[name])).days) <= config.EVAL_DAYS
    if name == "voltage_kv":
        return int(value) == int(label["voltage_kv"])
    return value == label[name]


def record_correct(record: ProjectRecord, label: dict) -> bool:
    """A record is correct when every field the overlap engine depends on is correct."""
    return all(field_correct(record, label, f) for f in config.CRITICAL_FIELDS)


def evaluate(records: list[ProjectRecord], labels: dict[str, dict] | None = None) -> dict:
    labels = labels or load_labels()
    matched = [(r, labels[r.project_id]) for r in records if r.project_id in labels]
    if not matched:
        return {"labeled": 0}

    per_field = {f: sum(field_correct(r, lab, f) for r, lab in matched) / len(matched) for f in CHECKED_FIELDS}
    correct = [record_correct(r, lab) for r, lab in matched]
    auto = [ok for (r, _), ok in zip(matched, correct) if r.status == "auto_approved"]
    return {
        "labeled": len(matched),
        "field_accuracy": per_field,
        "record_accuracy": sum(correct) / len(correct),
        "auto_approve_rate": len(auto) / len(matched),
        "auto_approved_accuracy": sum(auto) / len(auto) if auto else None,
        "missing_from_extraction": sorted(set(labels) - {r.project_id for r in records}),
    }


def threshold_sweep(records: list[ProjectRecord], labels: dict[str, dict] | None = None,
                    thresholds=(0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95)) -> list[dict]:
    """How auto-approve rate and auto-approved accuracy trade off as the threshold moves."""
    labels = labels or load_labels()
    matched = [(r, labels[r.project_id]) for r in records if r.project_id in labels]
    rows = []
    for t in thresholds:
        auto = [record_correct(r, lab) for r, lab in matched if route(r, t) == "auto_approved"]
        rows.append({
            "threshold": t,
            "auto_approve_rate": len(auto) / len(matched) if matched else 0.0,
            "auto_approved_accuracy": sum(auto) / len(auto) if auto else None,
            "sent_to_review": len(matched) - len(auto),
        })
    return rows
