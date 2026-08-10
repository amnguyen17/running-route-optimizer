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


def test_estimated_time_uses_configured_pace(simple_graph):
    from app.config import get_settings

    settings = get_settings()
    stats = compute_route_stats(simple_graph, ["A", "B", "C", "F"])
    expected_base_minutes = stats.distance_miles * settings.default_pace_min_per_mile
    # No elevation gain on this route, so no elevation time penalty.
    assert abs(stats.estimated_time_minutes - expected_base_minutes) < 0.05
