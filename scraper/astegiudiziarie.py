import re
from urllib.parse import quote
from bs4 import BeautifulSoup
from .schema import Listing
from .geocode import geocode as geocode_fn, GeocodeError

# NOTA: a differenza di subito.py/pvp_giustizia.py, qui "body" NON e' un
# selettore di attesa sicuro. Verificato con Playwright (page.wait_for_selector):
# <body> ha sempre offsetHeight 0 su questo sito (sia sulla pagina risultati
# reale "comune=Jesi" sia su una ricerca legittimamente vuota "comune"
# inesistente), quindi e' considerato "hidden" e wait_for_selector va sempre
# in TimeoutError, anche se il contenuto e' gia' presente nell'HTML servito.
# "header" (la barra di navigazione fissa del sito) e' invece sempre presente
# e visibile (verificato: 80px di altezza) sia con risultati che senza,
# quindi e' il selettore di attesa sicuro qui.
WAIT_SELECTOR = "header"

# Selettori verificati contro fixtures/astegiudiziarie_sample.html (ricerca
# reale per comune "Jesi", categoria "Immobile residenziale": 9 lotti). Il
# markup e' generato da un componente Vue (commenti "<!--v-if-->" nell'HTML
# servito), ma il risultato e' server-side rendered con classi CSS Bootstrap
# stabili (non hash di build), quindi qui i selettori sono exact-match su
# classe, come pvp_giustizia.py.
SELECTOR_CARD = "div.lista-ricerca div.card"
SELECTOR_TITLE = "h2"  # es. "Fabbricato", "Abitazione in villini" - tipologia specifica del bene
SELECTOR_LINK = "a"  # il link che avvolge l'intera card e' il primo <a> nel documento (prima dei link di condivisione social)
# Il prezzo vive in "<span class='text-truncate text-primary' ...><strong>€ X</strong></span>",
# mentre l'etichetta "Prezzo base" vive in un "<small class='text-primary'>" separato:
# selezionare "span.text-primary" (non "small") isola il solo valore numerico.
SELECTOR_PRICE = "p.my-0 > span.text-primary"
SELECTOR_COMUNE = "p.text-muted"  # indirizzo completo, es. "Via Mazzangrugno, 18, 60035 Jesi AN, Italia - Jesi (AN)"
# Il blocco tribunale/data vive in "<p class='mb-0'>" SENZA "text-muted": la
# card di indirizzo usa invece "<p class='text-muted mb-0 text-truncate'>",
# quindi ":not(.text-muted)" e' necessario per non prendere l'indirizzo per
# sbaglio (entrambi i <p> hanno la classe "mb-0" ed entrambi contengono un
# <small>, verificato sulla fixture reale).
SELECTOR_INFO = "p.mb-0:not(.text-muted)"  # es. "Tribunale di Ancona - Esecuzione Immobiliare / Ruolo: ... / Data udienza: 15/10/2026"


def build_search_url(centro_nome: str) -> str:
    """Costruisce l'URL di ricerca astegiudiziarie.it per un comune.

    NOTA (scostamento dalla bozza del piano): la bozza ipotizzava un path SEO
    tipo "/ricerca-aste-immobiliari?categoria=...&localita=...", verificato
    NON funzionante (nessuna pagina del genere esiste). Il sito reale usa un
    form "Cerca per indirizzo" (<form id="formSearchResults" method="post"
    action="/results">) con autocomplete JS-driven (basato su un file
    /assets/json/comuniIstat.json caricato via fetch, non su Google Places
    nonostante la Maps JS API sia comunque caricata in pagina) che al submit
    valorizza campi hidden (comune, provincia, regione, bounding box
    lat/lon). Verificato pero', simulando l'intero flusso UI (digitare
    "Jesi", selezionare il suggerimento "Comune Jesi, AN", selezionare
    "Immobile residenziale" e cliccare "Cerca") e confrontando il risultato,
    che l'endpoint GET /results?comune=<nome>&idTipologie=1&idGenere=1
    &tipoRicerca=1 produce l'IDENTICO risultato (stesso titolo pagina
    "Immobile residenziale all'asta a Jesi", stessi 9 annunci) di una POST
    completa - quindi una GET diretta, piu' semplice e stabile, e' sufficiente:
    - idTipologie=1: "Immobile residenziale" (verificato dalle <option> di
      <select id="tipologia" name="idTipologie">, valori 1-5 per le 5
      macro-categorie del portale)
    - idGenere=1: tab "Immobili" (verificato dai tab "Immobili/Mobili/
      Immateriali/Aziende" vicino al form; e' anche il valore di default)
    - tipoRicerca=1: modalita' di ricerca per indirizzo/comune (valore di
      default del form quando non si attiva "cerca su mappa")

    NOTA IMPORTANTE: a differenza di pvp_giustizia.py (che espone
    raggioAzione=25, un vero raggio in km), questo portale NON espone alcun
    parametro di raggio/distanza nel form di ricerca (verificato: nessun
    campo "raggio"/"distanza"/"radius" tra i ~70 campi di
    #formSearchResults, ne' altrove nella UI di ricerca per indirizzo). La
    ricerca e' per comune esatto (o provincia/regione se si digita quello),
    non per raggio in km attorno a un punto. E' la stessa situazione di fondo
    di subito.py: si cerca per nome del centro (qui: comune esatto), e il
    filtro per raggio_km configurato viene applicato a valle sulle
    coordinate geocodificate (webapp/generate.py), non lato scraper.
    """
    comune = quote(centro_nome)
    return (
        "https://www.astegiudiziarie.it/results"
        f"?comune={comune}&idTipologie=1&idGenere=1&tipoRicerca=1"
    )


