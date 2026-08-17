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


def build_targets(config: dict) -> list[str]:
    centro = config["centro"]["nome"]
    provincia = config["centro"]["provincia"]
    return [
        idealista.build_search_url(centro, provincia, tipo="vendita"),
        idealista.build_search_url(centro, provincia, tipo="affitto"),
        immobiliare.build_search_url(centro, tipo="vendita"),
        immobiliare.build_search_url(centro, tipo="affitto"),
        immobiliare.build_search_url(centro, tipo="asta"),
    ]


def main() -> None:
    config = yaml.safe_load(Path("config.yaml").read_text())
    CAPTURE_DIR.mkdir(exist_ok=True)
    urls = build_targets(config)

    print("Si aprono 5 schede nel browser predefinito.")
    print(f'Per ciascuna: Ctrl+S, salva dentro "{CAPTURE_DIR}/" (il nome che propone il browser va benissimo,')
    print("  non serve rinominare — lo script di import lo riconosce dal nome della pagina).\n")
    for url in urls:
        print(f"  {url}")
        webbrowser.open(url)

    print(f"\nFatto. Dopo aver salvato le pagine in {CAPTURE_DIR}/, lancia:")
    print("  python -m scripts.importa_ricerche_manuali")


if __name__ == "__main__":
    main()
