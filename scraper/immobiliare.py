import re
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
# salvato.

WAIT_SELECTOR = "body"

# VERIFICATO contro pagine reali salvate dall'utente (vendita, affitto, e
# aste-immobiliari a Jesi — tutte e tre usano lo stesso template/le stesse
# classi). Immobiliare.it usa CSS modules con la forma
# "{Componente}_{nomeSemantico}__{hash}" (hash che cambia ad ogni build, come
# gia' visto per Subito.it in Fase 1): match per sottostringa sulla parte
# semantica stabile, non sull'hash. Verificato che non collide con classi non
# correlate (es. "Breadcrumb_item__..." non contiene la sottostringa
# "ListItem_item__card"; ".item-price" di Idealista e' un file/sito diverso e
# non rilevante qui).
SELECTOR_CARD = "li[class*='ListItem_item__card']"
SELECTOR_TITLE = "a[class*='Title_title__']"
SELECTOR_PRICE = "[class*='Price_price__']"
SELECTOR_LINK = "a[class*='Title_title__']"
SELECTOR_FEATURE = "[class*='FeatureList_item__']"  # aria-label = "4 locali", "153 mq", "Arredato", ecc.
# Presenza di questo elemento (logo o placeholder testuale "Agenzia") = annuncio
# di agenzia; assenza = privato. Verificato su 25 card reali (vendita Jesi):
# le card con "AgencyLogo_" hanno sempre un img alt=<nome agenzia>, quella
# senza alcun elemento agenzia (1 card su 25 osservate) non ha branding —
# nessun'altra osservazione diretta di un badge "Privato" esplicito, quindi
# l'assunzione "nessun logo agenzia => privato" e' un'inferenza dal pattern
# osservato, non una label esplicita del sito.
SELECTOR_AGENZIA = "[class*='AgencyLogo_'], [class*='AgencyPlaceholder_']"


def build_search_url(centro_nome: str, tipo: str = "affitto") -> str:
    """Costruisce l'URL di ricerca Immobiliare.it per un comune e un tipo di annuncio.

    Pattern affitto/vendita/asta forniti dall'utente e verificati reali:
    https://www.immobiliare.it/vendita-case/jesi/,
    .../affitto-case/jesi/, .../aste-immobiliari/jesi/ (nota: le aste non
    hanno il suffisso "-case", sezione separata dagli annunci normali ma con
    lo stesso template di card nei risultati — verificato).
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
    usato direttamente — piu' affidabile del riconoscimento automatico dal
    contenuto della pagina, che comunque non sa riconoscere "asta".
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
        external_id = _external_id_from_card(card, url)

        titolo = title_el.get_text(strip=True)
        # NOTA: verificato sulla ricerca vendita reale di Jesi (7 casi su 25)
        # che immobiliare.it mescola annunci d'asta dentro i risultati di
        # vendita/affitto normali (titolo tipo "Villa all'asta via X, Jesi"),
        # non solo nella sezione aste-immobiliari dedicata. Il tipo della
        # singola card si corregge quindi dal proprio titolo, indipendente
        # dal tipo della ricerca/pagina.
        tipo_card = "asta" if "all'asta" in titolo.lower() else tipo
        comune = _extract_comune(titolo)
        lat = lon = None
        if comune:
            try:
                lat, lon = geocode_fn(comune)
            except (GeocodeError, requests.RequestException):
                pass

        prezzo = _parse_price(price_el.get_text(strip=True) if price_el else "")
        locali, superficie_mq, arredato = _extract_features(card)
        chi_vende = _extract_chi_vende(card)

        # NON VERIFICATO: tribunale e data_asta non compaiono nella vista
        # elenco delle aste (solo titolo + prezzo "da X€", verificato sulla
        # pagina aste-immobiliari reale) — probabilmente visibili solo nella
        # pagina di dettaglio del singolo annuncio, che questo scraper non
        # visita (stesso limite di PVP giustizia in Fase 1). offerta_minima
        # coincide con prezzo qui: e' l'unico valore mostrato in elenco.
        tribunale = data_asta = None
        offerta_minima = prezzo if tipo_card == "asta" else None

        listings.append(Listing(
            fonte="immobiliare",
            external_id=external_id,
            tipo=tipo_card,
            titolo=titolo,
            prezzo=prezzo,
            url=url,
            comune=comune,
            lat=lat,
            lon=lon,
            locali=locali,
            superficie_mq=superficie_mq,
            arredato=arredato,
            tribunale=tribunale,
            data_asta=data_asta,
            offerta_minima=offerta_minima,
            chi_vende=chi_vende,
        ))
    return listings


def _detect_tipo(soup: BeautifulSoup) -> str:
    heading = soup.find("h1")
    title_tag = soup.title
    text = " ".join([
        heading.get_text() if heading else "",
        title_tag.get_text() if title_tag else "",
    ]).lower()
    if "asta" in text:
        return "asta"
    return "vendita" if "vendita" in text else "affitto"


def _extract_comune(titolo: str) -> str | None:
    """Il comune e' l'ultimo segmento del titolo dopo l'ultima virgola
    (verificato su titoli reali, es. "Quadrilocale via Erbarella 8, San
    Pietro Martire - Erbarella, Jesi" -> "Jesi"). Non c'e' un elemento HTML
    dedicato alla localita' nella card (la bozza iniziale lo assumeva
    erroneamente)."""
    if "," not in titolo:
        return None
    comune = titolo.rsplit(",", 1)[-1].strip()
    return comune or None


def _external_id_from_card(card, url: str) -> str:
    """L'attributo `id` del <li> della card e' direttamente l'ID numerico
    dell'annuncio (verificato: es. id="131775402" per
    .../annunci/131775402/) — piu' affidabile del parsing dell'URL, usato
    solo come fallback se l'attributo manca."""
    card_id = card.get("id")
    if card_id:
        return card_id
    segments = [seg for seg in url.split("/") if seg]
    return segments[-1] if segments else url


