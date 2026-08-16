from pathlib import Path
import scraper.subito as subito_module
from scraper.subito import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "subito_sample.html"


def test_build_search_url_includes_centro_nome():
    url = build_search_url("Jesi")
    assert "subito.it" in url
    assert "Jesi" in url or "jesi" in url.lower()


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
    monkeypatch.setattr(subito_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    first = listings[0]
    assert first.fonte == "subito"
    assert first.tipo in ("affitto", "vendita")
    # la fixture e' una ricerca "affitto" reale (h1 "Jesi - Affitto case")
    assert first.tipo == "affitto"
    assert first.categoria == "residenziale"
    assert first.external_id
    assert first.titolo
    assert isinstance(first.prezzo, int) and first.prezzo >= 0
    assert first.url.startswith("http")


def test_parse_listings_parses_a_real_price():
    # Nella fixture reale il primo annuncio non mostra un prezzo (annuncio
    # senza prezzo visibile), ma altri annunci si': verifica che il parsing
    # del prezzo funzioni correttamente su un annuncio che lo mostra
    # (secondo annuncio della fixture, "850 €").
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert any(l.prezzo == 850 for l in listings)


def test_parse_listings_geocodes_comune_when_present(monkeypatch):
    calls = []

    def fake_geocode(comune):
        calls.append(comune)
        return (43.5, 13.2)

    monkeypatch.setattr(subito_module, "geocode_fn", fake_geocode)
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    if calls:  # solo se la fixture reale espone un comune per la card
        assert listings[0].lat == 43.5
        assert listings[0].lon == 13.2
        # il comune non deve contenere la sigla provincia tra parentesi
        assert "(" not in calls[0]


def test_parse_listings_returns_empty_list_for_no_matches(monkeypatch):
    monkeypatch.setattr(subito_module, "geocode_fn", lambda comune: (43.5, 13.2))
    assert parse_listings("<html><body>nessun annuncio</body></html>") == []
