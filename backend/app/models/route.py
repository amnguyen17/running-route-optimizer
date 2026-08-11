"""Pydantic schemas shared across the API and service layers."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.config import get_settings

settings = get_settings()


class RouteType(str, Enum):
    loop = "loop"
    out_and_back = "out_and_back"


class Algorithm(str, Enum):
    dijkstra = "dijkstra"
    astar = "astar"


class RouteRequest(BaseModel):
    """Body of POST /api/routes/generate."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    target_distance_miles: float = Field(
        ..., gt=0, description="Desired total route distance in miles."
    )
    desired_elevation_gain_ft: float = Field(
        ..., ge=0, description="Desired total elevation gain in feet."
    )
    max_elevation_gain_ft: float | None = Field(
        default=None,
        ge=0,
        description="Optional hard cap on elevation gain. Defaults to a generous "
        "multiple of desired_elevation_gain_ft if not supplied.",
    )
    pace_min_per_mile: float | None = Field(
        default=None,
        description="User's typical pace in minutes per mile, used to personalize "
        "estimated_time_minutes. Omit to fall back to settings.default_pace_min_per_mile.",
    )
    route_type: RouteType = RouteType.loop
    algorithm: Algorithm = Algorithm.astar

    @field_validator("target_distance_miles")
    @classmethod
    def _distance_within_bounds(cls, v: float) -> float:
        if not (settings.min_target_distance_miles <= v <= settings.max_target_distance_miles):
            raise ValueError(
                f"target_distance_miles must be between {settings.min_target_distance_miles} "
                f"and {settings.max_target_distance_miles}"
            )
        return v

    @field_validator("desired_elevation_gain_ft")
    @classmethod
    def _elevation_within_bounds(cls, v: float) -> float:
        if v > settings.max_elevation_gain_ft:
            raise ValueError(
                f"desired_elevation_gain_ft must not exceed {settings.max_elevation_gain_ft}"
            )
        return v

    @field_validator("pace_min_per_mile")
    @classmethod
    def _pace_within_bounds(cls, v: float | None) -> float | None:
        # None means "not supplied" -- generate_route falls back to the
        # configured default pace rather than treating this as an error.
        if v is None:
            return v
        if not (settings.min_pace_min_per_mile <= v <= settings.max_pace_min_per_mile):
            raise ValueError(
                f"pace_min_per_mile must be between {settings.min_pace_min_per_mile} "
                f"and {settings.max_pace_min_per_mile} minutes per mile"
            )
        return v


class RouteCoordinate(BaseModel):
    latitude: float
    longitude: float
    elevation_m: float | None = None


class GeneratedRoute(BaseModel):
    """Full result of route generation, returned by the API and persisted."""

    route: list[RouteCoordinate]
    distance_miles: float
    elevation_gain_ft: float
    elevation_loss_ft: float
    estimated_time_minutes: float
    average_pace_min_per_mile: float
    difficulty: float
    algorithm: str
    score: float
    start_latitude: float
    start_longitude: float
    end_latitude: float
    end_longitude: float
    elevation_available: bool = Field(
        default=True,
        description="False if the elevation API was unreachable for this request; "
        "elevation_gain_ft/elevation_loss_ft/difficulty default to 0 in that case "
        "rather than being fabricated.",
    )


class SavedRouteSummary(BaseModel):
    """Lightweight representation used when listing saved routes."""

    id: int
    created_at: str
    target_distance_miles: float
    desired_elevation_gain_ft: float
    route_type: str
    algorithm: str
    distance_miles: float
    elevation_gain_ft: float
    elevation_loss_ft: float
    estimated_time_minutes: float
    difficulty: float
    score: float

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def _serialize_created_at(cls, v):
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return v


class SavedRouteDetail(SavedRouteSummary):
    route: list[RouteCoordinate]
