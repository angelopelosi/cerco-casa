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

Crea due attivita programmate (Task Scheduler GUI o `schtasks`), entrambe con
"Start in" impostato sulla cartella del progetto:

Giornaliero (ogni giorno, es. 07:00):
schtasks /create /tn "CaseAffittoAsteVendite-Daily" /tr "\"C:\path\to\venv\Scripts\pythonw.exe\" -m scripts.daily" /sc daily /st 07:00 /sd 01/01/2026

Settimanale (ogni lunedi, dopo il job giornaliero, es. 08:00):
schtasks /create /tn "CaseAffittoAsteVendite-Weekly" /tr "\"C:\path\to\venv\Scripts\pythonw.exe\" -m scripts.weekly" /sc weekly /d MON /st 08:00 /sd 01/01/2026

Sostituisci `C:\path\to\venv` con il percorso reale del virtualenv creato nel
Setup. Se il PC e spento all'orario schedulato, il job viene saltato quel giorno.
