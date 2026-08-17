"""Apre nel browser reale dell'utente le pagine di ricerca di Immobiliare.it
e Idealista.it (bloccati per gli scraper automatici da anti-bot DataDome,
vedi scraper/immobiliare.py e scraper/idealista.py). Essendo il browser vero
dell'utente e non uno script automatico, DataDome non lo blocca.

Uso:
    python -m scripts.apri_ricerche_manuali

Poi, per ciascuna scheda aperta: Ctrl+S, salva come "Pagina web, solo HTML"
nel percorso indicato a schermo (dentro manual_captures/). Quando tutte le
pagine sono salvate:

    python -m scripts.importa_ricerche_manuali
"""
import webbrowser
from pathlib import Path

import yaml

from scraper import immobiliare, idealista

CAPTURE_DIR = Path("manual_captures")


def build_targets(config: dict) -> list[tuple[str, str]]:
    centro = config["centro"]["nome"]
    provincia = config["centro"]["provincia"]
    return [
        ("idealista_vendita.html", idealista.build_search_url(centro, provincia, tipo="vendita")),
        ("idealista_affitto.html", idealista.build_search_url(centro, provincia, tipo="affitto")),
        ("immobiliare_vendita.html", immobiliare.build_search_url(centro, tipo="vendita")),
        ("immobiliare_affitto.html", immobiliare.build_search_url(centro, tipo="affitto")),
        ("immobiliare_asta.html", immobiliare.build_search_url(centro, tipo="asta")),
    ]


def main() -> None:
    config = yaml.safe_load(Path("config.yaml").read_text())
    CAPTURE_DIR.mkdir(exist_ok=True)
    targets = build_targets(config)

    print("Si aprono 5 schede nel browser predefinito.")
    print('Per ciascuna: Ctrl+S, "Salva come tipo: Pagina web, solo HTML", nel percorso indicato.\n')
    for filename, url in targets:
        dest = CAPTURE_DIR / filename
        print(f"  {url}\n    -> salva come: {dest}\n")
        webbrowser.open(url)

    print(f"Fatto. Dopo aver salvato tutte le pagine in {CAPTURE_DIR}/, lancia:")
    print("  python -m scripts.importa_ricerche_manuali")


if __name__ == "__main__":
    main()
