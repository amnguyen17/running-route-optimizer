"""
OpenStreetMap ingestion via OSMnx.

Downloads a pedestrian/running network around a point, converts it to a
plain networkx.Graph with the attributes the rest of the system needs
(distance, elevation, elevation_gain, elevation_loss per edge), and
caches the result to disk so repeated requests for the same area do not
re-hit the OSM/Overpass API.

Caching strategy (documented per project requirement):
- Cache key = rounded (lat, lon, radius) tuple -> deterministic filename.
- On a cache hit whose cached radius covers the requested radius
  (+ a safety margin, `cache_coverage_margin_m`), the cached graph is
  reused unmodified.
- On a miss, OSMnx downloads a fresh graph, elevation is attached, and
  the result is pickled to `graph_cache_dir`.
- This is a simple file-based cache appropriate for a single-instance
  portfolio MVP; see README "Limitations" for how this would need to
  change for multi-instance production use (e.g. shared cache / DB-backed
  spatial index instead of local pickles).
"""
from __future__ import annotations

import hashlib
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from app.config import get_settings
from app.services.geo_utils import haversine_distance_m

logger = logging.getLogger(__name__)
settings = get_settings()


class OSMIngestionError(Exception):
    """Raised when OSM data cannot be downloaded or processed."""


@dataclass
class CacheEntry:
    center_lat: float
    center_lon: float
    radius_m: float
    path: Path


def _cache_dir() -> Path:
    d = Path(settings.graph_cache_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(lat: float, lon: float, radius_m: float) -> str:
    # Round to ~11m precision (4 decimal degrees) so nearby-but-identical
    # requests hit the same cache entry.
    raw = f"{round(lat, 4)}:{round(lon, 4)}:{round(radius_m)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _index_path() -> Path:
    return _cache_dir() / "index.pkl"


def _load_index() -> list[CacheEntry]:
    idx_path = _index_path()
    if not idx_path.exists():
        return []
    with open(idx_path, "rb") as f:
        return pickle.load(f)


def _save_index(entries: list[CacheEntry]) -> None:
    with open(_index_path(), "wb") as f:
        pickle.dump(entries, f)


def _find_covering_cache_entry(lat: float, lon: float, radius_m: float) -> CacheEntry | None:
    """Return a cached entry whose downloaded area fully covers the
    requested (lat, lon, radius) circle, if one exists."""
    needed = radius_m + settings.cache_coverage_margin_m
    for entry in _load_index():
        dist_between_centers = haversine_distance_m(lat, lon, entry.center_lat, entry.center_lon)
        # The cached circle covers the requested circle if the requested
        # circle (expanded by the safety margin) fits entirely within the
        # cached circle.
        if dist_between_centers + needed <= entry.radius_m:
            if entry.path.exists():
                return entry
    return None


def get_or_download_graph(
    latitude: float, longitude: float, radius_m: float
) -> nx.Graph:
    """
    Return a networkx.Graph covering the requested area, using the local
    cache when possible and falling back to an OSMnx download otherwise.

    Raises OSMIngestionError if the network cannot be downloaded and no
    usable cache entry exists.
    """
    cached = _find_covering_cache_entry(latitude, longitude, radius_m)
    if cached is not None:
        logger.info("Graph cache hit for (%s, %s, %sm)", latitude, longitude, radius_m)
        with open(cached.path, "rb") as f:
            return pickle.load(f)

    logger.info("Graph cache miss for (%s, %s, %sm); downloading from OSM", latitude, longitude, radius_m)
    graph = _download_graph(latitude, longitude, radius_m)

    key = _cache_key(latitude, longitude, radius_m)
    path = _cache_dir() / f"{key}.pkl"
    with open(path, "wb") as f:
        pickle.dump(graph, f)

    entries = _load_index()
    entries.append(CacheEntry(center_lat=latitude, center_lon=longitude, radius_m=radius_m, path=path))
    _save_index(entries)

    return graph


def _download_graph(latitude: float, longitude: float, radius_m: float) -> nx.Graph:
    try:
        import osmnx as ox
    except ImportError as exc:  # pragma: no cover - environment issue, not logic
        raise OSMIngestionError(
            "osmnx is not installed. Install backend requirements.txt to enable OSM ingestion."
        ) from exc

    try:
        multidigraph = ox.graph_from_point(
            (latitude, longitude),
            dist=radius_m,
            network_type=settings.osm_network_type,
            simplify=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise OSMIngestionError(
            f"Failed to download OSM network around ({latitude}, {longitude}), "
            f"radius={radius_m}m: {exc}"
        ) from exc

    return _convert_to_processing_graph(multidigraph)


def _convert_to_processing_graph(multidigraph) -> nx.Graph:
    """
    Convert an OSMnx MultiDiGraph into a plain undirected networkx.Graph
    with one edge per node pair, carrying the attributes the rest of the
    system needs. Parallel edges (multiple OSM ways between the same two
    nodes) are collapsed by keeping the shortest one, since for a running
    route the shortest connecting segment is the relevant one and keeping
    duplicates would only complicate the shortest-path algorithms without
    benefit.
    """
    import osmnx as ox

    graph = nx.Graph()

    for node_id, data in multidigraph.nodes(data=True):
        graph.add_node(
            node_id,
            latitude=data.get("y"),
            longitude=data.get("x"),
            elevation_m=None,  # filled in by the elevation service
        )

    for u, v, data in multidigraph.edges(data=True):
        length_m = data.get("length")
        if length_m is None:
            # Should not normally happen with osmnx-simplified graphs, but
            # guard against malformed data rather than silently using 0.
            length_m = haversine_distance_m(
                graph.nodes[u]["latitude"],
                graph.nodes[u]["longitude"],
                graph.nodes[v]["latitude"],
                graph.nodes[v]["longitude"],
            )

        highway = data.get("highway")
        name = data.get("name")

        if graph.has_edge(u, v):
            if length_m < graph.edges[u, v]["distance_m"]:
                graph.edges[u, v]["distance_m"] = length_m
                graph.edges[u, v]["highway"] = highway
                graph.edges[u, v]["name"] = name
        else:
            graph.add_edge(
                u,
                v,
                distance_m=length_m,
                highway=highway,
                name=name,
                elevation_gain_m=0.0,
                elevation_loss_m=0.0,
            )

    return graph
