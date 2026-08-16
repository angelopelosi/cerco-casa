import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from notifier.digest import run_weekly_digest


def weekly_main() -> None:
    load_dotenv()
    config = yaml.safe_load(Path("config.yaml").read_text())
    run_weekly_digest(
        "data/listings.db",
        config,
        os.environ["SMTP_USER"],
        os.environ["GMAIL_APP_PASSWORD"],
    )


if __name__ == "__main__":
    weekly_main()
