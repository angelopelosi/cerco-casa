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
