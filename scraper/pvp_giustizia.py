import re
from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing
from .geocode import geocode as geocode_fn, GeocodeError

# NOTA: verificato che la ricerca "Ricerca Geografica" per "localita" renderizza
# i risultati lato server (Angular Universal / SSR): la fixture, catturata con
# wait_selector="body" e delay_ms=4000, contiene gia' tutte le card dei lotti
# nella risposta HTML iniziale. "body" resta comunque il selettore di attesa
# piu' sicuro (stesso ragionamento di subito.py): una ricerca legittimamente
# senza risultati non fa comparire il contenitore <app-annuncio-card>, quindi
# attendere un selettore piu' specifico rischierebbe un TimeoutError.
WAIT_SELECTOR = "body"

# Selettori verificati contro fixtures/pvp_giustizia_sample.html (ricerca reale
# "Ricerca Geografica" per raggio d'azione 25km attorno a "Jesi", categoria
# IMMOBILI: 12 lotti, di cui 9 "Immobile Residenziale", 2 "Immobile
# Commerciale", 1 "Altra Categoria"). Il portale e' una SPA Angular
# ("app-annuncio-card" e' l'elemento custom che avvolge ogni card di lotto),
# ma il markup renderizzato usa classi CSS semantiche stabili (non hash di
# build come Subito), quindi qui i selettori sono exact-match su classe.
SELECTOR_CARD = "app-annuncio-card"
SELECTOR_TITLE = ".gui-card-title-text"  # es. "Lotto n. 1" - e' anche il link
SELECTOR_LINK = ".gui-card-title-text"
SELECTOR_DESC = ".gui-card-subtext-inner"  # descrizione del bene (piu' informativa del solo "Lotto n. X")
SELECTOR_PRICE = ".gui-card-price"  # es. "83.346,63" (formato IT, senza simbolo valuta)
SELECTOR_CATEGORY_CHIP = ".gui-chip-card"  # es. "Immobile Residenziale" / "Immobile Commerciale" / "Altra Categoria"
SELECTOR_COMUNE = ".gui-card-address-text"  # indirizzo completo, es. "Via Colle Pacifico, 3, 60035 Jesi"
SELECTOR_DATA_ASTA = ".gui-card-header .gui-text-tile-text"  # "Data vendita", es. "11/05/2018 15:30"
SELECTOR_DATA_PUBBLICAZIONE = ".gui-card-other-info .gui-text-tile-text"  # "Data Pubblicazione:", es. "26/03/2018"

# NOTA IMPORTANTE (correzione rispetto alla bozza del piano): la vista elenco
# lotti (questa pagina) NON espone il tribunale per singolo lotto nella card.
# La stringa "tribunale" compare nell'HTML solo come filtro nel form di
# ricerca avanzata (menu a tendina con tutti i ~140 tribunali italiani), non
# come dato per-lotto. Il tribunale competente e' visibile solo nella pagina
# di dettaglio del singolo annuncio (detail_annuncio.page?idAnnuncio=...), che
# questo scraper non visita (fuori scope: richiederebbe una fetch aggiuntiva
# per ogni lotto). SELECTOR_TRIBUNALE e' quindi None: non esiste un selettore
# verificabile in questa vista, e il campo tribunale del Listing resta sempre
# None, onestamente, invece di essere popolato con un selettore fittizio che
# non troverebbe mai nulla.
SELECTOR_TRIBUNALE = None

CATEGORIA_RESIDENZIALE_LABEL = "Immobile Residenziale"


