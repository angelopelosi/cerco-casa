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
            stato_annuncio='attivo', chi_vende=COALESCE(excluded.chi_vende, chi_vende)
        """,
        (listing.id, listing.fonte, listing.external_id, listing.tipo, listing.categoria,
         listing.titolo, listing.prezzo, listing.superficie_mq, listing.locali, listing.comune,
         listing.lat, listing.lon, listing.stato_disponibilita, listing.data_disponibilita,
         listing.arredato, listing.url, listing.data_pubblicazione, first_seen, today, "attivo",
         listing.tribunale, listing.data_asta, listing.offerta_minima, listing.chi_vende),
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
