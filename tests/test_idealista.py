# NOTA IMPORTANTE: Idealista.it e' bloccato da anti-bot DataDome per fetch
# automatici (headless e headed, entrambi verificati bloccati — vedi
# docs/superpowers/reports/task-9-idealista-antibot-report.md). I selettori
# in scraper/idealista.py sono pero' VERIFICATI: la fixture qui sotto e' una
# pagina reale salvata manualmente dall'utente nel proprio browser
# (percorso: scripts/apri_ricerche_manuali.py + scripts/importa_ricerche_manuali.py,
# vedi scraper/idealista.py per i dettagli), non piu' dati sintetici.
from pathlib import Path
import scraper.idealista as idealista_module
from scraper.idealista import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "idealista_sample.html"  # ricerca "vendita" reale, Jesi


def test_build_search_url_includes_centro_nome_e_provincia():
    url = build_search_url("Jesi", "Ancona")
    assert "idealista.it" in url
    assert "jesi" in url.lower()
    assert "ancona" in url.lower()


def test_build_search_url_matches_real_pattern_fornito_dall_utente():
    assert build_search_url("Jesi", "Ancona", tipo="vendita") == "https://www.idealista.it/vendita-case/jesi-ancona/"
    assert build_search_url("Jesi", "Ancona", tipo="affitto") == "https://www.idealista.it/affitto-case/jesi-ancona/"


def test_build_search_url_accepts_tipo_and_changes_path():
    affitto_url = build_search_url("Jesi", "Ancona", tipo="affitto")
    vendita_url = build_search_url("Jesi", "Ancona", tipo="vendita")
    assert "affitto" in affitto_url
    assert "vendita" in vendita_url
    assert affitto_url != vendita_url


def test_build_search_url_rejects_invalid_tipo():
    try:
        build_search_url("Jesi", "Ancona", tipo="asta")
    except ValueError:
        pass
    else:
        raise AssertionError("tipo non valido avrebbe dovuto sollevare ValueError")


def test_parse_listings_extracts_expected_fields(monkeypatch):
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html, tipo="vendita")
    assert len(listings) == 30  # verificato: 30 card reali sulla pagina salvata
    first = listings[0]
    assert first.fonte == "idealista"
    assert first.tipo == "vendita"
    assert first.categoria == "residenziale"
    assert first.external_id == "34938975"  # attributo data-element-id, verificato
    assert first.titolo.startswith("Villa in Via Adeodato Pieralisi")
    assert first.prezzo == 920000
    assert first.url == "https://www.idealista.it/immobile/34938975/"
    assert first.comune == "Jesi"


def test_parse_listings_returns_empty_list_for_no_matches(monkeypatch):
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    assert parse_listings("<html><body>nessun annuncio</body></html>", tipo="vendita") == []


def test_parse_listings_uses_explicit_tipo_when_given(monkeypatch):
    # Percorso di importazione manuale: sappiamo gia' da quale ricerca
    # proviene il file salvato, non serve indovinarlo dal contenuto pagina.
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html, tipo="affitto")
    assert all(l.tipo == "affitto" for l in listings)


def test_parse_listings_rejects_invalid_explicit_tipo(monkeypatch):
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    try:
        parse_listings(html, tipo="asta")
    except ValueError:
        pass
    else:
        raise AssertionError("tipo non valido avrebbe dovuto sollevare ValueError")


def test_selector_card_matches_exactly_30_real_cards():
    from bs4 import BeautifulSoup
    html = FIXTURE.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    matches = soup.select(idealista_module.SELECTOR_CARD)
    assert len(matches) == 30


def test_parse_listings_extracts_locali_e_superficie(monkeypatch):
    # Verificato su annunci reali: "21 locali", "545 mq".
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html, tipo="vendita")
    first = listings[0]
    assert first.locali == 21
    assert first.superficie_mq == 545


def test_parse_listings_chi_vende_true_maps_to_agenzia(monkeypatch):
    # Verificato: data-is-professional-ad="true" sulla prima card reale
    # (agenzia "Immobiliare Puzielli").
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html, tipo="vendita")
    assert listings[0].chi_vende == "agenzia"
    assert all(l.chi_vende == "agenzia" for l in listings)  # fixture reale: nessun annuncio privato in questo set


def test_extract_chi_vende_false_maps_to_privato():
    # data-is-professional-ad="false" non e' presente in questa fixture
    # reale (tutti gli annunci trovati sono di agenzia) — verifica diretta
    # della funzione di mapping, non dell'estrazione end-to-end dalla pagina.
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(
        '<article class="item" data-is-professional-ad="false"></article>', "html.parser"
    )
    card = soup.select_one("article.item")
    assert idealista_module._extract_chi_vende(card) == "privato"


def test_parse_listings_geocodes_comune_when_present(monkeypatch):
    calls = []

    def fake_geocode(comune):
        calls.append(comune)
        return (43.5, 13.2)

    monkeypatch.setattr(idealista_module, "geocode_fn", fake_geocode)
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html, tipo="vendita")
    assert len(listings) > 0
    assert calls
    assert listings[0].lat == 43.5
    assert listings[0].lon == 13.2
