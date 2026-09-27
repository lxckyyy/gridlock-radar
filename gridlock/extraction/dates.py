"""Turn schedule text like "Q2 2027 – Q3 2027" or "Summer 2027" into a date window with a confidence.

Vaguer text gets a wider window and a lower confidence, which is what sends it to review.
"""

from __future__ import annotations

import calendar
import re
from datetime import date

MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
MONTHS["sept"] = 9
MONTH_RE = r"\b(" +"|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?"
SEP = r"\s*(?:–|—|-|to|through|thru)\s*"
SEASONS = {"spring": (3, 5), "summer": (6, 8), "fall": (9, 11), "autumn": (9, 11), "winter": (12, 2)}

# Confidence by how precise the text is
CONF_MONTH_RANGE = 0.95
CONF_QUARTER_RANGE = 0.85
CONF_SINGLE_QUARTER = 0.75
CONF_SEASON = 0.70
CONF_YEAR_RANGE = 0.65
CONF_YEAR = 0.60
CONF_SINGLE_MONTH = 0.80


def month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _quarter(year: int, q: int) -> tuple[date, date]:
    return month_start(year, 3 * q - 2), month_end(year, 3 * q)


def parse_window(text: str) -> tuple[date, date, float] | None:
    """Return (start, end, confidence) or None when no schedule is found."""
    t = text.lower()

    m = re.search(MONTH_RE + r"\s+(\d{4})" + SEP + MONTH_RE + r"\s+(\d{4})", t)
    if m:
        start = month_start(int(m[2]), MONTHS[m[1]])
        end = month_end(int(m[4]), MONTHS[m[3]])
        return start, end, CONF_MONTH_RANGE

    m = re.search(r"q([1-4])\s*(\d{4})" + SEP + r"q([1-4])\s*(\d{4})", t)
    if m:
        return _quarter(int(m[2]), int(m[1]))[0], _quarter(int(m[4]), int(m[3]))[1], CONF_QUARTER_RANGE

    m = re.search(r"q([1-4])\s*(\d{4})", t)
    if m:
        start, end = _quarter(int(m[2]), int(m[1]))
        return start, end, CONF_SINGLE_QUARTER

    m = re.search(r"(spring|summer|fall|autumn|winter)\s+(\d{4})", t)
    if m:
        first, last = SEASONS[m[1]]
        year = int(m[2])
        end_year = year + 1 if last < first else year
        return month_start(year, first), month_end(end_year, last), CONF_SEASON

    m = re.search(MONTH_RE + r"\s+(\d{4})", t)
    if m:
        year, month = int(m[2]), MONTHS[m[1]]
        return month_start(year, month), month_end(year, month), CONF_SINGLE_MONTH

    m = re.search(r"\b(20\d{2})" + SEP + r"(20\d{2})\b", t)
    if m:
        return date(int(m[1]), 1, 1), date(int(m[2]), 12, 31), CONF_YEAR_RANGE

    m = re.search(r"\b(20\d{2})\b", t)
    if m:
        year = int(m[1])
        return date(year, 1, 1), date(year, 12, 31), CONF_YEAR

    return None
