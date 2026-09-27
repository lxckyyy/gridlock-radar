"""SQLite storage for documents, project records and the human review audit log."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .. import config
from ..models import ProjectRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    document TEXT PRIMARY KEY, utility TEXT, extractor TEXT, projects INTEGER,
    cost_usd REAL, latency_ms REAL, input_tokens INTEGER, output_tokens INTEGER
);
CREATE TABLE IF NOT EXISTS projects (
    utility TEXT, project_id TEXT, status TEXT, data TEXT,
    PRIMARY KEY (utility, project_id)
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, reviewer TEXT, utility TEXT,
    project_id TEXT, action TEXT, field TEXT, old_value TEXT, new_value TEXT
);
"""


@contextmanager
def connect(path=None):
    conn = sqlite3.connect(path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def reset(path=None) -> None:
    with connect(path) as conn:
        conn.executescript("DELETE FROM documents; DELETE FROM projects; DELETE FROM reviews;")


def save_document(document: str, utility: str, extractor: str, projects: int, stats: dict, path=None) -> None:
    with connect(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (document, utility, extractor, projects, stats.get("cost_usd", 0.0), stats.get("latency_ms", 0.0),
             stats.get("input_tokens", 0), stats.get("output_tokens", 0)),
        )


def save_record(record: ProjectRecord, path=None) -> None:
    with connect(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO projects VALUES (?, ?, ?, ?)",
            (record.utility, record.project_id, record.status, record.to_json()),
        )


def load_records(status: str | None = None, path=None) -> list[ProjectRecord]:
    with connect(path) as conn:
        if status:
            rows = conn.execute("SELECT data FROM projects WHERE status = ? ORDER BY utility, project_id", (status,))
        else:
            rows = conn.execute("SELECT data FROM projects ORDER BY utility, project_id")
        return [ProjectRecord.from_json(r["data"]) for r in rows]


def load_documents(path=None) -> list[dict]:
    with connect(path) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM documents ORDER BY document")]


def log_review(record: ProjectRecord, action: str, reviewer: str, changes: dict | None = None, path=None) -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = [(ts, reviewer, record.utility, record.project_id, action, f, str(old), str(new))
            for f, (old, new) in (changes or {}).items()]
    rows = rows or [(ts, reviewer, record.utility, record.project_id, action, None, None, None)]
    with connect(path) as conn:
        conn.executemany(
            "INSERT INTO reviews (ts, reviewer, utility, project_id, action, field, old_value, new_value)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )


def load_reviews(path=None) -> list[dict]:
    with connect(path) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM reviews ORDER BY id DESC")]
