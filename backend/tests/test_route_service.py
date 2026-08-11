"""Covers route_service orchestration behavior that spans multiple
layers: elevation.py raises ElevationUnavailableError when the API can't
be reached, and route generation must still succeed -- just with
elevation_available=False and zeroed elevation stats -- rather than
failing the whole request. Also covers that a request's pace_min_per_mile
actually reaches the final estimated_time_minutes end to end."""
from __future__ import annotations

import networkx as nx
import pytest

import app.services.route_service as route_service_module
from app.models.route import Algorithm, RouteRequest, RouteType
from app.services.ingestion.elevation import ElevationUnavailableError
from app.services.routing.graph_prep import prepare_graph


def _grid_graph(elevation_m) -> nx.Graph:
    """A 9x9 grid graph like conftest's `grid_graph`, but with a
    parameterized node elevation so tests can simulate an
    un-annotated (elevation_m=None, as OSM ingestion leaves it) graph."""
    g = nx.Graph()
    size = 9
    spacing_deg = 0.0007

    def node_id(i, j):
        return f"{i}_{j}"

    for i in range(size):
        for j in range(size):
            g.add_node(
                node_id(i, j),
                latitude=37.000 + i * spacing_deg,
                longitude=-80.000 + j * spacing_deg,
                elevation_m=elevation_m,
            )

    for i in range(size):
        for j in range(size):
            if i + 1 < size:
                g.add_edge(
                    node_id(i, j), node_id(i + 1, j),
                    distance_m=78.0, elevation_gain_m=0.0, elevation_loss_m=0.0,
                )
            if j + 1 < size:
                g.add_edge(
                    node_id(i, j), node_id(i, j + 1),
                    distance_m=78.0, elevation_gain_m=0.0, elevation_loss_m=0.0,
                )

    prepare_graph(g)
    return g


def _make_request(**overrides) -> RouteRequest:
    defaults = dict(
        latitude=37.0028,
        longitude=-80.0028,
        target_distance_miles=0.5,
        desired_elevation_gain_ft=50,
        route_type=RouteType.loop,
        algorithm=Algorithm.astar,
    )
    defaults.update(overrides)
    return RouteRequest(**defaults)


def test_generate_route_continues_without_elevation_when_api_unavailable(monkeypatch):
    graph = _grid_graph(elevation_m=None)  # as OSM ingestion leaves an un-annotated graph
    monkeypatch.setattr(route_service_module, "get_or_download_graph", lambda lat, lon, radius: graph)

    def _raise_unavailable(g, client=None):
        raise ElevationUnavailableError("simulated Open-Elevation outage")

    monkeypatch.setattr(route_service_module, "annotate_graph_with_elevation", _raise_unavailable)

    result = route_service_module.generate_route(_make_request())

    assert result.elevation_available is False
    assert result.elevation_gain_ft == 0.0
    assert result.elevation_loss_ft == 0.0
    assert result.distance_miles > 0  # route generation itself still worked


def test_generate_route_reports_elevation_available_on_success(monkeypatch):
    graph = _grid_graph(elevation_m=0.0)  # already annotated -- as if from a warm graph cache
    monkeypatch.setattr(route_service_module, "get_or_download_graph", lambda lat, lon, radius: graph)

    def _fail_if_called(g, client=None):
        pytest.fail("annotate_graph_with_elevation should not be called when the graph already has elevation")

    monkeypatch.setattr(route_service_module, "annotate_graph_with_elevation", _fail_if_called)

    result = route_service_module.generate_route(_make_request())

    assert result.elevation_available is True


def test_generate_route_personalizes_estimated_time_to_requested_pace(monkeypatch):
    graph = _grid_graph(elevation_m=0.0)  # flat, so no elevation time penalty to account for
    monkeypatch.setattr(route_service_module, "get_or_download_graph", lambda lat, lon, radius: graph)

    fast = route_service_module.generate_route(_make_request(pace_min_per_mile=6.0))
    slow = route_service_module.generate_route(_make_request(pace_min_per_mile=15.0))

    assert slow.estimated_time_minutes > fast.estimated_time_minutes
    assert abs(fast.estimated_time_minutes - fast.distance_miles * 6.0) < 0.1
    assert abs(slow.estimated_time_minutes - slow.distance_miles * 15.0) < 0.1


def test_generate_route_falls_back_to_default_pace_when_unspecified(monkeypatch):
    from app.config import get_settings

    graph = _grid_graph(elevation_m=0.0)
    monkeypatch.setattr(route_service_module, "get_or_download_graph", lambda lat, lon, radius: graph)

    result = route_service_module.generate_route(_make_request())  # no pace_min_per_mile

    settings = get_settings()
    assert abs(result.estimated_time_minutes - result.distance_miles * settings.default_pace_min_per_mile) < 0.1