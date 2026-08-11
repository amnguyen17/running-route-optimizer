"""
Central configuration for the Running Route Optimizer backend.

Every "magic number" used by the routing, optimization, and statistics
code should live here (or be derived from a value here) so that the
scoring/optimization behavior of the system can be understood and tuned
in one place, per the project requirement to avoid unexplained
hardcoded constants scattered throughout the codebase.

All values can be overridden with environment variables (see .env.example).
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ------------------------------------------------------------------
    # App / API
    # ------------------------------------------------------------------
    app_name: str = "Running Route Optimizer"
    api_v1_prefix: str = "/api"
    cors_allow_origins: list[str] = ["http://localhost:3000"]

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    database_url: str = (
        "postgresql+psycopg2://route_optimizer:route_optimizer@localhost:5432/route_optimizer"
    )

    # ------------------------------------------------------------------
    # OSM ingestion / caching
    # ------------------------------------------------------------------
    # Where cached graphs (GraphML, pickled with elevation) are stored.
    graph_cache_dir: str = "data/graph_cache"
    # Default network buffer radius (meters) around a start point when no
    # explicit radius is requested. Must comfortably exceed the longest
    # loop leg (target_distance / 2) with margin for detours.
    default_network_radius_buffer_m: float = 400.0
    # OSMnx network type for pedestrian/running routing.
    osm_network_type: str = "walk"
    # If a cached graph's bounding region covers the requested point +
    # required radius, reuse it instead of re-downloading from OSM.
    cache_coverage_margin_m: float = 250.0

    # ------------------------------------------------------------------
    # Elevation
    # ------------------------------------------------------------------
    # Open-Elevation is a free, keyless public elevation API.
    elevation_api_url: str = "https://api.open-elevation.com/api/v1/lookup"
    elevation_api_batch_size: int = 100
    elevation_api_timeout_s: float = 15.0
    # Local elevation cache (avoids re-querying the same coordinates).
    elevation_cache_path: str = "data/elevation_cache.json"
    # Rate-limit handling for 429 responses from the elevation API: retry
    # with exponential backoff (honoring Retry-After if present), capped so
    # a persistently rate-limited API fails fast instead of hanging.
    elevation_api_max_retries: int = 3
    elevation_api_backoff_base_s: float = 1.0
    elevation_api_backoff_max_s: float = 20.0

    # ------------------------------------------------------------------
    # Route generation defaults / bounds
    # ------------------------------------------------------------------
    min_target_distance_miles: float = 0.5
    max_target_distance_miles: float = 15.0
    min_elevation_gain_ft: float = 0.0
    max_elevation_gain_ft: float = 3000.0
    # Number of candidate loop routes generated per request before scoring.
    num_candidate_routes: int = 12
    # A generated loop route's total distance may not exceed the target
    # distance by more than this fraction (e.g. 0.35 = 35% over target).
    max_distance_overshoot_fraction: float = 0.35
    # A generated loop must return within this fraction of the target
    # distance from the starting node to be considered a valid "loop".
    max_loop_closure_fraction: float = 0.15

    # ------------------------------------------------------------------
    # Route scoring weights (see docs/OPTIMIZATION.md)
    # score = distance_error_weight * distance_error_norm
    #       + elevation_error_weight * elevation_error_norm
    #       + difficulty_penalty_weight * difficulty
    #       + invalid_constraint_penalty (flat, added once per violation)
    # Lower score is better.
    # ------------------------------------------------------------------
    distance_error_weight: float = 1.0
    elevation_error_weight: float = 0.8
    difficulty_penalty_weight: float = 0.2
    invalid_constraint_penalty: float = 5.0

    # ------------------------------------------------------------------
    # Difficulty score
    # difficulty = elevation_gain_ft_per_mile / difficulty_normalization_ft_per_mile
    # clamped to [0, 1] before weighting; this is a simple, documented,
    # non-personalized heuristic (see README "Limitations").
    # ------------------------------------------------------------------
    difficulty_normalization_ft_per_mile: float = 150.0

    # ------------------------------------------------------------------
    # Running time estimate
    # ------------------------------------------------------------------
    # Fallback pace (minutes per mile) used only when a request doesn't
    # supply RouteRequest.pace_min_per_mile. When it is supplied, the
    # estimate is personalized to that pace instead.
    default_pace_min_per_mile: float = 10.0
    # Reasonable bounds for a user-supplied pace, used to reject clearly
    # invalid input (zero, negative, or an implausible value) with a
    # clear validation error instead of producing a nonsensical estimate.
    min_pace_min_per_mile: float = 3.0
    max_pace_min_per_mile: float = 60.0
    # Extra minutes added per 100 ft of elevation gain to account for
    # the runner slowing down on climbs (simple linear model).
    elevation_time_penalty_min_per_100ft: float = 1.0

    # ------------------------------------------------------------------
    # Earth radius for haversine distance calculations (meters)
    # ------------------------------------------------------------------
    earth_radius_m: float = 6371000.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
