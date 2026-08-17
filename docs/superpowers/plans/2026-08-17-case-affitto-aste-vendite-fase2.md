# Case Affitto Aste Vendite — Fase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estendere la pipeline Fase 1 (già live, 2 portali) con il campo `chi_vende` (privato/agenzia) sui portali esistenti, e aggiungere 5 nuovi portali richiesti dall'utente: Idealista, Immobiliare.it, astegiudiziarie.it, asteimmobili.it, portaleaste — riusando invariata l'infrastruttura Fase 1 (schema, DB, orchestratore, generatore sito, digest).

**Architecture:** Nessun cambio architetturale. Ogni nuovo portale è un modulo `scraper/<nome>.py` che produce `Listing` e si registra in `PORTAL_MODULES` (pattern già supportato da Fase 1 Task 9). Il campo `chi_vende` è un'estensione additiva dello schema esistente, con migrazione SQLite non distruttiva sul DB di produzione già popolato (67 righe reali al momento della scrittura di questo piano).

**Tech Stack:** Invariato da Fase 1 — Python 3.11+, Playwright, BeautifulSoup4, SQLite, PyYAML, python-dotenv, pytest.

**Spec:** `Case Affitto Aste Vendite/docs/superpowers/specs/2026-08-16-case-affitto-aste-vendite-design.md`

**Riferimento Fase 1:** `Case Affitto Aste Vendite/docs/superpowers/plans/2026-08-16-case-affitto-aste-vendite-mvp.md` — stesso pattern per-task (Step 1: cattura fixture reale dal sito live, Step 2: ispeziona e fissa i selettori reali, poi TDD del parser). Questo piano lo replica identico per i 5 nuovi portali.

## Scope note

Lo spec originale elenca 8 portali (inclusa Casa.it). L'utente ha chiesto esplicitamente questi 5, non Casa.it — resta fuori scope, aggiungibile in una Fase 3 con lo stesso pattern se richiesto in futuro.

**Nota dominio non verificato:** l'utente ha scritto "portaleaste.com", lo spec originale dice "portaleaste.it" — nessuno dei due è verificato. Task 10 Step 1 risolve il dominio reale prima di scrivere qualunque selettore (non va indovinato né dato per buono da questo piano).

**Rischio anti-bot (dal rischio noto nello spec):** Idealista e Immobiliare.it hanno protezioni anti-bot esplicitamente segnalate. I loro task (8 e 9) iniziano con uno Step 0 di verifica fattibilità — un fetch rispettoso della pagina di ricerca reale — prima di investire tempo su selettori. Se il portale blocca (CAPTCHA, pagina di verifica, 403 persistente), **non provare a aggirare la protezione** (niente rotazione IP, fingerprint spoofing, risoluzione CAPTCHA): è esattamente il caso già previsto e accettato dallo spec ("se un portale blocca in modo persistente, si esclude da config senza bloccare gli altri") — documenta il blocco nel ledger, implementa comunque il modulo con i selettori migliori disponibili da fixture pubbliche/cache, ma **non aggiungerlo a `portali_attivi` di default** nel config, e passa al task successivo.

## Global Constraints

(Ereditati identici da Fase 1 — questo piano estende lo stesso codebase.)

- Centro di ricerca default: Jesi, lat 43.5219, lon 13.2437 — configurabile in `config.yaml`.
- Raggio di ricerca default: 20 km — configurabile in `config.yaml`.
- Categoria sempre `residenziale` — nessun immobile commerciale incluso.
- Nessun login: filtri applicati lato client sul sito statico, stessi per tutti i visitatori.
- Dedup per `(fonte, external_id)` → id = hash SHA256 troncato.
- Storage: SQLite unico, nessun DB server esterno. **Il DB di produzione ha già dati reali (Fase 1): ogni modifica di schema deve migrare, non ricreare.**
- Sito pubblicato come file statici su branch `gh-pages` (GitHub Pages).
- Email via Gmail SMTP + App Password; invio saltato se nessun destinatario configurato.
- Scraping: giornaliero. Digest email: lunedì, basato su `data_first_seen` negli ultimi 7 giorni.
- Nessuna richiesta di rete nei test automatici — solo fixture salvate su disco o file locali.
- Rate limiting rispettoso, no scraping aggressivo. Se un portale blocca in modo persistente, si esclude da config senza bloccare gli altri (accettato dallo spec).

---

## File structure

**Modify:**
- `scraper/schema.py` — nuovo campo `chi_vende: Optional[str] = None` sul dataclass `Listing`, validazione valori ammessi.
- `scraper/db.py` — colonna `chi_vende TEXT` nello SCHEMA, migrazione idempotente per DB esistenti, `upsert_listing` estesa.
- `scraper/subito.py` — estrazione `chi_vende` da `advertiser.company` nel JSON `__NEXT_DATA__` già presente nella pagina (verificato: vedi Task 2).
- `scraper/pvp_giustizia.py` — `chi_vende` sempre `None`, documentato (aste giudiziarie: il venditore è il tribunale, non si applica la distinzione privato/agenzia).
- `scraper/run_all.py` — registra i 5 nuovi moduli in `PORTAL_MODULES`.
- `webapp/template/index.html`, `webapp/template/app.js` — filtro e visualizzazione `chi_vende`.
- `notifier/digest.py` — includi `chi_vende` nella riga del digest quando presente.
- `config.yaml` — aggiungi i 5 nuovi portali a `portali_attivi` (tranne quelli che risultano bloccati da anti-bot, vedi Scope note).

**Create (per ciascuno dei 5 nuovi portali):**
- `scraper/idealista.py`, `scraper/immobiliare.py`, `scraper/astegiudiziarie.py`, `scraper/asteimmobili.py`, `scraper/portaleaste.py`
- `fixtures/idealista_sample.html`, `fixtures/immobiliare_sample.html`, `fixtures/astegiudiziarie_sample.html`, `fixtures/asteimmobili_sample.html`, `fixtures/portaleaste_sample.html` (catturate manualmente, come Fase 1)
- `tests/test_idealista.py`, `tests/test_immobiliare.py`, `tests/test_astegiudiziarie.py`, `tests/test_asteimmobili.py`, `tests/test_portaleaste.py`

---

### Task 1: Campo `chi_vende` — schema e migrazione DB

**Files:**
- Modify: `scraper/schema.py`
- Modify: `scraper/db.py`
- Modify: `tests/test_schema.py`
- Modify: `tests/test_db.py`

**Interfaces:**
- Produces: `Listing.chi_vende: Optional[str]` (valori ammessi: `None`, `"privato"`, `"agenzia"`). `db.connect()` migra automaticamente DB esistenti senza la colonna. Usato da Task 2-3 (retrofit) e Task 6-10 (nuovi scraper).

- [ ] **Step 1: Scrivi il test che fallisce per lo schema**

Aggiungi in `tests/test_schema.py`:

```python
def test_chi_vende_defaults_to_none():
    l = make_listing()
    assert l.chi_vende is None

def test_validate_accepts_privato_and_agenzia():
    make_listing(chi_vende="privato").validate()
    make_listing(chi_vende="agenzia").validate()

def test_validate_rejects_invalid_chi_vende():
    with pytest.raises(ValueError):
        make_listing(chi_vende="boh").validate()
```

- [ ] **Step 2: Esegui, verifica che fallisca**

Run: `pytest tests/test_schema.py -v`
Expected: FAIL (`chi_vende` non esiste sul dataclass, `TypeError`)

- [ ] **Step 3: Implementa in `scraper/schema.py`**

Aggiungi il campo al dataclass (dopo `offerta_minima`) e la validazione:

```python
    offerta_minima: Optional[int] = None
    chi_vende: Optional[str] = None
```

