import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing
from .geocode import geocode as geocode_fn, GeocodeError

# ATTENZIONE — anti-bot: un fetch di verifica (Playwright headless, poi
# anche headed/non-headless, nessuna evasione tentata in nessuno dei due
# casi) su https://www.immobiliare.it/affitto-case/jesi/ ha restituito in
# entrambi i casi una pagina di blocco DataDome (CAPTCHA in headless, pagina
# di verifica JS in headed — body con solo 14 caratteri di testo, nessun
# annuncio reale) — vedi
# docs/superpowers/reports/task-8-immobiliare-antibot-report.md per
# l'evidenza completa. Questo modulo quindi NON fa parte della pipeline
# automatica giornaliera (non e' in portali_attivi/PORTAL_TIPI di
# config.yaml/run_all.py) e non ci si prova ad aggirare l'anti-bot (niente
# proxy/fingerprint spoofing/captcha-solver).
#
# Percorso valido invece: cattura manuale. L'utente apre la ricerca nel
# proprio browser vero (navigazione umana reale, DataDome non la blocca) via
# scripts/apri_ricerche_manuali.py, salva la pagina, e
# scripts/importa_ricerche_manuali.py chiama parse_listings() su quel file
# salvato. I selettori sotto restano NON VERIFICATI contro markup reale
# finche' non arriva la prima pagina salvata per davvero — i test di questo
# modulo girano nel frattempo contro fixtures/immobiliare_synthetic.html
# (fixture costruita a mano, non scaricata).

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

# NON VERIFICATO — selettori aggiuntivi per le card di "aste-immobiliari"
# (sezione distinta dagli annunci normali, aggiunta senza aver mai visto
# markup reale: nessuna fixture, nemmeno sintetica, la copre ancora).
# Ragionevole prima ipotesi per analogia con gli altri scraper di aste di
# questo progetto (astegiudiziarie.py/asteimmobili.py) — da correggere non
# appena arriva la prima pagina "aste-immobiliari" salvata per davvero.
SELECTOR_TRIBUNALE = ".in-auction__court, .in-card__court"
SELECTOR_DATA_ASTA = ".in-auction__date, .in-card__auctionDate"


def build_search_url(centro_nome: str, tipo: str = "affitto") -> str:
    """Costruisce l'URL di ricerca Immobiliare.it per un comune e un tipo di annuncio.

    Pattern affitto/vendita fornito dall'utente e verificato reale (non piu'
    bozza): https://www.immobiliare.it/vendita-case/jesi/,
    .../affitto-case/jesi/ — Immobiliare.it separa affitto e vendita come
    path distinti, confermato.

    Pattern asta fornito dall'utente e verificato reale (URL, non il
    markup dei risultati): https://www.immobiliare.it/aste-immobiliari/jesi/
    — nota la forma diversa (niente suffisso "-case"), sezione separata dagli
    annunci normali.
    """
    if tipo not in ("affitto", "vendita", "asta"):
        raise ValueError(f"tipo non valido per immobiliare: {tipo}")
    slug = quote(centro_nome.lower())
    if tipo == "asta":
        return f"https://www.immobiliare.it/aste-immobiliari/{slug}/"
    return f"https://www.immobiliare.it/{tipo}-case/{slug}/"


def parse_listings(html: str, tipo: str | None = None) -> list[Listing]:
    """Estrae gli annunci da una pagina di ricerca Immobiliare.it salvata.

    Se `tipo` e' passato esplicitamente (percorso di importazione manuale,
    dove sappiamo gia' da quale ricerca proviene la pagina salvata) viene
    usato direttamente, piu' affidabile del riconoscimento automatico dal
    contenuto della pagina (mai verificato contro markup reale, e comunque
    incapace di riconoscere "asta" — non ha mai visto una pagina aste reale).
    """
    soup = BeautifulSoup(html, "html.parser")
    if tipo is None:
        tipo = _detect_tipo(soup)
    elif tipo not in ("affitto", "vendita", "asta"):
        raise ValueError(f"tipo non valido per immobiliare: {tipo}")
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

        prezzo = _parse_price(price_el.get_text(strip=True) if price_el else "")

        tribunale = data_asta = offerta_minima = None
        if tipo == "asta":
            tribunale_el = card.select_one(SELECTOR_TRIBUNALE)
            data_asta_el = card.select_one(SELECTOR_DATA_ASTA)
            tribunale = tribunale_el.get_text(strip=True) if tribunale_el else None
            data_asta = data_asta_el.get_text(strip=True) if data_asta_el else None
            offerta_minima = None  # NON VERIFICATO: nessun dato reale per distinguerla dal prezzo base

        listings.append(Listing(
            fonte="immobiliare",
            external_id=external_id,
            tipo=tipo,
            titolo=title_el.get_text(strip=True),
            prezzo=prezzo,
            url=url,
            comune=comune,
            lat=lat,
            lon=lon,
            tribunale=tribunale,
            data_asta=data_asta,
            offerta_minima=offerta_minima,
            # chi_vende volutamente non impostato (resta None, default dello
            # schema): nessun dato reale ancora disponibile per verificare se
            # e come Immobiliare.it espone un indicatore privato/agenzia —
            # non si inventa il valore. Da rivedere sulla prima cattura reale.
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
