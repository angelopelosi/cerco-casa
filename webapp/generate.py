import json
import shutil
from pathlib import Path
import yaml
from scraper import db
from scraper.radius import within_radius

def load_config(config_path: str) -> dict:
    return yaml.safe_load(Path(config_path).read_text())

def filter_listings(listings: list[dict], center_lat: float, center_lon: float, radius_km: float) -> list[dict]:
    return [
        l for l in listings
        if l.get("categoria") == "residenziale"
        and within_radius(center_lat, center_lon, l.get("lat"), l.get("lon"), radius_km)
    ]

def generate_site(db_path: str, config_path: str, output_dir: str, template_dir: str) -> None:
    config = load_config(config_path)
    conn = db.connect(db_path)
    listings = db.get_active(conn)
    filtered = filter_listings(
        listings,
        config["centro"]["lat"],
        config["centro"]["lon"],
        config["raggio_km"],
    )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template_dir, out, dirs_exist_ok=True)
    (out / "data.json").write_text(json.dumps(filtered, indent=2, default=str))
