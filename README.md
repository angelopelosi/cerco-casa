# Case Affitto Aste Vendite

Aggregatore di annunci residenziali (affitto/vendita/asta) attorno a un centro
configurabile (default Jesi). Sito statico pubblico + digest email settimanale.

## Setup

1. `python -m venv venv && venv\Scripts\activate` (Windows)
2. `pip install -r requirements.txt`
3. `playwright install chromium`
4. `copy .env.example .env` e compila `SMTP_USER` / `GMAIL_APP_PASSWORD`
   (App Password Gmail: https://myaccount.google.com/apppasswords)
5. Modifica `config.yaml` per centro/raggio/destinatari.
6. `pytest` per verificare che tutto funzioni.

## Uso manuale

- `python -m scripts.daily` — scrape + genera sito + pubblica
- `python -m scripts.weekly` — invia digest email

## Task Scheduler (Windows)

Vedi Task 13 del piano di implementazione per i comandi esatti.
