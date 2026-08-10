import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import crud
from app.database.session import Base
from app.models.route import GeneratedRoute, RouteCoordinate, RouteRequest


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/crud_test.db")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def _sample_request():
    return RouteRequest(
        latitude=37.2296,
        longitude=-80.4139,
        target_distance_miles=5.0,
        desired_elevation_gain_ft=300,
        route_type="loop",
        algorithm="astar",
    )


def _sample_route():
    return GeneratedRoute(
        route=[
            RouteCoordinate(latitude=37.2296, longitude=-80.4139, elevation_m=600.0),
            RouteCoordinate(latitude=37.2310, longitude=-80.4150, elevation_m=610.0),
        ],
        distance_miles=5.0,
        elevation_gain_ft=300.0,
        elevation_loss_ft=300.0,
        estimated_time_minutes=53.0,
        average_pace_min_per_mile=10.6,
        difficulty=0.4,
        algorithm="astar",
        score=0.05,
        start_latitude=37.2296,
        start_longitude=-80.4139,
        end_latitude=37.2296,
        end_longitude=-80.4139,
    )


def test_save_route_persists_points(db_session):
    record = crud.save_route(db_session, _sample_request(), _sample_route())
    assert record.id is not None
    assert len(record.points) == 2
    assert record.points[0].latitude == 37.2296


def test_get_route_returns_saved_record(db_session):
    saved = crud.save_route(db_session, _sample_request(), _sample_route())
    fetched = crud.get_route(db_session, saved.id)
    assert fetched is not None
    assert fetched.id == saved.id


def test_get_route_returns_none_for_missing_id(db_session):
    assert crud.get_route(db_session, 99999) is None


def test_list_routes_orders_newest_first(db_session):
    first = crud.save_route(db_session, _sample_request(), _sample_route())
    second = crud.save_route(db_session, _sample_request(), _sample_route())
    routes = crud.list_routes(db_session)
    assert routes[0].id == second.id
    assert routes[1].id == first.id


def test_delete_route_removes_record_and_points(db_session):
    saved = crud.save_route(db_session, _sample_request(), _sample_route())
    deleted = crud.delete_route(db_session, saved.id)
    assert deleted is True
    assert crud.get_route(db_session, saved.id) is None


def test_delete_nonexistent_route_returns_false(db_session):
    assert crud.delete_route(db_session, 12345) is False
