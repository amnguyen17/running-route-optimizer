"""
Elevation data via the free, keyless Open-Elevation API
(https://open-elevation.com), with a local JSON cache so the same (or
very close) coordinates are never re-queried.

Open-Elevation's public instance rate-limits aggressively (HTTP 429), so
fetching is retried with exponential backoff (honoring `Retry-After` when
present) up to `elevation_api_max_retries` times. If the API still can't
be reached after that, `ElevationUnavailableError` is raised so the
caller has a clear, explicit signal -- callers decide whether to treat
that as fatal or to degrade gracefully (see
`route_service.generate_route`, which continues without elevation data
rather than failing the whole request).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx
import networkx as nx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ElevationUnavailableError(Exception):
    """Raised when elevation data cannot be retrieved for one or more points."""


def _cache_path() -> Path:
    p = Path(settings.elevation_cache_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_cache() -> dict[str, float]:
    path = _cache_path()
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("Elevation cache at %s is corrupt; starting fresh.", path)
        return {}


def _save_cache(cache: dict[str, float]) -> None:
    with open(_cache_path(), "w") as f:
        json.dump(cache, f)


def _key(lat: float, lon: float) -> str:
    # Rounding to 5 decimal places (~1.1m) means nearby coordinates that
    # are effectively the same point on foot share a cache entry.
    return f"{round(lat, 5)},{round(lon, 5)}"


def get_elevations(
    points: list[tuple[float, float]], client: httpx.Client | None = None
) -> dict[tuple[float, float], float]:
    """
    Return elevation in meters for each (lat, lon) point, using the local
    cache where possible and batching cache-miss lookups to the
    Open-Elevation API.

    Raises ElevationUnavailableError if any uncached point cannot be
    resolved (network failure, API error, rate-limit retries exhausted,
    etc.) -- callers must not treat a partial/empty result as "elevation
    gain is 0"; they must decide explicitly how to handle unavailability.
    """
    cache = _load_cache()
    results: dict[tuple[float, float], float] = {}
    missing: list[tuple[float, float]] = []

    for lat, lon in points:
        k = _key(lat, lon)
        if k in cache:
            results[(lat, lon)] = cache[k]
        else:
            missing.append((lat, lon))

    if results:
        logger.info("Elevation: %d point(s) served from local cache.", len(results))

    if not missing:
        return results

    logger.info("Elevation: %d point(s) not cached; querying Open-Elevation API.", len(missing))

    def _persist_batch(batch_results: dict[tuple[float, float], float]) -> None:
        for (lat, lon), elev in batch_results.items():
            cache[_key(lat, lon)] = elev
        _save_cache(cache)
        logger.info("Elevation: cached %d point(s) fetched from the API.", len(batch_results))

    owns_client = client is None
    client = client or httpx.Client(timeout=settings.elevation_api_timeout_s)
    try:
        fetched = _fetch_elevations_batched(missing, client, on_batch_fetched=_persist_batch)
    finally:
        if owns_client:
            client.close()

    results.update(fetched)
    return results


def _fetch_elevations_batched(
    points: list[tuple[float, float]],
    client: httpx.Client,
    on_batch_fetched=None,
) -> dict[tuple[float, float], float]:
    """
    Fetch elevations for `points` from the API, chunked into batches of
    `elevation_api_batch_size`. If `on_batch_fetched` is given, it is
    called with each batch's results as soon as that batch succeeds, so a
    later batch's failure doesn't discard already-fetched (and
    already-billed-for) data -- it stays cached for next time.
    """
    results: dict[tuple[float, float], float] = {}
    batch_size = settings.elevation_api_batch_size

    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        batch_results = _fetch_single_batch(batch, client)
        results.update(batch_results)
        if on_batch_fetched:
            on_batch_fetched(batch_results)

    return results


def _fetch_single_batch(
    batch: list[tuple[float, float]], client: httpx.Client
) -> dict[tuple[float, float], float]:
    locations = [{"latitude": lat, "longitude": lon} for lat, lon in batch]
    payload = _post_with_retry(locations, client)

    api_results = payload.get("results")
    if not api_results or len(api_results) != len(batch):
        raise ElevationUnavailableError(
            "Elevation API returned an unexpected/empty response shape."
        )

    batch_results: dict[tuple[float, float], float] = {}
    for (lat, lon), item in zip(batch, api_results, strict=True):
        elevation = item.get("elevation")
        if elevation is None:
            raise ElevationUnavailableError(
                f"Elevation API returned no elevation for point ({lat}, {lon})."
            )
        batch_results[(lat, lon)] = float(elevation)

    return batch_results


def _post_with_retry(locations: list[dict], client: httpx.Client) -> dict:
    """
    POST one batch to the elevation API, retrying on HTTP 429 with
    exponential backoff (honoring `Retry-After` if the API sends one), up
    to `elevation_api_max_retries` attempts. Any other error (network
    failure, non-429 HTTP error, malformed JSON) fails immediately --
    only rate-limiting is considered worth waiting out.
    """
    attempt = 0
    while True:
        try:
            response = client.post(settings.elevation_api_url, json={"locations": locations})
        except httpx.HTTPError as exc:
            raise ElevationUnavailableError(f"Elevation API request failed: {exc}") from exc

        if response.status_code == 429:
            attempt += 1
            if attempt > settings.elevation_api_max_retries:
                raise ElevationUnavailableError(
                    f"Elevation API rate-limited (429) after {attempt - 1} retries."
                )
            delay = _retry_delay(response, attempt)
            logger.warning(
                "Elevation API rate-limited (429); retrying in %.1fs (attempt %d/%d).",
                delay,
                attempt,
                settings.elevation_api_max_retries,
            )
            time.sleep(delay)
            continue

        try:
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ElevationUnavailableError(
                f"Elevation API request failed for a batch of {len(locations)} points: {exc}"
            ) from exc


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After") if response.headers else None
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass  # Not a numeric seconds value (e.g. an HTTP-date) -- fall back to backoff.

    backoff = settings.elevation_api_backoff_base_s * (2 ** (attempt - 1))
    return min(backoff, settings.elevation_api_backoff_max_s)


def annotate_graph_with_elevation(graph: nx.Graph, client: httpx.Client | None = None) -> nx.Graph:
    """
    Populate `elevation_m` on every node and `elevation_gain_m` /
    `elevation_loss_m` on every edge. Mutates and returns the same graph.

    elevation_gain is defined as max(0, elevation(v) - elevation(u)) and
    elevation_loss as max(0, elevation(u) - elevation(v)) for edge (u, v),
    i.e. gain only counts positive changes, per the project requirement.

    Raises ElevationUnavailableError (propagated from get_elevations) if
    elevation data can't be obtained -- see that function's docstring.
    """
    node_points = [
        (data["latitude"], data["longitude"]) for _, data in graph.nodes(data=True)
    ]
    if not node_points:
        return graph

    elevations = get_elevations(node_points, client=client)

    for node_id, data in graph.nodes(data=True):
        key = (data["latitude"], data["longitude"])
        data["elevation_m"] = elevations[key]

    for u, v, data in graph.edges(data=True):
        elev_u = graph.nodes[u]["elevation_m"]
        elev_v = graph.nodes[v]["elevation_m"]
        delta = elev_v - elev_u
        data["elevation_gain_m"] = max(0.0, delta)
        data["elevation_loss_m"] = max(0.0, -delta)

    return graph