"""Legge le pagine salvate manualmente da scripts/apri_ricerche_manuali.py
(dentro manual_captures/) e le importa nello stesso DB usato dalla pipeline
automatica (data/listings.db) — stesso schema, stesso dedup, stesso sito
statico e stesso digest email degli altri portali.

I file salvati dal browser NON hanno il nome suggerito da
apri_ricerche_manuali.py (Chrome/Edge usa il titolo della pagina) — es.
"Case in vendita Jesi - Immobiliare.it - 2.html" invece di
"immobiliare_vendita.html". Il file viene quindi classificato (fonte, tipo)
dal proprio nome, non da un nome esatto atteso: e' normale e atteso avere
piu' file per la stessa ricerca (pagine diverse, ordinamenti diversi) — si
importano tutti, il dedup su (fonte, external_id) unisce gli annunci
ripetuti automaticamente.

Non chiama mark_stale_as_removed: essendo un import manuale e occasionale
(non ogni pagina/ordinamento viene ri-salvato ogni volta), marcare
"rimosso" qui rischierebbe di cancellare annunci ancora attivi solo perche'
quella particolare pagina non e' stata ri-salvata in questa sessione. Un
annuncio davvero sparito resta "attivo" nel DB finche' non viene ri-scoperto
assente in un futuro import completo — costo accettabile per uno strumento
manuale.

Uso:
    python -m scripts.importa_ricerche_manuali
"""
from pathlib import Path

from scraper import db, immobiliare, idealista

CAPTURE_DIR = Path("manual_captures")


def classifica(nome_file: str) -> tuple[object, str] | None:
    """Determina (modulo, tipo) dal nome del file salvato. None se non
    riconosciuto (l'utente ha salvato qualcos'altro nella cartella)."""
    nome = nome_file.lower()
    if "idealista" in nome:
        modulo = idealista
    elif "immobiliare" in nome:
        modulo = immobiliare
    else:
        return None

    if "asta" in nome or "aste" in nome:
        tipo = "asta"
    elif "affitto" in nome:
        tipo = "affitto"
    elif "vendita" in nome:
        tipo = "vendita"
    else:
        return None

    if modulo is idealista and tipo == "asta":
        return None  # idealista non ha una sezione aste

    return modulo, tipo


def main() -> None:
    conn = db.connect("data/listings.db")
    totale = 0
    saltati = []

    for path in sorted(CAPTURE_DIR.glob("*.html")):
        classificazione = classifica(path.name)
        if classificazione is None:
            saltati.append(path.name)
            continue
        modulo, tipo = classificazione

        html = path.read_text(encoding="utf-8", errors="replace")
        listings = modulo.parse_listings(html, tipo=tipo)
        for listing in listings:
            db.upsert_listing(conn, listing)

        print(f"{path.name}: {len(listings)} annunci ({modulo.__name__.rsplit('.', 1)[-1]}, {tipo})")
        totale += len(listings)

    if saltati:
        print(f"\nFile non riconosciuti, saltati: {', '.join(saltati)}")

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
