"""Tunable settings for the whole pipeline. Change numbers here, not in the modules."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PLANS_DIR = DATA_DIR / "plans"
LABELS_PATH = DATA_DIR / "labels.csv"
SUBSTATIONS_PATH = DATA_DIR / "substations.csv"
COUNTIES_PATH = DATA_DIR / "counties.csv"
DB_PATH = Path(os.environ.get("GRIDLOCK_DB", ROOT / "gridlock.db"))

# Routing: a record skips review only if every critical field reaches this confidence.
CONFIDENCE_THRESHOLD = 0.85
CRITICAL_FIELDS = ("geometry", "start_date", "end_date", "project_type")

# Geographic overlap is the primary signal. Two projects overlap when the CLOSEST points of
# their shapes are within MAX_OVERLAP_KM (about how far a crew drives from one staging yard).
# Tiers, closest first: (upper bound in km, label, what the two utilities can share).
MAX_OVERLAP_KM = 40.0
GEO_TIERS = (
    (0.1, "Touching / crossing", "Must coordinate outage timing and crossing structures"),
    (1.6, "Under 1.6 km", "Share the land itself: right-of-way, access roads, permits"),
    (8.0, "Under 8 km", "Share site logistics: laydown yards, deliveries"),
    (40.0, "Under 40 km", "Share crews, cranes and contractors"),
)
# Timeline overlap is the secondary signal: build windows that overlap. Optional padding in days.
TIME_BUFFER_DAYS = 0

# Sanity checks:
STANDARD_KV = {69, 115, 138, 161, 230, 345, 500, 765}
PLAN_YEARS = (2025, 2040)
# Contiguous U.S. screening bounds. Sources may cover a narrower utility territory.
SERVICE_BBOX = {"lat": (24.0, 50.0), "lon": (-126.0, -66.0)}

# Claude extraction
CLAUDE_MODEL = os.environ.get("GRIDLOCK_MODEL", "claude-opus-5")
CLAUDE_EFFORT = os.environ.get("GRIDLOCK_EFFORT", "medium")
# USD per million tokens (input, output)
MODEL_PRICES = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# Evaluation tolerances
EVAL_KM = 5.0
EVAL_DAYS = 31
