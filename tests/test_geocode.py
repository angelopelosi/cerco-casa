import json
import pytest
from scraper import geocode as geo

class FakeResponse:
    def __init__(self, json_data, status=200):
        self._json = json_data
        self.status_code = status
    def json(self):
        return self._json
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

def test_geocode_uses_cache_when_available(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps({"Jesi": [43.5219, 13.2437]}))

    def fail_if_called(*a, **k):
        raise AssertionError("non deve chiamare la rete se in cache")
    monkeypatch.setattr(geo.requests, "get", fail_if_called)

    result = geo.geocode("Jesi", cache_path=str(cache_path))
    assert result == (43.5219, 13.2437)

def test_geocode_calls_api_and_caches_on_miss(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    monkeypatch.setattr(
        geo.requests, "get",
        lambda *a, **k: FakeResponse([{"lat": "43.5", "lon": "13.2"}]),
    )
    monkeypatch.setattr(geo.time, "sleep", lambda *_: None)

    result = geo.geocode("Jesi", cache_path=str(cache_path))
    assert result == (43.5, 13.2)
    saved = json.loads(cache_path.read_text())
    assert saved["Jesi"] == [43.5, 13.2]

def test_geocode_raises_on_no_results(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    monkeypatch.setattr(geo.requests, "get", lambda *a, **k: FakeResponse([]))
    monkeypatch.setattr(geo.time, "sleep", lambda *_: None)

    with pytest.raises(geo.GeocodeError):
        geo.geocode("Luogo Inesistente Xyz", cache_path=str(cache_path))
