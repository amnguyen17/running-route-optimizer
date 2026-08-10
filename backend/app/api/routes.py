from fastapi import APIRouter, HTTPException

from app.models.route import GeneratedRoute, RouteRequest
from app.services.route_service import RouteGenerationError, generate_route

router = APIRouter(prefix="/routes", tags=["routes"])


@router.post("/generate", response_model=GeneratedRoute)
def generate(request: RouteRequest) -> GeneratedRoute:
    try:
        return generate_route(request)
    except RouteGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