```python
    def validate(self) -> None:
        if self.tipo not in TIPI_VALIDI:
            raise ValueError(f"tipo non valido: {self.tipo}")
        if not self.fonte or not self.external_id:
            raise ValueError("fonte e external_id sono obbligatori")
        if not self.url:
            raise ValueError("url obbligatorio")
        if self.prezzo is not None and self.prezzo < 0:
            raise ValueError("prezzo non puo essere negativo")
        if self.chi_vende is not None and self.chi_vende not in ("privato", "agenzia"):
            raise ValueError(f"chi_vende non valido: {self.chi_vende}")
```

- [ ] **Step 4: Esegui, verifica che passi**

Run: `pytest tests/test_schema.py -v`
Expected: PASS

- [ ] **Step 5: Scrivi il test di migrazione DB che fallisce**

Aggiungi in `tests/test_db.py`:

```python
import sqlite3

def test_connect_migrates_existing_db_missing_chi_vende_column(tmp_path):
    db_path = str(tmp_path / "old.db")
    # Simula un DB creato da una versione precedente dello schema (senza chi_vende)
    raw = sqlite3.connect(db_path)
    raw.execute("""
        CREATE TABLE listings (
            id TEXT PRIMARY KEY, fonte TEXT NOT NULL, external_id TEXT NOT NULL,
            tipo TEXT NOT NULL, categoria TEXT NOT NULL DEFAULT 'residenziale',
            titolo TEXT, prezzo INTEGER, superficie_mq INTEGER, locali INTEGER,
            comune TEXT, lat REAL, lon REAL, stato_disponibilita TEXT,
            data_disponibilita TEXT, arredato TEXT, url TEXT, data_pubblicazione TEXT,
            data_first_seen TEXT NOT NULL, data_last_seen TEXT NOT NULL,
            stato_annuncio TEXT NOT NULL DEFAULT 'attivo', tribunale TEXT,
            data_asta TEXT, offerta_minima INTEGER
        )
    """)
    raw.execute(
        "INSERT INTO listings (id, fonte, external_id, tipo, titolo, prezzo, url, "
        "data_first_seen, data_last_seen) VALUES ('x','subito','1','affitto','T',500,"
        "'https://example.com/1','2026-08-01','2026-08-01')"
    )
    raw.commit()
    raw.close()

    conn = db.connect(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    assert "chi_vende" in cols
    # la riga preesistente non deve andare persa dalla migrazione
    rows = db.get_active(conn)
    assert len(rows) == 1
    assert rows[0]["chi_vende"] is None

def test_upsert_listing_stores_chi_vende(tmp_path):
    conn = db.connect(str(tmp_path / "test.db"))
    listing = make_listing()
    listing.chi_vende = "agenzia"
    db.upsert_listing(conn, listing, today="2026-08-10")
    rows = db.get_active(conn)
    assert rows[0]["chi_vende"] == "agenzia"
```

- [ ] **Step 6: Esegui, verifica che fallisca**

Run: `pytest tests/test_db.py -v`
Expected: FAIL (colonna `chi_vende` non esiste)

- [ ] **Step 7: Implementa la migrazione in `scraper/db.py`**

Aggiungi `chi_vende TEXT` allo SCHEMA (dopo `offerta_minima INTEGER`):

```python
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
    offerta_minima INTEGER,
    chi_vende TEXT
);
"""

def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    _migrate(conn)
    conn.commit()
    return conn

def _migrate(conn: sqlite3.Connection) -> None:
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    if "chi_vende" not in existing_cols:
        conn.execute("ALTER TABLE listings ADD COLUMN chi_vende TEXT")
```

Aggiorna `upsert_listing` (INSERT statement, ON CONFLICT, e tupla dei valori):

```python
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
            tribunale, data_asta, offerta_minima, chi_vende)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            prezzo=excluded.prezzo, superficie_mq=excluded.superficie_mq, locali=excluded.locali,
            comune=excluded.comune, lat=excluded.lat, lon=excluded.lon,
            stato_disponibilita=excluded.stato_disponibilita,
            data_disponibilita=excluded.data_disponibilita,
            arredato=excluded.arredato, data_last_seen=excluded.data_last_seen,
            stato_annuncio='attivo', chi_vende=excluded.chi_vende
        """,
        (listing.id, listing.fonte, listing.external_id, listing.tipo, listing.categoria,
         listing.titolo, listing.prezzo, listing.superficie_mq, listing.locali, listing.comune,
         listing.lat, listing.lon, listing.stato_disponibilita, listing.data_disponibilita,
         listing.arredato, listing.url, listing.data_pubblicazione, first_seen, today, "attivo",
         listing.tribunale, listing.data_asta, listing.offerta_minima, listing.chi_vende),
    )
    conn.commit()
```

- [ ] **Step 8: Esegui, verifica che passi**

Run: `pytest tests/test_db.py tests/test_schema.py -v`
Expected: PASS (tutti i test, vecchi e nuovi)

- [ ] **Step 9: Migra il DB di produzione**

Il DB reale (`data/listings.db`, 67 righe da Fase 1) viene migrato automaticamente alla prossima chiamata di `db.connect()` (es. il prossimo `python -m scripts.daily`) — non serve nessuno script manuale, `_migrate` è idempotente e sicuro da rieseguire. Verifica comunque una volta con:

```bash
python -c "from scraper import db; conn = db.connect('data/listings.db'); print([r[1] for r in conn.execute('PRAGMA table_info(listings)')])"
```

Expected: la lista di colonne include `chi_vende`, e `sqlite3.connect('data/listings.db').execute('SELECT COUNT(*) FROM listings').fetchone()` restituisce ancora 67 (o più, se nel frattempo è girato un altro daily).

- [ ] **Step 10: Commit**

```bash
git add scraper/schema.py scraper/db.py tests/test_schema.py tests/test_db.py
git commit -m "feat: add chi_vende field with non-destructive DB migration"
```

---

### Task 2: `chi_vende` su Subito.it — da `__NEXT_DATA__`, non dal DOM

**Files:**
- Modify: `scraper/subito.py`
- Modify: `tests/test_subito.py`

**Interfaces:**
- Consumes: `Listing.chi_vende` (Task 1)
- Produces: `parse_listings()` popola `chi_vende` per ogni annuncio Subito quando disponibile.

