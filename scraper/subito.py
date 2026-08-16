from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing
from .geocode import geocode as geocode_fn, GeocodeError

# NOTA: le pagine di ricerca Subito sono server-rendered (verificato: la
# fixture catturata con wait_selector="body" contiene gia' gli annunci nella
# risposta HTML iniziale, senza bisogno di attendere hydration via JS).
# Si e' considerato "[data-testid='listing-container']" (visto nella fixture)
# come selettore piu' specifico, ma non e' verificato se e' presente anche
# per ricerche con zero risultati: usarlo rischierebbe un TimeoutError in
# page.wait_for_selector su una ricerca legittimamente vuota. "body" resta
# la scelta piu' sicura, verificata funzionante.
WAIT_SELECTOR = "body"

# Selettori verificati contro fixtures/subito_sample.html (ricerca reale
# "affitto immobili" a Jesi, 28 annunci). Subito usa CSS modules: ogni classe
# ha la forma "{componente}-module__{hash}__{nomeSemantico}" (es.
# "AdItem-module__7cUP-a__adItemCard") oppure "index-module_{nomeSemantico}__{hash}"
# (es. "index-module_price__ArUqZ"). L'hash cambia ad ogni build del sito, quindi
# i selettori qui sotto usano match parziale (*=) sulla parte semantica stabile
# del nome classe, non sull'hash, per essere piu' resistenti ai redeploy.
SELECTOR_CARD = "article[class*='adItemCard']"
SELECTOR_TITLE = "h3[class*='subject']"
SELECTOR_PRICE = "[class*='price__']"
SELECTOR_LINK = "a"
SELECTOR_COMUNE = "[class*='location__']"


def build_search_url(centro_nome: str, tipo: str = "affitto") -> str:
    """Costruisce l'URL di ricerca Subito.it per un comune e un tipo di annuncio.

    NOTA: Subito.it NON espone un'unica pagina che mischia affitto e vendita:
    il tipo fa parte del path (`/annunci-italia/affitto/immobili/` vs
    `/annunci-italia/vendita/immobili/`), verificato fetchando entrambi.
    Per questo `build_search_url` accetta un parametro `tipo` (default
    "affitto" per compatibilita' con la firma originale a un solo argomento) —
    run_all.py (Task 9) deve chiamarla una volta per "affitto" e una per
    "vendita" per coprire entrambi.
    """
    if tipo not in ("affitto", "vendita"):
        raise ValueError(f"tipo non valido per subito: {tipo}")
    query = quote(centro_nome)
    return f"https://www.subito.it/annunci-italia/{tipo}/immobili/?q={query}"


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
        url = href if href.startswith("http") else f"https://www.subito.it{href}"
        external_id = url.rstrip("/").split("/")[-1]

        comune = _extract_comune(card)
        lat = lon = None
        if comune:
            try:
                lat, lon = geocode_fn(comune)
            except GeocodeError:
                pass

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
        ))
    return listings


def _detect_tipo(soup: BeautifulSoup) -> str:
    """Determina affitto/vendita dal contenuto della pagina (h1/title).

    Gli URL dei singoli annunci (es. .../appartamenti/xxx-651171551.htm) non
    contengono mai la parola "vendita" o "affitto", quindi non e' possibile
    dedurre il tipo dall'URL della card come nella bozza iniziale: si legge
    invece l'intestazione della pagina dei risultati di ricerca, che riflette
    in modo affidabile il tipo cercato (es. "Jesi - Affitto case").
    """
    heading = soup.find("h1")
    title_tag = soup.title
    text = " ".join([
        heading.get_text() if heading else "",
        title_tag.get_text() if title_tag else "",
    ]).lower()
    if "vendita" in text:
        return "vendita"
    return "affitto"


def _extract_comune(card) -> str | None:
    comune_el = card.select_one(SELECTOR_COMUNE)
    if not comune_el:
        return None
    raw = comune_el.get_text(strip=True)
    # Il testo grezzo e' tipo "Jesi(AN)" o "Falconara Marittima(AN)": si tiene
    # solo il nome del comune, senza sigla provincia, per un geocoding pulito.
    comune = raw.split("(")[0].strip()
    return comune or None


def _parse_price(text: str) -> int:
    digits = "".join(c for c in text if c.isdigit())
    return int(digits) if digits else 0
