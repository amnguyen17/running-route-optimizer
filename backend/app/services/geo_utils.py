"""Shared geospatial math utilities."""
from __future__ import annotations

import math

from app.config import get_settings

settings = get_settings()

METERS_PER_MILE = 1609.344
METERS_PER_FOOT = 0.3048
FEET_PER_METER = 1.0 / METERS_PER_FOOT


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two lat/lon points in meters, using the
    haversine formula. This is used both as the A* heuristic (must be an
    admissible, i.e. never-overestimating, lower bound on true path
    distance -- straight-line distance satisfies this) and for general
    "how far apart are these two points" calculations.
    """
    r = settings.earth_radius_m
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def meters_to_miles(m: float) -> float:
    return m / METERS_PER_MILE


def miles_to_meters(mi: float) -> float:
    return mi * METERS_PER_MILE


def meters_to_feet(m: float) -> float:
    return m * FEET_PER_METER


def feet_to_meters(ft: float) -> float:
    return ft * METERS_PER_FOOT
