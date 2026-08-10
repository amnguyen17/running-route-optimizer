"""Shared pytest fixtures. All fixtures here are synthetic (no live OSM or
elevation API calls), per the project's testing requirements."""
from __future__ import annotations

import networkx as nx
import pytest

from app.services.routing.graph_prep import prepare_graph


@pytest.fixture
def simple_graph() -> nx.Graph:
    """
    A small 6-node graph shaped like a 2x3 grid, flat (no elevation),
    with two parallel-ish routes from A to F so shortest-path choice is
    meaningful.

        A --100-- B --100-- C
        |150      |150      |150
        D --100-- E --100-- F
    """
    g = nx.Graph()
    coords = {
        "A": (37.000, -80.000),
        "B": (37.001, -80.000),
        "C": (37.002, -80.000),
        "D": (37.000, -80.001),
        "E": (37.001, -80.001),
        "F": (37.002, -80.001),
    }
    for n, (lat, lon) in coords.items():
        g.add_node(n, latitude=lat, longitude=lon, elevation_m=0.0)

    edges = [
        ("A", "B", 100),
        ("B", "C", 100),
        ("A", "D", 150),
        ("B", "E", 150),
        ("C", "F", 150),
        ("D", "E", 100),
        ("E", "F", 100),
    ]
    for u, v, d in edges:
        g.add_edge(u, v, distance_m=d, elevation_gain_m=0.0, elevation_loss_m=0.0)

    prepare_graph(g)
    return g


@pytest.fixture
def hilly_graph() -> nx.Graph:
    """Two-node graph with a significant elevation gain on the only edge,
    used for elevation-gain/difficulty calculations."""
    g = nx.Graph()
    g.add_node("A", latitude=37.000, longitude=-80.000, elevation_m=100.0)
    g.add_node("B", latitude=37.002, longitude=-80.000, elevation_m=160.0)
    g.add_edge(
        "A", "B",
        distance_m=300.0,
        elevation_gain_m=60.0,
        elevation_loss_m=0.0,
    )
    prepare_graph(g)
    return g


@pytest.fixture
def disconnected_graph() -> nx.Graph:
    """Two separate components: {A, B} and {Z}."""
    g = nx.Graph()
    g.add_node("A", latitude=37.000, longitude=-80.000, elevation_m=0.0)
    g.add_node("B", latitude=37.001, longitude=-80.000, elevation_m=0.0)
    g.add_node("Z", latitude=38.000, longitude=-81.000, elevation_m=0.0)
    g.add_edge("A", "B", distance_m=100.0, elevation_gain_m=0.0, elevation_loss_m=0.0)
    prepare_graph(g)
    return g


@pytest.fixture
def grid_graph() -> nx.Graph:
    """
    A 9x9 lat/lon grid (~80m spacing) large enough to support loop-route
    generation tests without hitting a live OSM service. Flat elevation.
    """
    g = nx.Graph()
    size = 9
    spacing_deg = 0.0007  # ~78m at these latitudes

    def node_id(i, j):
        return f"{i}_{j}"

    for i in range(size):
        for j in range(size):
            lat = 37.000 + i * spacing_deg
            lon = -80.000 + j * spacing_deg
            g.add_node(node_id(i, j), latitude=lat, longitude=lon, elevation_m=0.0)

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