def build_search_url(centro_nome: str) -> str:
    """Costruisce l'URL di ricerca del Portale Vendite Pubbliche.

    NOTA: la bozza iniziale del piano ("risultati_ricerca.page?categoria=...")
    e' stata verificata NON funzionante: restituisce una pagina 404 "Pagina
    non trovata" reale (verificato con una fetch diretta). Il portale e' una
    SPA Angular il cui form di ricerca "Cerca un indirizzo" e' un autocomplete
    che normalmente richiede interazione JS per geocodificare il testo
    digitato. La ricerca "Ricerca Geografica" pero' accetta anche un URL con
    query string diretta (trovato tramite ricerca di URL reali indicizzati di
    pvp.giustizia.it, poi verificato con una fetch reale): la pagina
    "lista_annunci.page" con searchWith=Ricerca+Geografica e localita=<nome>
    produce risultati reali gia' renderizzati lato server, senza bisogno di
    passare "regione"/"nazione" (verificato: stessi 12 risultati identici
    con o senza questi due parametri).
    """
    localita = quote(centro_nome)
    return (
        "https://pvp.giustizia.it/pvp/it/lista_annunci.page"
        "?searchType=searchForm&page=0&size=12"
        "&sortProperty=dataOraVendita%2Casc&sortAlpha=citta%2Casc"
        f"&searchWith=Ricerca+Geografica&localita={localita}&raggioAzione=25"
        "&codTipoLotto=IMMOBILI"
    )


def parse_listings(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    for card in soup.select(SELECTOR_CARD):
        chip_el = card.select_one(SELECTOR_CATEGORY_CHIP)
        categoria_label = chip_el.get_text(strip=True) if chip_el else ""
        if categoria_label != CATEGORIA_RESIDENZIALE_LABEL:
            # Fuori scope MVP: qui si trattano solo immobili residenziali.
            # La ricerca per raggio d'azione restituisce anche lotti
            # commerciali e "altra categoria" (verificato nella fixture
            # reale), quindi vanno scartati esplicitamente.
            continue

        title_el = card.select_one(SELECTOR_TITLE)
        link_el = card.select_one(SELECTOR_LINK)
        if not (title_el and link_el and link_el.get("href")):
            continue
        href = link_el["href"]
        url = href if href.startswith("http") else f"https://pvp.giustizia.it{href}"
        external_id = _extract_external_id(url)

        desc_el = card.select_one(SELECTOR_DESC)
        titolo = _build_titolo(title_el.get_text(strip=True), desc_el)

        price_el = card.select_one(SELECTOR_PRICE)
        prezzo = _parse_price(price_el.get_text(strip=True) if price_el else "")

        data_asta_el = card.select_one(SELECTOR_DATA_ASTA)
        data_pubblicazione_el = card.select_one(SELECTOR_DATA_PUBBLICAZIONE)

        comune = _extract_comune(card)
        lat = lon = None
        if comune:
            try:
                lat, lon = geocode_fn(comune)
            except GeocodeError:
                pass

        listings.append(Listing(
            fonte="pvp_giustizia",
            external_id=external_id,
            tipo="asta",
            titolo=titolo,
            prezzo=prezzo,
            url=url,
            categoria="residenziale",
            comune=comune,
            lat=lat,
            lon=lon,
            tribunale=None,  # non disponibile nella vista elenco (vedi nota sopra)
            data_asta=data_asta_el.get_text(strip=True) if data_asta_el else None,
            data_pubblicazione=data_pubblicazione_el.get_text(strip=True) if data_pubblicazione_el else None,
            offerta_minima=prezzo,
        ))
    return listings


def _build_titolo(lotto_label: str, desc_el) -> str:
    desc = desc_el.get_text(strip=True) if desc_el else ""
    return f"{lotto_label} - {desc}" if desc else lotto_label


def _extract_external_id(url: str) -> str:
    # es. "https://pvp.giustizia.it/pvp/it/detail_annuncio.page?idAnnuncio=116192"
    # -> "116192"
    match = re.search(r"idAnnuncio=(\d+)", url)
    if match:
        return match.group(1)
    return url.rstrip("/").split("/")[-1]


def _extract_comune(card) -> str | None:
    comune_el = card.select_one(SELECTOR_COMUNE)
    if not comune_el:
        return None
    raw = comune_el.get_text(strip=True)
    # L'indirizzo completo e' tipo "Via Colle Pacifico, 3, 60035 Jesi" o
    # "Via Roncaglia 83, Jesi": il comune e' l'ultimo segmento dopo l'ultima
    # virgola, eventualmente preceduto dal CAP (5 cifre) da rimuovere.
    last_segment = raw.split(",")[-1].strip()
    comune = re.sub(r"^\d{5}\s*", "", last_segment).strip()
    return comune or None


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
