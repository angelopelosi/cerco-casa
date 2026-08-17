import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing
from .geocode import geocode as geocode_fn, GeocodeError

# ATTENZIONE — Task 9, Step 0 (verifica fattibilita' anti-bot): il fetch di
# verifica (Playwright headless, fetch normale, nessuna evasione tentata) su
# https://www.idealista.it/affitto-case/jesi-marche/ ha restituito una pagina
# di blocco DataDome CAPTCHA (non risultati reali) — pagina di 1499 byte,
# <title>idealista.it</title>, iframe title="DataDome CAPTCHA" verso
# geo.captcha-delivery.com — vedi
# docs/superpowers/reports/task-9-idealista-antibot-report.md per l'evidenza completa
# (stesso schema di blocco riscontrato da Task 8 su immobiliare.it). Di
# conseguenza NON e' stato possibile catturare una fixture reale ne'
# verificare i selettori sotto contro il markup reale del sito. I test di
# questo modulo girano contro fixtures/idealista_synthetic.html, una fixture
# costruita a mano (non scaricata) — vedi commento in testa a quel file e a
# tests/test_idealista.py.
# Questo modulo NON e' registrato in portali_attivi/PORTAL_TIPI/PORTAL_MODULES:
# la Task 11 deve saltarlo finche' non ci sara' una riverifica manuale
# dell'accesso al sito.

WAIT_SELECTOR = "body"

# NON VERIFICATO: cattura bloccata da anti-bot (Step 0, vedi nota sopra).
# Selettori di partenza presi dalla bozza del brief, non confermati contro
# HTML reale — potrebbero non corrispondere al markup effettivo del sito.
# Nota: sono gia' scritti come selettori CSS per classe/tag esatti (es.
# ".item-price", non "[class*='item-price']"), non per sottostringa
# dell'attributo class — lezione appresa dal fix-round di Task 8
# (immobiliare.py), dove un selettore a sottostringa matchava per errore
# anche classi figlie BEM tipo "in-card__title" essendo "in-card" una
# sottostringa. Qui, usando ".item"/".item-link"/".item-price"/ecc., il
# selettore CSS matcha per token di classe esatto: una eventuale classe
# figlia come "item-price-al-mq" NON verrebbe matchata da ".item-price".
SELECTOR_CARD = "article.item"
SELECTOR_TITLE = "a.item-link"
SELECTOR_PRICE = ".item-price"
SELECTOR_COMUNE = ".item-detail-char, .item-location"
SELECTOR_LINK = "a.item-link"


def build_search_url(centro_nome: str, tipo: str = "affitto") -> str:
    """Costruisce l'URL di ricerca Idealista.it per un comune e un tipo di annuncio.

    NON VERIFICATO end-to-end: e' lo stesso URL (per centro_nome="Jesi",
    tipo="affitto") usato per il fetch di verifica fattibilita' dello
    Step 0, che e' stato bloccato da un CAPTCHA anti-bot prima di poter
    confermare se la pagina di risultati raggiunta sia effettivamente
    corretta. Come Subito.it e Immobiliare.it, si assume che Idealista
    separi affitto e vendita come path distinti (bozza del brief, non
    confermato dal sito reale).
    """
    if tipo not in ("affitto", "vendita"):
        raise ValueError(f"tipo non valido per idealista: {tipo}")
    path = "affitto-case" if tipo == "affitto" else "vendita-case"
    slug = quote(centro_nome.lower())
    return f"https://www.idealista.it/{path}/{slug}-marche/"


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
        url = href if href.startswith("http") else f"https://www.idealista.it{href}"
        external_id = _external_id_from_url(url)

        comune = _extract_comune(card)
        lat = lon = None
        if comune:
            try:
                lat, lon = geocode_fn(comune)
            except (GeocodeError, requests.RequestException):
                pass

        listings.append(Listing(
            fonte="idealista",
            external_id=external_id,
            tipo=tipo,
            titolo=title_el.get_text(strip=True),
            prezzo=_parse_price(price_el.get_text(strip=True) if price_el else ""),
            url=url,
            comune=comune,
            lat=lat,
            lon=lon,
            # chi_vende volutamente non impostato (resta None, default dello
            # schema): nessun dato reale disponibile per verificare se/come
            # Idealista espone un indicatore privato/agenzia (stesso motivo
            # di Task 8 su immobiliare.py).
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
    """Ultimo segmento non vuoto del path dell'URL, a prescindere da eventuali
    slash finali (stessa correzione applicata in immobiliare.py, Task 8, dove
    la bozza originale con `[-2] if url.endswith('/') else [-1]` restituiva
    erroneamente il segmento statico precedente l'ID per URL terminanti con
    "/"). Qui si evita direttamente il bug facendo `rstrip("/")` prima dello
    split, indipendentemente dallo slash finale.
    """
    segments = [seg for seg in url.rstrip("/").split("/") if seg]
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
