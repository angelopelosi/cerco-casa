# Case Affitto Aste Vendite — MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working end-to-end pipeline — scrape 2 sources (Subito.it, Portale Vendite Pubbliche giustizia), store in SQLite, publish a filterable static site to GitHub Pages, send a weekly Monday email digest of new listings — proving the architecture before adding the remaining 6 portals.

**Architecture:** Python pipeline. Each portal has a scraper module producing a common `Listing` schema. A daily job fetches, dedups into SQLite, filters by geographic radius + residential category, and generates/publishes a static site. A weekly job queries listings first seen in the last 7 days and emails a digest via Gmail SMTP. Orchestrated by Windows Task Scheduler.

**Tech Stack:** Python 3.11+, Playwright (fetch/render), BeautifulSoup4 (parse), SQLite (storage), PyYAML (config), python-dotenv (secrets), pytest (testing), vanilla HTML/JS/CSS (frontend), Git + GitHub Pages (hosting).

**Spec:** `Case Affitto Aste Vendite/docs/superpowers/specs/2026-08-16-case-affitto-aste-vendite-design.md`

## Scope note

The spec lists 8 portals. This plan implements the full pipeline (schema, DB, radius filter, site generator, publisher, notifier, orchestration) plus **2 scrapers**: Subito.it (affitto/vendita) and Portale Vendite Pubbliche giustizia (aste). This proves the architecture end-to-end with one real listing source and one real auction source. The remaining 6 portals (Immobiliare.it, Casa.it, Idealista, astegiudiziarie.it, portaleaste.it, asteimmobili.it) follow in a separate plan once this one is validated — each new portal is a single self-contained task that reuses everything built here.

## Known limitation — scraper selectors and search URLs are first-pass

Tasks 7 and 8 include CSS selectors and search-URL paths for Subito.it and PVP giustizia written from general knowledge of typical site structure, not from a live page inspected right now. Each task's Step 1 requires capturing a real fixture from the live site and Step 2 requires verifying/adjusting both the selectors and `build_search_url` against that real markup before the test is trusted — in particular, confirm whether one search URL actually returns both affitto and vendita listings, or whether the portal requires a separate URL/category per tipo (in which case `build_search_url` and `run_all.py`'s call site need to fetch twice). Treat the selectors and URLs in the code blocks as a starting draft, not verified fact.

## Global Constraints

