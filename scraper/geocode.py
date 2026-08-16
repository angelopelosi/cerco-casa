import json
import time
from pathlib import Path
import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "case-affitto-aste-vendite/1.0 (uso personale)"

class GeocodeError(Exception):
    pass

def geocode(query: str, cache_path: str = "data/geocode_cache.json") -> tuple[float, float]:
    cache = _load_cache(cache_path)
    if query in cache:
        return tuple(cache[query])

    resp = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise GeocodeError(f"nessun risultato per: {query}")

    lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
    cache[query] = [lat, lon]
    _save_cache(cache_path, cache)
    time.sleep(1)  # rispetta il rate limit di Nominatim (max 1 richiesta/sec)
    return (lat, lon)

def _load_cache(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text())

def _save_cache(path: str, cache: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cache, indent=2))
