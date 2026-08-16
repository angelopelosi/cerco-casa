from pathlib import Path
import scraper.pvp_giustizia as pvp_module
from scraper.pvp_giustizia import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "pvp_giustizia_sample.html"


def test_build_search_url_includes_centro_nome():
    url = build_search_url("Jesi")
    assert "giustizia.it" in url
    assert "Jesi" in url or "jesi" in url.lower()


def test_parse_listings_extracts_expected_fields(monkeypatch):
    monkeypatch.setattr(pvp_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    first = listings[0]
    assert first.fonte == "pvp_giustizia"
    assert first.tipo == "asta"
    assert first.categoria == "residenziale"
    assert first.external_id
    assert first.titolo
    assert isinstance(first.prezzo, int) and first.prezzo >= 0
    assert first.url.startswith("http")


def test_parse_listings_only_keeps_immobile_residenziale(monkeypatch):
    # La fixture reale (ricerca "raggio d'azione" attorno a Jesi, categoria
    # IMMOBILI) contiene anche lotti taggati "Immobile Commerciale" e "Altra
    # Categoria" (12 lotti totali, di cui 9 residenziali): parse_listings deve
    # scartare i non residenziali, cosi' che categoria=="residenziale" valga
    # sempre per ogni Listing prodotto (invariante richiesto dal resto della
    # pipeline).
    monkeypatch.setattr(pvp_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) == 9
    assert all(l.categoria == "residenziale" for l in listings)


def test_parse_listings_parses_italian_formatted_price(monkeypatch):
    # Il primo lotto della fixture reale mostra "Prezzo base d'asta: 83.346,63"
    # (formato italiano: punto = migliaia, virgola = decimali). Il parsing
    # deve restituire 83346 (int), non un valore gonfiato dalla concatenazione
    # cieca delle cifre (che darebbe 8334663).
    monkeypatch.setattr(pvp_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert listings[0].prezzo == 83346
    assert listings[0].offerta_minima == 83346


def test_parse_listings_extracts_data_asta_and_data_pubblicazione(monkeypatch):
    monkeypatch.setattr(pvp_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    first = listings[0]
    assert first.data_asta == "11/05/2018 15:30"
    assert first.data_pubblicazione == "26/03/2018"


def test_parse_listings_tribunale_is_none_when_not_shown_in_list_view(monkeypatch):
    # Verificato contro la fixture reale: la vista elenco lotti del portale
    # (ricerca "Ricerca Geografica" per raggio d'azione) non espone il campo
    # tribunale per singolo lotto nella card (solo nel form di ricerca, come
    # elenco di TUTTI i tribunali italiani per il filtro). Il tribunale e'
    # visibile solo nella pagina di dettaglio del singolo annuncio, che questo
    # scraper non visita. tribunale resta quindi None qui: e' un dato onesto,
    # non un bug del parser.
    monkeypatch.setattr(pvp_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    assert all(l.tribunale is None for l in listings)


def test_parse_listings_geocodes_comune_when_present(monkeypatch):
    calls = []

    def fake_geocode(comune):
        calls.append(comune)
        return (43.5, 13.2)

    monkeypatch.setattr(pvp_module, "geocode_fn", fake_geocode)
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    if calls:  # solo se la fixture reale espone un comune per il lotto
        assert listings[0].lat == 43.5
        assert listings[0].lon == 13.2
        # tutti i lotti della fixture sono a Jesi: il comune estratto
        # dall'indirizzo completo deve essere pulito (niente CAP, niente via)
        assert calls[0] == "Jesi"


def test_parse_listings_returns_empty_list_for_no_matches(monkeypatch):
    monkeypatch.setattr(pvp_module, "geocode_fn", lambda comune: (43.5, 13.2))
    assert parse_listings("<html><body>nessuna asta</body></html>") == []
