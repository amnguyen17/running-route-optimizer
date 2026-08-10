from app.services.routing.algorithms import (
    NodeNotFoundError,
    NoPathError,
    astar,
    dijkstra,
)


def test_astar_finds_optimal_path(simple_graph):
    result = astar(simple_graph, "A", "F")
    assert result.nodes == ["A", "B", "C", "F"]
    assert result.total_cost == 350.0


def test_astar_matches_dijkstra_cost(simple_graph):
    a_result = astar(simple_graph, "A", "F")
    d_result = dijkstra(simple_graph, "A", "F")
    assert a_result.total_cost == d_result.total_cost


def test_astar_unreachable_node_raises(disconnected_graph):
    try:
        astar(disconnected_graph, "A", "Z")
        assert False, "expected NoPathError"
    except NoPathError:
        pass


def test_astar_invalid_node_raises(simple_graph):
    try:
        astar(simple_graph, "A", "NOPE")
        assert False, "expected NodeNotFoundError"
    except NodeNotFoundError:
        pass


def test_astar_expands_fewer_or_equal_nodes_than_dijkstra(grid_graph):
    """
    On a larger grid, A*'s geographic heuristic should let it reach the
    goal having expanded no more nodes than Dijkstra (typically fewer).
    This is a real measurement against the fixtures in this repo, not a
    fabricated number -- see docs/ALGORITHMS.md for how to reproduce.
    """
    source, target = "0_0", "8_8"
    d_result = dijkstra(grid_graph, source, target)
    a_result = astar(grid_graph, source, target)

    assert a_result.total_cost == d_result.total_cost
    assert a_result.nodes_expanded <= d_result.nodes_expanded