**Perché non dal DOM:** le card HTML della fixture non espongono un badge privato/agenzia visibile via CSS. La pagina però incorpora un blob JSON completo in `<script id="__NEXT_DATA__" type="application/json">` (stato Next.js), che contiene per ogni annuncio un oggetto `"advertiser":{"name":...,"company":true|false}` — verificato contro `fixtures/subito_sample.html` (28 annunci, ognuno con urn tipo `"id:ad:610830558:list:651171551"`, dove `651171551` è lo stesso ID numerico che compare in fondo all'URL della card, es. `.../appartamento-riviera-adriatica-ancona-651171551.htm`). `company: true` → annuncio di agenzia, `company: false` → privato.

- [ ] **Step 1: Scrivi il test che fallisce**

Aggiungi in `tests/test_subito.py`:

```python
def test_parse_listings_sets_chi_vende_from_next_data(monkeypatch):
    monkeypatch.setattr(subito_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    # il primo annuncio della fixture ("Appartamento riviera adriatica",
    # advertiser "alfio amici") ha company:false nel JSON __NEXT_DATA__ reale
    assert listings[0].chi_vende == "privato"
    assert any(l.chi_vende == "agenzia" for l in listings)
```

- [ ] **Step 2: Esegui, verifica che fallisca**

Run: `pytest tests/test_subito.py -v`
Expected: FAIL (`chi_vende` è sempre `None`, l'assert sul primo annuncio fallisce)

- [ ] **Step 3: Implementa in `scraper/subito.py`**

Aggiungi import e funzioni helper (in cima al file, dopo gli import esistenti):

```python
import json
import re
```

Aggiungi le funzioni helper (dopo `_extract_comune`, prima di `_parse_price`):

```python
def _parse_next_data(html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except json.JSONDecodeError:
        return None


def _find_ads_list(node):
    """Cerca ricorsivamente la lista di oggetti annuncio dentro __NEXT_DATA__.

    Non si assume il percorso esatto delle chiavi (es. props.pageProps...items.
    originalList): la struttura di Next.js puo' variare tra categorie/pagine.
    Si riconosce la lista giusta dalla forma degli elementi: dict con sia
    "urn" che "advertiser", che e' la firma stabile di un oggetto annuncio
    verificata su fixtures/subito_sample.html.
    """
    if isinstance(node, list):
        if node and all(isinstance(item, dict) and "urn" in item and "advertiser" in item for item in node):
            return node
        for item in node:
            found = _find_ads_list(item)
            if found is not None:
                return found
    elif isinstance(node, dict):
        for value in node.values():
            found = _find_ads_list(value)
            if found is not None:
                return found
    return None


def _build_chi_vende_lookup(html: str) -> dict[str, str]:
    data = _parse_next_data(html)
    if not data:
        return {}
    ads = _find_ads_list(data) or []
    lookup = {}
    for ad in ads:
        match = re.search(r":list:(\d+)$", ad.get("urn", ""))
        if not match:
            continue
        company = ad.get("advertiser", {}).get("company")
        if company is True:
            lookup[match.group(1)] = "agenzia"
        elif company is False:
            lookup[match.group(1)] = "privato"
    return lookup


def _numeric_id_from_url(url: str) -> str | None:
    match = re.search(r"-(\d+)\.htm$", url)
    return match.group(1) if match else None
```

Modifica `parse_listings` per costruire la lookup una volta e usarla per ogni card:

```python
def parse_listings(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    tipo = _detect_tipo(soup)
    chi_vende_lookup = _build_chi_vende_lookup(html)
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

        comune = _extract_comune(card)
        lat = lon = None
        if comune:
            try:
                lat, lon = geocode_fn(comune)
            except GeocodeError:
                pass

        numeric_id = _numeric_id_from_url(url)
        chi_vende = chi_vende_lookup.get(numeric_id) if numeric_id else None

        listings.append(Listing(
            fonte="subito",
            external_id=external_id,
            tipo=tipo,
            titolo=title_el.get_text(strip=True),
            prezzo=_parse_price(price_el.get_text(strip=True) if price_el else ""),
            url=url,
            comune=comune,
            lat=lat,
            lon=lon,
            chi_vende=chi_vende,
        ))
    return listings
```

- [ ] **Step 4: Esegui, verifica che passi**

Run: `pytest tests/test_subito.py -v`
Expected: PASS (tutti i test)

- [ ] **Step 5: Commit**

```bash
git add scraper/subito.py tests/test_subito.py
git commit -m "feat: extract chi_vende (privato/agenzia) from Subito __NEXT_DATA__"
```

---

### Task 3: `chi_vende` su PVP giustizia — sempre `None`, documentato

**Files:**
- Modify: `scraper/pvp_giustizia.py`
- Modify: `tests/test_pvp_giustizia.py`

**Interfaces:**
- Consumes: `Listing.chi_vende` (Task 1)

Le aste giudiziarie non hanno un "venditore" nel senso privato/agenzia: il
soggetto che vende è il tribunale/procedura esecutiva. Forzare uno dei due
valori sarebbe un dato falso, non mancante — resta `None` esplicitamente,
stesso trattamento già riservato a `tribunale` in questo modulo.

- [ ] **Step 1: Scrivi il test che fallisce**

Aggiungi in `tests/test_pvp_giustizia.py`:

```python
def test_parse_listings_chi_vende_is_always_none(monkeypatch):
    # Le aste giudiziarie non hanno un venditore privato/agenzia: il
    # "venditore" e' la procedura esecutiva, non una delle due categorie.
    monkeypatch.setattr(pvp_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    assert all(l.chi_vende is None for l in listings)
```

- [ ] **Step 2: Esegui, verifica che passi già**

Run: `pytest tests/test_pvp_giustizia.py -v`
Expected: PASS — `chi_vende` di `Listing` è già `None` di default (Task 1), quindi questo test documenta e blocca la scelta esplicitamente senza richiedere modifiche al parser.

- [ ] **Step 3: Aggiungi il commento esplicativo in `scraper/pvp_giustizia.py`**

Nel blocco `listings.append(Listing(...))`, aggiungi (accanto a `tribunale=None`):

```python
            tribunale=None,  # non disponibile nella vista elenco (vedi nota sopra)
            chi_vende=None,  # aste giudiziarie: venditore e' la procedura esecutiva, non privato/agenzia
```

- [ ] **Step 4: Esegui di nuovo, conferma nessuna regressione**

Run: `pytest tests/test_pvp_giustizia.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scraper/pvp_giustizia.py tests/test_pvp_giustizia.py
git commit -m "docs: document chi_vende=None for judicial auctions (no private/agency seller)"
```

---

### Task 4: `chi_vende` nel sito statico (filtro + visualizzazione)

**Files:**
- Modify: `webapp/template/index.html`
- Modify: `webapp/template/app.js`

**Interfaces:**
- Consumes: campo `chi_vende` già presente in `data.json` (nessuna modifica a `webapp/generate.py` — `filter_listings`/`generate_site` fanno già pass-through di tutte le colonne restituite da `db.get_active`, `chi_vende` incluso, dal momento che Task 1 lo aggiunge alla tabella).

**Nota sui test:** `webapp/template/app.js` non ha una suite di test automatica in questo progetto (JS vanilla senza harness, scelta già di Fase 1 — vedi `webapp/generate.py` per l'unica parte testata in Python). Questo task non introduce un'eccezione: verifica manuale in browser, come già accade per il resto del frontend.

- [ ] **Step 1: Aggiungi il filtro in `webapp/template/index.html`**

Nel form `#filters`, dopo il blocco `#f-arredato`:

```html
    <select id="f-chi-vende">
      <option value="">Privato/Agenzia: tutti</option>
      <option value="privato">Privato</option>
      <option value="agenzia">Agenzia</option>
    </select>
```

- [ ] **Step 2: Aggiungi la logica filtro in `webapp/template/app.js`**

In `applyFilters`, dopo la riga `const arredato = ...`:

```javascript
  const chiVende = document.getElementById("f-chi-vende").value;
```

E nel blocco `return listings.filter(...)`, dopo il check `arredato`:

```javascript
    if (chiVende && l.chi_vende !== chiVende) return false;
```

- [ ] **Step 3: Mostra `chi_vende` nella card, in `render`**

Nel blocco che costruisce `p2` (dettagli superficie/arredato), estendi `detailParts`:

```javascript
    const p2 = document.createElement("p");
    const mqText = l.superficie_mq ? l.superficie_mq + " mq" : "";
    const arredatoText = l.arredato && l.arredato !== "non_specificato" ? "· arredato: " + l.arredato : "";
    const chiVendeText = l.chi_vende ? "· " + l.chi_vende : "";
    const detailParts = [mqText, arredatoText, chiVendeText].filter(s => s);
    p2.textContent = detailParts.join(" ");
    card.appendChild(p2);
```

- [ ] **Step 4: Verifica manuale**

Rigenera il sito e apri in browser:

```bash
python -c "from webapp.generate import generate_site; generate_site('data/listings.db', 'config.yaml', 'webapp/build', 'webapp/template')"
```

Apri `webapp/build/index.html` nel browser: conferma che il menu "Privato/Agenzia" appare, filtra correttamente, e le card mostrano "· privato" o "· agenzia" quando il dato è presente (assente per gli annunci PVP giustizia, come atteso).

- [ ] **Step 5: Commit**

```bash
git add webapp/template/index.html webapp/template/app.js
git commit -m "feat: add chi_vende filter and display to static site"
```

---

### Task 5: `chi_vende` nel digest email

**Files:**
- Modify: `notifier/digest.py`
- Modify: `tests/test_digest.py`

**Interfaces:**
- Consumes: `chi_vende` dai dict restituiti da `db.get_new_since` (Task 1)

- [ ] **Step 1: Scrivi il test che fallisce**

Aggiungi in `tests/test_digest.py`:

```python
def test_build_digest_html_includes_chi_vende_when_present(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text(TEMPLATE)
    listings = [
        {"titolo": "Bilocale", "comune": "Jesi", "prezzo": 500, "fonte": "subito",
         "url": "https://example.com/1", "chi_vende": "agenzia"}
    ]
    html = digest.build_digest_html(listings, template_path=str(template_path))
    assert "agenzia" in html

def test_build_digest_html_omits_chi_vende_when_absent(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text(TEMPLATE)
    listings = [
        {"titolo": "Lotto n. 1", "comune": "Jesi", "prezzo": 1000, "fonte": "pvp_giustizia",
         "url": "https://example.com/1", "chi_vende": None}
    ]
    html = digest.build_digest_html(listings, template_path=str(template_path))
    assert "Lotto n. 1" in html
```

- [ ] **Step 2: Esegui, verifica che fallisca**

Run: `pytest tests/test_digest.py -v`
Expected: FAIL (`KeyError: 'chi_vende'` — il dict access diretto non gestisce il campo)

- [ ] **Step 3: Implementa in `notifier/digest.py`**

Modifica la costruzione di `rows` in `build_digest_html`:

```python
def build_digest_html(listings: list[dict], template_path: str = "notifier/email_template.html") -> str:
    template = Path(template_path).read_text(encoding="utf-8")
    if not listings:
        rows = "<p>Nessun nuovo annuncio questa settimana.</p>"
    else:
        rows = "".join(
            f'<li><a href="{escape(l["url"])}">{escape(l["titolo"])}</a> — '
            f'{escape(l["comune"] or "")}, {l["prezzo"]}€ ({escape(l["fonte"])}'
            f'{", " + escape(l["chi_vende"]) if l.get("chi_vende") else ""})</li>'
            for l in listings
        )
    return template.replace("{{LISTINGS}}", rows).replace("{{COUNT}}", str(len(listings)))
```

- [ ] **Step 4: Esegui, verifica che passi**

Run: `pytest tests/test_digest.py -v`
Expected: PASS (tutti i test, inclusi quelli di escaping già esistenti)

- [ ] **Step 5: Commit**

```bash
git add notifier/digest.py tests/test_digest.py
git commit -m "feat: include chi_vende in weekly digest email"
```

---

### Task 6: Scraper astegiudiziarie.it

**Files:**
- Create: `scraper/astegiudiziarie.py`
- Create: `fixtures/astegiudiziarie_sample.html` (catturata manualmente)
- Test: `tests/test_astegiudiziarie.py`

**Interfaces:**
- Consumes: `Listing` (Task 1)
- Produces: `build_search_url(centro_nome: str) -> str`, `parse_listings(html: str) -> list[Listing]`, `WAIT_SELECTOR: str`. Registrato in `scraper/run_all.py` (Task 11) come `PORTAL_MODULES["astegiudiziarie"]`.

- [ ] **Step 1: Cattura una fixture reale**

Apri https://www.astegiudiziarie.it in un browser, cerca aste di immobili residenziali nella zona di Jesi/provincia di Ancona (raggio ~20-25km, coerente col resto del progetto). Salva l'HTML della pagina risultati con devtools ("Copy outerHTML" sull'elemento `<html>`) in `fixtures/astegiudiziarie_sample.html`.

- [ ] **Step 2: Ispeziona la fixture e fissa i selettori reali**

Apri `fixtures/astegiudiziarie_sample.html`, usa devtools "Inspect" su alcune card annuncio, annota: selettore del contenitore ripetuto, titolo/descrizione lotto, prezzo/base d'asta, comune, data asta, link. Aggiorna le costanti `SELECTOR_*` allo Step 5 con i valori reali trovati — quelli sotto sono un punto di partenza basato sulla struttura tipica di portali aste giudiziarie, **non verificati contro il sito reale**, esattamente come i selettori draft di Subito/PVP in Fase 1 prima della verifica.

- [ ] **Step 3: Scrivi il test che fallisce**

```python
# tests/test_astegiudiziarie.py
from pathlib import Path
import scraper.astegiudiziarie as ag_module
from scraper.astegiudiziarie import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "astegiudiziarie_sample.html"

def test_build_search_url_includes_centro_nome():
    url = build_search_url("Jesi")
    assert "astegiudiziarie.it" in url
    assert "jesi" in url.lower()

def test_parse_listings_extracts_expected_fields(monkeypatch):
    monkeypatch.setattr(ag_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    first = listings[0]
    assert first.fonte == "astegiudiziarie"
    assert first.tipo == "asta"
    assert first.categoria == "residenziale"
    assert first.external_id
    assert first.titolo
    assert isinstance(first.prezzo, int) and first.prezzo >= 0
    assert first.url.startswith("http")
    assert first.chi_vende is None  # aste giudiziarie, stesso ragionamento di Task 3

def test_parse_listings_returns_empty_list_for_no_matches(monkeypatch):
    monkeypatch.setattr(ag_module, "geocode_fn", lambda comune: (43.5, 13.2))
    assert parse_listings("<html><body>nessuna asta</body></html>") == []
```

- [ ] **Step 4: Esegui, verifica che fallisca**

Run: `pytest tests/test_astegiudiziarie.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'scraper.astegiudiziarie'`

- [ ] **Step 5: Implementa `scraper/astegiudiziarie.py`**

```python
from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing
from .geocode import geocode as geocode_fn, GeocodeError

WAIT_SELECTOR = "body"

# NOTA: selettori di partenza — verificare/correggere contro
# fixtures/astegiudiziarie_sample.html (Step 2). Non ancora verificati contro
# il sito reale, stesso trattamento dei selettori draft di Subito/PVP in Fase 1.
SELECTOR_CARD = ".annuncio-asta, .risultato-asta, article.asta-item"
SELECTOR_TITLE = ".titolo, h2, h3"
SELECTOR_PRICE = ".prezzo, .prezzo-base"
SELECTOR_COMUNE = ".comune, .localita"
SELECTOR_DATA_ASTA = ".data-asta, .data-vendita"
SELECTOR_LINK = "a"


def build_search_url(centro_nome: str) -> str:
    query = quote(centro_nome)
    return f"https://www.astegiudiziarie.it/ricerca-aste-immobiliari?categoria=immobili-residenziali&localita={query}"


def parse_listings(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    for card in soup.select(SELECTOR_CARD):
        title_el = card.select_one(SELECTOR_TITLE)
        link_el = card.select_one(SELECTOR_LINK)
        if not (title_el and link_el and link_el.get("href")):
            continue
        href = link_el["href"]
        url = href if href.startswith("http") else f"https://www.astegiudiziarie.it{href}"
        external_id = url.rstrip("/").split("/")[-1]

        price_el = card.select_one(SELECTOR_PRICE)
        prezzo = _parse_price(price_el.get_text(strip=True) if price_el else "")

        comune = _extract_comune(card)
        lat = lon = None
        if comune:
            try:
                lat, lon = geocode_fn(comune)
            except GeocodeError:
                pass

        data_asta_el = card.select_one(SELECTOR_DATA_ASTA)

        listings.append(Listing(
            fonte="astegiudiziarie",
            external_id=external_id,
            tipo="asta",
            titolo=title_el.get_text(strip=True),
            prezzo=prezzo,
            url=url,
            categoria="residenziale",
            comune=comune,
            lat=lat,
            lon=lon,
            data_asta=data_asta_el.get_text(strip=True) if data_asta_el else None,
            offerta_minima=prezzo,
            chi_vende=None,  # asta giudiziaria: venditore e' la procedura esecutiva
        ))
    return listings


def _extract_comune(card) -> str | None:
    comune_el = card.select_one(SELECTOR_COMUNE)
    if not comune_el:
        return None
    return comune_el.get_text(strip=True) or None


def _parse_price(text: str) -> int:
    if not text:
        return 0
    cleaned = text.strip().replace("€", "").strip().replace(".", "").replace(",", ".")
    try:
        return int(float(cleaned))
    except ValueError:
        digits = "".join(c for c in cleaned if c.isdigit())
        return int(digits) if digits else 0
```

- [ ] **Step 6: Esegui, verifica che passi (adatta i selettori dello Step 2 se la fixture reale differisce)**

Run: `pytest tests/test_astegiudiziarie.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scraper/astegiudiziarie.py fixtures/astegiudiziarie_sample.html tests/test_astegiudiziarie.py
git commit -m "feat: add astegiudiziarie.it scraper"
```

---

### Task 7: Scraper asteimmobili.it

**Files:**
- Create: `scraper/asteimmobili.py`
- Create: `fixtures/asteimmobili_sample.html`
- Test: `tests/test_asteimmobili.py`

**Interfaces:**
- Consumes: `Listing` (Task 1)
- Produces: `build_search_url(centro_nome: str) -> str`, `parse_listings(html: str) -> list[Listing]`, `WAIT_SELECTOR: str`. Registrato come `PORTAL_MODULES["asteimmobili"]` (Task 11).

Stesso pattern di Task 6 (portale aste giudiziarie, meno restrittivo secondo lo spec).

- [ ] **Step 1: Cattura una fixture reale**

Apri https://www.asteimmobili.it, cerca aste immobiliari residenziali zona Jesi/Ancona, salva l'HTML in `fixtures/asteimmobili_sample.html` (stesso procedimento di Task 6 Step 1).

- [ ] **Step 2: Ispeziona la fixture e fissa i selettori reali**

Stesso procedimento di Task 6 Step 2: annota selettori reali per contenitore, titolo, prezzo, comune, data asta; aggiorna le costanti allo Step 5.

- [ ] **Step 3: Scrivi il test che fallisce**

```python
# tests/test_asteimmobili.py
from pathlib import Path
import scraper.asteimmobili as ai_module
from scraper.asteimmobili import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "asteimmobili_sample.html"

def test_build_search_url_includes_centro_nome():
    url = build_search_url("Jesi")
    assert "asteimmobili.it" in url
    assert "jesi" in url.lower()

def test_parse_listings_extracts_expected_fields(monkeypatch):
    monkeypatch.setattr(ai_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    first = listings[0]
    assert first.fonte == "asteimmobili"
    assert first.tipo == "asta"
    assert first.categoria == "residenziale"
    assert first.external_id
    assert first.titolo
    assert isinstance(first.prezzo, int) and first.prezzo >= 0
    assert first.url.startswith("http")
    assert first.chi_vende is None

def test_parse_listings_returns_empty_list_for_no_matches(monkeypatch):
    monkeypatch.setattr(ai_module, "geocode_fn", lambda comune: (43.5, 13.2))
    assert parse_listings("<html><body>nessuna asta</body></html>") == []
```

- [ ] **Step 4: Esegui, verifica che fallisca**

Run: `pytest tests/test_asteimmobili.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'scraper.asteimmobili'`

- [ ] **Step 5: Implementa `scraper/asteimmobili.py`**

```python
from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing
from .geocode import geocode as geocode_fn, GeocodeError

WAIT_SELECTOR = "body"

# NOTA: selettori di partenza, non ancora verificati contro il sito reale —
# verificare/correggere contro fixtures/asteimmobili_sample.html (Step 2).
SELECTOR_CARD = ".annuncio, .card-asta, article"
SELECTOR_TITLE = ".titolo, h2, h3"
SELECTOR_PRICE = ".prezzo, .prezzo-base-asta"
SELECTOR_COMUNE = ".comune, .indirizzo"
SELECTOR_DATA_ASTA = ".data-asta"
SELECTOR_LINK = "a"


def build_search_url(centro_nome: str) -> str:
    query = quote(centro_nome)
    return f"https://www.asteimmobili.it/ricerca?categoria=residenziale&localita={query}"


def parse_listings(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    for card in soup.select(SELECTOR_CARD):
        title_el = card.select_one(SELECTOR_TITLE)
        link_el = card.select_one(SELECTOR_LINK)
        if not (title_el and link_el and link_el.get("href")):
            continue
        href = link_el["href"]
        url = href if href.startswith("http") else f"https://www.asteimmobili.it{href}"
        external_id = url.rstrip("/").split("/")[-1]

        price_el = card.select_one(SELECTOR_PRICE)
        prezzo = _parse_price(price_el.get_text(strip=True) if price_el else "")

        comune = _extract_comune(card)
        lat = lon = None
        if comune:
            try:
                lat, lon = geocode_fn(comune)
            except GeocodeError:
                pass

        data_asta_el = card.select_one(SELECTOR_DATA_ASTA)

        listings.append(Listing(
            fonte="asteimmobili",
            external_id=external_id,
            tipo="asta",
            titolo=title_el.get_text(strip=True),
            prezzo=prezzo,
            url=url,
            categoria="residenziale",
            comune=comune,
            lat=lat,
            lon=lon,
            data_asta=data_asta_el.get_text(strip=True) if data_asta_el else None,
            offerta_minima=prezzo,
            chi_vende=None,
        ))
    return listings


def _extract_comune(card) -> str | None:
    comune_el = card.select_one(SELECTOR_COMUNE)
    if not comune_el:
        return None
    return comune_el.get_text(strip=True) or None


def _parse_price(text: str) -> int:
    if not text:
        return 0
    cleaned = text.strip().replace("€", "").strip().replace(".", "").replace(",", ".")
    try:
        return int(float(cleaned))
    except ValueError:
        digits = "".join(c for c in cleaned if c.isdigit())
        return int(digits) if digits else 0
```

- [ ] **Step 6: Esegui, verifica che passi (adatta i selettori se la fixture reale differisce)**

Run: `pytest tests/test_asteimmobili.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scraper/asteimmobili.py fixtures/asteimmobili_sample.html tests/test_asteimmobili.py
git commit -m "feat: add asteimmobili.it scraper"
```

---

### Task 8: Scraper Immobiliare.it (anti-bot: verifica fattibilità prima)

**Files:**
- Create: `scraper/immobiliare.py`
- Create: `fixtures/immobiliare_sample.html` (solo se lo Step 0 conferma accesso)
- Test: `tests/test_immobiliare.py`

**Interfaces:**
- Consumes: `Listing` (Task 1)
- Produces: `build_search_url(centro_nome: str, tipo: str = "affitto") -> str` (Immobiliare.it separa affitto/vendita in URL distinti, come Subito.it in Fase 1 — vedi Task 11 per il pattern multi-fetch), `parse_listings(html: str) -> list[Listing]`, `WAIT_SELECTOR: str`.

- [ ] **Step 0: Verifica fattibilità (anti-bot)**

Segnalato dallo spec come protetto da anti-bot. Prima di scrivere qualunque selettore: apri https://www.immobiliare.it/affitto-case/jesi/ in un browser normale (non headless, sessione pulita) e osserva se la pagina restituisce risultati reali o un blocco (CAPTCHA, pagina di verifica "sei un robot", 403). **Non tentare di aggirare un eventuale blocco** (niente proxy, niente fingerprint spoofing, niente risoluzione CAPTCHA) — è uno scenario già accettato dallo spec.

- Se la pagina carica normalmente: procedi da Step 1.
- Se blocca: documenta nel ledger (`Task 8: bloccato da anti-bot, vedi nota`), implementa comunque `scraper/immobiliare.py` con i migliori selettori disponibili a partire dalla struttura HTML nota del sito (senza fixture live catturata — segna chiaramente `# NON VERIFICATO: cattura bloccata da anti-bot` sopra i selettori), scrivi comunque i test contro una fixture minimale sintetica coerente con la struttura nota (non contro dati reali scaricati), **non aggiungere `immobiliare` a `portali_attivi` in `config.yaml`** (Task 11), e passa a Task 9.

- [ ] **Step 1: Cattura una fixture reale (solo se Step 0 conferma accesso)**

Cerca "casa" con filtro affitto in Jesi/zona, poi ripeti con vendita (Immobiliare.it separa i due come URL distinti — verificalo qui). Salva entrambe le pagine, usa quella affitto come fixture principale in `fixtures/immobiliare_sample.html` (stesso procedimento MVP Task 7 Step 1 per Subito).

- [ ] **Step 2: Ispeziona la fixture e fissa i selettori reali**

Stesso procedimento delle Fase 1 Task 7/8: annota contenitore card, titolo, prezzo, comune, superficie, link. Aggiorna le costanti allo Step 5. Verifica anche se la pagina espone un indicatore privato/agenzia (Immobiliare.it lista prevalentemente agenzie, ma verifica sul dato reale prima di assumere `chi_vende` sempre `"agenzia"`).

- [ ] **Step 3: Scrivi il test che fallisce**

```python
# tests/test_immobiliare.py
from pathlib import Path
import scraper.immobiliare as imm_module
from scraper.immobiliare import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "immobiliare_sample.html"

def test_build_search_url_includes_centro_nome():
    url = build_search_url("Jesi")
    assert "immobiliare.it" in url
    assert "jesi" in url.lower()

def test_build_search_url_accepts_tipo_and_changes_path():
    affitto_url = build_search_url("Jesi", tipo="affitto")
    vendita_url = build_search_url("Jesi", tipo="vendita")
    assert affitto_url != vendita_url

def test_parse_listings_extracts_expected_fields(monkeypatch):
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    first = listings[0]
    assert first.fonte == "immobiliare"
    assert first.tipo in ("affitto", "vendita")
    assert first.categoria == "residenziale"
    assert first.external_id
    assert first.titolo
    assert isinstance(first.prezzo, int) and first.prezzo >= 0
    assert first.url.startswith("http")

def test_parse_listings_returns_empty_list_for_no_matches(monkeypatch):
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    assert parse_listings("<html><body>nessun annuncio</body></html>") == []
```

- [ ] **Step 4: Esegui, verifica che fallisca**

Run: `pytest tests/test_immobiliare.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'scraper.immobiliare'`

- [ ] **Step 5: Implementa `scraper/immobiliare.py`**

```python
from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing
from .geocode import geocode as geocode_fn, GeocodeError

WAIT_SELECTOR = "body"

# NOTA: selettori di partenza — verificare/correggere contro
# fixtures/immobiliare_sample.html (Step 2). Se Step 0 ha rilevato un blocco
# anti-bot, questi selettori NON sono verificati contro dati reali.
SELECTOR_CARD = "[class*='in-card'], [class*='listing-item']"
SELECTOR_TITLE = "[class*='in-card__title']"
SELECTOR_PRICE = "[class*='in-price']"
SELECTOR_COMUNE = "[class*='in-card__location']"
SELECTOR_LINK = "a"


def build_search_url(centro_nome: str, tipo: str = "affitto") -> str:
    if tipo not in ("affitto", "vendita"):
        raise ValueError(f"tipo non valido per immobiliare: {tipo}")
    slug = quote(centro_nome.lower())
    return f"https://www.immobiliare.it/{tipo}-case/{slug}/"


def parse_listings(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    tipo = _detect_tipo(soup)
    listings = []
    for card in soup.select(SELECTOR_CARD):
        title_el = card.select_one(SELECTOR_TITLE)
        price_el = card.select_one(SELECTOR_PRICE)
        link_el = card.select_one(SELECTOR_LINK)
        if not (title_el and link_el and link_el.get("href")):
            continue
        href = link_el["href"]
        url = href if href.startswith("http") else f"https://www.immobiliare.it{href}"
        external_id = url.rstrip("/").split("/")[-2] if url.endswith("/") else url.rstrip("/").split("/")[-1]

        comune = _extract_comune(card)
        lat = lon = None
        if comune:
            try:
                lat, lon = geocode_fn(comune)
            except GeocodeError:
                pass

        listings.append(Listing(
            fonte="immobiliare",
            external_id=external_id,
            tipo=tipo,
            titolo=title_el.get_text(strip=True),
            prezzo=_parse_price(price_el.get_text(strip=True) if price_el else ""),
            url=url,
            comune=comune,
            lat=lat,
            lon=lon,
        ))
    return listings


def _detect_tipo(soup: BeautifulSoup) -> str:
    heading = soup.find("h1")
    title_tag = soup.title
    text = " ".join([
        heading.get_text() if heading else "",
        title_tag.get_text() if title_tag else "",
    ]).lower()
    return "vendita" if "vendita" in text else "affitto"


def _extract_comune(card) -> str | None:
    comune_el = card.select_one(SELECTOR_COMUNE)
    if not comune_el:
        return None
    return comune_el.get_text(strip=True) or None


def _parse_price(text: str) -> int:
    if not text:
        return 0
    cleaned = text.strip().replace("€", "").strip().replace(".", "").replace(",", ".")
    try:
        return int(float(cleaned))
    except ValueError:
        digits = "".join(c for c in cleaned if c.isdigit())
        return int(digits) if digits else 0
```

- [ ] **Step 6: Esegui, verifica che passi (adatta i selettori se la fixture reale differisce)**

Run: `pytest tests/test_immobiliare.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scraper/immobiliare.py fixtures/immobiliare_sample.html tests/test_immobiliare.py
git commit -m "feat: add Immobiliare.it scraper"
```

---

### Task 9: Scraper Idealista (anti-bot: verifica fattibilità prima)

**Files:**
- Create: `scraper/idealista.py`
- Create: `fixtures/idealista_sample.html` (solo se lo Step 0 conferma accesso)
- Test: `tests/test_idealista.py`

**Interfaces:**
- Consumes: `Listing` (Task 1)
- Produces: `build_search_url(centro_nome: str, tipo: str = "affitto") -> str`, `parse_listings(html: str) -> list[Listing]`, `WAIT_SELECTOR: str`.

Stesso trattamento anti-bot di Task 8.

- [ ] **Step 0: Verifica fattibilità (anti-bot)**

Apri https://www.idealista.it/affitto-case/jesi-marche/ in un browser normale. Idealista è segnalato dallo spec come tra i più protetti (spesso richiede verifica umana/CAPTCHA anche da browser normale). Stessa regola di Task 8 Step 0: se blocca, non aggirare — documenta, implementa con selettori non verificati chiaramente marcati, non attivare in `portali_attivi`.

- [ ] **Step 1: Cattura una fixture reale (solo se Step 0 conferma accesso)**

Stesso procedimento di Task 8 Step 1, adattato a Idealista (cerca affitto poi vendita, salva la pagina affitto come fixture principale).

- [ ] **Step 2: Ispeziona la fixture e fissa i selettori reali**

Stesso procedimento di Task 8 Step 2.

- [ ] **Step 3: Scrivi il test che fallisce**

```python
# tests/test_idealista.py
from pathlib import Path
import scraper.idealista as idealista_module
from scraper.idealista import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "idealista_sample.html"

def test_build_search_url_includes_centro_nome():
    url = build_search_url("Jesi")
    assert "idealista.it" in url
    assert "jesi" in url.lower()

def test_build_search_url_accepts_tipo_and_changes_path():
    affitto_url = build_search_url("Jesi", tipo="affitto")
    vendita_url = build_search_url("Jesi", tipo="vendita")
    assert affitto_url != vendita_url

def test_parse_listings_extracts_expected_fields(monkeypatch):
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    first = listings[0]
    assert first.fonte == "idealista"
    assert first.tipo in ("affitto", "vendita")
    assert first.categoria == "residenziale"
    assert first.external_id
    assert first.titolo
    assert isinstance(first.prezzo, int) and first.prezzo >= 0
    assert first.url.startswith("http")

def test_parse_listings_returns_empty_list_for_no_matches(monkeypatch):
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    assert parse_listings("<html><body>nessun annuncio</body></html>") == []
```

- [ ] **Step 4: Esegui, verifica che fallisca**

Run: `pytest tests/test_idealista.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'scraper.idealista'`

- [ ] **Step 5: Implementa `scraper/idealista.py`**

```python
from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing
from .geocode import geocode as geocode_fn, GeocodeError

WAIT_SELECTOR = "body"

# NOTA: selettori di partenza — verificare/correggere contro
# fixtures/idealista_sample.html (Step 2). Se Step 0 ha rilevato un blocco
# anti-bot, questi selettori NON sono verificati contro dati reali.
SELECTOR_CARD = "article.item"
SELECTOR_TITLE = "a.item-link"
SELECTOR_PRICE = ".item-price"
SELECTOR_COMUNE = ".item-detail-char, .item-location"
SELECTOR_LINK = "a.item-link"


def build_search_url(centro_nome: str, tipo: str = "affitto") -> str:
    if tipo not in ("affitto", "vendita"):
        raise ValueError(f"tipo non valido per idealista: {tipo}")
    path = "affitto-case" if tipo == "affitto" else "vendita-case"
    slug = quote(centro_nome.lower())
    return f"https://www.idealista.it/{path}/{slug}-marche/"


def parse_listings(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    tipo = _detect_tipo(soup)
    listings = []
    for card in soup.select(SELECTOR_CARD):
        title_el = card.select_one(SELECTOR_TITLE)
        price_el = card.select_one(SELECTOR_PRICE)
        link_el = card.select_one(SELECTOR_LINK)
        if not (title_el and link_el and link_el.get("href")):
            continue
        href = link_el["href"]
        url = href if href.startswith("http") else f"https://www.idealista.it{href}"
        external_id = url.rstrip("/").split("/")[-1]

        comune = _extract_comune(card)
        lat = lon = None
        if comune:
            try:
                lat, lon = geocode_fn(comune)
            except GeocodeError:
                pass

        listings.append(Listing(
            fonte="idealista",
            external_id=external_id,
            tipo=tipo,
            titolo=title_el.get_text(strip=True),
            prezzo=_parse_price(price_el.get_text(strip=True) if price_el else ""),
            url=url,
            comune=comune,
            lat=lat,
            lon=lon,
        ))
    return listings


def _detect_tipo(soup: BeautifulSoup) -> str:
    heading = soup.find("h1")
    title_tag = soup.title
    text = " ".join([
        heading.get_text() if heading else "",
        title_tag.get_text() if title_tag else "",
    ]).lower()
    return "vendita" if "vendita" in text else "affitto"


def _extract_comune(card) -> str | None:
    comune_el = card.select_one(SELECTOR_COMUNE)
    if not comune_el:
        return None
    return comune_el.get_text(strip=True) or None


def _parse_price(text: str) -> int:
    if not text:
        return 0
    cleaned = text.strip().replace("€", "").strip().replace(".", "").replace(",", ".")
    try:
        return int(float(cleaned))
    except ValueError:
        digits = "".join(c for c in cleaned if c.isdigit())
        return int(digits) if digits else 0
```

- [ ] **Step 6: Esegui, verifica che passi (adatta i selettori se la fixture reale differisce)**

Run: `pytest tests/test_idealista.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scraper/idealista.py fixtures/idealista_sample.html tests/test_idealista.py
git commit -m "feat: add Idealista scraper"
```

---

### Task 10: Scraper portaleaste — dominio da verificare

**Files:**
- Create: `scraper/portaleaste.py`
- Create: `fixtures/portaleaste_sample.html`
- Test: `tests/test_portaleaste.py`

**Interfaces:**
- Consumes: `Listing` (Task 1)
- Produces: `build_search_url(centro_nome: str) -> str`, `parse_listings(html: str) -> list[Listing]`, `WAIT_SELECTOR: str`. Registrato come `PORTAL_MODULES["portaleaste"]` (Task 11).

- [ ] **Step 1: Risolvi il dominio reale**

Né questo piano né lo spec originale hanno un dominio verificato per "portaleaste" (utente: `portaleaste.com`, spec: `portaleaste.it` — nessuno dei due è stato controllato dal vivo). Prima di qualunque altra cosa: cerca "portaleaste aste immobiliari" con un motore di ricerca, apri il risultato, conferma che è un portale aste giudiziarie/immobiliari (coerente con la descrizione dello spec, sezione "Fonti dati"). Usa quel dominio reale ovunque in questo task (URL di ricerca, fixture, test) — se il dominio reale è diverso sia da `.it` che da `.com`, usa quello, non forzare una delle due ipotesi.

- [ ] **Step 2: Cattura una fixture reale**

Cerca aste immobiliari residenziali zona Jesi/Ancona sul dominio risolto allo Step 1, salva l'HTML in `fixtures/portaleaste_sample.html` (stesso procedimento di Task 6 Step 1).

- [ ] **Step 3: Ispeziona la fixture e fissa i selettori reali**

Stesso procedimento di Task 6 Step 2: contenitore, titolo, prezzo, comune, data asta.

- [ ] **Step 4: Scrivi il test che fallisce**

```python
# tests/test_portaleaste.py
from pathlib import Path
import scraper.portaleaste as pa_module
from scraper.portaleaste import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "portaleaste_sample.html"

def test_build_search_url_includes_centro_nome():
    url = build_search_url("Jesi")
    # dominio verificato allo Step 1 di questo task — sostituisci l'assert
    # sotto con il dominio reale trovato, se diverso da entrambe le ipotesi
    assert "portaleaste" in url
    assert "jesi" in url.lower()

def test_parse_listings_extracts_expected_fields(monkeypatch):
    monkeypatch.setattr(pa_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    first = listings[0]
    assert first.fonte == "portaleaste"
    assert first.tipo == "asta"
    assert first.categoria == "residenziale"
    assert first.external_id
    assert first.titolo
    assert isinstance(first.prezzo, int) and first.prezzo >= 0
    assert first.url.startswith("http")
    assert first.chi_vende is None

def test_parse_listings_returns_empty_list_for_no_matches(monkeypatch):
    monkeypatch.setattr(pa_module, "geocode_fn", lambda comune: (43.5, 13.2))
    assert parse_listings("<html><body>nessuna asta</body></html>") == []
```

- [ ] **Step 5: Esegui, verifica che fallisca**

Run: `pytest tests/test_portaleaste.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'scraper.portaleaste'`

- [ ] **Step 6: Implementa `scraper/portaleaste.py`**

```python
from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing
from .geocode import geocode as geocode_fn, GeocodeError

WAIT_SELECTOR = "body"

# Dominio verificato allo Step 1 di questo task — sostituisci se diverso.
BASE_URL = "https://www.portaleaste.it"

# NOTA: selettori di partenza, non ancora verificati contro il sito reale —
# verificare/correggere contro fixtures/portaleaste_sample.html (Step 3).
SELECTOR_CARD = ".annuncio-asta, .card-asta, article"
SELECTOR_TITLE = ".titolo, h2, h3"
SELECTOR_PRICE = ".prezzo, .prezzo-base-asta"
SELECTOR_COMUNE = ".comune, .indirizzo"
SELECTOR_DATA_ASTA = ".data-asta"
SELECTOR_LINK = "a"


def build_search_url(centro_nome: str) -> str:
    query = quote(centro_nome)
    return f"{BASE_URL}/ricerca?categoria=residenziale&localita={query}"


def parse_listings(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    for card in soup.select(SELECTOR_CARD):
        title_el = card.select_one(SELECTOR_TITLE)
        link_el = card.select_one(SELECTOR_LINK)
        if not (title_el and link_el and link_el.get("href")):
            continue
        href = link_el["href"]
        url = href if href.startswith("http") else f"{BASE_URL}{href}"
        external_id = url.rstrip("/").split("/")[-1]

        price_el = card.select_one(SELECTOR_PRICE)
        prezzo = _parse_price(price_el.get_text(strip=True) if price_el else "")

        comune = _extract_comune(card)
        lat = lon = None
        if comune:
            try:
                lat, lon = geocode_fn(comune)
            except GeocodeError:
                pass

        data_asta_el = card.select_one(SELECTOR_DATA_ASTA)

        listings.append(Listing(
            fonte="portaleaste",
            external_id=external_id,
            tipo="asta",
            titolo=title_el.get_text(strip=True),
            prezzo=prezzo,
            url=url,
            categoria="residenziale",
            comune=comune,
            lat=lat,
            lon=lon,
            data_asta=data_asta_el.get_text(strip=True) if data_asta_el else None,
            offerta_minima=prezzo,
            chi_vende=None,
        ))
    return listings


def _extract_comune(card) -> str | None:
    comune_el = card.select_one(SELECTOR_COMUNE)
    if not comune_el:
        return None
    return comune_el.get_text(strip=True) or None


def _parse_price(text: str) -> int:
    if not text:
        return 0
    cleaned = text.strip().replace("€", "").strip().replace(".", "").replace(",", ".")
    try:
        return int(float(cleaned))
    except ValueError:
        digits = "".join(c for c in cleaned if c.isdigit())
        return int(digits) if digits else 0
```

- [ ] **Step 7: Esegui, verifica che passi (adatta i selettori se la fixture reale differisce)**

Run: `pytest tests/test_portaleaste.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add scraper/portaleaste.py fixtures/portaleaste_sample.html tests/test_portaleaste.py
git commit -m "feat: add portaleaste scraper"
```

---

### Task 11: Registra i nuovi portali nell'orchestratore e in config

**Files:**
- Modify: `scraper/run_all.py`
- Modify: `config.yaml`
- Modify: `tests/test_run_all.py`

**Interfaces:**
- Consumes: tutti i moduli scraper Task 6-10
- Produces: `PORTAL_MODULES` esteso, `PORTAL_TIPI` esteso per i portali multi-tipo (immobiliare, idealista — affitto+vendita come Subito).

- [ ] **Step 1: Scrivi il test che fallisce**

Aggiungi in `tests/test_run_all.py`:

```python
def test_run_all_registers_all_phase2_portals():
    for nome in ("astegiudiziarie", "asteimmobili", "immobiliare", "idealista", "portaleaste"):
        assert nome in run_all_module.PORTAL_MODULES

def test_run_all_fetches_immobiliare_and_idealista_once_per_tipo(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    fetched_urls = []

    def fake_fetch(url, wait_selector=None, **kwargs):
        fetched_urls.append(url)
        return FAKE_HTML

    monkeypatch.setattr(run_all_module, "fetch_html", fake_fetch)
    for modulo in run_all_module.PORTAL_MODULES.values():
        monkeypatch.setattr(modulo, "parse_listings", lambda html: [])

    config = {"portali_attivi": ["immobiliare", "idealista"], "centro": {"nome": "Jesi"}}
    run_all_module.run_all(config, db_path)

    assert len(fetched_urls) == 4  # 2 tipi x 2 portali
```

- [ ] **Step 2: Esegui, verifica che fallisca**

Run: `pytest tests/test_run_all.py -v`
Expected: FAIL (`AssertionError`, i nuovi portali non sono ancora in `PORTAL_MODULES`)

- [ ] **Step 3: Implementa in `scraper/run_all.py`**

```python
from . import db, subito, pvp_giustizia, astegiudiziarie, asteimmobili, immobiliare, idealista, portaleaste
from .fetch import fetch_html

PORTAL_MODULES = {
    "subito": subito,
    "pvp_giustizia": pvp_giustizia,
    "astegiudiziarie": astegiudiziarie,
    "asteimmobili": asteimmobili,
    "immobiliare": immobiliare,
    "idealista": idealista,
    "portaleaste": portaleaste,
}

# Portali la cui unica ricerca non copre sia affitto che vendita: una fetch
# per tipo. Assente dal dict = una singola fetch (portali di sole aste).
PORTAL_TIPI = {
    "subito": ("affitto", "vendita"),
    "immobiliare": ("affitto", "vendita"),
    "idealista": ("affitto", "vendita"),
}
```

(Il resto di `run_all.py` — `_search_urls` e `run_all` — non cambia: già generico rispetto al contenuto di `PORTAL_MODULES`/`PORTAL_TIPI`.)

- [ ] **Step 4: Esegui, verifica che passi**

Run: `pytest tests/test_run_all.py -v`
Expected: PASS

- [ ] **Step 5: Aggiorna `config.yaml`**

Aggiungi a `portali_attivi` solo i portali che Task 6, 7, 10 hanno confermato funzionanti, e — per Task 8/9 — solo se lo Step 0 di quel task NON ha rilevato un blocco anti-bot:

```yaml
portali_attivi:
  - subito
  - pvp_giustizia
  - astegiudiziarie
  - asteimmobili
  - portaleaste
  # immobiliare, idealista: aggiungi qui solo se Task 8/9 Step 0 ha confermato
  # accesso senza blocco anti-bot — altrimenti lascia commentati/assenti e
  # documenta il motivo nel ledger.
```

- [ ] **Step 6: Esegui l'intera suite**

Run: `pytest -v`
Expected: PASS (tutti i test, Fase 1 + Fase 2)

- [ ] **Step 7: Commit**

```bash
git add scraper/run_all.py config.yaml tests/test_run_all.py
git commit -m "feat: register phase 2 portals in orchestrator"
```

---

### Task 12: Smoke test finale (manuale, non pytest)

Come la Fase 1 Task 14 — verifica dal vivo, non automatizzabile.

**Files:** nessuno (solo verifica)

- [ ] **Step 1: Suite completa**

Run: `pytest -v`
Expected: tutti i test Task 1-11 PASS

- [ ] **Step 2: Pipeline reale**

Run: `python -m scripts.daily`
Expected: completa senza eccezioni; `webapp/build/data.json` contiene annunci dai nuovi portali attivi (oltre a subito/pvp_giustizia); apri `webapp/build/index.html`, conferma che il filtro "Privato/Agenzia" funziona e che le card mostrano la fonte corretta per ogni nuovo portale.

- [ ] **Step 3: Verifica pubblicazione**

Conferma che il sito pubblicato su GitHub Pages (https://angelopelosi.github.io/cerco-casa/) mostra i nuovi annunci dopo il prossimo run schedulato (o forzane uno manuale).

- [ ] **Step 4: Commit di eventuali aggiustamenti selettori emersi dal run reale**

Se il run reale rivela selettori da correggere (comune per portali con anti-bot o markup diverso dalla fixture), correggili e committa separatamente per portale, non in un unico commit cumulativo.
