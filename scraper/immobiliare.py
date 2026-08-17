import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing
from .geocode import geocode as geocode_fn, GeocodeError

# ATTENZIONE — Task 8, Step 0 (verifica fattibilita' anti-bot): il fetch di
# verifica (Playwright headless, fetch normale, nessuna evasione tentata) su
# https://www.immobiliare.it/affitto-case/jesi/ ha restituito una pagina di
# blocco DataDome CAPTCHA (non risultati reali) — vedi
# docs/superpowers/reports/task-8-immobiliare-antibot-report.md per
# l'evidenza completa. Di conseguenza NON e' stato possibile catturare una
# fixture reale ne' verificare i selettori sotto contro il markup reale del
# sito. I test di questo modulo girano contro
# fixtures/immobiliare_synthetic.html, una fixture costruita a mano (non
# scaricata) — vedi commento in testa a quel file e a tests/test_immobiliare.py.
# Questo modulo NON e' registrato in portali_attivi/PORTAL_TIPI/PORTAL_MODULES:
# la Task 11 deve saltarlo finche' non ci sara' una riverifica manuale
# dell'accesso al sito.

WAIT_SELECTOR = "body"

# NON VERIFICATO: cattura bloccata da anti-bot (Step 0, vedi nota sopra).
# Selettori di partenza presi dalla bozza del brief, non confermati contro
# HTML reale — potrebbero non corrispondere al markup effettivo del sito.
#
# NOTA (review fix): la bozza originale usava match per sottostringa
# sull'attributo class (`[class*='in-card']`), che matcha per errore anche
# classi figlie BEM come "in-card__title"/"in-card__location" (contengono
# "in-card" come sottostringa) e qualunque wrapper il cui nome contenga
# "listing-item" come sottostringa (es. "listing-items"). Verificato contro
# fixtures/immobiliare_synthetic.html: la vecchia regex produceva 9 match di
# soup.select(SELECTOR_CARD) invece dei 3 attesi (i 6 in piu' erano le
# classi figlie in-card__title/in-card__location di ciascuna delle 3 card).
# Non causava un bug visibile solo per una fortuita coincidenza strutturale
# della fixture (quei nodi extra sono foglie senza title/link annidati, quindi
# il guard `if not (title_el and link_el...)` li scartava) — non e' una
# garanzia della selettore stessa. Corretto passando a selettori CSS per
# classe esatta (match sul singolo token di classe, non sottostringa), che
# elimina la collisione a prescindere dal markup reale del sito (fix valido
# per qualunque sito che segua la stessa convenzione BEM assunta dalla bozza
# del brief, non un'assunzione aggiuntiva sul markup).
SELECTOR_CARD = ".in-card, .listing-item"
SELECTOR_TITLE = ".in-card__title"
SELECTOR_PRICE = ".in-price"
SELECTOR_COMUNE = ".in-card__location"
SELECTOR_LINK = "a"


def build_search_url(centro_nome: str, tipo: str = "affitto") -> str:
    """Costruisce l'URL di ricerca Immobiliare.it per un comune e un tipo di annuncio.

    NON VERIFICATO end-to-end: e' lo stesso URL (per centro_nome="Jesi",
    tipo="affitto") usato per il fetch di verifica fattibilita' dello
    Step 0, che e' stato bloccato da un CAPTCHA anti-bot prima di poter
    confermare se la pagina di risultati raggiunta sia effettivamente
    corretta. Come Subito.it in Fase 1, Immobiliare.it separa affitto e
    vendita come path distinti (bozza del brief, non confermato dal sito
    reale).
    """
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
        external_id = _external_id_from_url(url)

        comune = _extract_comune(card)
        lat = lon = None
        if comune:
            try:
                lat, lon = geocode_fn(comune)
            except (GeocodeError, requests.RequestException):
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
            # chi_vende volutamente non impostato (resta None, default dello
            # schema): il brief chiede di verificare sul dato reale prima di
            # assumere sempre "agenzia", ma lo Step 0 non ha permesso alcuna
            # verifica — non si inventa il valore.
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


def _external_id_from_url(url: str) -> str:
    """Ultimo segmento non vuoto del path dell'URL.

    NOTA: la bozza del brief calcolava questo valore con
    `url.rstrip("/").split("/")[-2] if url.endswith("/") else ...[-1]`, che
    per un URL del tipo ".../annunci/123456789/" restituisce erroneamente
    "annunci" (il segmento statico prima dell'ID) invece di "123456789".
    E' un bug di logica nell'indicizzazione, non un'assunzione sul markup
    reale del sito: corretto qui prendendo sempre l'ultimo segmento non
    vuoto del path, indipendentemente dallo slash finale.
    """
    segments = [seg for seg in url.split("/") if seg]
    return segments[-1] if segments else url


def _parse_price(text: str) -> int:
    if not text:
        return 0
    cleaned = text.strip().replace("€", "").strip().replace(".", "").replace(",", ".")
    try:
        return int(float(cleaned))
    except ValueError:
        digits = "".join(c for c in cleaned if c.isdigit())
        return int(digits) if digits else 0