_LOCALI_RE = re.compile(r"^(\d+)\s*local")
_MQ_RE = re.compile(r"^(\d+)\s*m")


def _extract_features(card) -> tuple[int | None, int | None, str]:
    """Legge locali/superficie/arredamento dagli aria-label delle icone
    FeatureList (verificato: es. "4 locali", "153 mq", "Parzialmente
    Arredato" — testo reale, non assunto)."""
    locali = superficie_mq = None
    arredato = "non_specificato"
    for feat in card.select(SELECTOR_FEATURE):
        label = (feat.get("aria-label") or "").strip()
        if not label:
            continue
        m = _LOCALI_RE.match(label)
        if m:
            locali = int(m.group(1))
            continue
        m = _MQ_RE.match(label)
        if m:
            superficie_mq = int(m.group(1))
            continue
        lowered = label.lower()
        if lowered == "arredato":
            arredato = "si"
        elif lowered == "non arredato":
            arredato = "no"
        elif "arredat" in lowered:
            arredato = lowered  # es. "parzialmente arredato": info reale, non forzata in si/no
    return locali, superficie_mq, arredato


def _extract_chi_vende(card) -> str | None:
    """"agenzia" se la card mostra un logo/placeholder agenzia, "privato"
    altrimenti — inferenza dal pattern osservato (vedi nota su
    SELECTOR_AGENZIA), non una label esplicita "Privato" mai vista sul sito."""
    return "agenzia" if card.select_one(SELECTOR_AGENZIA) else "privato"


def _parse_price(text: str) -> int:
    if not text:
        return 0
    cleaned = text.strip().replace("€", "").strip().replace(".", "").replace(",", ".")
    # Le aste mostrano "da 28.800,00 €": "da" non e' numerico, va scartato
    # prima della conversione.
    cleaned = re.sub(r"[^\d.]", "", cleaned)
    try:
        return int(float(cleaned)) if cleaned else 0
    except ValueError:
        digits = "".join(c for c in cleaned if c.isdigit())
        return int(digits) if digits else 0
