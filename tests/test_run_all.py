# tests/test_run_all.py
from scraper import run_all as run_all_module, db
from scraper.schema import Listing

FAKE_HTML = "<html><body>irrelevant, fetch_html is mocked out</body></html>"

def test_run_all_upserts_listings_from_active_portals(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    fake_listings = [
        Listing(
            fonte="subito", external_id="1", tipo="affitto",
            titolo="Bilocale", prezzo=500, url="https://example.com/1",
        )
    ]
    monkeypatch.setattr(run_all_module, "fetch_html", lambda *a, **k: FAKE_HTML)
    monkeypatch.setattr(run_all_module.subito, "parse_listings", lambda html: fake_listings)
    monkeypatch.setattr(run_all_module.pvp_giustizia, "parse_listings", lambda html: [])

    config = {"portali_attivi": ["subito", "pvp_giustizia"], "centro": {"nome": "Jesi"}}
    run_all_module.run_all(config, db_path)

    conn = db.connect(db_path)
    active = db.get_active(conn)
    assert len(active) == 1
    assert active[0]["fonte"] == "subito"

def test_run_all_fetches_subito_once_per_tipo(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    fetched_urls = []

    def fake_fetch(url, wait_selector=None, **kwargs):
        fetched_urls.append(url)
        return FAKE_HTML

    monkeypatch.setattr(run_all_module, "fetch_html", fake_fetch)
    monkeypatch.setattr(run_all_module.subito, "parse_listings", lambda html: [])
    monkeypatch.setattr(run_all_module.pvp_giustizia, "parse_listings", lambda html: [])

    config = {"portali_attivi": ["subito", "pvp_giustizia"], "centro": {"nome": "Jesi"}}
    run_all_module.run_all(config, db_path)

    expected_subito_urls = {
        run_all_module.subito.build_search_url("Jesi", tipo="affitto"),
        run_all_module.subito.build_search_url("Jesi", tipo="vendita"),
    }
    assert expected_subito_urls.issubset(set(fetched_urls))
    assert len(fetched_urls) == 3  # 2 subito (affitto+vendita) + 1 pvp_giustizia

def test_run_all_skips_unregistered_portals(tmp_path, monkeypatch, capsys):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(run_all_module, "fetch_html", lambda *a, **k: FAKE_HTML)
    monkeypatch.setattr(run_all_module.subito, "parse_listings", lambda html: [])
    monkeypatch.setattr(run_all_module.pvp_giustizia, "parse_listings", lambda html: [])

    # "immobiliare" e' stato registrato in PORTAL_MODULES dalla Task 11 (ma
    # tenuto fuori da portali_attivi in config.yaml per il blocco anti-bot,
    # vedi scraper/immobiliare.py) — non e' piu' un esempio valido di portale
    # non registrato. Uso un nome inesistente per testare lo skip.
    config = {"portali_attivi": ["portale_inesistente"], "centro": {"nome": "Jesi"}}
    run_all_module.run_all(config, db_path)

    captured = capsys.readouterr()
    assert "portale_inesistente" in captured.out


def test_run_all_registers_all_phase2_portals():
    for nome in ("astegiudiziarie", "asteimmobili", "immobiliare", "idealista", "portaleaste"):
        assert nome in run_all_module.PORTAL_MODULES

def test_run_all_fetches_immobiliare_and_idealista_once_per_tipo(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    fetched_urls = []

    def fake_fetch(url, wait_selector=None, **kwargs):
        fetched_urls.append(url)
        return FAKE_HTML

    monkeypatch.setattr(run_all_module, "fetch_html", fake_fetch)
    for modulo in run_all_module.PORTAL_MODULES.values():
        monkeypatch.setattr(modulo, "parse_listings", lambda html: [])

    config = {"portali_attivi": ["immobiliare", "idealista"], "centro": {"nome": "Jesi"}}
    run_all_module.run_all(config, db_path)

    assert len(fetched_urls) == 4  # 2 tipi x 2 portali

def test_run_all_marks_previously_seen_listings_as_removed_when_absent(tmp_path, monkeypatch):
    # Rimozione genuina: il portale continua a restituire risultati (seen_ids
    # non vuoto), solo uno specifico annuncio precedentemente visto non c'e'
    # piu' tra quelli parsati -> va marcato rimosso, gli altri restano attivi.
    db_path = str(tmp_path / "test.db")
    listing1 = Listing(fonte="subito", external_id="1", tipo="affitto",
                        titolo="Bilocale", prezzo=500, url="https://example.com/1")
    listing2 = Listing(fonte="subito", external_id="2", tipo="affitto",
                        titolo="Trilocale", prezzo=700, url="https://example.com/2")

    monkeypatch.setattr(run_all_module, "fetch_html", lambda *a, **k: FAKE_HTML)
    monkeypatch.setattr(run_all_module.pvp_giustizia, "parse_listings", lambda html: [])

    config = {"portali_attivi": ["subito", "pvp_giustizia"], "centro": {"nome": "Jesi"}}

    monkeypatch.setattr(run_all_module.subito, "parse_listings", lambda html: [listing1, listing2])
    run_all_module.run_all(config, db_path)

    monkeypatch.setattr(run_all_module.subito, "parse_listings", lambda html: [listing1])
    run_all_module.run_all(config, db_path)

    conn = db.connect(db_path)
    active_ids = {row["id"] for row in db.get_active(conn)}
    assert active_ids == {listing1.id}


def test_run_all_does_not_wipe_inventory_on_empty_parse_result(tmp_path, monkeypatch, capsys):
    # Finding 5 (review finale): un parse_listings che torna [] pur avendo
    # fatto fetch con successo (pagina lenta a renderizzare, selettore
    # cambiato) non deve azzerare l'intero inventario attivo del portale.
    db_path = str(tmp_path / "test.db")
    listing = Listing(fonte="subito", external_id="1", tipo="affitto",
                       titolo="Bilocale", prezzo=500, url="https://example.com/1")

    monkeypatch.setattr(run_all_module, "fetch_html", lambda *a, **k: FAKE_HTML)
    monkeypatch.setattr(run_all_module.pvp_giustizia, "parse_listings", lambda html: [])

    config = {"portali_attivi": ["subito", "pvp_giustizia"], "centro": {"nome": "Jesi"}}

    monkeypatch.setattr(run_all_module.subito, "parse_listings", lambda html: [listing])
    run_all_module.run_all(config, db_path)

    monkeypatch.setattr(run_all_module.subito, "parse_listings", lambda html: [])
    run_all_module.run_all(config, db_path)

    conn = db.connect(db_path)
    active_ids = {row["id"] for row in db.get_active(conn)}
    assert active_ids == {listing.id}

    captured = capsys.readouterr()
    assert "subito" in captured.out
    assert "salto la rimozione" in captured.out


def test_run_all_continues_after_one_portal_raises(tmp_path, monkeypatch, capsys):
    # Finding 4 (review finale): un'eccezione durante il fetch/parse di un
    # portale (timeout di rete, sito down) non deve propagarsi ne' impedire
    # l'elaborazione degli altri portali attivi.
    db_path = str(tmp_path / "test.db")
    fake_listings = [
        Listing(fonte="pvp_giustizia", external_id="1", tipo="asta",
                titolo="Bilocale", prezzo=500, url="https://example.com/1")
    ]

    def fake_fetch(url, wait_selector=None, **kwargs):
        if "subito" in url:
            raise TimeoutError("simulato: portale non raggiungibile")
        return FAKE_HTML

    monkeypatch.setattr(run_all_module, "fetch_html", fake_fetch)
    monkeypatch.setattr(run_all_module.pvp_giustizia, "parse_listings", lambda html: fake_listings)

    config = {"portali_attivi": ["subito", "pvp_giustizia"], "centro": {"nome": "Jesi"}}
    run_all_module.run_all(config, db_path)  # non deve sollevare

    conn = db.connect(db_path)
    active = db.get_active(conn)
    assert len(active) == 1
    assert active[0]["fonte"] == "pvp_giustizia"

    captured = capsys.readouterr()
    assert "subito" in captured.out
    assert "errore" in captured.out.lower()
