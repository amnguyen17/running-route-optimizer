"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as routes_router
from app.api.health import router as health_router
from app.api.saved_routes import router as saved_routes_router
from app.config import get_settings
from app.database.session import Base, engine

settings = get_settings()

# Create tables on startup if they don't exist yet. For a portfolio-scale
# MVP this is simpler than requiring Alembic migrations to run first;
# Alembic is still included for anyone who wants proper migrations.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    description="Generates optimized running routes from OpenStreetMap data.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(routes_router, prefix=settings.api_v1_prefix)
app.include_router(saved_routes_router, prefix=settings.api_v1_prefix)
