"""Legge le pagine salvate manualmente da scripts/apri_ricerche_manuali.py
(dentro manual_captures/) e le importa nello stesso DB usato dalla pipeline
automatica (data/listings.db) — stesso schema, stesso dedup, stesso sito
statico e stesso digest email degli altri portali.

Non chiama mark_stale_as_removed: essendo un import manuale e occasionale
(non ogni pagina viene ri-salvata ogni volta), marcare "rimosso" qui
rischierebbe di cancellare annunci ancora attivi solo perche' quella
particolare pagina non e' stata ri-salvata in questa sessione. Un annuncio
davvero sparito resta "attivo" nel DB finche' non viene ri-scoperto assente
in un futuro import completo — costo accettabile per uno strumento manuale.

Uso:
    python -m scripts.importa_ricerche_manuali
"""
from pathlib import Path

from scraper import db, immobiliare, idealista

CAPTURE_DIR = Path("manual_captures")

FILE_MAP = {
    "idealista_vendita.html": (idealista, "vendita"),
    "idealista_affitto.html": (idealista, "affitto"),
    "immobiliare_vendita.html": (immobiliare, "vendita"),
    "immobiliare_affitto.html": (immobiliare, "affitto"),
    "immobiliare_asta.html": (immobiliare, "asta"),
}


def main() -> None:
    conn = db.connect("data/listings.db")
    totale = 0

    for filename, (module, tipo) in FILE_MAP.items():
        path = CAPTURE_DIR / filename
        if not path.exists():
            print(f"salto {filename}: non trovato in {CAPTURE_DIR}/")
            continue

        html = path.read_text(encoding="utf-8")
        listings = module.parse_listings(html, tipo=tipo)
        for listing in listings:
            db.upsert_listing(conn, listing)

        print(f"{filename}: {len(listings)} annunci importati")
        totale += len(listings)

    print(f"\nTotale annunci importati: {totale}")
    if totale:
        print("\nPer rigenerare il sito con questi dati:")
        print(
            '  python -c "from webapp.generate import generate_site; '
            "generate_site('data/listings.db','config.yaml','webapp/build','webapp/template')\""
        )
        print("Per pubblicarlo: python -c \"from scripts.publish import publish; publish()\"")


if __name__ == "__main__":
    main()
