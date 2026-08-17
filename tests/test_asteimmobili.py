from pathlib import Path
import scraper.asteimmobili as ai_module
from scraper.asteimmobili import parse_listings, build_search_url

FIXTURE = Path(__file__).parent.parent / "fixtures" / "asteimmobili_sample.html"


def test_build_search_url_includes_centro_nome():
    url = build_search_url("Jesi")
    assert "asteimmobili.it" in url
    assert "jesi" in url.lower()


def test_parse_listings_extracts_expected_fields(monkeypatch):
    monkeypatch.setattr(ai_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    first = listings[0]
    assert first.fonte == "asteimmobili"
    assert first.tipo == "asta"
    assert first.categoria == "residenziale"
    assert first.external_id
    assert first.titolo
    assert isinstance(first.prezzo, int) and first.prezzo >= 0
    assert first.url.startswith("http")
    assert first.chi_vende is None


def test_parse_listings_returns_expected_count(monkeypatch):
    # Fixture reale: ricerca "luoghi=jesi" + "categories=residenziali" su
    # https://www.asteimmobili.it/Immobili. Il filtro e' applicato
    # server-side dal portale stesso (verificato: il testo della pagina
    # risultati dice esplicitamente "5 Risultati per Immobili nel comune di
    # jesi nella categoria residenziali" e tutti e 5 i lotti mostrati sono
    # "Abitazione di tipo civile"), quindi - come astegiudiziarie.py - non
    # serve un filtro lato client sulla categoria.
    monkeypatch.setattr(ai_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) == 5
    assert all(l.categoria == "residenziale" for l in listings)


def test_parse_listings_parses_italian_formatted_price(monkeypatch):
    # Il primo lotto della fixture reale mostra "Prezzo base: € 231.975,00"
    # (formato italiano: punto = separatore migliaia). Deve dare 231975 (int).
    monkeypatch.setattr(ai_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert listings[0].prezzo == 231975


def test_parse_listings_extracts_distinct_offerta_minima(monkeypatch):
    # A differenza di astegiudiziarie.py/pvp_giustizia.py (dove
    # offerta_minima == prezzo, un placeholder), qui la card mostra un
    # secondo valore esplicito "Offerta minima: € 173.982,00", distinto dal
    # prezzo base: verificato sulla fixture reale, quindi offerta_minima e'
    # popolato con il dato reale, non duplicato da prezzo.
    monkeypatch.setattr(ai_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert listings[0].offerta_minima == 173982
    assert listings[0].offerta_minima != listings[0].prezzo


def test_parse_listings_extracts_data_asta(monkeypatch):
    # Verificato contro la fixture reale: la card mostra "Data asta:
    # 15/10/2026 - 12:45". parse_listings estrae la sola data (gg/mm/aaaa),
    # scartando l'orario.
    monkeypatch.setattr(ai_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert listings[0].data_asta == "15/10/2026"
    assert all(l.data_asta for l in listings)


def test_parse_listings_extracts_tribunale(monkeypatch):
    # Come astegiudiziarie.py (e a differenza di pvp_giustizia.py), la card
    # espone esplicitamente "Tribunale di Ancona": il tribunale e' quindi
    # popolato con un dato reale, non lasciato None.
    monkeypatch.setattr(ai_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert listings[0].tribunale == "Tribunale di Ancona"


def test_parse_listings_geocodes_comune_when_present(monkeypatch):
    calls = []

    def fake_geocode(comune):
        calls.append(comune)
        return (43.5, 13.2)

    monkeypatch.setattr(ai_module, "geocode_fn", fake_geocode)
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert len(listings) > 0
    assert listings[0].lat == 43.5
    assert listings[0].lon == 13.2
    # Il comune viene estratto dal badge dedicato "<span class='comune'>"
    # della card (testo gia' pulito, "Jesi"), non da un parsing di indirizzo
    # completo come in astegiudiziarie.py.
    assert calls[0] == "Jesi"


def test_parse_listings_extracts_external_id_from_astalegale_domain(monkeypatch):
    # Scostamento reale rispetto alla bozza: il link di dettaglio della card
    # punta al dominio astalegale.net (la societa' madre, stesso gruppo),
    # non ad asteimmobili.it - verificato sulla fixture reale
    # ("https://www.astalegale.net/Aste/Detail/B2428933-..."). L'external_id
    # e' il codice lotto "B<numero>" che precede lo slug nell'URL.
    monkeypatch.setattr(ai_module, "geocode_fn", lambda comune: (43.5, 13.2))
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_listings(html)
    assert listings[0].external_id == "B2428933"
    assert listings[0].url.startswith("https://www.astalegale.net/")


def test_parse_listings_returns_empty_list_for_no_matches(monkeypatch):
    monkeypatch.setattr(ai_module, "geocode_fn", lambda comune: (43.5, 13.2))
    assert parse_listings("<html><body>nessuna asta</body></html>") == []
