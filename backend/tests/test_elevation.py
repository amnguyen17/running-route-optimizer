import json

import httpx
import pytest

import app.services.ingestion.elevation as elevation_module
from app.services.ingestion.elevation import (
    ElevationUnavailableError,
    _fetch_elevations_batched,
    _post_with_retry,
    annotate_graph_with_elevation,
    get_elevations,
)


def _mock_get_elevations(monkeypatch, node_to_elevation):
    """Mock get_elevations so these tests never hit the live Open-Elevation
    API -- the graph's node lat/lon -> elevation mapping is supplied
    directly by the test."""

    def fake_get_elevations(points, client=None):
        return {(lat, lon): node_to_elevation[(lat, lon)] for lat, lon in points}

    monkeypatch.setattr(elevation_module, "get_elevations", fake_get_elevations)


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Every test gets its own empty on-disk cache file, and no test ever
    actually sleeps during retry backoff."""
    monkeypatch.setattr(
        elevation_module.settings, "elevation_cache_path", str(tmp_path / "elevation_cache.json")
    )
    monkeypatch.setattr(elevation_module.time, "sleep", lambda _seconds: None)


def test_annotate_graph_computes_gain_and_loss_correctly(hilly_graph, monkeypatch):
    mapping = {
        (37.000, -80.000): 100.0,
        (37.002, -80.000): 160.0,
    }
    _mock_get_elevations(monkeypatch, mapping)

    annotate_graph_with_elevation(hilly_graph)

    edge = hilly_graph.edges["A", "B"]
    # A is 100m, B is 160m -> 60m gain, 0m loss
    assert edge["elevation_gain_m"] == 60.0
    assert edge["elevation_loss_m"] == 0.0


def test_elevation_gain_is_directional(hilly_graph, monkeypatch):
    # Reverse direction (B -> A) should show as loss, not gain, if we
    # recompute with B's elevation lower than A's.
    mapping = {
        (37.000, -80.000): 200.0,
        (37.002, -80.000): 150.0,
    }
    _mock_get_elevations(monkeypatch, mapping)

    annotate_graph_with_elevation(hilly_graph)

    edge = hilly_graph.edges["A", "B"]
    assert edge["elevation_gain_m"] == 0.0
    assert edge["elevation_loss_m"] == 50.0


class _FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._payload


class _CountingClient:
    """Fake httpx.Client that returns one canned response per call and
    records every call it received, so tests can assert exactly how many
    (and which) HTTP requests were made."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    def post(self, url, json):
        self.calls.append(json["locations"])
        response = self._responses[len(self.calls) - 1]
        if isinstance(response, Exception):
            raise response
        return response


# ---------------------------------------------------------------------------
# Successful lookup / caching behavior (get_elevations)
# ---------------------------------------------------------------------------


def test_get_elevations_successful_lookup_hits_api_and_caches():
    client = _CountingClient(
        [_FakeResponse({"results": [{"elevation": 123.0}]})]
    )

    result = get_elevations([(37.0, -80.0)], client=client)

    assert result[(37.0, -80.0)] == 123.0
    assert len(client.calls) == 1

    with open(elevation_module.settings.elevation_cache_path) as f:
        cache = json.load(f)
    assert cache["37.0,-80.0"] == 123.0


def test_get_elevations_cached_lookup_does_not_call_api():
    client = _CountingClient(
        [_FakeResponse({"results": [{"elevation": 123.0}]})]
    )
    get_elevations([(37.0, -80.0)], client=client)  # first call: populates cache
    assert len(client.calls) == 1

    # Second call for the same point must be served entirely from cache.
    result = get_elevations([(37.0, -80.0)], client=client)

    assert result[(37.0, -80.0)] == 123.0
    assert len(client.calls) == 1  # unchanged -- no new API call


def test_get_elevations_nearby_coordinate_reuses_cache():
    client = _CountingClient(
        [_FakeResponse({"results": [{"elevation": 123.0}]})]
    )
    get_elevations([(37.00000, -80.00000)], client=client)

    # A coordinate close enough to round to the same 5-decimal-place key.
    result = get_elevations([(37.000001, -80.000001)], client=client)

    assert result[(37.000001, -80.000001)] == 123.0
    assert len(client.calls) == 1


