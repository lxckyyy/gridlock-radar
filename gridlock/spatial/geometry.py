"""Project shapes and closest-point distances.

A project's geometry is stored as GeoJSON-style dicts in lon/lat order:
    {"type": "Point", "coordinates": [lon, lat]}
    {"type": "LineString", "coordinates": [[lon, lat], [lon, lat], ...]}

Distances are measured between the CLOSEST points of two shapes, never their centers,
after projecting to the local UTM zone so that units are meters. (Degrees of longitude
shrink toward the poles, so measuring in raw lon/lat would be wrong.)
"""

from __future__ import annotations

from functools import lru_cache

from pyproj import Transformer
from shapely.geometry import LineString, shape
from shapely.ops import nearest_points, transform


def point(lat: float, lon: float) -> dict:
    return {"type": "Point", "coordinates": [lon, lat]}


def line(latlons: list[tuple[float, float]]) -> dict:
    return {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in latlons]}


def to_shape(geom: dict):
    return shape(geom)


def representative_latlon(geom: dict) -> tuple[float, float]:
    """A single (lat, lon) for map markers and labels: the midpoint of a line, or the point itself."""
    s = to_shape(geom)
    p = s.interpolate(0.5, normalized=True) if isinstance(s, LineString) else s.centroid
    return p.y, p.x


def latlon_path(geom: dict) -> tuple[list[float], list[float]]:
    """(lats, lons) of every vertex, for drawing."""
    s = to_shape(geom)
    coords = list(s.coords)
    return [c[1] for c in coords], [c[0] for c in coords]


@lru_cache(maxsize=64)
def _transformers(zone: int, north: bool) -> tuple[Transformer, Transformer]:
    epsg = (32600 if north else 32700) + zone
    fwd = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    inv = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    return fwd, inv


def _local_utm(a, b) -> tuple[Transformer, Transformer]:
    """Pick the UTM zone at the midpoint of the two shapes."""
    mid = LineString([a.centroid, b.centroid]).centroid
    zone = min(60, int((mid.x + 180) // 6) + 1)
    return _transformers(zone, mid.y >= 0)


def closest_points(a_geom: dict, b_geom: dict) -> tuple[float, tuple[float, float], tuple[float, float]]:
    """Return (distance_km, closest point on a as (lat, lon), closest point on b as (lat, lon))."""
    a, b = to_shape(a_geom), to_shape(b_geom)
    fwd, inv = _local_utm(a, b)
    pa, pb = nearest_points(transform(fwd.transform, a), transform(fwd.transform, b))
    distance_km = pa.distance(pb) / 1000
    (ax, ay), (bx, by) = inv.transform(pa.x, pa.y), inv.transform(pb.x, pb.y)
    return distance_km, (ay, ax), (by, bx)


def distance_km(a_geom: dict, b_geom: dict) -> float:
    return closest_points(a_geom, b_geom)[0]

