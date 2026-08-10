"""
Candidate route generation.

This deliberately does NOT attempt to solve the "find the loop with
exactly distance D and elevation gain E" problem optimally -- that is a
constrained variant of the traveling salesman / orienteering problem and
is not tractable to solve exactly for a portfolio MVP. Instead:

1. For `loop` routes: generate several candidate loops by picking two
   waypoints roughly 1/3 and 2/3 of the way around a circle whose
   circumference approximates the target distance, at angles spread
   around the compass, then connect start -> waypoint1 -> waypoint2 ->
   start using the chosen shortest-path algorithm for each leg. Varying
   the base angle across candidates produces geometrically different
   loops to choose from.

2. For `out_and_back` routes: pick a single turnaround point at roughly
   half the target distance along a candidate bearing, and generate the
   path there and back (there and back use the same shortest path, which
   is what "out and back" means).

Each candidate is then scored by app.services.optimization.scoring, and
the best-scoring candidate is returned.

Known limitation: because waypoints are chosen from idealized
circle geometry and then snapped to the nearest real graph node, actual
road networks can pull candidates significantly off the intended shape,
especially in sparse/rural areas. Increasing `num_candidate_routes` (see
config) improves the odds of finding a good match at the cost of more
computation. See README "Limitations" for more.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import networkx as nx

from app.config import get_settings
from app.models.route import RouteType
from app.services.geo_utils import haversine_distance_m, miles_to_meters
from app.services.optimization.scoring import ScoreBreakdown, score_candidate
from app.services.routing.algorithms import ALGORITHMS, NoPathError, PathResult
from app.services.routing.node_lookup import destination_point, nearest_node
from app.services.routing.route_stats import RouteStats, compute_route_stats

settings = get_settings()


class NoValidRouteError(Exception):
    """Raised when no candidate route could be generated at all (e.g. isolated graph)."""


@dataclass
class RouteCandidate:
    node_path: list
    stats: RouteStats
    score_breakdown: ScoreBreakdown
    loop_closure_distance_m: float


def generate_best_route(
    graph: nx.Graph,
    start_latitude: float,
    start_longitude: float,
    target_distance_miles: float,
    desired_elevation_gain_ft: float,
    max_elevation_gain_ft: float,
    route_type: RouteType,
    algorithm_name: str,
) -> RouteCandidate:
    algorithm = ALGORITHMS[algorithm_name]
    start_node = nearest_node(graph, start_latitude, start_longitude)

    candidates: list[RouteCandidate] = []
    n = settings.num_candidate_routes
    max_loop_closure_m = miles_to_meters(target_distance_miles) * settings.max_loop_closure_fraction

    for i in range(n):
        base_bearing = (360.0 / n) * i
        try:
            if route_type == RouteType.loop:
                candidate = _build_loop_candidate(
                    graph, start_node, base_bearing, target_distance_miles, algorithm
                )
            else:
                candidate = _build_out_and_back_candidate(
                    graph, start_node, base_bearing, target_distance_miles, algorithm
                )
        except NoPathError:
            continue

        if candidate is None:
            continue

        node_path, loop_closure_distance_m = candidate
        stats = compute_route_stats(graph, node_path)

        breakdown = score_candidate(
            actual_distance_miles=stats.distance_miles,
            target_distance_miles=target_distance_miles,
            actual_elevation_gain_ft=stats.elevation_gain_ft,
            desired_elevation_gain_ft=desired_elevation_gain_ft,
            max_elevation_gain_ft=max_elevation_gain_ft,
            difficulty=stats.difficulty,
            loop_closure_distance_m=loop_closure_distance_m,
            max_loop_closure_m=max_loop_closure_m,
            is_loop=(route_type == RouteType.loop),
        )

        candidates.append(
            RouteCandidate(
                node_path=node_path,
                stats=stats,
                score_breakdown=breakdown,
                loop_closure_distance_m=loop_closure_distance_m,
            )
        )

    if not candidates:
        raise NoValidRouteError(
            "Could not generate any candidate route for this location/distance combination. "
            "The road network here may be too sparse or disconnected for the requested distance."
        )

    candidates.sort(key=lambda c: c.score_breakdown.score)
    return candidates[0]


def _build_loop_candidate(
    graph: nx.Graph, start_node, base_bearing: float, target_distance_miles: float, algorithm
) -> tuple[list, float] | None:
    start_data = graph.nodes[start_node]

    # Aim for a rough loop circumference matching target distance: place
    # two waypoints ~1/3 and ~2/3 of the way around a circle whose
    # circumference approximates the target, at angles offset from
    # base_bearing so different candidates trace different loop shapes.
    circumference_m = miles_to_meters(target_distance_miles)
    radius_m = circumference_m / (2 * math.pi)

    bearing1 = base_bearing
    bearing2 = (base_bearing + 130) % 360  # roughly spreads the two waypoints apart

    wp1_lat, wp1_lon = destination_point(start_data["latitude"], start_data["longitude"], bearing1, radius_m)
    wp2_lat, wp2_lon = destination_point(start_data["latitude"], start_data["longitude"], bearing2, radius_m)

    wp1_node = nearest_node(graph, wp1_lat, wp1_lon)
    wp2_node = nearest_node(graph, wp2_lat, wp2_lon)

    if wp1_node == start_node or wp2_node == start_node or wp1_node == wp2_node:
        return None

    leg1 = algorithm(graph, start_node, wp1_node)
    leg2 = algorithm(graph, wp1_node, wp2_node)
    leg3 = algorithm(graph, wp2_node, start_node)

    node_path = _stitch_paths([leg1, leg2, leg3])

    end_data = graph.nodes[node_path[-1]]
    closure_distance_m = haversine_distance_m(
        start_data["latitude"], start_data["longitude"], end_data["latitude"], end_data["longitude"]
    )

    return node_path, closure_distance_m


def _build_out_and_back_candidate(
    graph: nx.Graph, start_node, base_bearing: float, target_distance_miles: float, algorithm
) -> tuple[list, float] | None:
    start_data = graph.nodes[start_node]

    half_distance_m = miles_to_meters(target_distance_miles) / 2.0
    turn_lat, turn_lon = destination_point(
        start_data["latitude"], start_data["longitude"], base_bearing, half_distance_m
    )
    turn_node = nearest_node(graph, turn_lat, turn_lon)

    if turn_node == start_node:
        return None

    outbound = algorithm(graph, start_node, turn_node)
    inbound = algorithm(graph, turn_node, start_node)

    node_path = _stitch_paths([outbound, inbound])
    # Out-and-back always closes exactly at the start node by construction.
    return node_path, 0.0


def _stitch_paths(legs: list[PathResult]) -> list:
    """Concatenate a sequence of PathResult node lists, dropping the
    duplicated junction node between consecutive legs."""
    full_path: list = []
    for leg in legs:
        if full_path and full_path[-1] == leg.nodes[0]:
            full_path.extend(leg.nodes[1:])
        else:
            full_path.extend(leg.nodes)
    return full_path
