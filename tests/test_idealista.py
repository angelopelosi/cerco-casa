# NOTA IMPORTANTE: Task 9 (Idealista.it) e' passato per il percorso di
# fallback previsto dal brief. Lo Step 0 (verifica fattibilita' anti-bot,
# fetch Playwright headless normale su
# https://www.idealista.it/affitto-case/jesi-marche/, nessuna evasione
# tentata) ha restituito una pagina di blocco DataDome CAPTCHA, non risultati
# reali (vedi task-9-report.md per l'HTML del blocco — stesso schema di
# blocco riscontrato da Task 8 su immobiliare.it). Di conseguenza NON e'
# stato possibile catturare una fixture reale come per subito/
# astegiudiziarie/asteimmobili: `fixtures/idealista_synthetic.html` e' una
# pagina costruita a mano da questo task, strutturalmente coerente con i
# selettori di bozza del brief (SELECTOR_CARD/TITLE/PRICE/COMUNE/LINK), NON
# dati reali scaricati dal sito. I selettori in scraper/idealista.py restano
# quindi NON VERIFICATI contro il markup reale del sito.
from pathlib import Path
from bs4 import BeautifulSoup
import scraper.idealista as idealista_module
from scraper.idealista import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "idealista_synthetic.html"


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
    listings = parse_listings(html)
    assert len(listings) > 0
    first = listings[0]
    assert first.fonte == "idealista"
    assert first.tipo in ("affitto", "vendita")
    # la fixture sintetica simula una ricerca "affitto" (h1/title senza "vendita")
    assert first.tipo == "affitto"
    assert first.categoria == "residenziale"
    assert first.external_id
    assert first.titolo
    assert isinstance(first.prezzo, int) and first.prezzo >= 0
    assert first.url.startswith("http")


def test_parse_listings_returns_empty_list_for_no_matches(monkeypatch):
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    assert parse_listings("<html><body>nessun annuncio</body></html>") == []


def test_parse_listings_uses_explicit_tipo_when_given(monkeypatch):
    # Percorso di importazione manuale: sappiamo gia' da quale ricerca
    # proviene il file salvato, non serve indovinarlo dal contenuto pagina.
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html, tipo="vendita")
    assert all(l.tipo == "vendita" for l in listings)


def test_parse_listings_rejects_invalid_explicit_tipo(monkeypatch):
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    try:
        parse_listings(html, tipo="asta")
    except ValueError:
        pass
    else:
        raise AssertionError("tipo non valido avrebbe dovuto sollevare ValueError")


def test_selector_card_matches_exactly_the_three_cards():
    # Verifica proattiva (lezione da Task 8, vedi commento in testa a questo
    # file e in idealista.py): SELECTOR_CARD = "article.item" e' un
    # selettore CSS per classe esatta, non per sottostringa
    # (`[class*='item']`) — deve matchare esattamente le 3 card e nient'altro.
    html = FIXTURE.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    matches = soup.select(idealista_module.SELECTOR_CARD)
    assert len(matches) == 3


def test_selector_price_does_not_match_sibling_item_price_old_class(monkeypatch):
    # Regressione proattiva: la prima card della fixture include un elemento
    # sibling con classe "item-price-old" (prezzo precedente) accanto a
    # ".item-price" (prezzo attuale), apposta per verificare che il
    # selettore CSS per classe esatta ".item-price" non matchi per errore
    # "item-price-old" come avrebbe fatto un selettore a sottostringa
    # (`[class*='item-price']`) — vedi addendum di Task 8 su
    # scraper/immobiliare.py per il bug analogo che questa fixture previene.
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    first = listings[0]
    assert first.prezzo == 650  # non 750 (il prezzo "vecchio" barrato)


def test_parse_listings_extracts_correct_external_id_from_trailing_slash_url(monkeypatch):
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    first = listings[0]
    assert first.external_id == "12345678"
    assert first.external_id != "immobile"


def test_parse_listings_parses_price_with_thousands_separator(monkeypatch):
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert any(l.prezzo == 1200 for l in listings)


def test_parse_listings_defaults_price_to_zero_when_missing(monkeypatch):
    # Terza card della fixture sintetica: nessun elemento prezzo presente.
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert any(l.prezzo == 0 for l in listings)


def test_parse_listings_does_not_assume_chi_vende(monkeypatch):
    # Nessun dato reale disponibile per verificare se/come Idealista espone
    # un indicatore privato/agenzia (stesso motivo di Task 8 su
    # immobiliare.py): il parser non deve inventare un valore.
    monkeypatch.setattr(idealista_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert all(l.chi_vende is None for l in listings)


def test_parse_listings_geocodes_comune_when_present(monkeypatch):
    calls = []

    def fake_geocode(comune):
        calls.append(comune)
        return (43.5, 13.2)

    monkeypatch.setattr(idealista_module, "geocode_fn", fake_geocode)
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    assert calls  # la fixture sintetica espone sempre un comune per card
    assert listings[0].lat == 43.5
    assert listings[0].lon == 13.2
