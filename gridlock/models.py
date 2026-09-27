"""Data model: a project record made of fields, each with a value, a confidence and its evidence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from .spatial.geometry import representative_latlon

PROJECT_TYPES = ("line_rebuild", "new_line", "substation", "transformer", "substation_equipment", "other")
TYPE_FAMILY = {
    "line_rebuild": "line",
    "new_line": "line",
    "substation": "station",
    "transformer": "station",
    "substation_equipment": "station",
    "other": "other",
}


@dataclass
class Field:
    value: object = None
    confidence: float = 0.0
    quote: str = ""  # source text the value came from
    page: int | None = None  # 1-based page number
    note: str = ""  # how the value was derived, e.g. "county centroid"


@dataclass
class ProjectRecord:
    project_id: str
    utility: str
    document: str
    fields: dict[str, Field] = field(default_factory=dict)
    extractor: str = "rules"
    status: str = "pending"  # auto_approved | needs_review | approved | rejected
    issues: list[str] = field(default_factory=list)

    def value(self, name: str):
        f = self.fields.get(name)
        return f.value if f else None

    def confidence(self, name: str) -> float:
        f = self.fields.get(name)
        return f.confidence if f else 0.0

    @property
    def geometry(self) -> dict | None:
        return self.value("geometry")

    @property
    def lat(self):
        return representative_latlon(self.geometry)[0] if self.geometry else None

    @property
    def lon(self):
        return representative_latlon(self.geometry)[1] if self.geometry else None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, text: str) -> ProjectRecord:
        raw = json.loads(text)
        raw["fields"] = {k: Field(**v) for k, v in raw["fields"].items()}
        return cls(**raw)
