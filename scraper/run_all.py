from . import db, subito, pvp_giustizia
from .fetch import fetch_html

PORTAL_MODULES = {
    "subito": subito,
    "pvp_giustizia": pvp_giustizia,
}

# Portali la cui unica ricerca non copre sia affitto che vendita: una fetch
# per tipo. Assente dal dict = una singola fetch (es. pvp_giustizia, dove
# tipo e sempre "asta").
PORTAL_TIPI = {
    "subito": ("affitto", "vendita"),
}

def _search_urls(module, portale: str, centro_nome: str) -> list[str]:
    tipi = PORTAL_TIPI.get(portale)
    if tipi:
        return [module.build_search_url(centro_nome, tipo=t) for t in tipi]
    return [module.build_search_url(centro_nome)]

def run_all(config: dict, db_path: str) -> None:
    conn = db.connect(db_path)
    for portale in config["portali_attivi"]:
        module = PORTAL_MODULES.get(portale)
        if module is None:
            print(f"scraper non ancora implementato: {portale}, skip")
            continue
        seen_ids = set()
        for url in _search_urls(module, portale, config["centro"]["nome"]):
            html = fetch_html(url, wait_selector=module.WAIT_SELECTOR)
            for listing in module.parse_listings(html):
                db.upsert_listing(conn, listing)
                seen_ids.add(listing.id)
        db.mark_stale_as_removed(conn, portale, seen_ids)
