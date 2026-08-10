"""
ORM models for persistence.

Design:
- `RouteRecord` stores one row per generated route the user chose to save,
  including the request parameters that produced it (for reproducibility)
  and its summary statistics.
- `RouteStatistic` stores time-series-style auxiliary metrics that don't
  need to live on the main row (kept as a separate table so RouteRecord
  stays a lean "identity + summary" row, and so we can attach multiple
  named metrics per route without schema churn).
- `RoutePoint` stores the ordered polyline coordinates for a saved route,
  one row per point, referencing RouteRecord.

This intentionally normalizes route geometry out of RouteRecord rather
than storing raw JSON, so query code doesn't need ad hoc JSON parsing in
unrelated parts of the app (see requirement: no SQL/JSON-shape logic
scattered around the codebase -- it all lives behind
app/database/crud.py).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Float, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class RouteRecord(Base):
    __tablename__ = "route_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc)
    )

    # Request parameters (stored for reproducibility / debugging).
    start_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    start_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    target_distance_miles: Mapped[float] = mapped_column(Float, nullable=False)
    desired_elevation_gain_ft: Mapped[float] = mapped_column(Float, nullable=False)
    route_type: Mapped[str] = mapped_column(String(20), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(20), nullable=False)

    # Result summary.
    distance_miles: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_gain_ft: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_loss_ft: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_time_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    difficulty: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)

    points: Mapped[list["RoutePoint"]] = relationship(
        back_populates="route", cascade="all, delete-orphan", order_by="RoutePoint.sequence"
    )
    statistics: Mapped[list["RouteStatistic"]] = relationship(
        back_populates="route", cascade="all, delete-orphan"
    )


class RoutePoint(Base):
    __tablename__ = "route_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("route_records.id"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    route: Mapped[RouteRecord] = relationship(back_populates="points")


class RouteStatistic(Base):
    """Named key/value metric attached to a route (extensible metrics)."""

    __tablename__ = "route_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("route_records.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    route: Mapped[RouteRecord] = relationship(back_populates="statistics")
