import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date, timedelta
from pathlib import Path
from html import escape
from scraper import db

def build_digest_html(listings: list[dict], template_path: str = "notifier/email_template.html") -> str:
    template = Path(template_path).read_text(encoding="utf-8")
    if not listings:
        rows = "<p>Nessun nuovo annuncio questa settimana.</p>"
    else:
        rows = "".join(
            f'<li><a href="{escape(l["url"])}">{escape(l["titolo"])}</a> — '
            f'{escape(l["comune"] or "")}, {l["prezzo"]}€ ({escape(l["fonte"])}'
            f'{", " + escape(l["chi_vende"]) if l.get("chi_vende") else ""})</li>'
            for l in listings
        )
    return template.replace("{{LISTINGS}}", rows).replace("{{COUNT}}", str(len(listings)))

def send_digest(smtp_user: str, smtp_password: str, recipients: list[str], html_body: str) -> None:
    if not recipients:
        print("nessun destinatario configurato, skip invio")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Case Affitto Aste Vendite — nuovi annunci questa settimana"
    msg["From"] = smtp_user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, recipients, msg.as_string())

def run_weekly_digest(db_path: str, config: dict, smtp_user: str, smtp_password: str) -> None:
    conn = db.connect(db_path)
    since = (date.today() - timedelta(days=7)).isoformat()
    new_listings = db.get_new_since(conn, since)
    html = build_digest_html(new_listings)
    send_digest(smtp_user, smtp_password, config["email"]["destinatari"], html)
