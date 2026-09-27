"""Load the curated public utility project snapshot used by the dashboard."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from shapely.geometry import shape

from . import config
from .models import PROJECT_TYPES, Field, ProjectRecord

PUBLIC_PROJECTS_PATH = config.DATA_DIR / "public_projects.json"
ALLOWED_GEOMETRIES = {"Point", "LineString"}


def load_public_projects(path: Path | None = None) -> list[ProjectRecord]:
    """Load and validate public-source records for transparent geographic screening."""
    source_path = path or PUBLIC_PROJECTS_PATH
    payload = json.loads(source_path.read_text())
    snapshot_date = payload.get("retrieved_at")
    if snapshot_date:
        date.fromisoformat(snapshot_date)

    records = []
    seen_ids: set[tuple[str, str]] = set()
    utilities: set[str] = set()
    for project in payload.get("projects", []):
        for key in ("project_id", "utility", "project_name", "source_url", "geometry"):
            if not project.get(key):
                raise ValueError(f"Public project is missing required field: {key}")

        record_key = (project["utility"], project["project_id"])
        if record_key in seen_ids:
            raise ValueError(f"Duplicate public project: {project['utility']} / {project['project_id']}")
        seen_ids.add(record_key)
        utilities.add(project["utility"])

        source_url = project["source_url"]
        if not source_url.startswith(("https://", "http://")):
            raise ValueError(f"Public project source must be an HTTP URL: {project['project_id']}")

        project_type = project.get("project_type", "other")
        if project_type not in PROJECT_TYPES:
            raise ValueError(f"Unsupported project type for {project['project_id']}: {project_type}")
        voltage = project.get("voltage_kv")
        if voltage is not None and (not isinstance(voltage, int) or voltage <= 0):
            raise ValueError(f"Voltage must be a positive integer for {project['project_id']}")

        geometry = project["geometry"]
        try:
            parsed_geometry = shape(geometry)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"Invalid GeoJSON geometry for {project['project_id']}") from exc
        if parsed_geometry.geom_type not in ALLOWED_GEOMETRIES or parsed_geometry.is_empty or not parsed_geometry.is_valid:
            raise ValueError(f"Unsupported or invalid geometry for {project['project_id']}")
        min_lon, min_lat, max_lon, max_lat = parsed_geometry.bounds
        if not (-180 <= min_lon <= max_lon <= 180 and -90 <= min_lat <= max_lat <= 90):
            raise ValueError(f"Coordinates outside longitude/latitude bounds for {project['project_id']}")

        start_value, end_value = project.get("start_date"), project.get("end_date")
        start_date = date.fromisoformat(start_value) if start_value else None
        end_date = date.fromisoformat(end_value) if end_value else None
        if start_date and end_date and start_date > end_date:
            raise ValueError(f"End date precedes start date for {project['project_id']}")

        quote = project.get("source_quote", "")
        geometry_note = project.get("geometry_quality", "Geometry quality not specified")
        schedule_text = project.get("schedule_text", "")
        region = project.get("region", "South Florida" if project["utility"] in {"Florida Power & Light", "Homestead Public Services Energy"} else "Georgia + South Carolina")
        fields = {
            "project_name": Field(project["project_name"], 1.0, quote),
            "project_type": Field(project_type, 0.9, quote),
            "voltage_kv": Field(voltage, 0.9 if voltage is not None else 0.0, quote),
            "location_text": Field(project.get("location_text", ""), 0.8, quote, note=geometry_note),
            "geometry": Field(geometry, 0.45 if "approximate" in geometry_note.lower() or "county-level" in geometry_note.lower() else 0.8, quote, note=geometry_note),
            "start_date": Field(start_value, 0.8 if start_value else 0.0, schedule_text),
            "end_date": Field(end_value, 0.8 if end_value else 0.0, schedule_text),
            "source_url": Field(source_url, 1.0),
            "source_title": Field(project.get("source_title", "Public utility source"), 1.0),
            "schedule_text": Field(schedule_text, 1.0),
            "geometry_quality": Field(geometry_note, 1.0),
            "source_snapshot_date": Field(snapshot_date, 1.0),
            "region": Field(region, 1.0),
        }
        records.append(ProjectRecord(
            project_id=project["project_id"],
            utility=project["utility"],
            document=project.get("source_title", "Public utility source"),
            fields=fields,
            extractor="public-source-snapshot",
            status="public_screening",
            issues=["Confirm the official route before treating this distance as definitive."],
        ))

    if len(utilities) < 2:
        raise ValueError("The public project snapshot must include at least two utilities")
    return records
