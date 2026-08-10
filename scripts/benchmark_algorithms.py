"""
Benchmark: Dijkstra vs A* on synthetic grid graphs of increasing size.

Run with:
    cd backend && python ../scripts/benchmark_algorithms.py

This does not depend on any live OSM/elevation service -- it builds
synthetic lat/lon grid graphs locally, matching the same fixtures used
in tests/test_astar.py, so results are fully reproducible.

Prints a table of: grid size, node count, path cost (should match
between algorithms), nodes expanded by each algorithm, and wall-clock
time. This script produces real measurements each time it's run; it is
not a source of pre-baked "performance numbers" for the README -- if you
want up-to-date numbers, run it yourself and paste the output.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import networkx as nx

from app.services.routing.algorithms import astar, dijkstra
from app.services.routing.graph_prep import prepare_graph


def build_grid_graph(size: int) -> nx.Graph:
    g = nx.Graph()
    spacing_deg = 0.0007

    def node_id(i, j):
        return f"{i}_{j}"

    for i in range(size):
        for j in range(size):
            g.add_node(
                node_id(i, j),
                latitude=37.000 + i * spacing_deg,
                longitude=-80.000 + j * spacing_deg,
                elevation_m=0.0,
            )

    for i in range(size):
        for j in range(size):
            if i + 1 < size:
                g.add_edge(node_id(i, j), node_id(i + 1, j), distance_m=78.0, elevation_gain_m=0.0, elevation_loss_m=0.0)
            if j + 1 < size:
                g.add_edge(node_id(i, j), node_id(i, j + 1), distance_m=78.0, elevation_gain_m=0.0, elevation_loss_m=0.0)

    prepare_graph(g)
    return g


def run_benchmark():
    sizes = [5, 9, 15, 25, 40]
    print(f"{'grid':>6} {'nodes':>7} {'cost':>10} {'dij_expanded':>13} {'astar_expanded':>15} {'dij_ms':>9} {'astar_ms':>10}")

    for size in sizes:
        g = build_grid_graph(size)
        source = "0_0"
        target = f"{size - 1}_{size - 1}"

        t0 = time.perf_counter()
        d_result = dijkstra(g, source, target)
        t1 = time.perf_counter()
        a_result = astar(g, source, target)
        t2 = time.perf_counter()

        assert d_result.total_cost == a_result.total_cost, "algorithms disagree on optimal cost!"

        print(
            f"{size:>6} {g.number_of_nodes():>7} {d_result.total_cost:>10.1f} "
            f"{d_result.nodes_expanded:>13} {a_result.nodes_expanded:>15} "
            f"{(t1 - t0) * 1000:>9.2f} {(t2 - t1) * 1000:>10.2f}"
        )


if __name__ == "__main__":
    run_benchmark()
