import pytest

from app.models.route import RouteType
from app.services.optimization.loop_generator import (
    NoValidRouteError,
    generate_best_route,
)


def test_generates_valid_loop_on_grid(grid_graph):
    result = generate_best_route(
        graph=grid_graph,
        start_latitude=37.0028,
        start_longitude=-80.0028,
        target_distance_miles=0.35,
        desired_elevation_gain_ft=0,
        max_elevation_gain_ft=100,
        route_type=RouteType.loop,
        algorithm_name="astar",
    )
    assert len(result.node_path) >= 2
    assert result.stats.distance_miles > 0
    # Loop should return reasonably close to the start point.
    assert result.loop_closure_distance_m < 200


def test_generates_valid_out_and_back_on_grid(grid_graph):
    result = generate_best_route(
        graph=grid_graph,
        start_latitude=37.0028,
        start_longitude=-80.0028,
        target_distance_miles=0.3,
        desired_elevation_gain_ft=0,
        max_elevation_gain_ft=100,
        route_type=RouteType.out_and_back,
        algorithm_name="dijkstra",
    )
    # Out-and-back always closes exactly at the start by construction.
    assert result.loop_closure_distance_m == 0.0
    assert result.node_path[0] == result.node_path[-1]


def test_raises_when_graph_too_small_for_any_candidate():
    import networkx as nx

    from app.services.routing.graph_prep import prepare_graph

    tiny = nx.Graph()
    tiny.add_node("A", latitude=37.0, longitude=-80.0, elevation_m=0.0)
    prepare_graph(tiny)

    with pytest.raises(NoValidRouteError):
        generate_best_route(
            graph=tiny,
            start_latitude=37.0,
            start_longitude=-80.0,
            target_distance_miles=1.0,
            desired_elevation_gain_ft=0,
            max_elevation_gain_ft=100,
            route_type=RouteType.loop,
            algorithm_name="astar",
        )


def test_dijkstra_and_astar_produce_comparable_distance(grid_graph):
    d_result = generate_best_route(
        graph=grid_graph,
        start_latitude=37.0028,
        start_longitude=-80.0028,
        target_distance_miles=0.3,
        desired_elevation_gain_ft=0,
        max_elevation_gain_ft=100,
        route_type=RouteType.loop,
        algorithm_name="dijkstra",
    )
    a_result = generate_best_route(
        graph=grid_graph,
        start_latitude=37.0028,
        start_longitude=-80.0028,
        target_distance_miles=0.3,
        desired_elevation_gain_ft=0,
        max_elevation_gain_ft=100,
        route_type=RouteType.loop,
        algorithm_name="astar",
    )
    # Both algorithms are optimal for shortest-path legs, so overall
    # route distance should be very close (candidate waypoint selection
    # is identical between the two calls).
    assert abs(d_result.stats.distance_miles - a_result.stats.distance_miles) < 0.05
