import re
from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing
from .geocode import geocode as geocode_fn, GeocodeError

# Verificato con Playwright (page.wait_for_selector): a differenza di
# astegiudiziarie.it, qui "body" e' un selettore di attesa sicuro (visibile
# sia sulla pagina risultati reale "luoghi=jesi" con 5 lotti).
WAIT_SELECTOR = "body"

# Selettori verificati contro fixtures/asteimmobili_sample.html (ricerca
# reale per luogo "jesi", categoria "residenziali": 5 lotti). Il markup e'
# generato da un componente Vue (attributi "data-v-*", commenti "<!--v-if-->"
# nell'HTML servito), server-side rendered.
#
# NOTA sul parsing con html.parser (unico parser disponibile, niente lxml):
# ogni card ha markup duplicato per la variante responsive mobile/desktop
# (stesso dato ripetuto due volte nel DOM, mostrato/nascosto via classi
# Bootstrap "d-lg-none"/"d-none d-lg-flex"), e per una qualche irregolarita'
# di markup non individuata (probabilmente un tag Vue non bilanciato) tutte
# le 5 card ".card.hover" della pagina finiscono, secondo html.parser, come
# figlie dello STESSO elemento ".card-wrapper" (verificato: stesso id()
# Python per il .parent di tutte e 5), invece di 5 wrapper distinti. Le card
# restano pero' sorelle fra loro (non annidate l'una nell'altra - verificato
# con "c1 in c0.descendants" False in entrambe le direzioni), quindi
# selezionare direttamente "div.card.hover" (non il wrapper) e usare
# card.select_one(...)/card.select(...) per i campi resta sicuro e isolato
# per singola card.
SELECTOR_CARD = "div.card.hover"
# Tipologia specifica del bene (es. "Abitazione di tipo civile") - usata
# come titolo, stesso ruolo di SELECTOR_TITLE in astegiudiziarie.py.
SELECTOR_TITLE = ".card-header a .text-uppercase"
# Il link di dettaglio: NOTA - punta al dominio astalegale.net (la societa'
# madre dello stesso gruppo, copyright "Astalegale.net S.p.A." in homepage),
# NON ad asteimmobili.it (scostamento reale dalla bozza, che assumeva un
# link relativo sullo stesso dominio). E' gia' assoluto.
SELECTOR_LINK = ".card-header a"
# Badge "comune" dedicato della card (es. "Jesi") - testo gia' pulito,
# niente indirizzo/CAP/provincia da ripulire (a differenza di
# astegiudiziarie.py, che deve estrarlo da un indirizzo completo).
SELECTOR_COMUNE = "span.comune"
SELECTOR_TRIBUNALE_ICON = "i.fa-building-columns"
SELECTOR_DATA_ICON = "i.fa-calendar"


def build_search_url(centro_nome: str) -> str:
    """Costruisce l'URL di ricerca asteimmobili.it per un comune.

    NOTA (scostamento dalla bozza del piano): la bozza ipotizzava un path
    tipo "/ricerca?categoria=residenziale&localita=...", verificato NON
    funzionante. Il sito reale (una SPA Vue) usa un widget "Luogo" con
    autocomplete JS-driven (nel tab "Beni immobili" della homepage) che,
    dopo aver digitato "Jesi" e selezionato il suggerimento "Jesi", e
    selezionato la categoria "Residenziali" (dietro l'accordion "Ricerca
    avanzata", non visibile senza espanderlo), sottomette il form e
    reindirizza a:
        https://www.asteimmobili.it/Immobili?categories=residenziali&luoghi=jesi
    Verificato inoltre che una **GET diretta e senza cookie/sessione** a
    questo stesso URL (browser Playwright pulito, nessun consenso cookie
    accettato, nessuna interazione UI) restituisce gli IDENTICI 5 annunci
    (stesso testo pagina "5 Risultati per Immobili nel comune di jesi nella
    categoria residenziali", stessi 5 href di dettaglio) del flusso UI
    completo - quindi una GET diretta, piu' semplice e stabile, e'
    sufficiente. "luoghi" accetta il nome del comune in minuscolo (lo stesso
    testo digitato nell'autocomplete, non un id numerico).

    NOTA IMPORTANTE (stessa situazione di astegiudiziarie.py/subito.py):
    questo portale non espone un parametro di raggio/km nel widget di
    ricerca "Luogo" (solo autocomplete su regione/provincia/comune) - la
    ricerca e' quindi per comune esatto, non per raggio attorno a un punto.
    Il filtro raggio_km configurato va applicato a valle sulle coordinate
    geocodificate (webapp/generate.py), non lato scraper.
    """
    luogo = quote(centro_nome.lower())
    return f"https://www.asteimmobili.it/Immobili?categories=residenziali&luoghi={luogo}"


