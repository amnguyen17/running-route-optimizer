"""
Route candidate scoring.

score = distance_error_weight * distance_error_norm
      + elevation_error_weight * elevation_error_norm
      + difficulty_penalty_weight * difficulty
      + invalid_constraint_penalty  (added once per violated constraint)

Lower is better. All weights come from app.config so they can be tuned
in one place (see README "Route Optimization" section for rationale).

- distance_error_norm = |actual - target| / target   (fractional error,
  so it's comparable across different target distances)
- elevation_error_norm = |actual - desired| / max(desired, 1 ft)  (guards
  against divide-by-zero when desired elevation gain is 0)
- difficulty contributes a small, separately-weighted term so two routes
  with identical distance/elevation error but different steepness
  distribution can still be differentiated.
- invalid_constraint_penalty is a flat penalty added once per violated
  hard constraint (e.g. exceeds max elevation gain, distance overshoot
  too large, loop doesn't return close enough to start) rather than a
  hard rejection, so the optimizer can still return "the least bad"
  candidate with a clearly elevated score if literally nothing better
  is available -- callers can decide whether to surface that as an
  error using the `is_valid` flag.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings

settings = get_settings()


@dataclass
class ScoreBreakdown:
    score: float
    distance_error_norm: float
    elevation_error_norm: float
    is_valid: bool
    violations: list[str]


def score_candidate(
    *,
    actual_distance_miles: float,
    target_distance_miles: float,
    actual_elevation_gain_ft: float,
    desired_elevation_gain_ft: float,
    max_elevation_gain_ft: float,
    difficulty: float,
    loop_closure_distance_m: float,
    max_loop_closure_m: float,
    is_loop: bool,
) -> ScoreBreakdown:
    violations: list[str] = []

    distance_error_norm = abs(actual_distance_miles - target_distance_miles) / target_distance_miles
    elevation_error_norm = abs(actual_elevation_gain_ft - desired_elevation_gain_ft) / max(
        desired_elevation_gain_ft, 1.0
    )

    max_allowed_distance = target_distance_miles * (1 + settings.max_distance_overshoot_fraction)
    if actual_distance_miles > max_allowed_distance:
        violations.append(
            f"distance {actual_distance_miles:.2f}mi exceeds max allowed {max_allowed_distance:.2f}mi"
        )

    if actual_elevation_gain_ft > max_elevation_gain_ft:
        violations.append(
            f"elevation gain {actual_elevation_gain_ft:.0f}ft exceeds max allowed {max_elevation_gain_ft:.0f}ft"
        )

    if is_loop and loop_closure_distance_m > max_loop_closure_m:
        violations.append(
            f"loop does not return close enough to start "
            f"({loop_closure_distance_m:.0f}m > {max_loop_closure_m:.0f}m allowed)"
        )

    score = (
        settings.distance_error_weight * distance_error_norm
        + settings.elevation_error_weight * elevation_error_norm
        + settings.difficulty_penalty_weight * difficulty
        + settings.invalid_constraint_penalty * len(violations)
    )

    return ScoreBreakdown(
        score=round(score, 4),
        distance_error_norm=round(distance_error_norm, 4),
        elevation_error_norm=round(elevation_error_norm, 4),
        is_valid=len(violations) == 0,
        violations=violations,
    )
