import re
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
# salvato.

WAIT_SELECTOR = "body"

# VERIFICATO contro pagine reali salvate dall'utente (vendita e affitto a
# Jesi). A differenza di Immobiliare.it, Idealista usa classi CSS semantiche
# semplici (non CSS modules con hash) — i selettori draft erano gia'
# corretti quasi tutti, eccetto SELECTOR_COMUNE (sotto).
SELECTOR_CARD = "article.item"
SELECTOR_TITLE = "a.item-link"
SELECTOR_PRICE = ".item-price"
SELECTOR_LINK = "a.item-link"
SELECTOR_DETAIL = ".item-detail-char .item-detail"  # "21 locali", "545 mq", ecc.


def build_search_url(centro_nome: str, provincia: str, tipo: str = "affitto") -> str:
    """Costruisce l'URL di ricerca Idealista.it per un comune+provincia e un tipo di annuncio.

    Pattern URL fornito dall'utente e verificato reale:
    https://www.idealista.it/vendita-case/jesi-ancona/
    https://www.idealista.it/affitto-case/jesi-ancona/
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
    contenuto della pagina.
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
        external_id = _external_id(card, url)

        titolo = title_el.get_text(strip=True)
        comune = _extract_comune(titolo)
        lat = lon = None
        if comune:
            try:
                lat, lon = geocode_fn(comune)
            except (GeocodeError, requests.RequestException):
                pass

        locali, superficie_mq = _extract_details(card)

        listings.append(Listing(
            fonte="idealista",
            external_id=external_id,
            tipo=tipo,
            titolo=titolo,
            prezzo=_parse_price(price_el.get_text(strip=True) if price_el else ""),
            url=url,
            comune=comune,
            lat=lat,
            lon=lon,
            locali=locali,
            superficie_mq=superficie_mq,
            chi_vende=_extract_chi_vende(card),
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


def _extract_comune(titolo: str) -> str | None:
    """Il comune e' l'ultimo segmento del titolo dopo l'ultima virgola
    (verificato su titoli reali, es. "Villa in Via Adeodato Pieralisi, San
    Giuseppe, Jesi" -> "Jesi"). SELECTOR_COMUNE della bozza iniziale
    (".item-detail-char, .item-location") era sbagliato: `.item-detail-char`
    contiene in realta' le caratteristiche (locali/mq), non la localita' —
    corretto qui usando il titolo, che la contiene sempre in coda."""
    if "," not in titolo:
        return None
    comune = titolo.rsplit(",", 1)[-1].strip()
    return comune or None


def _external_id(card, url: str) -> str:
    """L'attributo `data-element-id` dell'<article> e' direttamente l'ID
    numerico dell'annuncio (verificato: es. data-element-id="34938975" per
    .../immobile/34938975/) — piu' affidabile del parsing dell'URL, usato
    solo come fallback se l'attributo manca."""
    element_id = card.get("data-element-id")
    if element_id:
        return element_id
    segments = [seg for seg in url.rstrip("/").split("/") if seg]
    return segments[-1] if segments else url


_LOCALI_RE = re.compile(r"^(\d+)\s*local")
_MQ_RE = re.compile(r"^(\d+)\s*m")


def _extract_details(card) -> tuple[int | None, int | None]:
    """Legge locali/superficie da .item-detail-char .item-detail (verificato:
    testo reale tipo "21 locali", "545 mq" — l'ordine e la presenza dei
    dettagli variano per annuncio, quindi si riconosce ciascuno dal
    contenuto, non dalla posizione)."""
    locali = superficie_mq = None
    for detail in card.select(SELECTOR_DETAIL):
        text = detail.get_text(strip=True)
        m = _LOCALI_RE.match(text)
        if m:
            locali = int(m.group(1))
            continue
        m = _MQ_RE.match(text)
        if m:
            superficie_mq = int(m.group(1))
    return locali, superficie_mq


def _extract_chi_vende(card) -> str | None:
    """L'attributo `data-is-professional-ad` dell'<article> distingue
    esplicitamente annunci di agenzia/professionista da privati (verificato:
    "true" su un annuncio con logo agenzia "Immobiliare Puzielli") — segnale
    diretto del sito, non un'inferenza come per immobiliare.py."""
    value = card.get("data-is-professional-ad")
    if value == "true":
        return "agenzia"
    if value == "false":
        return "privato"
    return None


def _parse_price(text: str) -> int:
    if not text:
        return 0
    cleaned = text.strip().replace("€", "").strip().replace(".", "").replace(",", ".")
    try:
        return int(float(cleaned))
    except ValueError:
        digits = "".join(c for c in cleaned if c.isdigit())
        return int(digits) if digits else 0
