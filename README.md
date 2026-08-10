# Running Route Optimizer

A full-stack application that generates running routes from real
OpenStreetMap street/trail data, optimized against a target distance and
desired elevation gain, using self-implemented Dijkstra and A* shortest-path
algorithms and a configurable scoring function.

Built as a portfolio project. It is an **MVP**, not a production system —
see [Limitations](#limitations) for an honest accounting of what that means.

---

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [How OSM data works](#how-osm-data-works)
- [Graph representation](#graph-representation)
- [Routing algorithms](#routing-algorithms)
- [Route optimization](#route-optimization)
- [API documentation](#api-documentation)
- [Database design](#database-design)
- [Testing](#testing)
- [Setup instructions](#setup-instructions)
- [Environment variables](#environment-variables)
- [Limitations](#limitations)
- [Future improvements](#future-improvements)
- [Files to understand before using this on your resume](#files-to-understand-before-using-this-on-your-resume)

---

## Features

- Enter a starting location, target distance, desired elevation gain, and
  whether you want a loop or an out-and-back route.
- Choose which shortest-path algorithm powers the route (Dijkstra or A*).
- View the generated route on an interactive Leaflet map with start/end
  markers.
- See distance, elevation gain/loss, estimated time, pace, a 0–1
  difficulty score, which algorithm was used, and the optimizer's score.
- Save generated routes to PostgreSQL and retrieve them later.
- OSM graph downloads are cached locally so repeat requests for the same
  area don't re-hit the Overpass API.

## Architecture

```
OpenStreetMap (Overpass API)
        |
        v
OSMnx ingestion  -------------->  local graph cache (pickled)
        |                              ^
        v                              | (cache hit)
Geospatial graph (networkx.Graph)  -----'
        |
        v
Graph preprocessing (edge weight = distance + elevation penalty)
        |
        v
Dijkstra  /  A*   (self-implemented, selectable per request)
        |
        v
Candidate route generation (multiple loop/out-and-back candidates)
        |
        v
Route scoring / optimization (configurable weighted scoring function)
        |
        v
FastAPI  (REST API, Pydantic validation, PostgreSQL persistence)
        |
        v
Next.js + Leaflet  (interactive map + stats UI)
```

## Tech stack

**Backend**: Python, FastAPI, OSMnx, NetworkX, PostgreSQL (SQLAlchemy +
Alembic), Pydantic, pytest.

**Frontend**: Next.js (App Router), TypeScript, React, Leaflet,
react-leaflet.

**Data**: OpenStreetMap (via OSMnx/Overpass) for the street/trail graph;
[Open-Elevation](https://open-elevation.com) (free, keyless) for
elevation.

**Dev**: Git, Docker / Docker Compose, environment-variable configuration.

No paid APIs are used anywhere in this project.

## How OSM data works

`backend/app/services/ingestion/osm_graph.py` uses OSMnx's
`graph_from_point` to download the pedestrian/walking network within a
radius of the requested start point. OSMnx returns a `MultiDiGraph`
(directed, allows parallel edges) with OSM's raw attributes; this project
converts that into a plain undirected `networkx.Graph` with one edge per
node pair (parallel edges are collapsed, keeping the shorter one — see
`_convert_to_processing_graph`), carrying just the fields routing needs:
`distance_m`, `highway`, `name`.

**Caching**: downloaded graphs are pickled to `data/graph_cache/` keyed by
a hash of `(rounded lat, rounded lon, radius)`. A lightweight on-disk
index (`index.pkl`) records each cached region's center and radius. A new
request reuses a cached graph if that graph's downloaded circle already
covers the new request's circle (plus a safety margin,
`cache_coverage_margin_m`), so nearby/smaller requests never re-hit
Overpass. This is a simple file-based cache appropriate for a
single-instance MVP — see Limitations for what would need to change for
multi-instance deployment.

## Graph representation

Each **node** carries `latitude`, `longitude`, and `elevation_m` (filled
in by the elevation service).

Each **edge** carries:
- `distance_m` — physical length in meters
- `elevation_gain_m` / `elevation_loss_m` — computed from the elevation
  difference between its endpoints; **gain only counts positive change**
  (`max(0, delta_elevation)`), loss only counts negative change
- `weight` — the actual cost used by the routing algorithms:
  `distance_m + ELEVATION_PENALTY_FACTOR * elevation_gain_m` (see
  `graph_prep.py`). This keeps `weight >= distance_m` always, which is
  required for the A* heuristic below to remain admissible.

## Routing algorithms

Full write-up with complexity analysis and an honestly-reported
Dijkstra-vs-A* benchmark: **[docs/ALGORITHMS.md](docs/ALGORITHMS.md)**.

Short version: both are implemented from scratch with a binary heap.
Dijkstra explores by accumulated cost `g(n)`; A* explores by
`f(n) = g(n) + h(n)` where `h(n)` is the haversine distance to the goal,
which is provably admissible given how edge weight is constructed.

## Route optimization

Full write-up: **[docs/OPTIMIZATION.md](docs/OPTIMIZATION.md)**.

Short version: this is a generate-and-score heuristic, not an exact
solver. Several candidate loops/out-and-backs are generated from
waypoints placed around a circle approximating the target distance, each
is scored by a configurable weighted function
(`distance_error + elevation_error + difficulty_penalty +
invalid_constraint_penalty`), and the best-scoring candidate is returned.
All weights live in `backend/app/config.py`.

## API documentation

Interactive Swagger docs are available at `http://localhost:8000/docs`
once the backend is running. Key endpoints:

### `POST /api/routes/generate`

Generates a route without persisting it.

**Request:**
```json
{
  "latitude": 37.2296,
  "longitude": -80.4139,
  "target_distance_miles": 5.0,
  "desired_elevation_gain_ft": 300,
  "route_type": "loop",
  "algorithm": "astar"
}
```

**Response (expected shape — see note below):**
```json
{
  "route": [
    { "latitude": 37.2296, "longitude": -80.4139, "elevation_m": 634.2 },
    { "latitude": 37.2301, "longitude": -80.4144, "elevation_m": 636.8 }
  ],
  "distance_miles": 5.02,
  "elevation_gain_ft": 312.0,
  "elevation_loss_ft": 308.0,
  "estimated_time_minutes": 53.4,
  "average_pace_min_per_mile": 10.64,
  "difficulty": 0.42,
  "algorithm": "astar",
  "score": 0.061,
  "start_latitude": 37.2296,
  "start_longitude": -80.4139,
  "end_latitude": 37.2298,
  "end_longitude": -80.4141
}
```
> **Honesty note:** this response was **not** captured from a live run —
> the sandboxed environment this project was built in does not have
> network access to the Overpass or Open-Elevation APIs, so an actual
> `/api/routes/generate` call could not be executed here. The shape above
> is generated directly from the `GeneratedRoute` Pydantic model (i.e. it
> is accurate to the schema), with illustrative example values. **Run
> this yourself** once the backend is up (see
> [Setup instructions](#setup-instructions)) to see real output for your
> location — every algorithm, scoring, and persistence code path *has*
> been tested, against synthetic graphs and mocked external services (see
> [Testing](#testing)), just not against the live OSM/Open-Elevation APIs
> end-to-end in this environment.

Errors: `422` with a `detail` string if the location has no usable
network or no valid candidate route could be generated. `422` with
FastAPI's standard validation error shape for malformed input (bad
lat/lon, out-of-bounds distance, etc.). Elevation API failures do
*not* produce a `422` — route generation retries (with backoff) and
then falls back to generating the route without elevation data, with
`elevation_available: false` in the response (see "Elevation source
reliability" below).

### `POST /api/saved-routes`

Generates a route and persists it. Returns the same shape as
`/routes/generate` plus `id` and `created_at`.

### `GET /api/saved-routes`

Lists saved routes (summary, no polyline), newest first. Supports
`?limit=&offset=`.

### `GET /api/saved-routes/{id}`

Full saved route including its polyline. `404` if not found.

### `DELETE /api/saved-routes/{id}`

Deletes a saved route. `204` on success, `404` if not found.

### `GET /api/health`, `GET /api/health/db`

Liveness and database-connectivity checks.

## Database design

Three tables (`backend/app/database/models.py`):

- **`route_records`** — one row per saved route: the request parameters
  (for reproducibility) and the result summary statistics.
- **`route_points`** — one row per polyline coordinate, foreign-keyed to
  `route_records`, ordered by `sequence`. Normalized out of the main
  table rather than stored as a JSON blob, so no ad hoc JSON parsing is
  needed elsewhere in the codebase.
- **`route_statistics`** — extensible named key/value metrics per route
  (currently just `avg_pace_min_per_mile`), so new metrics can be added
  without a schema migration touching `route_records`.

All reads/writes go through `backend/app/database/crud.py` — no SQL/ORM
calls are scattered through API or service code.

Migrations are managed with Alembic (`backend/alembic/`); an initial
migration is already generated at
`backend/alembic/versions/3cda899c9a6b_initial_schema.py`. `app/main.py`
also calls `Base.metadata.create_all()` on startup as a convenience for
local development, so the app works even before running migrations.

## Testing

**61 tests, all passing**, run in this environment with real pytest
execution (not fabricated) — see the commands below to reproduce.

All tests use synthetic graphs (`tests/conftest.py`) or mock external
calls (`osmnx.graph_from_point`, the Open-Elevation HTTP client), so the
**entire suite runs with zero live external dependencies** — no network
access, no running database beyond a temporary SQLite file created per
test.

| File | Covers |
|---|---|
| `test_dijkstra.py` | shortest path, same-node, unreachable node, invalid node |
| `test_astar.py` | optimal path, cost matches Dijkstra, node-expansion comparison on a grid |
| `test_elevation.py` | gain/loss directionality, cache hit/miss, 429 retry/backoff/`Retry-After`, retry exhaustion, non-429 failure handling (all mocked) |
| `test_route_service.py` | route generation continues (with `elevation_available=false`) when the elevation API is unavailable |
| `test_route_stats.py` | distance/elevation/time/difficulty calculations |
| `test_scoring.py` | scoring function across 9 cases including edge cases (zero desired elevation, constraint violations) |
| `test_loop_generation.py` | loop & out-and-back generation on a synthetic grid, `NoValidRouteError` on an isolated graph |
| `test_osm_ingestion.py` | parallel-edge collapsing, cache hit/miss behavior, ingestion failure handling |
| `test_api.py` | full HTTP layer: validation, error translation, saved-routes CRUD cycle |
| `test_database.py` | CRUD operations directly against SQLAlchemy models |

Run the backend suite:
```bash
cd backend
python -m venv venv && source venv/bin/activate    # or venv\Scripts\activate on Windows
pip install -r requirements.txt
DATABASE_URL="sqlite:///./test.db" pytest -v
```

**What you should test yourself, that could not be verified here**: an
actual end-to-end call to `/api/routes/generate` against live OSM +
Open-Elevation data (this environment had no network access to those
services); the Docker Compose stack end-to-end (`docker compose up`);
the frontend map rendering in a real browser. The frontend *did* have a
real `npm run build` (TypeScript compilation + Next.js production build)
succeed in this environment.

Run the algorithm benchmark (also fully reproducible locally, no network
needed):
```bash
python scripts/benchmark_algorithms.py
```

## Setup instructions

### Option A: Docker Compose (recommended)

```bash
cp .env.example .env
docker compose up --build
```
- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8000/docs
- Postgres: localhost:5432

### Option B: Run locally without Docker

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Point at a local Postgres, or use SQLite for a quick spin:
export DATABASE_URL="sqlite:///./local.db"

uvicorn app.main:app --reload
```

**Frontend** (in a second terminal):
```bash
cd frontend
npm install
export NEXT_PUBLIC_API_BASE_URL="http://localhost:8000/api"
npm run dev
```

Then open http://localhost:3000.

## Environment variables

See [`.env.example`](.env.example) for the full list with defaults. The
ones you're most likely to touch:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy connection string |
| `NEXT_PUBLIC_API_BASE_URL` | Where the frontend sends API requests |
| `GRAPH_CACHE_DIR` | Where downloaded OSM graphs are cached |
| `NUM_CANDIDATE_ROUTES` | How many loop candidates to generate per request |
| `DISTANCE_ERROR_WEIGHT`, `ELEVATION_ERROR_WEIGHT`, `DIFFICULTY_PENALTY_WEIGHT`, `INVALID_CONSTRAINT_PENALTY` | Scoring function weights |
| `DEFAULT_PACE_MIN_PER_MILE` | Flat pace assumption used for time estimates |

## Limitations

This is an MVP, not a production system. Specifically:

- **Not personalized**: estimated time uses one configurable flat pace
  assumption for everyone, not the runner's actual fitness or history.
- **Difficulty score is a simple heuristic** (elevation gain per mile,
  normalized and clamped), not a real physiological effort model.
- **Loop generation is heuristic, not exact**: it will not necessarily
  find the best possible loop for a given target — see
  [docs/OPTIMIZATION.md](docs/OPTIMIZATION.md) "Known limitations" for
  detail on waypoint snapping and possible edge reuse.
- **Nearest-node lookup is a linear scan** (`node_lookup.py`), fine for
  the small, radius-bounded graphs this project downloads, but would not
  scale to city-or-larger graphs without a spatial index (KD-tree/BallTree).
- **File-based graph/elevation cache**: works well for a single instance
  and local development; a multi-instance production deployment would
  need a shared cache (e.g. Redis, S3, or a PostGIS-backed spatial index)
  instead of local pickle files.
- **No authentication**: saved routes are not scoped to a user account;
  anyone with API access can list/delete any saved route.
- **Elevation source reliability**: Open-Elevation is free but has no
  uptime SLA and rate-limits aggressively (HTTP 429). Elevation lookups
  are cached on disk (so the same/nearby coordinates are never re-queried)
  and 429s are retried with exponential backoff, honoring `Retry-After`,
  up to `elevation_api_max_retries` (see `app/services/ingestion/elevation.py`).
  If the API is still unreachable after that, route generation continues
  anyway — it just skips elevation, and the response comes back with
  `elevation_available: false` and zeroed elevation/difficulty stats,
  rather than fabricating numbers or failing the whole request.
- **Benchmark caveat**: the Dijkstra-vs-A* benchmark included here used
  synthetic uniform grids (no network access to real OSM data in the
  build environment) and, honestly, did *not* show A* expanding fewer
  nodes on that particular graph shape — see
  [docs/ALGORITHMS.md](docs/ALGORITHMS.md) for the real numbers and why.

## Future improvements

- Spatial index (KD-tree) for nearest-node lookup on larger graphs.
- Multi-instance-friendly caching (Redis/S3 instead of local pickles).
- User accounts and per-user saved routes.
- A real orienteering-style optimizer (e.g. simulated annealing over
  candidate waypoint placement) instead of fixed circle-geometry
  waypoints.
- Elevation-aware difficulty using grade (%) per segment rather than
  total gain per mile.
- Real-world benchmark numbers against live OSM data for a few named
  cities.

## Files to understand before using this on your resume

If you're going to claim this project, make sure you can explain these
without notes:

1. `backend/app/services/routing/algorithms.py` — the actual Dijkstra/A*
   implementations; be ready to explain g/h/f and why the heuristic is
   admissible.
2. `backend/app/services/optimization/loop_generator.py` — how candidate
   loops are actually generated (and that it's a heuristic, not exact).
3. `backend/app/services/optimization/scoring.py` — the scoring formula
   and what each weight does.
4. `backend/app/services/ingestion/osm_graph.py` — how the OSM graph is
   downloaded, converted, and cached.
5. `backend/app/services/route_service.py` — how all the pieces above are
   wired together end-to-end for a single request.
6. `backend/app/config.py` — every tunable constant in the system and why
   it exists.
7. `docs/ALGORITHMS.md` and `docs/OPTIMIZATION.md` — the "why" behind (1)–(3).
