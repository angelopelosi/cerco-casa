import json
from webapp.generate import filter_listings, generate_site
from scraper import db
from scraper.schema import Listing

def test_filter_listings_excludes_non_residential():
    listings = [
        {"categoria": "commerciale", "lat": 43.52, "lon": 13.24},
        {"categoria": "residenziale", "lat": 43.52, "lon": 13.24},
    ]
    result = filter_listings(listings, 43.5219, 13.2437, 20)
    assert len(result) == 1
    assert result[0]["categoria"] == "residenziale"

def test_filter_listings_excludes_outside_radius():
    listings = [
        {"categoria": "residenziale", "lat": 43.52, "lon": 13.24},   # vicino a Jesi
        {"categoria": "residenziale", "lat": 45.46, "lon": 9.19},    # Milano, fuori raggio
    ]
    result = filter_listings(listings, 43.5219, 13.2437, 20)
    assert len(result) == 1

def test_generate_site_writes_filtered_data_json(tmp_path):
    db_path = str(tmp_path / "test.db")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "centro:\n  nome: Jesi\n  lat: 43.5219\n  lon: 13.2437\nraggio_km: 20\n"
    )
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "index.html").write_text("<html></html>")
    output_dir = tmp_path / "build"

    conn = db.connect(db_path)
    listing = Listing(fonte="subito", external_id="1", tipo="affitto",
                       titolo="Bilocale", prezzo=500, url="https://example.com/1",
                       lat=43.52, lon=13.24)
    db.upsert_listing(conn, listing)

    generate_site(db_path, str(config_path), str(output_dir), str(template_dir))

    data = json.loads((output_dir / "data.json").read_text())
    assert len(data) == 1
    assert data[0]["fonte"] == "subito"
    assert (output_dir / "index.html").exists()
