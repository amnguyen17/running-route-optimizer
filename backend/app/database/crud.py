"""
All database read/write logic lives here so that API and service code
never constructs queries directly (requirement: don't scatter SQL/ORM
calls throughout unrelated application code).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models import RoutePoint, RouteRecord, RouteStatistic
from app.models.route import GeneratedRoute, RouteRequest


def save_route(db: Session, request: RouteRequest, route: GeneratedRoute) -> RouteRecord:
    record = RouteRecord(
        start_latitude=request.latitude,
        start_longitude=request.longitude,
        target_distance_miles=request.target_distance_miles,
        desired_elevation_gain_ft=request.desired_elevation_gain_ft,
        route_type=request.route_type.value,
        algorithm=route.algorithm,
        distance_miles=route.distance_miles,
        elevation_gain_ft=route.elevation_gain_ft,
        elevation_loss_ft=route.elevation_loss_ft,
        estimated_time_minutes=route.estimated_time_minutes,
        difficulty=route.difficulty,
        score=route.score,
    )
    record.points = [
        RoutePoint(
            sequence=i,
            latitude=coord.latitude,
            longitude=coord.longitude,
            elevation_m=coord.elevation_m,
        )
        for i, coord in enumerate(route.route)
    ]
    record.statistics = [
        RouteStatistic(name="avg_pace_min_per_mile", value=route.average_pace_min_per_mile),
    ]

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_route(db: Session, route_id: int) -> RouteRecord | None:
    return db.get(RouteRecord, route_id)


def list_routes(db: Session, limit: int = 50, offset: int = 0) -> list[RouteRecord]:
    return (
        db.query(RouteRecord)
        .order_by(RouteRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def delete_route(db: Session, route_id: int) -> bool:
    record = db.get(RouteRecord, route_id)
    if record is None:
        return False
    db.delete(record)
    db.commit()
    return True
