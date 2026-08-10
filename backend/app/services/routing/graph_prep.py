"""
Graph preprocessing.

Turns the raw ingested graph (distance + elevation per edge) into a
routing-ready graph where every edge has a `weight` attribute: the cost
used by Dijkstra/A*.

weight = distance_m + elevation_penalty_m

where elevation_penalty_m is a small, non-negative penalty proportional
to the edge's elevation gain. This keeps `weight` >= `distance_m`
always, which is required for the A* haversine heuristic to remain
admissible (see algorithms.py docstring).

This module is intentionally the *only* place edge weight is computed,
so the routing algorithms stay agnostic to what "cost" means.
"""
from __future__ import annotations

import networkx as nx

# Meters of penalty added to an edge's weight per meter of elevation
# gain on that edge. A small, documented constant (not buried inline in
# the algorithm code) reflecting that climbing is modestly "costlier"
# than flat distance for routing purposes, while keeping weight >=
# distance_m so the A* heuristic stays admissible.
ELEVATION_PENALTY_FACTOR = 1.5


def prepare_graph(graph: nx.Graph) -> nx.Graph:
    """Mutates and returns `graph`, adding a `weight` attribute to every edge."""
    for _, _, data in graph.edges(data=True):
        distance_m = data["distance_m"]
        elevation_gain_m = data.get("elevation_gain_m", 0.0)
        data["weight"] = distance_m + ELEVATION_PENALTY_FACTOR * elevation_gain_m
    return graph
