"""
Orchestrates the full pipeline described in the architecture diagram:

OpenStreetMap -> OSMnx ingestion -> geospatial graph -> preprocessing
-> Dijkstra/A* -> candidate generation -> scoring -> GeneratedRoute

This is the only module the API layer calls into for route generation,
keeping FastAPI route handlers thin (per project requirement to separate
API code from routing/optimization logic).
"""
from __future__ import annotations

import logging

import networkx as nx

from app.config import get_settings
from app.models.route import GeneratedRoute, RouteCoordinate, RouteRequest
from app.services.geo_utils import miles_to_meters
from app.services.ingestion.elevation import ElevationUnavailableError, annotate_graph_with_elevation
from app.services.ingestion.osm_graph import OSMIngestionError, get_or_download_graph
from app.services.optimization.loop_generator import NoValidRouteError, generate_best_route
from app.services.routing.graph_prep import prepare_graph

settings = get_settings()
logger = logging.getLogger(__name__)


class RouteGenerationError(Exception):
    """Wraps all recoverable failure modes into one type the API layer can
    translate into an HTTP error response."""


def generate_route(request: RouteRequest) -> GeneratedRoute:
    max_elevation_gain_ft = (
        request.max_elevation_gain_ft
        if request.max_elevation_gain_ft is not None
        else max(request.desired_elevation_gain_ft * 2.0, 100.0)
    )

    radius_m = (
        miles_to_meters(request.target_distance_miles) / 2.0
        + settings.default_network_radius_buffer_m
    )

    try:
        graph = get_or_download_graph(request.latitude, request.longitude, radius_m)
    except OSMIngestionError as exc:
        raise RouteGenerationError(f"Failed to obtain OpenStreetMap network data: {exc}") from exc

    if graph.number_of_nodes() == 0:
        raise RouteGenerationError(
            "No walkable OpenStreetMap network was found near this location."
        )

    elevation_available = _graph_has_elevation(graph)
    if not elevation_available:
        try:
            annotate_graph_with_elevation(graph)
            elevation_available = True
        except ElevationUnavailableError as exc:
            # Elevation is a nice-to-have, not a hard dependency: fall back
            # to the graph's zero-elevation defaults (set at ingestion
            # time) rather than failing route generation outright. The
            # response's `elevation_available=False` tells the caller
            # elevation/difficulty numbers are not meaningful this time.
            logger.warning(
                "Elevation data unavailable; generating route without it: %s", exc
            )

    prepare_graph(graph)

    try:
        best = generate_best_route(
            graph=graph,
            start_latitude=request.latitude,
            start_longitude=request.longitude,
            target_distance_miles=request.target_distance_miles,
            desired_elevation_gain_ft=request.desired_elevation_gain_ft,
            max_elevation_gain_ft=max_elevation_gain_ft,
            route_type=request.route_type,
            algorithm_name=request.algorithm.value,
        )
    except NoValidRouteError as exc:
        raise RouteGenerationError(str(exc)) from exc

    coordinates = [
        RouteCoordinate(
            latitude=graph.nodes[n]["latitude"],
            longitude=graph.nodes[n]["longitude"],
            elevation_m=graph.nodes[n].get("elevation_m"),
        )
        for n in best.node_path
    ]

    start = coordinates[0]
    end = coordinates[-1]

    return GeneratedRoute(
        route=coordinates,
        distance_miles=best.stats.distance_miles,
        elevation_gain_ft=best.stats.elevation_gain_ft,
        elevation_loss_ft=best.stats.elevation_loss_ft,
        estimated_time_minutes=best.stats.estimated_time_minutes,
        average_pace_min_per_mile=best.stats.average_pace_min_per_mile,
        difficulty=best.stats.difficulty,
        algorithm=request.algorithm.value,
        score=best.score_breakdown.score,
        start_latitude=start.latitude,
        start_longitude=start.longitude,
        end_latitude=end.latitude,
        end_longitude=end.longitude,
        elevation_available=elevation_available,
    )


def _graph_has_elevation(graph: nx.Graph) -> bool:
    if graph.number_of_nodes() == 0:
        return False
    _, sample = next(iter(graph.nodes(data=True)))
    return sample.get("elevation_m") is not None
