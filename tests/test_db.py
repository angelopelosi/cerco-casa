import sqlite3
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

def test_upsert_listing_does_not_null_out_chi_vende_on_reupsert(tmp_path):
    # Review finale del branch: un re-scrape la cui estrazione chi_vende
    # fallisce transitoriamente (es. __NEXT_DATA__ di subito.py non parsabile)
    # non deve azzerare un valore privato/agenzia gia' noto per lo stesso
    # annuncio. chi_vende non cambia mai legittimamente per un annuncio reale,
    # quindi l'ultimo valore non-null noto va preservato (ON CONFLICT usa
    # COALESCE(excluded.chi_vende, chi_vende), non un overwrite incondizionato).
    conn = db.connect(str(tmp_path / "test.db"))
    listing = make_listing()
    listing.chi_vende = "privato"
    db.upsert_listing(conn, listing, today="2026-08-10")
    rows = db.get_active(conn)
    assert rows[0]["chi_vende"] == "privato"

    reupserted = make_listing()
    reupserted.chi_vende = None  # estrazione fallita in questo re-scrape
    db.upsert_listing(conn, reupserted, today="2026-08-12")
    rows = db.get_active(conn)
    assert rows[0]["chi_vende"] == "privato"

def test_upsert_listing_updates_chi_vende_when_newly_determined(tmp_path):
    # Contro-caso della COALESCE: se il nuovo scrape determina un valore, deve
    # comunque sovrascrivere il precedente (COALESCE si applica solo quando il
    # nuovo valore e' None).
    conn = db.connect(str(tmp_path / "test.db"))
    listing = make_listing()
    listing.chi_vende = None
    db.upsert_listing(conn, listing, today="2026-08-10")
    rows = db.get_active(conn)
    assert rows[0]["chi_vende"] is None

    reupserted = make_listing()
    reupserted.chi_vende = "agenzia"
    db.upsert_listing(conn, reupserted, today="2026-08-12")
    rows = db.get_active(conn)
    assert rows[0]["chi_vende"] == "agenzia"
