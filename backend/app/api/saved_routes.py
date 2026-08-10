from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import crud
from app.database.session import get_db
from app.models.route import (
    GeneratedRoute,
    RouteCoordinate,
    RouteRequest,
    SavedRouteDetail,
    SavedRouteSummary,
)
from app.services.route_service import RouteGenerationError, generate_route

router = APIRouter(prefix="/saved-routes", tags=["saved-routes"])


@router.post("", response_model=SavedRouteDetail, status_code=201)
def create_saved_route(request: RouteRequest, db: Session = Depends(get_db)) -> SavedRouteDetail:
    """Generate a route and persist it in one call."""
    try:
        route: GeneratedRoute = generate_route(request)
    except RouteGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record = crud.save_route(db, request, route)
    return _to_detail(record)


@router.get("", response_model=list[SavedRouteSummary])
def list_saved_routes(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    records = crud.list_routes(db, limit=limit, offset=offset)
    return [SavedRouteSummary.model_validate(r) for r in records]


@router.get("/{route_id}", response_model=SavedRouteDetail)
def get_saved_route(route_id: int, db: Session = Depends(get_db)) -> SavedRouteDetail:
    record = crud.get_route(db, route_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Saved route {route_id} not found.")
    return _to_detail(record)


@router.delete("/{route_id}", status_code=204)
def delete_saved_route(route_id: int, db: Session = Depends(get_db)) -> None:
    deleted = crud.delete_route(db, route_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Saved route {route_id} not found.")


def _to_detail(record) -> SavedRouteDetail:
    return SavedRouteDetail(
        id=record.id,
        created_at=record.created_at.isoformat(),
        target_distance_miles=record.target_distance_miles,
        desired_elevation_gain_ft=record.desired_elevation_gain_ft,
        route_type=record.route_type,
        algorithm=record.algorithm,
        distance_miles=record.distance_miles,
        elevation_gain_ft=record.elevation_gain_ft,
        elevation_loss_ft=record.elevation_loss_ft,
        estimated_time_minutes=record.estimated_time_minutes,
        difficulty=record.difficulty,
        score=record.score,
        route=[
            RouteCoordinate(latitude=p.latitude, longitude=p.longitude, elevation_m=p.elevation_m)
            for p in record.points
        ],
    )
