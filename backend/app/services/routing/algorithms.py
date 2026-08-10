"""
Shortest-path algorithms implemented from scratch (not via
nx.shortest_path or any external routing API), per project requirements.

Both algorithms operate on a networkx.Graph where each edge has a
numeric `weight` attribute (set by graph_prep.prepare_graph) representing
the cost to traverse that edge, and each node has `latitude`/`longitude`
attributes.

Both return a `PathResult` with the same shape, so calling code (loop
generation, API layer) does not need to know which algorithm produced a
given path.

--------------------------------------------------------------------
Dijkstra's algorithm
--------------------------------------------------------------------
g(n): cost accumulated so far from the source to node n (exact, not
      estimated).
Explores nodes in increasing order of g(n) using a min-priority queue
(Python's `heapq`, a binary heap -- O(log n) push/pop).

Time complexity: O((V + E) log V) with a binary heap, since every edge
may trigger one decrease-key-equivalent push and every node is popped
at most once.

--------------------------------------------------------------------
A* algorithm
--------------------------------------------------------------------
g(n): same as Dijkstra -- exact cost so far from source to n.
h(n): admissible heuristic estimating the remaining cost from n to the
      goal. Here h(n) = haversine straight-line distance from n to the
      goal, converted to the same units as edge weight.
f(n) = g(n) + h(n): priority used to order the frontier.

Heuristic admissibility: because edge `weight` is always >= the edge's
physical distance (weight is distance plus a non-negative elevation
penalty -- see graph_prep.py), and haversine distance is the shortest
possible physical distance between two points, h(n) never overestimates
the true remaining cost. This guarantees A* still finds an optimal path
with respect to `weight`.

Why A* can be faster: Dijkstra explores outward from the source with no
sense of direction, potentially visiting many nodes that lead away from
the goal. A*'s h(n) term biases the frontier toward nodes that are
geographically closer to the goal, so in practice it expands far fewer
nodes before reaching the goal, especially over larger/sparser graphs.
Worst case (e.g. h(n) = 0 everywhere) it degrades to Dijkstra; a tighter,
still-admissible heuristic (like ours) can prune large portions of the
search space. See tests/test_benchmark.py for an empirical comparison on
synthetic graphs.

Time complexity: same asymptotic bound as Dijkstra, O((V + E) log V),
since the priority queue operations are the same; A*'s practical speedup
comes from visiting fewer nodes in practice, not from a better
asymptotic bound.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field

import networkx as nx

from app.services.geo_utils import haversine_distance_m


class NodeNotFoundError(Exception):
    """Raised when a requested source/target node does not exist in the graph."""


class NoPathError(Exception):
    """Raised when no path exists between source and target (disconnected graph)."""


@dataclass
class PathResult:
    nodes: list  # ordered list of node ids from source to target (inclusive)
    total_cost: float  # sum of edge `weight` along the path
    nodes_expanded: int = 0  # for benchmarking / documentation purposes


def _validate_endpoints(graph: nx.Graph, source, target) -> None:
    if source not in graph:
        raise NodeNotFoundError(f"Source node {source!r} not found in graph.")
    if target not in graph:
        raise NodeNotFoundError(f"Target node {target!r} not found in graph.")


def dijkstra(graph: nx.Graph, source, target) -> PathResult:
    """Single-pair shortest path via Dijkstra's algorithm."""
    _validate_endpoints(graph, source, target)

    dist: dict = {source: 0.0}
    prev: dict = {}
    visited: set = set()
    heap: list[tuple[float, int, object]] = [(0.0, 0, source)]
    counter = 1  # heap tie-breaker so we never compare node ids directly
    nodes_expanded = 0

    while heap:
        d, _, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        nodes_expanded += 1

        if node == target:
            break

        for neighbor in graph.neighbors(node):
            if neighbor in visited:
                continue
            weight = graph.edges[node, neighbor]["weight"]
            new_dist = d + weight
            if new_dist < dist.get(neighbor, float("inf")):
                dist[neighbor] = new_dist
                prev[neighbor] = node
                heapq.heappush(heap, (new_dist, counter, neighbor))
                counter += 1

    if target not in visited:
        raise NoPathError(f"No path found between {source!r} and {target!r}.")

    return PathResult(
        nodes=_reconstruct_path(prev, source, target),
        total_cost=dist[target],
        nodes_expanded=nodes_expanded,
    )


def astar(graph: nx.Graph, source, target) -> PathResult:
    """Single-pair shortest path via A*, using haversine distance to the
    target as the heuristic h(n)."""
    _validate_endpoints(graph, source, target)

    def h(node) -> float:
        n1 = graph.nodes[node]
        n2 = graph.nodes[target]
        return haversine_distance_m(n1["latitude"], n1["longitude"], n2["latitude"], n2["longitude"])

    g_score: dict = {source: 0.0}
    prev: dict = {}
    visited: set = set()
    heap: list[tuple[float, int, object]] = [(h(source), 0, source)]
    counter = 1
    nodes_expanded = 0

    while heap:
        f, _, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        nodes_expanded += 1

        if node == target:
            break

        for neighbor in graph.neighbors(node):
            if neighbor in visited:
                continue
            weight = graph.edges[node, neighbor]["weight"]
            tentative_g = g_score[node] + weight
            if tentative_g < g_score.get(neighbor, float("inf")):
                g_score[neighbor] = tentative_g
                prev[neighbor] = node
                f_score = tentative_g + h(neighbor)
                heapq.heappush(heap, (f_score, counter, neighbor))
                counter += 1

    if target not in visited:
        raise NoPathError(f"No path found between {source!r} and {target!r}.")

    return PathResult(
        nodes=_reconstruct_path(prev, source, target),
        total_cost=g_score[target],
        nodes_expanded=nodes_expanded,
    )


def _reconstruct_path(prev: dict, source, target) -> list:
    if source == target:
        return [source]
    path = [target]
    node = target
    while node != source:
        node = prev[node]
        path.append(node)
    path.reverse()
    return path


ALGORITHMS = {
    "dijkstra": dijkstra,
    "astar": astar,
}
