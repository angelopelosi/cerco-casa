# NOTA IMPORTANTE: Task 8 (Immobiliare.it) e' passato per il percorso di
# fallback previsto dal brief. Lo Step 0 (verifica fattibilita' anti-bot,
# fetch Playwright headless normale su
# https://www.immobiliare.it/affitto-case/jesi/, nessuna evasione tentata) ha
# restituito una pagina di blocco DataDome CAPTCHA, non risultati reali (vedi
# task-8-report.md per l'HTML del blocco). Di conseguenza NON e' stato
# possibile catturare una fixture reale come per subito/astegiudiziarie/
# asteimmobili: `fixtures/immobiliare_synthetic.html` e' una pagina
# costruita a mano da questo task, strutturalmente coerente con i selettori
# di bozza del brief (SELECTOR_CARD/TITLE/PRICE/COMUNE/LINK), NON dati reali
# scaricati dal sito. I selettori in scraper/immobiliare.py restano quindi
# NON VERIFICATI contro il markup reale del sito.
from pathlib import Path
from bs4 import BeautifulSoup
import scraper.immobiliare as imm_module
from scraper.immobiliare import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "immobiliare_synthetic.html"


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


def test_build_search_url_rejects_invalid_tipo():
    try:
        build_search_url("Jesi", tipo="asta")
    except ValueError:
        pass
    else:
        raise AssertionError("tipo non valido avrebbe dovuto sollevare ValueError")


def test_parse_listings_extracts_expected_fields(monkeypatch):
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    first = listings[0]
    assert first.fonte == "immobiliare"
    assert first.tipo in ("affitto", "vendita")
    # la fixture sintetica simula una ricerca "affitto" (h1/title senza "vendita")
    assert first.tipo == "affitto"
    assert first.categoria == "residenziale"
    assert first.external_id
    assert first.titolo
    assert isinstance(first.prezzo, int) and first.prezzo >= 0
    assert first.url.startswith("http")


def test_parse_listings_returns_empty_list_for_no_matches(monkeypatch):
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    assert parse_listings("<html><body>nessun annuncio</body></html>") == []


def test_selector_card_matches_exactly_the_three_cards_not_child_classes():
    # Regressione (review finding): la vecchia SELECTOR_CARD faceva match
    # per sottostringa sull'attributo class (`[class*='in-card']`), che
    # matchava anche le classi figlie BEM come "in-card__title" e
    # "in-card__location" (contengono "in-card" come sottostringa),
    # producendo 9 match invece dei 3 attesi su questa fixture. I selettori
    # per classe esatta (".in-card, .listing-item") non devono avere questo
    # problema: verifica diretta del conteggio dei match.
    html = FIXTURE.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    matches = soup.select(imm_module.SELECTOR_CARD)
    assert len(matches) == 3


def test_parse_listings_extracts_correct_external_id_from_trailing_slash_url(monkeypatch):
    # La bozza del brief calcolava l'external_id con un'euristica
    # (url.endswith("/") -> penultimo segmento del path) che, per un URL del
    # tipo ".../annunci/123456789/", restituisce erroneamente "annunci"
    # (segmento statico) invece dell'ID numerico "123456789". Corretto
    # prendendo sempre l'ultimo segmento non vuoto del path, a prescindere
    # dallo slash finale. Verificato qui con la seconda card della fixture
    # sintetica, il cui href termina con "/".
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    second = listings[1]
    assert second.external_id == "987654321"
    assert second.external_id != "annunci"


def test_parse_listings_parses_price_with_thousands_separator(monkeypatch):
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert any(l.prezzo == 1200 for l in listings)


def test_parse_listings_defaults_price_to_zero_when_missing(monkeypatch):
    # Terza card della fixture sintetica: nessun elemento prezzo presente.
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert any(l.prezzo == 0 for l in listings)


def test_parse_listings_does_not_assume_chi_vende(monkeypatch):
    # Il brief chiede di verificare sul dato reale prima di assumere
    # chi_vende sempre "agenzia": lo Step 0 non ha permesso alcuna verifica,
    # quindi il parser non deve inventare un valore.
    monkeypatch.setattr(imm_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert all(l.chi_vende is None for l in listings)


def test_parse_listings_geocodes_comune_when_present(monkeypatch):
    calls = []

    def fake_geocode(comune):
        calls.append(comune)
        return (43.5, 13.2)

    monkeypatch.setattr(imm_module, "geocode_fn", fake_geocode)
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    assert calls  # la fixture sintetica espone sempre un comune per card
    assert listings[0].lat == 43.5
    assert listings[0].lon == 13.2
