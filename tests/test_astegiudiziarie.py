from pathlib import Path
import scraper.astegiudiziarie as ag_module
from scraper.astegiudiziarie import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "astegiudiziarie_sample.html"


def test_build_search_url_includes_centro_nome():
    url = build_search_url("Jesi")
    assert "astegiudiziarie.it" in url
    assert "jesi" in url.lower()


def test_parse_listings_extracts_expected_fields(monkeypatch):
    monkeypatch.setattr(ag_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    first = listings[0]
    assert first.fonte == "astegiudiziarie"
    assert first.tipo == "asta"
    assert first.categoria == "residenziale"
    assert first.external_id
    assert first.titolo
    assert isinstance(first.prezzo, int) and first.prezzo >= 0
    assert first.url.startswith("http")
    assert first.chi_vende is None  # aste giudiziarie, stesso ragionamento di Task 3


def test_parse_listings_returns_expected_count(monkeypatch):
    # Fixture reale: ricerca "comune=Jesi" + categoria "Immobile residenziale"
    # (idTipologie=1). Il filtro per categoria e' applicato server-side dal
    # portale stesso (verificato: il titolo della pagina risultati e' "Immobile
    # residenziale all'asta a Jesi" e tutti i 9 lotti mostrati sono tipologie
    # abitative), quindi qui - a differenza di pvp_giustizia.py - non serve un
    # filtro lato client sulla categoria.
    monkeypatch.setattr(ag_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) == 9
    assert all(l.categoria == "residenziale" for l in listings)


def test_parse_listings_parses_italian_formatted_price(monkeypatch):
    # Il primo lotto della fixture reale mostra "Prezzo base € 231.975"
    # (formato italiano: punto = separatore migliaia). Deve dare 231975 (int).
    monkeypatch.setattr(ag_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert listings[0].prezzo == 231975
    assert listings[0].offerta_minima == 231975


def test_parse_listings_extracts_data_asta(monkeypatch):
    # Verificato contro la fixture reale: la card mostra "Data udienza:
    # 15/10/2026" (o, per un lotto, "Ultima data vendita: ..."). parse_listings
    # estrae sempre la data nel formato gg/mm/aaaa indipendentemente
    # dall'etichetta esatta che la precede.
    monkeypatch.setattr(ag_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert listings[0].data_asta == "15/10/2026"
    assert all(l.data_asta for l in listings)


def test_parse_listings_extracts_tribunale(monkeypatch):
    # A differenza di pvp_giustizia.py (dove il tribunale non e' esposto
    # nella vista elenco), qui la card mostra esplicitamente "Tribunale di
    # Ancona - Esecuzione Immobiliare": il tribunale e' quindi popolato con
    # un dato reale, non lasciato None.
    monkeypatch.setattr(ag_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert listings[0].tribunale == "Tribunale di Ancona"


def test_parse_listings_geocodes_comune_when_present(monkeypatch):
    calls = []

    def fake_geocode(comune):
        calls.append(comune)
        return (43.5, 13.2)

    monkeypatch.setattr(ag_module, "geocode_fn", fake_geocode)
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    assert listings[0].lat == 43.5
    assert listings[0].lon == 13.2
    # tutti i lotti della fixture sono a Jesi: il comune estratto
    # dall'indirizzo completo deve essere pulito (niente CAP, niente via,
    # niente sigla provincia)
    assert calls[0] == "Jesi"


def test_parse_listings_returns_empty_list_for_no_matches(monkeypatch):
    monkeypatch.setattr(ag_module, "geocode_fn", lambda comune: (43.5, 13.2))
    assert parse_listings("<html><body>nessuna asta</body></html>") == []
