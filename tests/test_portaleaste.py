from pathlib import Path
import scraper.portaleaste as pa_module
from scraper.portaleaste import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "portaleaste_sample.html"


def test_build_search_url_includes_centro_nome():
    url = build_search_url("Jesi")
    # Dominio verificato per davvero in questo task (WebSearch + WebFetch +
    # probe diretto https su entrambe le ipotesi): "portaleaste.it" risponde
    # 404 con un certificato TLS di un dominio diverso (astalegale.net), non
    # e' un sito reale. "portaleaste.com" e' invece il portale reale (HTTP
    # 200, homepage con logo "PORTALE ASTE", copy "Le aste giudiziarie a
    # portata di click dal 1995", stesso gruppo Astalegale.net di
    # asteimmobili.it - Task 7). Sostituisce sia l'ipotesi utente
    # ("portaleaste.com", corretta) sia quella dello spec originale
    # ("portaleaste.it", NON funzionante).
    assert "portaleaste.com" in url
    assert "jesi" in url.lower()


def test_parse_listings_extracts_expected_fields(monkeypatch):
    monkeypatch.setattr(pa_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    first = listings[0]
    assert first.fonte == "portaleaste"
    assert first.tipo == "asta"
    assert first.categoria == "residenziale"
    assert first.external_id
    assert first.titolo
    assert isinstance(first.prezzo, int) and first.prezzo >= 0
    assert first.url.startswith("http")
    assert first.chi_vende is None


def test_parse_listings_returns_expected_count(monkeypatch):
    # Fixture reale: ricerca "luoghi=jesi" + "categories=residenziali" su
    # https://www.portaleaste.com/Immobili (stesso schema URL di
    # asteimmobili.it - Task 7, stessa piattaforma Astalegale.net). Il
    # filtro e' applicato server-side dal portale stesso (verificato: il
    # testo della pagina risultati dice "5 Risultati per Immobili nel comune
    # di jesi nella categoria residenziali" e tutti e 5 i lotti mostrati sono
    # "Abitazione di tipo civile"), quindi non serve un filtro lato client
    # sulla categoria.
    monkeypatch.setattr(pa_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) == 5
    assert all(l.categoria == "residenziale" for l in listings)


def test_parse_listings_parses_italian_formatted_price(monkeypatch):
    # Il primo lotto della fixture reale mostra "Prezzo base: € 231.975,00"
    # (formato italiano: punto = separatore migliaia). Deve dare 231975 (int).
    # NOTA: e' lo stesso identico importo del primo lotto della fixture di
    # astegiudiziarie.py (Task 6) - non e' un errore di copia, e' lo stesso
    # immobile reale (Tribunale di Ancona, Jesi) aggregato da piu' portali.
    monkeypatch.setattr(pa_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert listings[0].prezzo == 231975


def test_parse_listings_extracts_distinct_offerta_minima(monkeypatch):
    # Come asteimmobili.it (a differenza di astegiudiziarie.py/
    # pvp_giustizia.py), la card mostra un secondo valore esplicito
    # "Offerta minima: € 173.982,00", distinto dal prezzo base: verificato
    # sulla fixture reale.
    monkeypatch.setattr(pa_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert listings[0].offerta_minima == 173982
    assert listings[0].offerta_minima != listings[0].prezzo


def test_parse_listings_extracts_data_asta(monkeypatch):
    # Verificato contro la fixture reale: la card mostra "Data asta:
    # 15/10/2026 - 12:45". parse_listings estrae la sola data (gg/mm/aaaa),
    # scartando l'orario.
    monkeypatch.setattr(pa_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert listings[0].data_asta == "15/10/2026"
    assert all(l.data_asta for l in listings)


def test_parse_listings_extracts_tribunale(monkeypatch):
    # Come astegiudiziarie.py/asteimmobili.py, la card espone esplicitamente
    # "Tribunale di Ancona": il tribunale e' quindi popolato con un dato
    # reale, non lasciato None.
    monkeypatch.setattr(pa_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert listings[0].tribunale == "Tribunale di Ancona"


def test_parse_listings_geocodes_comune_when_present(monkeypatch):
    calls = []

    def fake_geocode(comune):
        calls.append(comune)
        return (43.5, 13.2)

    monkeypatch.setattr(pa_module, "geocode_fn", fake_geocode)
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    assert listings[0].lat == 43.5
    assert listings[0].lon == 13.2
    # Il comune viene estratto dal badge dedicato "<span class='comune'>"
    # della card (testo gia' pulito, "Jesi"), stesso markup di
    # asteimmobili.py (stessa piattaforma Astalegale.net).
    assert calls[0] == "Jesi"


def test_parse_listings_extracts_external_id_from_astalegale_domain(monkeypatch):
    # Come asteimmobili.py: il link di dettaglio della card punta al dominio
    # astalegale.net (la societa' madre, stesso gruppo che possiede anche
    # portaleaste.com), non a portaleaste.com stesso - verificato sulla
    # fixture reale ("https://www.astalegale.net/Aste/Detail/B2428933-...").
    # L'external_id e' il codice lotto "B<numero>" che precede lo slug
    # nell'URL.
    monkeypatch.setattr(pa_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert listings[0].external_id == "B2428933"
    assert listings[0].url.startswith("https://www.astalegale.net/")


def test_parse_listings_returns_empty_list_for_no_matches(monkeypatch):
    monkeypatch.setattr(pa_module, "geocode_fn", lambda comune: (43.5, 13.2))
    assert parse_listings("<html><body>nessuna asta</body></html>") == []
