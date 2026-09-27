"""Claude extractor for messy documents the rule extractor cannot parse.

Claude returns JSON matching SCHEMA, including its own per-field confidence and a verbatim
quote. We never trust that blindly: every quote is checked against the page text, and
vague schedules are capped by the same date rules the offline extractor uses.
"""

from __future__ import annotations

import json
import re
import time

from .. import config
from .dates import parse_window
from ..models import PROJECT_TYPES, Field, ProjectRecord

CONF_UNVERIFIED = 0.30


def _nullable(kind: str) -> dict:
    return {"anyOf": [{"type": kind}, {"type": "null"}]}


CONFIDENCE_KEYS = ("project_type", "voltage_kv", "location_text", "construction_start", "construction_end")
SCHEMA = {
    "type": "object",
    "properties": {
        "utility": {"type": "string"},
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "project_name": {"type": "string"},
                    "project_type": {"type": "string", "enum": list(PROJECT_TYPES)},
                    "voltage_kv": _nullable("integer"),
                    "location_text": _nullable("string"),
                    "schedule_text": _nullable("string"),
                    "construction_start": _nullable("string"),
                    "construction_end": _nullable("string"),
                    "status": _nullable("string"),
                    "page": {"type": "integer"},
                    "source_quote": {"type": "string"},
                    "confidence": {
                        "type": "object",
                        "properties": {k: {"type": "number"} for k in CONFIDENCE_KEYS},
                        "required": list(CONFIDENCE_KEYS),
                        "additionalProperties": False,
                    },
                },
                "required": [
                    "project_id", "project_name", "project_type", "voltage_kv", "location_text",
                    "schedule_text", "construction_start", "construction_end", "status", "page",
                    "source_quote", "confidence",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["utility", "projects"],
    "additionalProperties": False,
}

PROMPT = """You are extracting planned construction projects from an electric utility's public planning document.
The pages are marked "=== Page N ===".

For every project, return:
- project_id and project_name as written (invent an id like "<UTILITY>-<n>" only if none is given)
- project_type: one of {types}
- voltage_kv: the main voltage in kV, or null
- location_text: the location exactly as written in the document (copy the words), or null
- schedule_text: the construction or in-service schedule exactly as written, or null
- construction_start / construction_end: ISO dates (YYYY-MM-DD) for the construction window. If only a year, quarter or
  season is given, use its first and last day. If only an in-service date is given, set the end to it and estimate the start.
- page: the page number the project appears on
- source_quote: one verbatim line from that page that names the project
- confidence: 0 to 1 per field. Be honest: 0.9+ only when the document states it plainly; 0.5-0.7 when you inferred or
  estimated it; below 0.5 when you are guessing.

Document:
{document}"""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _iso_or_none(value: str | None) -> str | None:
    from datetime import date

    try:
        return date.fromisoformat(value).isoformat() if value else None
    except ValueError:
        return None


def available() -> bool:
    import importlib.util

    try:
        package_available = importlib.util.find_spec("anthropic") is not None
    except (ImportError, ValueError):
        package_available = False
    if not package_available:
        return False
    import os

    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def call_claude(document_text: str) -> tuple[dict, dict]:
    """Return (parsed JSON, usage stats). Raises RuntimeError on a refusal."""
    import anthropic

    client = anthropic.Anthropic()
    prompt = PROMPT.format(types=", ".join(PROJECT_TYPES), document=document_text)
    started = time.perf_counter()
    with client.messages.stream(
        model=config.CLAUDE_MODEL,
        max_tokens=32000,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": config.CLAUDE_EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        # If a safety classifier declines, the API re-runs the request on a recommended fallback model.
        extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
        extra_body={"fallbacks": "default"},
    ) as stream:
        response = stream.get_final_message()
    latency_ms = (time.perf_counter() - started) * 1000

    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined to extract this document: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Extraction was cut off at max_tokens; split the document and retry.")

    price_in, price_out = config.MODEL_PRICES.get(config.CLAUDE_MODEL, (0.0, 0.0))
    usage = response.usage
    cost = (usage.input_tokens * price_in + usage.output_tokens * price_out) / 1_000_000
    text = next(block.text for block in response.content if block.type == "text")
    stats = {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost_usd": cost,
        "latency_ms": latency_ms,
        "model": response.model,
    }
    return json.loads(text), stats


def to_records(data: dict, pages: list[str], document: str) -> list[ProjectRecord]:
    """Convert Claude's JSON into records, lowering confidence wherever the evidence does not check out."""
    records = []
    for p in data["projects"]:
        page = p["page"] if 1 <= p["page"] <= len(pages) else None
        page_text = _normalize(pages[page - 1]) if page else ""
        conf = {k: max(0.0, min(1.0, v)) for k, v in p["confidence"].items()}

        def found(snippet):
            return bool(snippet) and _normalize(snippet) in page_text

        record = ProjectRecord(p["project_id"], data["utility"], document, extractor="claude")
        quote_ok = found(p["source_quote"])
        if not quote_ok:
            record.issues.append("Claude's source quote was not found on the cited page")
            conf = {k: min(v, CONF_UNVERIFIED) for k, v in conf.items()}

        if p["location_text"] and not found(p["location_text"]):
            conf["location_text"] = min(conf["location_text"], CONF_UNVERIFIED)

        window = parse_window(p["schedule_text"]) if p["schedule_text"] else None
        if p["schedule_text"] and not found(p["schedule_text"]):
            conf["construction_start"] = min(conf["construction_start"], CONF_UNVERIFIED)
            conf["construction_end"] = min(conf["construction_end"], CONF_UNVERIFIED)
        elif window:
            # Vague text ("2028", "Summer 2027") caps confidence no matter what Claude reported.
            conf["construction_start"] = min(conf["construction_start"], window[2])
            conf["construction_end"] = min(conf["construction_end"], window[2])

        start, end = _iso_or_none(p["construction_start"]), _iso_or_none(p["construction_end"])
        if start is None:
            conf["construction_start"] = 0.0
        if end is None:
            conf["construction_end"] = 0.0

        quote = p["source_quote"]
        record.fields = {
            "project_name": Field(p["project_name"], 0.95 if quote_ok else CONF_UNVERIFIED, quote, page),
            "project_type": Field(p["project_type"], conf["project_type"], quote, page),
            "voltage_kv": Field(p["voltage_kv"], conf["voltage_kv"], quote, page),
            "location_text": Field(p["location_text"], conf["location_text"], p["location_text"] or "", page),
            "start_date": Field(start, conf["construction_start"], p["schedule_text"] or "", page),
            "end_date": Field(end, conf["construction_end"], p["schedule_text"] or "", page),
            "status": Field((p["status"] or "").lower() or None, 0.9 if p["status"] else 0.0, quote, page),
        }
        records.append(record)
    return records


def extract(pages: list[str], document: str) -> tuple[list[ProjectRecord], dict]:
    text = "\n".join(f"=== Page {i} ===\n{page}" for i, page in enumerate(pages, start=1))
    data, stats = call_claude(text)
    return to_records(data, pages, document), stats