def parse_listings(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    for card in soup.select(SELECTOR_CARD):
        title_el = card.select_one(SELECTOR_TITLE)
        link_el = card.select_one(SELECTOR_LINK)
        if not (title_el and link_el and link_el.get("href")):
            continue
        href = link_el["href"]
        url = href if href.startswith("http") else f"https://www.asteimmobili.it{href}"
        external_id = _extract_external_id(href)

        prezzo, offerta_minima = _extract_prezzi(card)

        comune = _extract_comune(card)
        lat = lon = None
        if comune:
            try:
                lat, lon = geocode_fn(comune)
            except GeocodeError:
                pass

        tribunale = _extract_tribunale(card)
        data_asta = _extract_data_asta(card)

        listings.append(Listing(
            fonte="asteimmobili",
            external_id=external_id,
            tipo="asta",
            titolo=title_el.get_text(strip=True),
            prezzo=prezzo,
            url=url,
            # categoria fissa: il filtro "categories=residenziali" e'
            # applicato server-side dalla query di ricerca stessa
            # (verificato: il testo della pagina risultati dice "...nella
            # categoria residenziali" e tutti i lotti della fixture sono
            # "Abitazione di tipo civile"), quindi non serve un filtro
            # aggiuntivo lato client come in pvp_giustizia.py.
            categoria="residenziale",
            comune=comune,
            lat=lat,
            lon=lon,
            tribunale=tribunale,
            data_asta=data_asta,
            offerta_minima=offerta_minima,
            chi_vende=None,  # asta giudiziaria: venditore e' la procedura esecutiva, non privato/agenzia
        ))
    return listings


def _extract_external_id(href: str) -> str:
    # es. "https://www.astalegale.net/Aste/Detail/B2428933-Abitazione-di-
    # tipo-civile-Via-Mazzangrugno-18-60035-Jesi-AN-Italia-Jesi" -> "B2428933"
    # (il codice lotto che precede lo slug descrittivo, verificato univoco
    # per lotto sui 5 annunci della fixture reale).
    match = re.search(r"/Aste/Detail/([A-Za-z0-9]+)-", href)
    if match:
        return match.group(1)
    return href.rstrip("/").split("/")[-1]


def _extract_comune(card) -> str | None:
    comune_el = card.select_one(SELECTOR_COMUNE)
    if not comune_el:
        return None
    return comune_el.get_text(strip=True) or None


def _extract_tribunale(card) -> str | None:
    icon = card.select_one(SELECTOR_TRIBUNALE_ICON)
    if not icon or not icon.parent:
        return None
    # il testo del tribunale (es. "Tribunale di Ancona") e' l'unico testo
    # del <span> genitore dell'icona: l'icona stessa non produce testo.
    return icon.parent.get_text(strip=True) or None


def _extract_data_asta(card) -> str | None:
    icon = card.select_one(SELECTOR_DATA_ICON)
    if not icon or not icon.parent:
        return None
    # es. "Data asta: 15/10/2026 - 12:45": si estrae la sola data
    # (gg/mm/aaaa), scartando l'etichetta e l'orario.
    text = icon.parent.get_text(" ", strip=True)
    match = re.search(r"\d{2}/\d{2}/\d{4}", text)
    return match.group() if match else None


def _extract_prezzi(card) -> tuple[int, int | None]:
    # A differenza di astegiudiziarie.py/pvp_giustizia.py (dove
    # offerta_minima e' un placeholder duplicato da prezzo), qui la card
    # mostra due valori distinti nel testo: "Prezzo base: € X" e "Offerta
    # minima: € Y" (verificato sulla fixture reale, X != Y su tutti i 5
    # lotti). Si estraggono entrambi via regex sul testo dell'intera card
    # (il markup e' duplicato mobile/mobile per via responsive, ma i valori
    # sono identici nelle due copie, quindi il primo match e' sufficiente).
    text = card.get_text(" ", strip=True)
    prezzo_match = re.search(r"Prezzo base:\s*€\s*([\d.,]+)", text)
    offerta_match = re.search(r"Offerta minima:\s*€\s*([\d.,]+)", text)
    prezzo = _parse_price(prezzo_match.group(1)) if prezzo_match else 0
    offerta_minima = _parse_price(offerta_match.group(1)) if offerta_match else None
    return prezzo, offerta_minima


def _parse_price(text: str) -> int:
    if not text:
        return 0
    cleaned = text.strip().replace("€", "").strip()
    # Formato italiano: punto = separatore migliaia, virgola = decimali.
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return int(float(cleaned))
    except ValueError:
        digits = "".join(c for c in cleaned if c.isdigit())
        return int(digits) if digits else 0
