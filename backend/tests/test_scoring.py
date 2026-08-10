from app.services.optimization.scoring import score_candidate


def _base_kwargs(**overrides):
    kwargs = dict(
        actual_distance_miles=5.0,
        target_distance_miles=5.0,
        actual_elevation_gain_ft=300,
        desired_elevation_gain_ft=300,
        max_elevation_gain_ft=600,
        difficulty=0.2,
        loop_closure_distance_m=10,
        max_loop_closure_m=800,
        is_loop=True,
    )
    kwargs.update(overrides)
    return kwargs


def test_perfect_match_scores_near_zero():
    result = score_candidate(**_base_kwargs())
    assert result.is_valid
    assert result.score < 0.1  # only the small difficulty term contributes


def test_distance_error_increases_score():
    close = score_candidate(**_base_kwargs(actual_distance_miles=5.0))
    far = score_candidate(**_base_kwargs(actual_distance_miles=5.5))
    assert far.score > close.score


def test_elevation_error_increases_score():
    close = score_candidate(**_base_kwargs(actual_elevation_gain_ft=300))
    far = score_candidate(**_base_kwargs(actual_elevation_gain_ft=500))
    assert far.score > close.score


def test_exceeding_max_distance_is_invalid():
    result = score_candidate(**_base_kwargs(actual_distance_miles=9.0))
    assert not result.is_valid
    assert any("distance" in v for v in result.violations)


def test_exceeding_max_elevation_is_invalid():
    result = score_candidate(**_base_kwargs(actual_elevation_gain_ft=1000))
    assert not result.is_valid
    assert any("elevation gain" in v for v in result.violations)


def test_poor_loop_closure_is_invalid():
    result = score_candidate(**_base_kwargs(loop_closure_distance_m=5000))
    assert not result.is_valid
    assert any("loop" in v for v in result.violations)


def test_out_and_back_ignores_loop_closure():
    result = score_candidate(**_base_kwargs(loop_closure_distance_m=5000, is_loop=False))
    assert result.is_valid


def test_zero_desired_elevation_does_not_divide_by_zero():
    result = score_candidate(**_base_kwargs(desired_elevation_gain_ft=0, actual_elevation_gain_ft=50))
    assert result.elevation_error_norm == 50.0  # normalized against the 1ft floor
