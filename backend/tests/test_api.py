"""
API-layer tests. Route generation itself is mocked at the service-call
boundary (`app.api.routes.generate_route` / `app.api.saved_routes.generate_route`)
so these tests never contact live OSM/elevation services -- they verify
request validation, response shaping, error translation, and persistence
wiring, using a temporary SQLite database.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    """
    Build a TestClient wired to an isolated, file-backed SQLite database
    via FastAPI's dependency_overrides, rather than mutating global state
    or reloading modules. Each test gets a fresh database.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.main as main_module
    from app.database.session import Base, get_db

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(main_module.app)
    yield test_client
    main_module.app.dependency_overrides.clear()


VALID_PAYLOAD = {
    "latitude": 37.2296,
    "longitude": -80.4139,
    "target_distance_miles": 5.0,
    "desired_elevation_gain_ft": 300,
    "route_type": "loop",
    "algorithm": "astar",
}


def _fake_generated_route():
    from app.models.route import GeneratedRoute, RouteCoordinate

    return GeneratedRoute(
        route=[
            RouteCoordinate(latitude=37.2296, longitude=-80.4139, elevation_m=600.0),
            RouteCoordinate(latitude=37.2310, longitude=-80.4150, elevation_m=610.0),
            RouteCoordinate(latitude=37.2296, longitude=-80.4139, elevation_m=600.0),
        ],
        distance_miles=5.02,
        elevation_gain_ft=305.0,
        elevation_loss_ft=305.0,
        estimated_time_minutes=53.2,
        average_pace_min_per_mile=10.6,
        difficulty=0.4,
        algorithm="astar",
        score=0.05,
        start_latitude=37.2296,
        start_longitude=-80.4139,
        end_latitude=37.2296,
        end_longitude=-80.4139,
    )


def test_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_generate_route_success(client, monkeypatch):
    import app.api.routes as routes_module

    monkeypatch.setattr(routes_module, "generate_route", lambda req: _fake_generated_route())

    resp = client.post("/api/routes/generate", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["distance_miles"] == 5.02
    assert body["algorithm"] == "astar"
    assert len(body["route"]) == 3


def test_generate_route_invalid_distance_returns_422(client):
    payload = dict(VALID_PAYLOAD, target_distance_miles=-1)
    resp = client.post("/api/routes/generate", json=payload)
    assert resp.status_code == 422


def test_generate_route_invalid_latitude_returns_422(client):
    payload = dict(VALID_PAYLOAD, latitude=999)
    resp = client.post("/api/routes/generate", json=payload)
    assert resp.status_code == 422


def test_generate_route_distance_too_large_returns_422(client):
    payload = dict(VALID_PAYLOAD, target_distance_miles=1000)
    resp = client.post("/api/routes/generate", json=payload)
    assert resp.status_code == 422


def test_generate_route_zero_pace_returns_422(client):
    payload = dict(VALID_PAYLOAD, pace_min_per_mile=0)
    resp = client.post("/api/routes/generate", json=payload)
    assert resp.status_code == 422


def test_generate_route_negative_pace_returns_422(client):
    payload = dict(VALID_PAYLOAD, pace_min_per_mile=-5)
    resp = client.post("/api/routes/generate", json=payload)
    assert resp.status_code == 422


def test_generate_route_unreasonably_slow_pace_returns_422(client):
    payload = dict(VALID_PAYLOAD, pace_min_per_mile=500)
    resp = client.post("/api/routes/generate", json=payload)
    assert resp.status_code == 422


def test_generate_route_accepts_custom_pace(client, monkeypatch):
    import app.api.routes as routes_module

    monkeypatch.setattr(routes_module, "generate_route", lambda req: _fake_generated_route())

    payload = dict(VALID_PAYLOAD, pace_min_per_mile=8.5)
    resp = client.post("/api/routes/generate", json=payload)
    assert resp.status_code == 200


def test_generate_route_omitted_pace_still_succeeds(client, monkeypatch):
    import app.api.routes as routes_module

    monkeypatch.setattr(routes_module, "generate_route", lambda req: _fake_generated_route())

    resp = client.post("/api/routes/generate", json=VALID_PAYLOAD)  # no pace_min_per_mile key at all
    assert resp.status_code == 200


def test_generate_route_translates_service_error_to_422(client, monkeypatch):
    import app.api.routes as routes_module
    from app.services.route_service import RouteGenerationError

    def raise_error(req):
        raise RouteGenerationError("no walkable network found nearby")

    monkeypatch.setattr(routes_module, "generate_route", raise_error)

    resp = client.post("/api/routes/generate", json=VALID_PAYLOAD)
    assert resp.status_code == 422
    assert "no walkable network" in resp.json()["detail"]


def test_saved_routes_full_crud_cycle(client, monkeypatch):
    import app.api.saved_routes as saved_routes_module

    monkeypatch.setattr(saved_routes_module, "generate_route", lambda req: _fake_generated_route())

    create_resp = client.post("/api/saved-routes", json=VALID_PAYLOAD)
    assert create_resp.status_code == 201
    created = create_resp.json()
    route_id = created["id"]
    assert created["distance_miles"] == 5.02
    assert len(created["route"]) == 3

    list_resp = client.get("/api/saved-routes")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    get_resp = client.get(f"/api/saved-routes/{route_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == route_id

    delete_resp = client.delete(f"/api/saved-routes/{route_id}")
    assert delete_resp.status_code == 204

    get_after_delete = client.get(f"/api/saved-routes/{route_id}")
    assert get_after_delete.status_code == 404


def test_get_nonexistent_saved_route_returns_404(client):
    resp = client.get("/api/saved-routes/9999")
    assert resp.status_code == 404
