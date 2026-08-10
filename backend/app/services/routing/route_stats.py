"""Compute route statistics from an ordered node path over the graph."""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from app.config import get_settings
from app.services.geo_utils import meters_to_feet, meters_to_miles

settings = get_settings()


@dataclass
class RouteStats:
    distance_miles: float
    elevation_gain_ft: float
    elevation_loss_ft: float
    estimated_time_minutes: float
    average_pace_min_per_mile: float
    difficulty: float


def compute_route_stats(graph: nx.Graph, node_path: list) -> RouteStats:
    if len(node_path) < 2:
        return RouteStats(
            distance_miles=0.0,
            elevation_gain_ft=0.0,
            elevation_loss_ft=0.0,
            estimated_time_minutes=0.0,
            average_pace_min_per_mile=settings.default_pace_min_per_mile,
            difficulty=0.0,
        )

    total_distance_m = 0.0
    total_gain_m = 0.0
    total_loss_m = 0.0

    for u, v in zip(node_path[:-1], node_path[1:]):
        edge = graph.edges[u, v]
        total_distance_m += edge["distance_m"]
        total_gain_m += edge.get("elevation_gain_m", 0.0)
        total_loss_m += edge.get("elevation_loss_m", 0.0)

    distance_miles = meters_to_miles(total_distance_m)
    elevation_gain_ft = meters_to_feet(total_gain_m)
    elevation_loss_ft = meters_to_feet(total_loss_m)

    # Estimated time: configurable flat pace + a linear penalty for
    # elevation gain. This is explicitly a non-personalized estimate
    # (see README "Limitations") using settings.default_pace_min_per_mile.
    base_time = distance_miles * settings.default_pace_min_per_mile
    elevation_time_penalty = (
        elevation_gain_ft / 100.0
    ) * settings.elevation_time_penalty_min_per_100ft
    estimated_time_minutes = base_time + elevation_time_penalty

    average_pace_min_per_mile = (
        estimated_time_minutes / distance_miles if distance_miles > 0 else settings.default_pace_min_per_mile
    )

    difficulty = _compute_difficulty(distance_miles, elevation_gain_ft)

    return RouteStats(
        distance_miles=round(distance_miles, 3),
        elevation_gain_ft=round(elevation_gain_ft, 1),
        elevation_loss_ft=round(elevation_loss_ft, 1),
        estimated_time_minutes=round(estimated_time_minutes, 1),
        average_pace_min_per_mile=round(average_pace_min_per_mile, 2),
        difficulty=round(difficulty, 3),
    )


def _compute_difficulty(distance_miles: float, elevation_gain_ft: float) -> float:
    """
    Simple, documented difficulty heuristic: elevation gain per mile,
    normalized against `difficulty_normalization_ft_per_mile` and clamped
    to [0, 1]. 0 = flat, 1 = at-or-above the normalization threshold.

    This is intentionally simple (not personalized fitness modeling) --
    see README "Limitations".
    """
    if distance_miles <= 0:
        return 0.0
    gain_per_mile = elevation_gain_ft / distance_miles
    return max(0.0, min(1.0, gain_per_mile / settings.difficulty_normalization_ft_per_mile))
