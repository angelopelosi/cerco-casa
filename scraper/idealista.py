import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing
from .geocode import geocode as geocode_fn, GeocodeError

# ATTENZIONE — anti-bot: un fetch di verifica (Playwright headless, poi
# anche headed/non-headless, nessuna evasione tentata in nessuno dei due
# casi) su https://www.idealista.it/affitto-case/jesi-marche/ ha restituito
# in entrambi i casi una pagina di blocco DataDome (CAPTCHA in headless,
# pagina di verifica JS in headed — body con 14 caratteri di testo, nessun
# annuncio reale) — vedi
# docs/superpowers/reports/task-9-idealista-antibot-report.md per l'evidenza
# completa. Questo modulo quindi NON fa parte della pipeline automatica
# giornaliera (non e' in portali_attivi/PORTAL_TIPI di config.yaml/run_all.py)
# e non ci si prova ad aggirare l'anti-bot (niente proxy/fingerprint
# spoofing/captcha-solver).
#
# Percorso valido invece: cattura manuale. L'utente apre la ricerca nel
# proprio browser vero (navigazione umana reale, DataDome non la blocca) via
# scripts/apri_ricerche_manuali.py, salva la pagina, e
# scripts/importa_ricerche_manuali.py chiama parse_listings() su quel file
# salvato. I selettori sotto restano NON VERIFICATI contro markup reale
# finche' non arriva la prima pagina salvata per davvero — i test di questo
# modulo girano nel frattempo contro fixtures/idealista_synthetic.html
# (fixture costruita a mano, non scaricata).

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


def build_search_url(centro_nome: str, provincia: str, tipo: str = "affitto") -> str:
    """Costruisce l'URL di ricerca Idealista.it per un comune+provincia e un tipo di annuncio.

    Pattern URL fornito dall'utente e verificato reale (non piu' bozza):
    https://www.idealista.it/vendita-case/jesi-ancona/
    https://www.idealista.it/affitto-case/jesi-ancona/
    — comune e provincia uniti da un trattino, non la sola regione come
    nella bozza iniziale (che usava "-marche", mai verificata e sostituita).
    """
    if tipo not in ("affitto", "vendita"):
        raise ValueError(f"tipo non valido per idealista: {tipo}")
    path = "affitto-case" if tipo == "affitto" else "vendita-case"
    comune_slug = quote(centro_nome.lower())
    provincia_slug = quote(provincia.lower())
    return f"https://www.idealista.it/{path}/{comune_slug}-{provincia_slug}/"


def parse_listings(html: str, tipo: str | None = None) -> list[Listing]:
    """Estrae gli annunci da una pagina di ricerca Idealista.it salvata.

    Se `tipo` e' passato esplicitamente (percorso di importazione manuale,
    dove sappiamo gia' da quale ricerca proviene la pagina salvata) viene
    usato direttamente, piu' affidabile del riconoscimento automatico dal
    contenuto della pagina (mai verificato contro markup reale).
    """
    soup = BeautifulSoup(html, "html.parser")
    if tipo is None:
        tipo = _detect_tipo(soup)
    elif tipo not in ("affitto", "vendita"):
        raise ValueError(f"tipo non valido per idealista: {tipo}")
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