- Centro di ricerca default: Jesi, lat 43.5219, lon 13.2437 — configurabile in `config.yaml`.
- Raggio di ricerca default: 20 km — configurabile in `config.yaml`.
- Categoria sempre `residenziale` — nessun immobile commerciale incluso.
- Nessun login: filtri applicati lato client sul sito statico, stessi per tutti i visitatori.
- Dedup per `(fonte, external_id)` → id = hash SHA256 troncato.
- Storage: SQLite unico, nessun DB server esterno.
- Sito pubblicato come file statici su branch `gh-pages` (GitHub Pages).
- Email via Gmail SMTP + App Password; invio saltato se nessun destinatario configurato.
- Scraping: giornaliero. Digest email: lunedì, basato su `data_first_seen` negli ultimi 7 giorni.
- Nessuna richiesta di rete nei test automatici — solo fixture salvate su disco o file locali.

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `config.yaml`
- Create: `.env.example`
- Create: `README.md`
- Create: `scraper/__init__.py`, `webapp/__init__.py`, `notifier/__init__.py`, `scripts/__init__.py` (empty)
- Create: `data/.gitkeep`, `fixtures/.gitkeep`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.yaml` with keys `centro.nome`, `centro.lat`, `centro.lon`, `raggio_km`, `portali_attivi` (list), `email.destinatari` (list) — consumed by every later task.

- [ ] **Step 1: Create folder structure**

```bash
mkdir -p scraper webapp/template notifier scripts fixtures tests data
touch scraper/__init__.py webapp/__init__.py notifier/__init__.py scripts/__init__.py
touch data/.gitkeep fixtures/.gitkeep
```

- [ ] **Step 2: Write `requirements.txt`**

```
playwright>=1.40
beautifulsoup4>=4.12
requests>=2.31
pyyaml>=6.0
python-dotenv>=1.0
pytest>=7.4
```

- [ ] **Step 3: Write `.gitignore`**

```
data/*.db
data/geocode_cache.json
webapp/build/
.env
__pycache__/
*.pyc
.pytest_cache/
venv/
```

- [ ] **Step 4: Write `config.yaml`**

```yaml
centro:
  nome: "Jesi"
  lat: 43.5219
  lon: 13.2437
raggio_km: 20
portali_attivi:
  - subito
  - pvp_giustizia
email:
  destinatari: []
```

- [ ] **Step 5: Write `.env.example`**

```
SMTP_USER=tuoaccount@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

- [ ] **Step 6: Write `README.md`**

```markdown
# Case Affitto Aste Vendite

Aggregatore di annunci residenziali (affitto/vendita/asta) attorno a un centro
configurabile (default Jesi). Sito statico pubblico + digest email settimanale.

## Setup

1. `python -m venv venv && venv\Scripts\activate` (Windows)
2. `pip install -r requirements.txt`
3. `playwright install chromium`
4. `copy .env.example .env` e compila `SMTP_USER` / `GMAIL_APP_PASSWORD`
   (App Password Gmail: https://myaccount.google.com/apppasswords)
5. Modifica `config.yaml` per centro/raggio/destinatari.
6. `pytest` per verificare che tutto funzioni.

## Uso manuale

- `python -m scripts.daily` — scrape + genera sito + pubblica
- `python -m scripts.weekly` — invia digest email

## Task Scheduler (Windows)

Vedi Task 13 del piano di implementazione per i comandi esatti.
```

- [ ] **Step 7: Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

- [ ] **Step 8: Write failing test**

```python
# tests/test_config.py
from pathlib import Path
import yaml

def test_config_has_required_keys():
    config = yaml.safe_load(Path("config.yaml").read_text())
    assert "centro" in config
    assert "nome" in config["centro"]
    assert "lat" in config["centro"]
    assert "lon" in config["centro"]
    assert "raggio_km" in config
    assert isinstance(config["portali_attivi"], list)
    assert "email" in config and "destinatari" in config["email"]
```

- [ ] **Step 9: Run test, verify it passes** (config.yaml already written in Step 4)

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add requirements.txt .gitignore config.yaml .env.example README.md scraper webapp notifier scripts data fixtures tests
git commit -m "chore: project scaffolding"
```

---

### Task 2: Listing schema

**Files:**
- Create: `scraper/schema.py`
- Test: `tests/test_schema.py`

**Interfaces:**
- Produces: `Listing` dataclass with fields `fonte, external_id, tipo, titolo, prezzo, url, categoria, superficie_mq, locali, comune, lat, lon, stato_disponibilita, data_disponibilita, arredato, data_pubblicazione, tribunale, data_asta, offerta_minima`; property `.id -> str`; method `.validate() -> None` (raises `ValueError`). Used by every scraper and by `scraper/db.py`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_schema.py
import pytest
from scraper.schema import Listing

def make_listing(**overrides):
    base = dict(
        fonte="subito", external_id="123", tipo="affitto",
        titolo="Bilocale centro", prezzo=500, url="https://example.com/123",
    )
    base.update(overrides)
    return Listing(**base)

def test_id_is_deterministic_hash_of_fonte_and_external_id():
    l1 = make_listing()
    l2 = make_listing()
    assert l1.id == l2.id
    assert l1.id != make_listing(external_id="456").id

def test_defaults():
    l = make_listing()
    assert l.categoria == "residenziale"
    assert l.arredato == "non_specificato"
    assert l.superficie_mq is None

def test_validate_accepts_valid_listing():
    make_listing().validate()  # non deve sollevare eccezioni

def test_validate_rejects_bad_tipo():
    with pytest.raises(ValueError):
        make_listing(tipo="ufficio").validate()

def test_validate_rejects_missing_fonte():
    with pytest.raises(ValueError):
        make_listing(fonte="").validate()

def test_validate_rejects_negative_price():
    with pytest.raises(ValueError):
        make_listing(prezzo=-10).validate()
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scraper.schema'`

- [ ] **Step 3: Implement `scraper/schema.py`**

```python
from dataclasses import dataclass
from typing import Optional
import hashlib

TIPI_VALIDI = ("affitto", "vendita", "asta")

@dataclass
class Listing:
    fonte: str
    external_id: str
    tipo: str
    titolo: str
    prezzo: int
    url: str
    categoria: str = "residenziale"
    superficie_mq: Optional[int] = None
    locali: Optional[int] = None
    comune: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    stato_disponibilita: Optional[str] = None
    data_disponibilita: Optional[str] = None
    arredato: str = "non_specificato"
    data_pubblicazione: Optional[str] = None
    tribunale: Optional[str] = None
    data_asta: Optional[str] = None
    offerta_minima: Optional[int] = None

    @property
    def id(self) -> str:
        raw = f"{self.fonte}:{self.external_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def validate(self) -> None:
        if self.tipo not in TIPI_VALIDI:
            raise ValueError(f"tipo non valido: {self.tipo}")
        if not self.fonte or not self.external_id:
            raise ValueError("fonte e external_id sono obbligatori")
        if not self.url:
            raise ValueError("url obbligatorio")
        if self.prezzo is not None and self.prezzo < 0:
            raise ValueError("prezzo non puo essere negativo")
```

- [ ] **Step 4: Run test, verify it passes**

Run: `pytest tests/test_schema.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add scraper/schema.py tests/test_schema.py
git commit -m "feat: add Listing schema with dedup id and validation"
```

---

### Task 3: SQLite DB layer

**Files:**
- Create: `scraper/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `Listing` from `scraper/schema.py` (Task 2)
- Produces: `connect(db_path: str) -> sqlite3.Connection`, `upsert_listing(conn, listing: Listing, today: str = None) -> None`, `mark_stale_as_removed(conn, fonte: str, seen_ids: set[str], today: str = None) -> None`, `get_active(conn) -> list[dict]`, `get_new_since(conn, since_date: str) -> list[dict]`. Used by `scraper/run_all.py` (Task 9), `webapp/generate.py` (Task 10), `notifier/digest.py` (Task 12).

- [ ] **Step 1: Write failing test**

```python
# tests/test_db.py
from scraper import db
from scraper.schema import Listing

def make_listing(external_id="1", fonte="subito"):
    return Listing(fonte=fonte, external_id=external_id, tipo="affitto",
                    titolo="Bilocale", prezzo=500, url="https://example.com/1")

def test_connect_creates_table(tmp_path):
    conn = db.connect(str(tmp_path / "test.db"))
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='listings'")
    assert cur.fetchone() is not None

def test_upsert_new_listing_sets_first_seen_and_last_seen(tmp_path):
    conn = db.connect(str(tmp_path / "test.db"))
    db.upsert_listing(conn, make_listing(), today="2026-08-10")
    rows = db.get_active(conn)
    assert len(rows) == 1
    assert rows[0]["data_first_seen"] == "2026-08-10"
    assert rows[0]["data_last_seen"] == "2026-08-10"
    assert rows[0]["stato_annuncio"] == "attivo"

def test_upsert_existing_listing_preserves_first_seen_updates_last_seen(tmp_path):
    conn = db.connect(str(tmp_path / "test.db"))
    db.upsert_listing(conn, make_listing(), today="2026-08-10")
    updated = make_listing()
    updated.prezzo = 600
    db.upsert_listing(conn, updated, today="2026-08-12")
    rows = db.get_active(conn)
    assert len(rows) == 1
    assert rows[0]["data_first_seen"] == "2026-08-10"
    assert rows[0]["data_last_seen"] == "2026-08-12"
    assert rows[0]["prezzo"] == 600

def test_mark_stale_as_removed(tmp_path):
    conn = db.connect(str(tmp_path / "test.db"))
    l1 = make_listing(external_id="1")
    l2 = make_listing(external_id="2")
    db.upsert_listing(conn, l1, today="2026-08-10")
    db.upsert_listing(conn, l2, today="2026-08-10")
    db.mark_stale_as_removed(conn, "subito", {l1.id}, today="2026-08-11")
    active = db.get_active(conn)
    assert len(active) == 1
    assert active[0]["id"] == l1.id

def test_mark_stale_as_removed_with_empty_seen_ids_removes_all(tmp_path):
    conn = db.connect(str(tmp_path / "test.db"))
    l1 = make_listing(external_id="1")
    db.upsert_listing(conn, l1, today="2026-08-10")
    db.mark_stale_as_removed(conn, "subito", set(), today="2026-08-11")
    assert db.get_active(conn) == []

def test_get_new_since_filters_by_first_seen_date(tmp_path):
    conn = db.connect(str(tmp_path / "test.db"))
    old = make_listing(external_id="old")
    new = make_listing(external_id="new")
    db.upsert_listing(conn, old, today="2026-08-01")
    db.upsert_listing(conn, new, today="2026-08-15")
    recent = db.get_new_since(conn, "2026-08-10")
    assert len(recent) == 1
    assert recent[0]["external_id"] == "new"
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scraper.db'`

- [ ] **Step 3: Implement `scraper/db.py`**

```python
import sqlite3
from datetime import date
from .schema import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,
    fonte TEXT NOT NULL,
    external_id TEXT NOT NULL,
    tipo TEXT NOT NULL,
    categoria TEXT NOT NULL DEFAULT 'residenziale',
    titolo TEXT,
    prezzo INTEGER,
    superficie_mq INTEGER,
    locali INTEGER,
    comune TEXT,
    lat REAL,
    lon REAL,
    stato_disponibilita TEXT,
    data_disponibilita TEXT,
    arredato TEXT,
    url TEXT,
    data_pubblicazione TEXT,
    data_first_seen TEXT NOT NULL,
    data_last_seen TEXT NOT NULL,
    stato_annuncio TEXT NOT NULL DEFAULT 'attivo',
    tribunale TEXT,
    data_asta TEXT,
    offerta_minima INTEGER
);
"""

def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn

def upsert_listing(conn: sqlite3.Connection, listing: Listing, today: str | None = None) -> None:
    listing.validate()
    today = today or date.today().isoformat()
    existing = conn.execute(
        "SELECT data_first_seen FROM listings WHERE id = ?", (listing.id,)
    ).fetchone()
    first_seen = existing[0] if existing else today
    conn.execute(
        """
        INSERT INTO listings (id, fonte, external_id, tipo, categoria, titolo, prezzo,
            superficie_mq, locali, comune, lat, lon, stato_disponibilita, data_disponibilita,
            arredato, url, data_pubblicazione, data_first_seen, data_last_seen, stato_annuncio,
            tribunale, data_asta, offerta_minima)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            prezzo=excluded.prezzo, superficie_mq=excluded.superficie_mq, locali=excluded.locali,
            comune=excluded.comune, lat=excluded.lat, lon=excluded.lon,
            stato_disponibilita=excluded.stato_disponibilita,
            data_disponibilita=excluded.data_disponibilita,
            arredato=excluded.arredato, data_last_seen=excluded.data_last_seen,
            stato_annuncio='attivo'
        """,
        (listing.id, listing.fonte, listing.external_id, listing.tipo, listing.categoria,
         listing.titolo, listing.prezzo, listing.superficie_mq, listing.locali, listing.comune,
         listing.lat, listing.lon, listing.stato_disponibilita, listing.data_disponibilita,
         listing.arredato, listing.url, listing.data_pubblicazione, first_seen, today, "attivo",
         listing.tribunale, listing.data_asta, listing.offerta_minima),
    )
    conn.commit()

def mark_stale_as_removed(conn: sqlite3.Connection, fonte: str, seen_ids: set[str], today: str | None = None) -> None:
    today = today or date.today().isoformat()
    if seen_ids:
        placeholders = ",".join("?" * len(seen_ids))
        conn.execute(
            f"UPDATE listings SET stato_annuncio = 'rimosso', data_last_seen = data_last_seen "
            f"WHERE fonte = ? AND stato_annuncio = 'attivo' AND id NOT IN ({placeholders})",
            (fonte, *seen_ids),
        )
    else:
        conn.execute(
            "UPDATE listings SET stato_annuncio = 'rimosso' WHERE fonte = ? AND stato_annuncio = 'attivo'",
            (fonte,),
        )
    conn.commit()

def _rows_to_dicts(cur: sqlite3.Cursor) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

def get_active(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute("SELECT * FROM listings WHERE stato_annuncio = 'attivo'")
    return _rows_to_dicts(cur)

def get_new_since(conn: sqlite3.Connection, since_date: str) -> list[dict]:
    cur = conn.execute(
        "SELECT * FROM listings WHERE data_first_seen >= ? AND stato_annuncio = 'attivo'",
        (since_date,),
    )
    return _rows_to_dicts(cur)
```

- [ ] **Step 4: Run test, verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add scraper/db.py tests/test_db.py
git commit -m "feat: add SQLite storage layer with dedup and staleness tracking"
```

---

### Task 4: Geocode helper

**Files:**
- Create: `scraper/geocode.py`
- Test: `tests/test_geocode.py`

**Interfaces:**
- Produces: `geocode(query: str, cache_path: str) -> tuple[float, float]`, `GeocodeError` exception. Used by scrapers that need to resolve a `comune` name to lat/lon when the portal doesn't provide coordinates directly.

- [ ] **Step 1: Write failing test**

```python
# tests/test_geocode.py
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
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_geocode.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scraper.geocode'`

- [ ] **Step 3: Implement `scraper/geocode.py`**

```python
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
```

- [ ] **Step 4: Run test, verify it passes**

Run: `pytest tests/test_geocode.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scraper/geocode.py tests/test_geocode.py
git commit -m "feat: add geocoding helper with on-disk cache"
```

---

### Task 5: Radius filter

**Files:**
- Create: `scraper/radius.py`
- Test: `tests/test_radius.py`

**Interfaces:**
- Produces: `haversine_km(lat1, lon1, lat2, lon2) -> float`, `within_radius(center_lat, center_lon, lat, lon, radius_km) -> bool`. Used by `webapp/generate.py` (Task 10).

- [ ] **Step 1: Write failing test**

```python
# tests/test_radius.py
from scraper.radius import haversine_km, within_radius

def test_haversine_same_point_is_zero():
    assert haversine_km(43.5, 13.2, 43.5, 13.2) == 0

def test_haversine_one_degree_longitude_at_equator_is_about_111km():
    distance = haversine_km(0, 0, 0, 1)
    assert 110 < distance < 112

def test_within_radius_true_when_inside():
    assert within_radius(43.5, 13.2, 43.5, 13.21, 20) is True

def test_within_radius_false_when_outside():
    assert within_radius(43.5, 13.2, 44.5, 14.2, 20) is False

def test_within_radius_false_when_coords_missing():
    assert within_radius(43.5, 13.2, None, None, 20) is False
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_radius.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scraper.radius'`

- [ ] **Step 3: Implement `scraper/radius.py`**

```python
import math

EARTH_RADIUS_KM = 6371.0

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))

def within_radius(center_lat: float, center_lon: float, lat: float | None, lon: float | None, radius_km: float) -> bool:
    if lat is None or lon is None:
        return False
    return haversine_km(center_lat, center_lon, lat, lon) <= radius_km
```

- [ ] **Step 4: Run test, verify it passes**

Run: `pytest tests/test_radius.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add scraper/radius.py tests/test_radius.py
git commit -m "feat: add haversine distance and radius filter"
```

---

### Task 6: Playwright fetch helper

**Files:**
- Create: `scraper/fetch.py`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Produces: `fetch_html(url: str, wait_selector: str | None = None, delay_ms: int = 1500) -> str`. Used by `scraper/run_all.py` (Task 9).

- [ ] **Step 1: Write failing test** (uses a local `file://` URL so no network call is needed)

```python
# tests/test_fetch.py
from pathlib import Path
from scraper.fetch import fetch_html

def test_fetch_html_returns_page_content(tmp_path):
    html_file = tmp_path / "sample.html"
    html_file.write_text("<html><body><h1 id='marker'>ciao</h1></body></html>", encoding="utf-8")

    result = fetch_html(f"file:///{html_file.as_posix()}", wait_selector="#marker", delay_ms=0)

    assert "ciao" in result
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_fetch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scraper.fetch'`

- [ ] **Step 3: Implement `scraper/fetch.py`**

```python
from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

def fetch_html(url: str, wait_selector: str | None = None, delay_ms: int = 1500) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, timeout=30000)
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=15000)
        if delay_ms:
            page.wait_for_timeout(delay_ms)
        html = page.content()
        browser.close()
        return html
```

- [ ] **Step 4: Run test, verify it passes**

Run: `pytest tests/test_fetch.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scraper/fetch.py tests/test_fetch.py
git commit -m "feat: add Playwright-based HTML fetcher"
```

---

### Task 7: Subito.it scraper

**Files:**
- Create: `scraper/subito.py`
- Create: `fixtures/subito_sample.html` (captured manually — see Step 1)
- Test: `tests/test_subito.py`

**Interfaces:**
- Consumes: `Listing` (Task 2)
- Produces: `build_search_url(centro_nome: str) -> str`, `parse_listings(html: str) -> list[Listing]`, `WAIT_SELECTOR: str`. Registered in `scraper/run_all.py` (Task 9) as `PORTAL_MODULES["subito"]`.

- [ ] **Step 1: Capture a real fixture**

Open https://www.subito.it in a browser, search for "casa" with filter affitto in Jesi or the Marche region, save that page's HTML, then repeat the same search with filter vendita and save that too (see Step 2 for why both are needed). Wait for each page to fully load. Open devtools, select the `<html>` element, "Copy outerHTML", and save the affitto version to `fixtures/subito_sample.html` (used by the test). This gives real markup to test against instead of guessed structure.

- [ ] **Step 2: Inspect the fixture and identify real selectors and category URLs**

Open `fixtures/subito_sample.html`, use devtools "Inspect" on a few listing cards, and note: the repeating card container selector, and within it the title, price, and link elements. Update `SELECTOR_CARD`, `SELECTOR_TITLE`, `SELECTOR_PRICE` constants at the top of `scraper/subito.py` (Step 5) to match what you found. Also compare the two URLs from Step 1 (affitto search vs vendita search): if Subito uses separate category paths for each, update `build_search_url` to accept a `tipo` parameter and change `run_all.py`'s call site (Task 9) to fetch both; if a single URL/category already mixes both, keep the current signature. The values in Step 5 are a starting draft based on Subito's typical structure and must be verified against the real fixture.

- [ ] **Step 3: Write failing test**

```python
# tests/test_subito.py
from pathlib import Path
from scraper.subito import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "subito_sample.html"

def test_build_search_url_includes_centro_nome():
    url = build_search_url("Jesi")
    assert "subito.it" in url
    assert "Jesi" in url or "jesi" in url.lower()

def test_parse_listings_extracts_expected_fields():
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    first = listings[0]
    assert first.fonte == "subito"
    assert first.tipo in ("affitto", "vendita")
    assert first.categoria == "residenziale"
    assert first.external_id
    assert first.titolo
    assert isinstance(first.prezzo, int) and first.prezzo >= 0
    assert first.url.startswith("http")

def test_parse_listings_returns_empty_list_for_no_matches():
    assert parse_listings("<html><body>nessun annuncio</body></html>") == []
```

- [ ] **Step 4: Run test, verify it fails**

Run: `pytest tests/test_subito.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scraper.subito'`

- [ ] **Step 5: Implement `scraper/subito.py`**

```python
from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing

WAIT_SELECTOR = "body"

# NOTA: selettori di partenza — verificare/correggere contro fixtures/subito_sample.html (Step 2)
SELECTOR_CARD = "[data-testid='item-card']"
SELECTOR_TITLE = "h2"
SELECTOR_PRICE = "[data-testid='price']"
SELECTOR_LINK = "a"

def build_search_url(centro_nome: str) -> str:
    # NOTA: URL di partenza, cerca genericamente su tutta la categoria immobili
    # residenziali. Verificare allo Step 2 se Subito richiede un URL/categoria
    # separato per affitto vs vendita — se si, aggiungere un parametro `tipo`
    # e far chiamare run_all.py (Task 9) una volta per ciascun tipo.
    query = quote(f"{centro_nome} casa")
    return f"https://www.subito.it/annunci-italia/vendita-affitto/immobili/?q={query}"

def parse_listings(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    for card in soup.select(SELECTOR_CARD):
        title_el = card.select_one(SELECTOR_TITLE)
        price_el = card.select_one(SELECTOR_PRICE)
        link_el = card.select_one(SELECTOR_LINK)
        if not (title_el and link_el and link_el.get("href")):
            continue
        href = link_el["href"]
        url = href if href.startswith("http") else f"https://www.subito.it{href}"
        external_id = url.rstrip("/").split("/")[-1]
        listings.append(Listing(
            fonte="subito",
            external_id=external_id,
            tipo="vendita" if "vendita" in url else "affitto",
            titolo=title_el.get_text(strip=True),
            prezzo=_parse_price(price_el.get_text(strip=True) if price_el else ""),
            url=url,
        ))
    return listings

def _parse_price(text: str) -> int:
    digits = "".join(c for c in text if c.isdigit())
    return int(digits) if digits else 0
```

- [ ] **Step 6: Run test, verify it passes** (adjust selectors from Step 2 if the fixture's real markup differs)

Run: `pytest tests/test_subito.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scraper/subito.py fixtures/subito_sample.html tests/test_subito.py
git commit -m "feat: add Subito.it scraper"
```

---

### Task 8: Portale Vendite Pubbliche giustizia scraper

**Files:**
- Create: `scraper/pvp_giustizia.py`
- Create: `fixtures/pvp_giustizia_sample.html` (captured manually — see Step 1)
- Test: `tests/test_pvp_giustizia.py`

**Interfaces:**
- Consumes: `Listing` (Task 2)
- Produces: `build_search_url(centro_nome: str) -> str`, `parse_listings(html: str) -> list[Listing]`, `WAIT_SELECTOR: str`. Registered in `scraper/run_all.py` (Task 9) as `PORTAL_MODULES["pvp_giustizia"]`.

- [ ] **Step 1: Capture a real fixture**

Open https://pvp.giustizia.it, search for aste immobiliari residenziali (categoria "immobili", tipo "residenziale") nella zona di Jesi/provincia di Ancona. Save the resulting page HTML to `fixtures/pvp_giustizia_sample.html` the same way as Task 7 Step 1.

- [ ] **Step 2: Inspect the fixture and identify real selectors**

Same process as Task 7 Step 2: find the listing/lotto container selector and the fields for title, prezzo base d'asta, tribunale, data asta. Update the constants in `scraper/pvp_giustizia.py` (Step 5) to match.

- [ ] **Step 3: Write failing test**

```python
# tests/test_pvp_giustizia.py
from pathlib import Path
from scraper.pvp_giustizia import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "pvp_giustizia_sample.html"

def test_build_search_url_includes_centro_nome():
    url = build_search_url("Jesi")
    assert "giustizia.it" in url
    assert "Jesi" in url or "jesi" in url.lower()

def test_parse_listings_extracts_expected_fields():
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    first = listings[0]
    assert first.fonte == "pvp_giustizia"
    assert first.tipo == "asta"
    assert first.categoria == "residenziale"
    assert first.external_id
    assert first.titolo
    assert isinstance(first.prezzo, int) and first.prezzo >= 0
    assert first.url.startswith("http")

def test_parse_listings_returns_empty_list_for_no_matches():
    assert parse_listings("<html><body>nessuna asta</body></html>") == []
```

- [ ] **Step 4: Run test, verify it fails**

Run: `pytest tests/test_pvp_giustizia.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scraper.pvp_giustizia'`

- [ ] **Step 5: Implement `scraper/pvp_giustizia.py`**

```python
from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing

WAIT_SELECTOR = "body"

# NOTA: selettori di partenza — verificare/correggere contro fixtures/pvp_giustizia_sample.html (Step 2)
SELECTOR_CARD = ".risultato-annuncio"
SELECTOR_TITLE = ".titolo-annuncio"
SELECTOR_PRICE = ".prezzo-base"
SELECTOR_TRIBUNALE = ".tribunale"
SELECTOR_DATA_ASTA = ".data-asta"
SELECTOR_LINK = "a"

def build_search_url(centro_nome: str) -> str:
    query = quote(centro_nome)
    return f"https://pvp.giustizia.it/pvp/it/risultati_ricerca.page?categoria=immobili&comune={query}"

def parse_listings(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    for card in soup.select(SELECTOR_CARD):
        title_el = card.select_one(SELECTOR_TITLE)
        price_el = card.select_one(SELECTOR_PRICE)
        link_el = card.select_one(SELECTOR_LINK)
        if not (title_el and link_el and link_el.get("href")):
            continue
        href = link_el["href"]
        url = href if href.startswith("http") else f"https://pvp.giustizia.it{href}"
        external_id = url.rstrip("/").split("/")[-1]
        tribunale_el = card.select_one(SELECTOR_TRIBUNALE)
        data_asta_el = card.select_one(SELECTOR_DATA_ASTA)
        listings.append(Listing(
            fonte="pvp_giustizia",
            external_id=external_id,
            tipo="asta",
            titolo=title_el.get_text(strip=True),
            prezzo=_parse_price(price_el.get_text(strip=True) if price_el else ""),
            url=url,
            tribunale=tribunale_el.get_text(strip=True) if tribunale_el else None,
            data_asta=data_asta_el.get_text(strip=True) if data_asta_el else None,
            offerta_minima=_parse_price(price_el.get_text(strip=True) if price_el else ""),
        ))
    return listings

def _parse_price(text: str) -> int:
    digits = "".join(c for c in text if c.isdigit())
    return int(digits) if digits else 0
```

- [ ] **Step 6: Run test, verify it passes** (adjust selectors from Step 2 if the fixture's real markup differs)

Run: `pytest tests/test_pvp_giustizia.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scraper/pvp_giustizia.py fixtures/pvp_giustizia_sample.html tests/test_pvp_giustizia.py
git commit -m "feat: add Portale Vendite Pubbliche giustizia scraper"
```

---

### Task 9: Scraper orchestrator

**Files:**
- Create: `scraper/run_all.py`
- Test: `tests/test_run_all.py`

**Interfaces:**
- Consumes: `db.connect/upsert_listing/mark_stale_as_removed` (Task 3), `fetch_html` (Task 6), `subito.build_search_url/parse_listings/WAIT_SELECTOR` (Task 7), `pvp_giustizia.build_search_url/parse_listings/WAIT_SELECTOR` (Task 8)
- Produces: `PORTAL_MODULES: dict[str, module]`, `run_all(config: dict, db_path: str) -> None`. Used by `scripts/daily.py` (Task 13).

- [ ] **Step 1: Write failing test**

```python
# tests/test_run_all.py
from scraper import run_all as run_all_module, db
from scraper.schema import Listing

FAKE_HTML = "<html><body>irrelevant, fetch_html is mocked out</body></html>"

def test_run_all_upserts_listings_from_active_portals(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    fake_listings = [
        Listing(
            fonte="subito", external_id="1", tipo="affitto",
            titolo="Bilocale", prezzo=500, url="https://example.com/1",
        )
    ]
    monkeypatch.setattr(run_all_module, "fetch_html", lambda *a, **k: FAKE_HTML)
    monkeypatch.setattr(run_all_module.subito, "parse_listings", lambda html: fake_listings)
    monkeypatch.setattr(run_all_module.pvp_giustizia, "parse_listings", lambda html: [])

    config = {"portali_attivi": ["subito", "pvp_giustizia"], "centro": {"nome": "Jesi"}}
    run_all_module.run_all(config, db_path)

    conn = db.connect(db_path)
    active = db.get_active(conn)
    assert len(active) == 1
    assert active[0]["fonte"] == "subito"

def test_run_all_skips_unregistered_portals(tmp_path, monkeypatch, capsys):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(run_all_module, "fetch_html", lambda *a, **k: FAKE_HTML)
    monkeypatch.setattr(run_all_module.subito, "parse_listings", lambda html: [])
    monkeypatch.setattr(run_all_module.pvp_giustizia, "parse_listings", lambda html: [])

    config = {"portali_attivi": ["immobiliare"], "centro": {"nome": "Jesi"}}
    run_all_module.run_all(config, db_path)

    captured = capsys.readouterr()
    assert "immobiliare" in captured.out

def test_run_all_marks_previously_seen_listings_as_removed_when_absent(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    listing = Listing(fonte="subito", external_id="1", tipo="affitto",
                       titolo="Bilocale", prezzo=500, url="https://example.com/1")

    monkeypatch.setattr(run_all_module, "fetch_html", lambda *a, **k: FAKE_HTML)
    monkeypatch.setattr(run_all_module.pvp_giustizia, "parse_listings", lambda html: [])

    config = {"portali_attivi": ["subito", "pvp_giustizia"], "centro": {"nome": "Jesi"}}

    monkeypatch.setattr(run_all_module.subito, "parse_listings", lambda html: [listing])
    run_all_module.run_all(config, db_path)

    monkeypatch.setattr(run_all_module.subito, "parse_listings", lambda html: [])
    run_all_module.run_all(config, db_path)

    conn = db.connect(db_path)
    assert db.get_active(conn) == []
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_run_all.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scraper.run_all'`

- [ ] **Step 3: Implement `scraper/run_all.py`**

```python
from . import db, subito, pvp_giustizia
from .fetch import fetch_html

PORTAL_MODULES = {
    "subito": subito,
    "pvp_giustizia": pvp_giustizia,
}

def run_all(config: dict, db_path: str) -> None:
    conn = db.connect(db_path)
    for portale in config["portali_attivi"]:
        module = PORTAL_MODULES.get(portale)
        if module is None:
            print(f"scraper non ancora implementato: {portale}, skip")
            continue
        url = module.build_search_url(config["centro"]["nome"])
        html = fetch_html(url, wait_selector=module.WAIT_SELECTOR)
        listings = module.parse_listings(html)
        seen_ids = set()
        for listing in listings:
            db.upsert_listing(conn, listing)
            seen_ids.add(listing.id)
        db.mark_stale_as_removed(conn, portale, seen_ids)
```

- [ ] **Step 4: Run test, verify it passes**

Run: `pytest tests/test_run_all.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scraper/run_all.py tests/test_run_all.py
git commit -m "feat: add scraper orchestrator wiring portals to storage"
```

---

### Task 10: Static site generator

**Files:**
- Create: `webapp/generate.py`
- Create: `webapp/template/index.html`
- Create: `webapp/template/app.js`
- Create: `webapp/template/style.css`
- Test: `tests/test_generate.py`

**Interfaces:**
- Consumes: `db.connect/get_active` (Task 3), `within_radius` (Task 5)
- Produces: `load_config(config_path: str) -> dict`, `filter_listings(listings, center_lat, center_lon, radius_km) -> list[dict]`, `generate_site(db_path, config_path, output_dir, template_dir) -> None`. Used by `scripts/daily.py` (Task 13).

- [ ] **Step 1: Write failing test**

```python
# tests/test_generate.py
import json
from webapp.generate import filter_listings, generate_site
from scraper import db
from scraper.schema import Listing

def test_filter_listings_excludes_non_residential():
    listings = [
        {"categoria": "commerciale", "lat": 43.52, "lon": 13.24},
        {"categoria": "residenziale", "lat": 43.52, "lon": 13.24},
    ]
    result = filter_listings(listings, 43.5219, 13.2437, 20)
    assert len(result) == 1
    assert result[0]["categoria"] == "residenziale"

def test_filter_listings_excludes_outside_radius():
    listings = [
        {"categoria": "residenziale", "lat": 43.52, "lon": 13.24},   # vicino a Jesi
        {"categoria": "residenziale", "lat": 45.46, "lon": 9.19},    # Milano, fuori raggio
    ]
    result = filter_listings(listings, 43.5219, 13.2437, 20)
    assert len(result) == 1

def test_generate_site_writes_filtered_data_json(tmp_path):
    db_path = str(tmp_path / "test.db")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "centro:\n  nome: Jesi\n  lat: 43.5219\n  lon: 13.2437\nraggio_km: 20\n"
    )
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "index.html").write_text("<html></html>")
    output_dir = tmp_path / "build"

    conn = db.connect(db_path)
    listing = Listing(fonte="subito", external_id="1", tipo="affitto",
                       titolo="Bilocale", prezzo=500, url="https://example.com/1",
                       lat=43.52, lon=13.24)
    db.upsert_listing(conn, listing)

    generate_site(db_path, str(config_path), str(output_dir), str(template_dir))

    data = json.loads((output_dir / "data.json").read_text())
    assert len(data) == 1
    assert data[0]["fonte"] == "subito"
    assert (output_dir / "index.html").exists()
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_generate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.generate'`

- [ ] **Step 3: Implement `webapp/generate.py`**

```python
import json
import shutil
from pathlib import Path
import yaml
from scraper import db
from scraper.radius import within_radius

def load_config(config_path: str) -> dict:
    return yaml.safe_load(Path(config_path).read_text())

def filter_listings(listings: list[dict], center_lat: float, center_lon: float, radius_km: float) -> list[dict]:
    return [
        l for l in listings
        if l.get("categoria") == "residenziale"
        and within_radius(center_lat, center_lon, l.get("lat"), l.get("lon"), radius_km)
    ]

def generate_site(db_path: str, config_path: str, output_dir: str, template_dir: str) -> None:
    config = load_config(config_path)
    conn = db.connect(db_path)
    listings = db.get_active(conn)
    filtered = filter_listings(
        listings,
        config["centro"]["lat"],
        config["centro"]["lon"],
        config["raggio_km"],
    )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template_dir, out, dirs_exist_ok=True)
    (out / "data.json").write_text(json.dumps(filtered, indent=2, default=str))
```

- [ ] **Step 4: Write `webapp/template/index.html`**

```html
<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8" />
  <title>Case Affitto Aste Vendite — Jesi</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <h1>Case, affitti e aste — zona Jesi</h1>
  <form id="filters">
    <select id="f-tipo">
      <option value="">Tutti i tipi</option>
      <option value="affitto">Affitto</option>
      <option value="vendita">Vendita</option>
      <option value="asta">Asta</option>
    </select>
    <input id="f-prezzo-min" type="number" placeholder="Prezzo min" />
    <input id="f-prezzo-max" type="number" placeholder="Prezzo max" />
    <input id="f-mq-min" type="number" placeholder="Mq min" />
    <input id="f-mq-max" type="number" placeholder="Mq max" />
    <input id="f-comune" type="text" placeholder="Comune" />
    <select id="f-fonte">
      <option value="">Tutte le fonti</option>
    </select>
    <select id="f-disponibilita">
      <option value="">Disponibilita: tutte</option>
      <option value="libero">Libero</option>
      <option value="occupato">Occupato</option>
    </select>
    <select id="f-arredato">
      <option value="">Arredato: tutti</option>
      <option value="si">Si</option>
      <option value="no">No</option>
    </select>
  </form>
  <div id="listings"></div>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 5: Write `webapp/template/app.js`**

```javascript
async function main() {
  const response = await fetch("data.json");
  const listings = await response.json();
  populateFonteOptions(listings);
  render(listings);
  document.getElementById("filters").addEventListener("input", () => render(listings));
}

function populateFonteOptions(listings) {
  const select = document.getElementById("f-fonte");
  const fonti = [...new Set(listings.map((l) => l.fonte))].sort();
  for (const fonte of fonti) {
    const opt = document.createElement("option");
    opt.value = fonte;
    opt.textContent = fonte;
    select.appendChild(opt);
  }
}

function applyFilters(listings) {
  const tipo = document.getElementById("f-tipo").value;
  const prezzoMin = parseFloat(document.getElementById("f-prezzo-min").value) || null;
  const prezzoMax = parseFloat(document.getElementById("f-prezzo-max").value) || null;
  const mqMin = parseFloat(document.getElementById("f-mq-min").value) || null;
  const mqMax = parseFloat(document.getElementById("f-mq-max").value) || null;
  const comune = document.getElementById("f-comune").value.trim().toLowerCase();
  const fonte = document.getElementById("f-fonte").value;
  const disponibilita = document.getElementById("f-disponibilita").value;
  const arredato = document.getElementById("f-arredato").value;

  return listings.filter((l) => {
    if (tipo && l.tipo !== tipo) return false;
    if (prezzoMin !== null && l.prezzo < prezzoMin) return false;
    if (prezzoMax !== null && l.prezzo > prezzoMax) return false;
    if (mqMin !== null && (l.superficie_mq === null || l.superficie_mq < mqMin)) return false;
    if (mqMax !== null && (l.superficie_mq === null || l.superficie_mq > mqMax)) return false;
    if (comune && !(l.comune || "").toLowerCase().includes(comune)) return false;
    if (fonte && l.fonte !== fonte) return false;
    if (disponibilita && l.stato_disponibilita !== disponibilita) return false;
    if (arredato && l.arredato !== arredato) return false;
    return true;
  });
}

function render(allListings) {
  const filtered = applyFilters(allListings);
  const container = document.getElementById("listings");
  container.innerHTML = filtered
    .map(
      (l) => `
      <div class="card">
        <h3><a href="${l.url}" target="_blank" rel="noopener">${l.titolo}</a></h3>
        <p>${l.tipo} — ${l.prezzo}€ — ${l.comune || ""} — ${l.fonte}</p>
        <p>${l.superficie_mq ? l.superficie_mq + " mq" : ""} ${l.arredato !== "non_specificato" ? "· arredato: " + l.arredato : ""}</p>
      </div>`
    )
    .join("");
  if (filtered.length === 0) {
    container.innerHTML = "<p>Nessun annuncio corrisponde ai filtri.</p>";
  }
}

main();
```

- [ ] **Step 6: Write `webapp/template/style.css`**

```css
body { font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }
#filters { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1.5rem; }
#filters input, #filters select { padding: 0.4rem; }
.card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; }
.card h3 { margin: 0 0 0.25rem 0; }
```

- [ ] **Step 7: Run test, verify it passes**

Run: `pytest tests/test_generate.py -v`
Expected: PASS (3 tests)

- [ ] **Step 8: Commit**

```bash
git add webapp/generate.py webapp/template tests/test_generate.py
git commit -m "feat: add static site generator with client-side filters"
```

---

### Task 11: Publisher

**Files:**
- Create: `scripts/publish.py`
- Test: `tests/test_publish.py`

**Interfaces:**
- Produces: `publish(build_dir: str = "webapp/build", branch: str = "gh-pages") -> None`. Used by `scripts/daily.py` (Task 13).

- [ ] **Step 1: Write failing test**

```python
# tests/test_publish.py
import pytest
from scripts import publish as publish_module

def test_publish_raises_if_build_dir_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        publish_module.publish(build_dir="webapp/build")

def test_publish_skips_commit_when_no_changes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "webapp" / "build").mkdir(parents=True)
    calls = []

    def fake_run(cmd, check=False, **kwargs):
        calls.append(cmd)
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(publish_module.subprocess, "run", fake_run)
    publish_module.publish(build_dir="webapp/build")

    assert any(c[:2] == ["git", "diff"] for c in calls)
    assert not any(c[:2] == ["git", "commit"] for c in calls)
    assert "nessuna modifica" in capsys.readouterr().out

def test_publish_commits_and_pushes_when_changed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "webapp" / "build").mkdir(parents=True)
    calls = []

    def fake_run(cmd, check=False, **kwargs):
        calls.append(cmd)
        class Result:
            returncode = 1 if cmd[:2] == ["git", "diff"] else 0
        return Result()

    monkeypatch.setattr(publish_module.subprocess, "run", fake_run)
    publish_module.publish(build_dir="webapp/build", branch="gh-pages")

    assert any(c[:2] == ["git", "commit"] for c in calls)
    assert any("subtree" in c for c in calls)
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_publish.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.publish'`

- [ ] **Step 3: Implement `scripts/publish.py`**

```python
import subprocess
from pathlib import Path

def publish(build_dir: str = "webapp/build", branch: str = "gh-pages") -> None:
    build_path = Path(build_dir)
    if not build_path.exists():
        raise FileNotFoundError(f"build dir non trovata: {build_dir}")

    subprocess.run(["git", "add", "-f", build_dir], check=True)
    diff_result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if diff_result.returncode == 0:
        print("nessuna modifica al sito, skip pubblicazione")
        return

    subprocess.run(["git", "commit", "-m", "chore: aggiorna sito"], check=True)
    subprocess.run(["git", "subtree", "push", "--prefix", build_dir, "origin", branch], check=True)
```

- [ ] **Step 4: Run test, verify it passes**

Run: `pytest tests/test_publish.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/publish.py tests/test_publish.py
git commit -m "feat: add GitHub Pages publisher via git subtree push"
```

---

### Task 12: Notifier digest

**Files:**
- Create: `notifier/digest.py`
- Create: `notifier/email_template.html`
- Test: `tests/test_digest.py`

**Interfaces:**
- Consumes: `db.connect/get_new_since` (Task 3)
- Produces: `build_digest_html(listings, template_path) -> str`, `send_digest(smtp_user, smtp_password, recipients, html_body) -> None`, `run_weekly_digest(db_path, config, smtp_user, smtp_password) -> None`. Used by `scripts/weekly.py` (Task 13).

- [ ] **Step 1: Write failing test**

```python
# tests/test_digest.py
from pathlib import Path
from notifier import digest

TEMPLATE = "<html><body><p>{{COUNT}} nuovi annunci</p><ul>{{LISTINGS}}</ul></body></html>"

def test_build_digest_html_with_no_listings(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text(TEMPLATE)
    html = digest.build_digest_html([], template_path=str(template_path))
    assert "Nessun nuovo annuncio" in html

def test_build_digest_html_with_listings(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text(TEMPLATE)
    listings = [{"titolo": "Bilocale", "comune": "Jesi", "prezzo": 500, "fonte": "subito", "url": "https://example.com/1"}]
    html = digest.build_digest_html(listings, template_path=str(template_path))
    assert "Bilocale" in html
    assert "1 nuovi annunci" in html

def test_send_digest_skips_when_no_recipients(monkeypatch):
    called = []
    monkeypatch.setattr(digest.smtplib, "SMTP_SSL", lambda *a, **k: called.append(True))
    digest.send_digest("user@example.com", "pw", [], "<html></html>")
    assert called == []

def test_send_digest_sends_via_smtp(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def login(self, user, pw): sent["login"] = (user, pw)
        def sendmail(self, from_addr, to_addrs, msg): sent["sendmail"] = (from_addr, to_addrs)

    monkeypatch.setattr(digest.smtplib, "SMTP_SSL", lambda *a, **k: FakeSMTP())
    digest.send_digest("user@example.com", "pw", ["dest@example.com"], "<html></html>")
    assert sent["login"] == ("user@example.com", "pw")
    assert sent["sendmail"][1] == ["dest@example.com"]
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_digest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'notifier.digest'`

- [ ] **Step 3: Write `notifier/email_template.html`**

```html
<!DOCTYPE html>
<html lang="it">
<body>
  <h2>Case Affitto Aste Vendite — nuovi annunci questa settimana</h2>
  <p>{{COUNT}} nuovi annunci trovati.</p>
  <ul>{{LISTINGS}}</ul>
</body>
</html>
```

- [ ] **Step 4: Implement `notifier/digest.py`**

```python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date, timedelta
from pathlib import Path
from scraper import db

def build_digest_html(listings: list[dict], template_path: str = "notifier/email_template.html") -> str:
    template = Path(template_path).read_text(encoding="utf-8")
    if not listings:
        rows = "<p>Nessun nuovo annuncio questa settimana.</p>"
    else:
        rows = "".join(
            f'<li><a href="{l["url"]}">{l["titolo"]}</a> — {l["comune"]}, {l["prezzo"]}€ ({l["fonte"]})</li>'
            for l in listings
        )
    return template.replace("{{LISTINGS}}", rows).replace("{{COUNT}}", str(len(listings)))

def send_digest(smtp_user: str, smtp_password: str, recipients: list[str], html_body: str) -> None:
    if not recipients:
        print("nessun destinatario configurato, skip invio")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Case Affitto Aste Vendite — nuovi annunci questa settimana"
    msg["From"] = smtp_user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, recipients, msg.as_string())

def run_weekly_digest(db_path: str, config: dict, smtp_user: str, smtp_password: str) -> None:
    conn = db.connect(db_path)
    since = (date.today() - timedelta(days=7)).isoformat()
    new_listings = db.get_new_since(conn, since)
    html = build_digest_html(new_listings)
    send_digest(smtp_user, smtp_password, config["email"]["destinatari"], html)
```

- [ ] **Step 5: Run test, verify it passes**

Run: `pytest tests/test_digest.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add notifier/digest.py notifier/email_template.html tests/test_digest.py
git commit -m "feat: add weekly email digest builder and sender"
```

---

### Task 13: Orchestration entrypoints and Task Scheduler setup

**Files:**
- Create: `scripts/daily.py`
- Create: `scripts/weekly.py`
- Modify: `README.md` (add Task Scheduler section)
- Test: `tests/test_entrypoints.py`

**Interfaces:**
- Consumes: `run_all` (Task 9), `generate_site` (Task 10), `publish` (Task 11), `run_weekly_digest` (Task 12)
- Produces: `daily_main() -> None`, `weekly_main() -> None` — the two callables Task Scheduler invokes via `python -m scripts.daily` / `python -m scripts.weekly`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_entrypoints.py
from scripts import daily, weekly

def test_daily_main_calls_pipeline_in_order(monkeypatch):
    calls = []
    monkeypatch.setattr(daily, "load_dotenv", lambda: None)
    monkeypatch.setattr(daily.yaml, "safe_load", lambda text: {"portali_attivi": [], "centro": {"nome": "Jesi"}})
    monkeypatch.setattr(daily.Path, "read_text", lambda self: "")
    monkeypatch.setattr(daily, "run_all", lambda config, db_path: calls.append(("run_all", db_path)))
    monkeypatch.setattr(daily, "generate_site", lambda *a: calls.append(("generate_site", a)))
    monkeypatch.setattr(daily, "publish", lambda build_dir: calls.append(("publish", build_dir)))

    daily.daily_main()

    assert [c[0] for c in calls] == ["run_all", "generate_site", "publish"]

def test_weekly_main_calls_digest(monkeypatch):
    calls = []
    monkeypatch.setattr(weekly, "load_dotenv", lambda: None)
    monkeypatch.setattr(weekly.yaml, "safe_load", lambda text: {"email": {"destinatari": []}})
    monkeypatch.setattr(weekly.Path, "read_text", lambda self: "")
    monkeypatch.setattr(weekly.os, "environ", {"SMTP_USER": "u@example.com", "GMAIL_APP_PASSWORD": "pw"})
    monkeypatch.setattr(weekly, "run_weekly_digest", lambda db_path, config, user, pw: calls.append((db_path, user, pw)))

    weekly.weekly_main()

    assert calls == [("data/listings.db", "u@example.com", "pw")]
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_entrypoints.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.daily'`

- [ ] **Step 3: Implement `scripts/daily.py`**

```python
import yaml
from pathlib import Path
from dotenv import load_dotenv
from scraper.run_all import run_all
from webapp.generate import generate_site
from .publish import publish

def daily_main() -> None:
    load_dotenv()
    config = yaml.safe_load(Path("config.yaml").read_text())
    run_all(config, "data/listings.db")
    generate_site("data/listings.db", "config.yaml", "webapp/build", "webapp/template")
    publish("webapp/build")

if __name__ == "__main__":
    daily_main()
```

- [ ] **Step 4: Implement `scripts/weekly.py`**

```python
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from notifier.digest import run_weekly_digest

def weekly_main() -> None:
    load_dotenv()
    config = yaml.safe_load(Path("config.yaml").read_text())
    run_weekly_digest(
        "data/listings.db",
        config,
        os.environ["SMTP_USER"],
        os.environ["GMAIL_APP_PASSWORD"],
    )

if __name__ == "__main__":
    weekly_main()
```

- [ ] **Step 5: Run test, verify it passes**

Run: `pytest tests/test_entrypoints.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Add Task Scheduler section to `README.md`**

```markdown
## Task Scheduler (Windows)

Crea due attivita programmate (Task Scheduler GUI o `schtasks`), entrambe con
"Start in" impostato sulla cartella del progetto:

Giornaliero (ogni giorno, es. 07:00):
schtasks /create /tn "CaseAffittoAsteVendite-Daily" /tr "\"C:\path\to\venv\Scripts\pythonw.exe\" -m scripts.daily" /sc daily /st 07:00 /sd 01/01/2026

Settimanale (ogni lunedi, dopo il job giornaliero, es. 08:00):
schtasks /create /tn "CaseAffittoAsteVendite-Weekly" /tr "\"C:\path\to\venv\Scripts\pythonw.exe\" -m scripts.weekly" /sc weekly /d MON /st 08:00 /sd 01/01/2026

Sostituisci `C:\path\to\venv` con il percorso reale del virtualenv creato nel
Setup. Se il PC e spento all'orario schedulato, il job viene saltato quel giorno.
```

- [ ] **Step 7: Commit**

```bash
git add scripts/daily.py scripts/weekly.py README.md tests/test_entrypoints.py
git commit -m "feat: add daily/weekly entrypoints and Task Scheduler setup docs"
```

---

### Task 14: End-to-end manual smoke test

Not a pytest task — this is the acceptance check that the real pipeline works against live sites, which cannot be safely automated (live network, real Gmail send).

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite one more time**

Run: `pytest -v`
Expected: all tests from Tasks 1-13 PASS

- [ ] **Step 2: Run the daily pipeline for real**

Run: `python -m scripts.daily`
Expected: completes without exceptions; `webapp/build/data.json` contains at least one listing from Subito or PVP giustizia within 20km of Jesi; check by opening `webapp/build/index.html` in a browser and confirming cards render and filters work.

- [ ] **Step 3: Verify GitHub Pages**

Confirm a GitHub repo exists for this project with a remote named `origin`, and that GitHub Pages is configured to serve from the `gh-pages` branch (repo Settings → Pages). Visit the published URL and confirm listings appear.

- [ ] **Step 4: Add at least one real recipient and run the weekly digest for real**

Edit `config.yaml` → `email.destinatari` to include your own email address, commit the change, then:

Run: `python -m scripts.weekly`
Expected: no exceptions; digest email arrives in the configured inbox within a few minutes, listing items seen in the last 7 days (or "Nessun nuovo annuncio" if the DB has no recent first-seen listings).

- [ ] **Step 5: Commit any config changes**

```bash
git add config.yaml
git commit -m "chore: configure email recipient for weekly digest"
```
