from app.services.routing.route_stats import compute_route_stats


def test_stats_for_flat_route(simple_graph):
    stats = compute_route_stats(simple_graph, ["A", "B", "C", "F"])
    # 100 + 100 + 150 = 350m = 0.2175 mi
    assert abs(stats.distance_miles - 0.2175) < 0.001
    assert stats.elevation_gain_ft == 0.0
    assert stats.elevation_loss_ft == 0.0
    assert stats.difficulty == 0.0


def test_stats_for_hilly_route(hilly_graph):
    stats = compute_route_stats(hilly_graph, ["A", "B"])
    # 300m = 0.1864 mi, 60m gain = 196.85 ft
    assert abs(stats.distance_miles - 0.1864) < 0.001
    assert abs(stats.elevation_gain_ft - 196.9) < 0.5
    assert stats.difficulty > 0  # steep for its distance


def test_stats_empty_path_returns_zeroes(simple_graph):
    stats = compute_route_stats(simple_graph, ["A"])
    assert stats.distance_miles == 0.0
    assert stats.elevation_gain_ft == 0.0
    assert stats.estimated_time_minutes == 0.0


def test_estimated_time_defaults_to_configured_pace_when_unspecified(simple_graph):
    from app.config import get_settings

    settings = get_settings()
    stats = compute_route_stats(simple_graph, ["A", "B", "C", "F"])
    expected_base_minutes = stats.distance_miles * settings.default_pace_min_per_mile
    # No elevation gain on this route, so no elevation time penalty.
    assert abs(stats.estimated_time_minutes - expected_base_minutes) < 0.05
    assert abs(stats.average_pace_min_per_mile - settings.default_pace_min_per_mile) < 0.05


def test_estimated_time_uses_user_supplied_pace(simple_graph):
    fast = compute_route_stats(simple_graph, ["A", "B", "C", "F"], pace_min_per_mile=6.0)
    slow = compute_route_stats(simple_graph, ["A", "B", "C", "F"], pace_min_per_mile=15.0)

    # No elevation gain on this route, so time should scale linearly with pace.
    assert abs(fast.estimated_time_minutes - fast.distance_miles * 6.0) < 0.05
    assert abs(slow.estimated_time_minutes - slow.distance_miles * 15.0) < 0.05
    assert slow.estimated_time_minutes > fast.estimated_time_minutes


def test_elevation_penalty_still_applies_on_top_of_user_pace(hilly_graph):
    stats = compute_route_stats(hilly_graph, ["A", "B"], pace_min_per_mile=8.0)
    # 300m = 0.1864mi, 60m gain = 196.9ft -> elevation penalty = 1.969 min
    # at the default elevation_time_penalty_min_per_100ft=1.0.
    base_time = stats.distance_miles * 8.0
    assert stats.estimated_time_minutes > base_time
    assert abs(stats.estimated_time_minutes - base_time - 1.969) < 0.1


def test_empty_path_reports_requested_pace_even_with_no_distance(simple_graph):
    stats = compute_route_stats(simple_graph, ["A"], pace_min_per_mile=7.5)
    assert stats.average_pace_min_per_mile == 7.5
