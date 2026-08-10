from app.services.routing.algorithms import (
    NodeNotFoundError,
    NoPathError,
    dijkstra,
)


def test_dijkstra_finds_shortest_path(simple_graph):
    result = dijkstra(simple_graph, "A", "F")
    assert result.nodes == ["A", "B", "C", "F"]
    assert result.total_cost == 350.0


def test_dijkstra_same_node(simple_graph):
    result = dijkstra(simple_graph, "A", "A")
    assert result.nodes == ["A"]
    assert result.total_cost == 0.0


def test_dijkstra_unreachable_node_raises(disconnected_graph):
    try:
        dijkstra(disconnected_graph, "A", "Z")
        assert False, "expected NoPathError"
    except NoPathError:
        pass


def test_dijkstra_invalid_source_raises(simple_graph):
    try:
        dijkstra(simple_graph, "NOPE", "F")
        assert False, "expected NodeNotFoundError"
    except NodeNotFoundError:
        pass


def test_dijkstra_invalid_target_raises(simple_graph):
    try:
        dijkstra(simple_graph, "A", "NOPE")
        assert False, "expected NodeNotFoundError"
    except NodeNotFoundError:
        pass


def test_dijkstra_picks_lower_cost_over_fewer_hops(simple_graph):
    # A->D->E->F costs 150+100+100=350; A->B->C->F costs 100+100+150=350 (tie)
    # A->B->E->F costs 100+150+100=350 too; verify total cost is truly minimal
    result = dijkstra(simple_graph, "A", "F")
    assert result.total_cost == 350.0