def parse_listings(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    for card in soup.select(SELECTOR_CARD):
        title_el = card.select_one(SELECTOR_TITLE)
        link_el = card.select_one(SELECTOR_LINK)
        if not (title_el and link_el and link_el.get("href")):
            continue
        href = link_el["href"]
        url = href if href.startswith("http") else f"https://www.astegiudiziarie.it{href}"
        external_id = _extract_external_id(href)

        price_el = card.select_one(SELECTOR_PRICE)
        prezzo = _parse_price(price_el.get_text(strip=True) if price_el else "")

        comune = _extract_comune(card)
        lat = lon = None
        if comune:
            try:
                lat, lon = geocode_fn(comune)
            except GeocodeError:
                pass

        tribunale, data_asta = _extract_tribunale_e_data(card)

        listings.append(Listing(
            fonte="astegiudiziarie",
            external_id=external_id,
            tipo="asta",
            titolo=title_el.get_text(strip=True),
            prezzo=prezzo,
            url=url,
            # categoria fissa: il filtro "Immobile residenziale" (idTipologie=1)
            # e' applicato server-side dalla query di ricerca stessa
            # (verificato: titolo pagina "Immobile residenziale all'asta a
            # Jesi" e tutti i lotti della fixture sono tipologie abitative),
            # quindi non serve un filtro aggiuntivo lato client come in
            # pvp_giustizia.py (dove la ricerca restituiva categorie miste).
            categoria="residenziale",
            comune=comune,
            lat=lat,
            lon=lon,
            tribunale=tribunale,
            data_asta=data_asta,
            offerta_minima=prezzo,
            chi_vende=None,  # asta giudiziaria: venditore e' la procedura esecutiva, non privato/agenzia
        ))
    return listings


def _extract_external_id(href: str) -> str:
    # es. "/vendita-asta-fabbricato-civile-jesi-...-l2331804-p1313086"
    # "l<n>" e' l'id del lotto, "p<n>" l'id della procedura/annuncio: la
    # coppia e' univoca per lotto (verificato: nella fixture reale due lotti
    # diversi della stessa procedura condividono lo stesso "p", es.
    # "l2327231-p1310167" e "l2327230-p1310167", ma "l" li distingue).
    match = re.search(r"-l(\d+)-p(\d+)$", href)
    if match:
        return f"l{match.group(1)}-p{match.group(2)}"
    return href.rstrip("/").split("/")[-1]


def _extract_comune(card) -> str | None:
    comune_el = card.select_one(SELECTOR_COMUNE)
    if not comune_el:
        return None
    raw = comune_el.get_text(strip=True)
    # Formato indirizzo reale: "Via Mazzangrugno, 18, 60035 Jesi AN, Italia -
    # Jesi (AN)". Il comune pulito e' l'ultimo segmento dopo l'ultimo " - ",
    # con la sigla provincia tra parentesi rimossa.
    last_segment = raw.split(" - ")[-1].strip()
    comune = re.sub(r"\s*\([A-Za-zÀ-ÿ]+\)\s*$", "", last_segment).strip()
    return comune or None


def _extract_tribunale_e_data(card) -> tuple[str | None, str | None]:
    info_el = card.select_one(SELECTOR_INFO)
    if not info_el:
        return None, None

    tribunale = None
    span = info_el.select_one("span.text-truncate")
    if span:
        # es. "Tribunale di Ancona - Esecuzione Immobiliare" -> tribunale e'
        # il segmento prima del primo " - " (il resto e' il tipo di procedura)
        tribunale = span.get_text(strip=True).split(" - ")[0].strip() or None

    # La data compare con etichette diverse a seconda dello stato del lotto
    # (verificato sulla fixture reale: "Data udienza: 15/10/2026" per i lotti
    # con prossima data fissata, "Ultima data vendita: 09/06/2026" per un
    # lotto senza prossima udienza fissata): si estrae la data nel formato
    # gg/mm/aaaa ovunque compaia nel blocco, senza dipendere dall'etichetta.
    text = info_el.get_text(" ", strip=True)
    date_match = re.search(r"\d{2}/\d{2}/\d{4}", text)
    data_asta = date_match.group() if date_match else None

    return tribunale, data_asta


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