def test_get_elevations_persists_partial_progress_before_raising(monkeypatch):
    monkeypatch.setattr(elevation_module.settings, "elevation_api_batch_size", 1)
    client = _CountingClient(
        [
            _FakeResponse({"results": [{"elevation": 10.0}]}),
            httpx.ConnectError("connection refused"),
        ]
    )

    with pytest.raises(ElevationUnavailableError):
        get_elevations([(1.0, 1.0), (2.0, 2.0)], client=client)

    # The first (successful) batch must still be cached even though the
    # second batch's failure aborted the overall request.
    with open(elevation_module.settings.elevation_cache_path) as f:
        cache = json.load(f)
    assert cache == {"1.0,1.0": 10.0}


# ---------------------------------------------------------------------------
# 429 / retry / backoff behavior (_post_with_retry)
# ---------------------------------------------------------------------------


def test_post_with_retry_retries_after_429_then_succeeds():
    client = _CountingClient(
        [
            _FakeResponse({}, status_code=429, headers={"Retry-After": "2"}),
            _FakeResponse({"results": [{"elevation": 50.0}]}),
        ]
    )

    payload = _post_with_retry([{"latitude": 1.0, "longitude": 1.0}], client)

    assert payload == {"results": [{"elevation": 50.0}]}
    assert len(client.calls) == 2


def test_post_with_retry_honors_retry_after_header(monkeypatch):
    sleeps = []
    monkeypatch.setattr(elevation_module.time, "sleep", lambda s: sleeps.append(s))
    client = _CountingClient(
        [
            _FakeResponse({}, status_code=429, headers={"Retry-After": "7"}),
            _FakeResponse({"results": [{"elevation": 50.0}]}),
        ]
    )

    _post_with_retry([{"latitude": 1.0, "longitude": 1.0}], client)

    assert sleeps == [7.0]


def test_post_with_retry_exponential_backoff_without_retry_after_header(monkeypatch):
    monkeypatch.setattr(elevation_module.settings, "elevation_api_backoff_base_s", 1.0)
    monkeypatch.setattr(elevation_module.settings, "elevation_api_backoff_max_s", 100.0)
    sleeps = []
    monkeypatch.setattr(elevation_module.time, "sleep", lambda s: sleeps.append(s))
    client = _CountingClient(
        [
            _FakeResponse({}, status_code=429),
            _FakeResponse({}, status_code=429),
            _FakeResponse({"results": [{"elevation": 50.0}]}),
        ]
    )

    _post_with_retry([{"latitude": 1.0, "longitude": 1.0}], client)

    # attempt 1 -> base * 2^0 = 1.0, attempt 2 -> base * 2^1 = 2.0
    assert sleeps == [1.0, 2.0]


def test_post_with_retry_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(elevation_module.settings, "elevation_api_max_retries", 2)
    client = _CountingClient([_FakeResponse({}, status_code=429) for _ in range(10)])

    with pytest.raises(ElevationUnavailableError):
        _post_with_retry([{"latitude": 1.0, "longitude": 1.0}], client)

    # 1 initial attempt + 2 retries = 3 requests total, then it gives up
    # instead of hanging indefinitely.
    assert len(client.calls) == 3


# ---------------------------------------------------------------------------
# Non-429 / permanent failure behavior (kept close to the original tests)
# ---------------------------------------------------------------------------


def test_fetch_elevations_batched_success():
    class FakeClient:
        def post(self, url, json):
            locations = json["locations"]
            return _FakeResponse(
                {"results": [{"elevation": 100.0 + i} for i in range(len(locations))]}
            )

    result = _fetch_elevations_batched([(37.0, -80.0), (37.1, -80.1)], FakeClient())
    assert result[(37.0, -80.0)] == 100.0
    assert result[(37.1, -80.1)] == 101.0


def test_fetch_elevations_batched_raises_on_http_error():
    class FailingClient:
        def post(self, url, json):
            raise httpx.ConnectError("connection refused")

    with pytest.raises(ElevationUnavailableError):
        _fetch_elevations_batched([(37.0, -80.0)], FailingClient())


def test_fetch_elevations_batched_raises_on_missing_elevation():
    class BadClient:
        def post(self, url, json):
            return _FakeResponse({"results": [{"elevation": None}]})

    with pytest.raises(ElevationUnavailableError):
        _fetch_elevations_batched([(37.0, -80.0)], BadClient())