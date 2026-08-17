# NOTA IMPORTANTE: Immobiliare.it e' bloccato da anti-bot DataDome per fetch
# automatici (headless e headed, entrambi verificati bloccati — vedi
# docs/superpowers/reports/task-8-immobiliare-antibot-report.md). I selettori
# in scraper/immobiliare.py sono pero' VERIFICATI: le fixture qui sotto sono
# pagine reali salvate manualmente dall'utente nel proprio browser
# (percorso: scripts/apri_ricerche_manuali.py + scripts/importa_ricerche_manuali.py,
# vedi scraper/immobiliare.py per i dettagli), non piu' dati sintetici.
from pathlib import Path
import scraper.immobiliare as imm_module
from scraper.immobiliare import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "immobiliare_sample.html"  # ricerca "vendita" reale, Jesi
FIXTURE_ASTA = Path(__file__).parent.parent / "fixtures" / "immobiliare_asta_sample.html"  # ricerca "aste-immobiliari" reale, Jesi


def test_build_search_url_includes_centro_nome():
    url = build_search_url("Jesi")
    assert "immobiliare.it" in url
    assert "jesi" in url.lower()


def test_build_search_url_accepts_tipo_and_changes_path():
    affitto_url = build_search_url("Jesi", tipo="affitto")
    vendita_url = build_search_url("Jesi", tipo="vendita")
    assert "affitto" in affitto_url
    assert "vendita" in vendita_url
    assert affitto_url != vendita_url


def test_build_search_url_asta_matches_real_pattern_fornito_dall_utente():
    # Pattern reale fornito dall'utente: niente suffisso "-case" per le aste,
    # a differenza di affitto/vendita.
    assert build_search_url("Jesi", tipo="asta") == "https://www.immobiliare.it/aste-immobiliari/jesi/"


def test_build_search_url_rejects_invalid_tipo():
    try:
        build_search_url("Jesi", tipo="boh")
    except ValueError:
        pass
    else:
        raise AssertionError("tipo non valido avrebbe dovuto sollevare ValueError")


def test_parse_listings_extracts_expected_fields(monkeypatch):
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html, tipo="vendita")
    assert len(listings) == 25  # verificato: 25 card reali sulla pagina salvata
    first = listings[0]
    assert first.fonte == "immobiliare"
    assert first.categoria == "residenziale"
    assert first.external_id == "131775402"  # attributo id del <li>, verificato
    assert first.titolo.startswith("Quadrilocale via Erbarella")
    assert first.prezzo == 250000
    assert first.url == "https://www.immobiliare.it/annunci/131775402/"
    assert first.comune == "Jesi"


def test_parse_listings_returns_empty_list_for_no_matches(monkeypatch):
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    assert parse_listings("<html><body>nessun annuncio</body></html>", tipo="vendita") == []


def test_parse_listings_rejects_invalid_explicit_tipo(monkeypatch):
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    try:
        parse_listings(html, tipo="boh")
    except ValueError:
        pass
    else:
        raise AssertionError("tipo non valido avrebbe dovuto sollevare ValueError")


def test_parse_listings_reclassifies_auction_cards_within_vendita_search(monkeypatch):
    # Scoperta reale (non nel piano originale): la ricerca "vendita" mischia
    # annunci d'asta veri e propri (titolo "Villa all'asta via X, Jesi") tra
    # i risultati normali — 7 casi su 25 nella fixture reale. Il tipo della
    # singola card si corregge dal proprio titolo, non dal tipo della pagina.
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html, tipo="vendita")
    aste = [l for l in listings if l.tipo == "asta"]
    vendite = [l for l in listings if l.tipo == "vendita"]
    assert len(aste) == 7
    assert len(vendite) == 18
    assert all("all'asta" in l.titolo.lower() for l in aste)
    assert all(l.offerta_minima == l.prezzo for l in aste)  # unico valore disponibile in elenco
    assert all(l.offerta_minima is None for l in vendite)


def test_selector_card_matches_exactly_25_real_cards():
    from bs4 import BeautifulSoup
    html = FIXTURE.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    matches = soup.select(imm_module.SELECTOR_CARD)
    assert len(matches) == 25


def test_parse_listings_extracts_locali_superficie_arredato(monkeypatch):
    # Verificato su annunci reali: "4 locali", "153 mq", "Parzialmente Arredato".
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html, tipo="vendita")
    first = listings[0]
    assert first.locali == 4
    assert first.superficie_mq == 153
    assert first.arredato == "parzialmente arredato"


def test_parse_listings_chi_vende_from_agency_badge_presence(monkeypatch):
    # Verificato su annunci reali: la prima card (senza logo agenzia) e'
    # "privato", la seconda (logo "Alfalux S.R.L.S") e' "agenzia".
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html, tipo="vendita")
    assert listings[0].chi_vende == "privato"
    assert listings[1].chi_vende == "agenzia"
    assert any(l.chi_vende == "agenzia" for l in listings)
    assert any(l.chi_vende == "privato" for l in listings)


def test_parse_listings_geocodes_comune_when_present(monkeypatch):
    calls = []

    def fake_geocode(comune):
        calls.append(comune)
        return (43.5, 13.2)

    monkeypatch.setattr(imm_module, "geocode_fn", fake_geocode)
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html, tipo="vendita")
    assert len(listings) > 0
    assert calls
    assert listings[0].lat == 43.5
    assert listings[0].lon == 13.2


def test_parse_listings_asta_page_extracts_expected_fields(monkeypatch):
    # Pagina "aste-immobiliari" dedicata (non mischiata come sopra): 4
    # aste reali trovate per Jesi.
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE_ASTA.read_text(encoding="utf-8")
    listings = parse_listings(html, tipo="asta")
    assert len(listings) == 4
    first = listings[0]
    assert first.tipo == "asta"
    assert first.external_id == "130802974"
    assert first.prezzo == 28800  # testo reale: "da 28.800,00 �", il prefisso "da" va scartato
    assert first.offerta_minima == 28800
    assert first.tribunale is None  # non visibile in elenco, non inventato
    assert first.data_asta is None  # idem
    assert first.chi_vende == "agenzia"
