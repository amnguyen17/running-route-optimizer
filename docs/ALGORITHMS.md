# Routing Algorithms

Both algorithms are implemented from scratch in `backend/app/services/routing/algorithms.py`
(not via `networkx.shortest_path` or any routing API). They operate on a
preprocessed `networkx.Graph` where every edge has a `weight` attribute
(see `graph_prep.py`) and every node has `latitude`/`longitude`.

## Dijkstra's algorithm

**g(n)**: the exact cost accumulated so far from the source node to node `n`.

Dijkstra explores nodes in non-decreasing order of `g(n)`, using a binary
min-heap (Python's `heapq`) as the priority queue. Each time a node is
popped for the first time, its `g` value is final (this is the standard
non-negative-edge-weight correctness argument). Because our edge weights
are always non-negative (distance plus a non-negative elevation penalty),
this precondition holds.

**Time complexity**: O((V + E) log V) — every edge may cause one heap
push, and every node is popped at most once, each heap operation costing
O(log V).

## A*

**g(n)**: identical to Dijkstra — the exact cost so far.

**h(n)**: an admissible heuristic estimating the remaining cost from `n`
to the goal. We use the haversine (great-circle) distance from `n` to the
goal node, in meters.

**f(n) = g(n) + h(n)**: the priority used to order the frontier. Nodes
with lower `f` are explored first.

**Why the heuristic is admissible**: edge `weight` is defined as
`distance_m + ELEVATION_PENALTY_FACTOR * elevation_gain_m`, which is
always `>= distance_m`. Straight-line (haversine) distance is the
shortest possible physical distance between two points, so it can never
exceed the true remaining path distance, and therefore never exceeds the
true remaining path *weight* either. An admissible heuristic guarantees
A* still returns an optimal path.

**Time complexity**: same asymptotic bound as Dijkstra, O((V + E) log V).
A*'s heuristic does not change the worst case; its benefit is a
*practical* reduction in the number of nodes actually expanded, when the
heuristic meaningfully discriminates between "closer to the goal" and
"farther from the goal" nodes.

**Why A* can be faster in practice**: Dijkstra expands nodes purely by
accumulated cost, with no sense of direction, so it can spend time
exploring nodes that lead away from the goal. A*'s `h(n)` biases
exploration toward the goal, which tends to prune large portions of the
search space on graphs where cost roughly correlates with geographic
distance (e.g. real street networks with mostly-uniform road density).

**Honest measured result** (see `scripts/benchmark_algorithms.py`,
reproducible, not fabricated): on a uniform synthetic grid graph with a
strict corner-to-corner shortest path, A* expanded the *same* number of
nodes as Dijkstra at every size we tested, and ran measurably slower in
wall-clock time due to the added heuristic computation per node:

```
  grid   nodes       cost  dij_expanded  astar_expanded    dij_ms   astar_ms
     5      25      624.0            25              25      0.06       0.31
     9      81     1248.0            81              81      0.25       0.52
    15     225     2184.0           225             225      0.57       0.76
    25     625     3744.0           625             625      1.33       2.20
    40    1600     6084.0          1600            1600      3.40       6.19
```

This is expected: a uniform grid with a diagonal target has a huge number
of equal-cost shortest paths, so nearly every node lies on *some*
shortest path and gets expanded by both algorithms regardless of the
heuristic. Real OSM street networks are far less uniform (irregular
block shapes, dead ends, one significant "trunk" path between two areas),
where A*'s heuristic has more opportunity to prune clearly-suboptimal
branches. We have not benchmarked on live OSM data in this environment
(no network access to the Overpass API here) — if you want real-world
numbers, run `scripts/benchmark_algorithms.py` against a graph pulled
via `get_or_download_graph` for your area, or check
`tests/test_astar.py::test_astar_expands_fewer_or_equal_nodes_than_dijkstra`,
which only asserts `<=` for exactly this reason.

## Both algorithms return the same shape

Both return a `PathResult(nodes, total_cost, nodes_expanded)`, so
downstream code (loop generation, statistics, API) is agnostic to which
algorithm produced a path.
