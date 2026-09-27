"""Find where two utilities' approved projects overlap.

Geographic overlap is the primary signal: the closest points of the two project shapes are
within config.MAX_OVERLAP_KM. Pairs are ranked by distance tier (touching first), then by
whether their build windows overlap (the secondary signal), then by exact distance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from itertools import combinations

from .. import config
from ..models import ProjectRecord
from .geometry import closest_points

COMPARABLE_STATUSES = {"auto_approved", "approved", "public_screening"}


@dataclass
class Overlap:
    a: ProjectRecord
    b: ProjectRecord
    distance_km: float
    point_a: tuple[float, float]  # closest point on a (lat, lon)
    point_b: tuple[float, float]  # closest point on b (lat, lon)
    tier: int  # index into config.GEO_TIERS, 0 = closest
    overlap_days: int | None  # None = unpublished dates; 0 = known dates with no overlap

    @property
    def tier_label(self) -> str:
        return config.GEO_TIERS[self.tier][1]

    @property
    def action(self) -> str:
        return config.GEO_TIERS[self.tier][2]

    @property
    def same_window(self) -> bool:
        return self.overlap_days is not None and self.overlap_days > 0

    @property
    def rank_key(self) -> tuple:
        temporal_rank = 0 if self.same_window else (1 if self.overlap_days is None else 2)
        return (self.tier, temporal_rank, self.distance_km)


def geo_tier(distance_km: float) -> int | None:
    """Index of the closest tier the distance falls in, or None if beyond every tier."""
    for i, (limit, _, _) in enumerate(config.GEO_TIERS):
        if distance_km <= limit:
            return i
    return None


def window_overlap_days(a_start: date, a_end: date, b_start: date, b_end: date) -> int:
    """Days two build windows share, after padding each side of A by the configured buffer."""
    buffer = timedelta(days=config.TIME_BUFFER_DAYS)
    lo, hi = max(a_start - buffer, b_start), min(a_end + buffer, b_end)
    return max(0, (hi - lo).days + 1)


def _dates(r: ProjectRecord) -> tuple[date | None, date | None]:
    start, end = r.value("start_date"), r.value("end_date")
    return (date.fromisoformat(start) if start else None, date.fromisoformat(end) if end else None)


def _usable(r: ProjectRecord) -> bool:
    # Geographic screening can still be useful when a public source omits its schedule.
    return r.status in COMPARABLE_STATUSES and bool(r.geometry)


def compare(a: ProjectRecord, b: ProjectRecord, max_km: float = config.MAX_OVERLAP_KM) -> Overlap | None:
    distance, pa, pb = closest_points(a.geometry, b.geometry)
    tier = geo_tier(distance)
    if tier is None or distance > max_km:
        return None
    a_start, a_end = _dates(a)
    b_start, b_end = _dates(b)
    dates_complete = all((a_start, a_end, b_start, b_end))
    overlap_days = window_overlap_days(a_start, a_end, b_start, b_end) if dates_complete else None
    return Overlap(a, b, distance, pa, pb, tier, overlap_days)


def find_overlaps(records: list[ProjectRecord], max_km: float = config.MAX_OVERLAP_KM,
                  same_window_only: bool = False) -> list[Overlap]:
    """Every comparable cross-utility pair within max_km, best ranked first."""
    by_utility: dict[str, list[ProjectRecord]] = {}
    for r in records:
        if _usable(r):
            by_utility.setdefault(r.utility, []).append(r)

    found = []
    for ua, ub in combinations(sorted(by_utility), 2):
        for a in by_utility[ua]:
            for b in by_utility[ub]:
                o = compare(a, b, max_km)
                if o and (o.same_window or not same_window_only):
                    found.append(o)
    return sorted(found, key=lambda o: o.rank_key)
