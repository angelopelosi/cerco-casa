import yaml
from pathlib import Path
from dotenv import load_dotenv
from scraper.run_all import run_all
from webapp.generate import generate_site
from .publish import publish


def daily_main() -> None:
    load_dotenv()
    config = yaml.safe_load(Path("config.yaml").read_text())
    run_all(config, "data/listings.db")
    generate_site("data/listings.db", "config.yaml", "webapp/build", "webapp/template")
    publish("webapp/build")


if __name__ == "__main__":
    daily_main()
