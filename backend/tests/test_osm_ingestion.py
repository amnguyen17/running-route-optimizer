"""
Tests for app.services.ingestion.osm_graph.

These tests mock osmnx.graph_from_point so the suite never contacts the
live Overpass/OSM API, per the project's testing requirements.
"""
from __future__ import annotations

import networkx as nx
import pytest

import app.services.ingestion.osm_graph as osm_graph_module
from app.services.ingestion.osm_graph import (
    OSMIngestionError,
    _convert_to_processing_graph,
    get_or_download_graph,
)


def _make_fake_multidigraph():
    """A minimal MultiDiGraph shaped like what osmnx.graph_from_point returns."""
    g = nx.MultiDiGraph()
    g.add_node(1, y=37.000, x=-80.000)
    g.add_node(2, y=37.001, x=-80.000)
    g.add_node(3, y=37.002, x=-80.000)
    # Two parallel edges between 1 and 2 (simulating duplicate OSM ways) --
    # the shorter one should win.
    g.add_edge(1, 2, key=0, length=120.0, highway="footway", name="Path A")
    g.add_edge(1, 2, key=1, length=100.0, highway="footway", name="Path A Alt")
    g.add_edge(2, 3, key=0, length=90.0, highway="path", name=None)
    return g


def test_convert_to_processing_graph_collapses_parallel_edges():
    fake = _make_fake_multidigraph()
    result = _convert_to_processing_graph(fake)

    assert isinstance(result, nx.Graph)
    assert result.number_of_nodes() == 3
    # The shorter parallel edge (100m) should be kept, not 120m.
    assert result.edges[1, 2]["distance_m"] == 100.0
    assert result.edges[2, 3]["distance_m"] == 90.0


def test_convert_to_processing_graph_preserves_node_coordinates():
    fake = _make_fake_multidigraph()
    result = _convert_to_processing_graph(fake)
    assert result.nodes[1]["latitude"] == 37.000
    assert result.nodes[1]["longitude"] == -80.000


def test_get_or_download_graph_downloads_on_cache_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(
        osm_graph_module.get_settings(), "graph_cache_dir", str(tmp_path), raising=False
    )
    # Redirect the module-level settings used inside osm_graph_module too.
    osm_graph_module.settings.graph_cache_dir = str(tmp_path)

    call_count = {"n": 0}

    def fake_download(lat, lon, radius_m):
        call_count["n"] += 1
        g = nx.Graph()
        g.add_node("x", latitude=lat, longitude=lon, elevation_m=None)
        return g

    monkeypatch.setattr(osm_graph_module, "_download_graph", fake_download)

    graph1 = get_or_download_graph(37.0, -80.0, 500)
    assert call_count["n"] == 1
    assert graph1.number_of_nodes() == 1


def test_get_or_download_graph_reuses_cache_on_covering_hit(tmp_path, monkeypatch):
    osm_graph_module.settings.graph_cache_dir = str(tmp_path)

    call_count = {"n": 0}

    def fake_download(lat, lon, radius_m):
        call_count["n"] += 1
        g = nx.Graph()
        g.add_node("x", latitude=lat, longitude=lon, elevation_m=None)
        return g

    monkeypatch.setattr(osm_graph_module, "_download_graph", fake_download)

    # First call downloads a graph covering a 1000m radius.
    get_or_download_graph(37.0, -80.0, 1000)
    assert call_count["n"] == 1

    # A second call for the same point with a smaller radius should reuse
    # the cache, not download again.
    get_or_download_graph(37.0, -80.0, 400)
    assert call_count["n"] == 1


def test_download_graph_raises_ingestion_error_on_failure(monkeypatch):
    import sys
    import types

    fake_osmnx = types.ModuleType("osmnx")

    def failing_graph_from_point(*args, **kwargs):
        raise RuntimeError("simulated Overpass timeout")

    fake_osmnx.graph_from_point = failing_graph_from_point
    monkeypatch.setitem(sys.modules, "osmnx", fake_osmnx)

    with pytest.raises(OSMIngestionError):
        osm_graph_module._download_graph(37.0, -80.0, 500)
