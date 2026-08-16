# Case Affitto Aste Vendite — Design

Data: 2026-08-16

## Obiettivo

Tool che aggrega annunci residenziali (affitto, vendita, asta giudiziaria) da più portali online, filtrati per raggio geografico attorno a un centro configurabile (default: Jesi). Pubblicato come sito statico condivisibile pubblicamente, senza login. Ogni lunedì invia una email di digest con i nuovi annunci apparsi nella settimana.

## Non-obiettivi

- Nessun login / account utente. Filtri condivisi da tutti i visitatori del sito.
- Nessun immobile commerciale (uffici, negozi, capannoni) — solo residenziale.
- Nessun backend dinamico: il sito è statico, i filtri girano lato client (JS).
- Non è un servizio always-on: gira su schedule locale, non 24/7.

## Fonti dati (8 portali)

1. Immobiliare.it
2. Casa.it
3. Idealista
4. Subito.it
5. Portale Vendite Pubbliche (PVP giustizia) — aste
6. astegiudiziarie.it — aste
7. portaleaste.it — aste
8. asteimmobili.it — aste

### Rischio scraping

Immobiliare.it, Casa.it e Idealista hanno protezioni anti-bot e Termini di Servizio che vietano lo scraping automatico. Questo tool è per uso personale non commerciale, con:
- rate limiting rispettoso (delay tra richieste, no scraping aggressivo)
- Playwright headless per rendering JS dove serve
- possibilità che un portale blocchi l'IP o cambi struttura HTML — richiede manutenzione periodica dei selettori
- se un portale blocca in modo persistente, si esclude da config senza bloccare gli altri

Le fonti aste giudiziarie (PVP, astegiudiziarie.it, portaleaste.it, asteimmobili.it) pubblicano dati generalmente pubblici e sono meno restrittive. Subito.it ha annunci HTML semplice, scraping meno invasivo.

## Architettura

```
[Task Scheduler: giornaliero]
  → Scraper (per-portale) → normalizza → SQLite (dedup)
  → Generatore sito statico → build/ (HTML+JS)
  → Publisher → push su GitHub Pages

[Task Scheduler: lunedì mattina, dopo lo scrape del giorno]
  → Notifier → query nuovi annunci (first_seen ultimi 7gg) → digest HTML → SMTP Gmail → lista destinatari
```

### Componenti

- **Scraper**: un modulo Python per portale (`scraper/immobiliare.py`, `scraper/casa.py`, ecc.). Ogni modulo produce record nello schema comune. Playwright per siti con anti-bot/JS pesante, requests+BeautifulSoup dove basta HTML statico.
- **Storage**: SQLite (`data/listings.db`), singola tabella `listings`.
- **Generatore sito**: legge da SQLite, applica filtro raggio (distanza geodetica da centro configurabile), scrive dati come JSON statico + pagina HTML con filtri client-side in JS (no framework pesante, vanilla o libreria leggera).
- **Publisher**: script che copia `build/` e fa commit+push automatico su branch `gh-pages` (o repo dedicato) collegato a GitHub Pages.
- **Notifier**: script Python, query annunci nuovi ultimi 7 giorni, genera email HTML (template semplice), invio via SMTP Gmail (App Password).
- **Orchestrazione**: Windows Task Scheduler, due job separati (vedi diagramma sopra). Se il PC è spento nell'orario schedulato, il job salta quel giorno — accettato come limite noto.

## Modello dati

Tabella `listings`:

| Campo | Tipo | Note |
|---|---|---|
| id | TEXT PK | hash di (fonte, external_id) — dedup |
| fonte | TEXT | nome portale |
| external_id | TEXT | id annuncio sul portale sorgente |
| tipo | TEXT | affitto \| vendita \| asta |
| categoria | TEXT | sempre "residenziale" (filtro applicato a monte o post-scrape) |
| titolo | TEXT | |
| prezzo | INTEGER | prezzo o prezzo base asta |
| superficie_mq | INTEGER | nullable |
| locali | INTEGER | nullable |
| comune | TEXT | |
| lat, lon | REAL | geocoded se non fornito dal portale |
| stato_disponibilita | TEXT | libero \| occupato \| null |
| data_disponibilita | DATE | nullable, se occupato |
| arredato | TEXT | si \| no \| non_specificato |
| url | TEXT | link originale annuncio |
| data_pubblicazione | DATE | dal portale, se disponibile |
| data_first_seen | DATE | prima volta vista dallo scraper |
| data_last_seen | DATE | ultima volta vista attiva |
| stato_annuncio | TEXT | attivo \| rimosso |
| tribunale | TEXT | solo aste, nullable |
| data_asta | DATE | solo aste, nullable |
| offerta_minima | INTEGER | solo aste, nullable |

Campi non disponibili per una data fonte/tipo restano null — non tutti i portali espongono tutti i dati (es. "arredato" tipicamente assente per le aste).

### Filtro residenziale

Applicato per quanto possibile a monte, nella query di ricerca del portale (categoria "residenziale" quando il portale la espone come parametro). Dove non è filtrabile a monte, classificazione post-scrape basata su titolo/categoria dichiarata dal portale, escludendo annunci taggati come commerciale/ufficio/negozio/capannone.

### Selezione zona

Centro configurabile in `config.yaml` (default: Jesi, geocoded a lat/lon). Raggio in km configurabile. Il generatore sito calcola distanza geodetica tra ogni listing e il centro, include solo quelli entro il raggio.

## Config (`config.yaml`)

```yaml
centro:
  nome: "Jesi"
  lat: null   # geocoded automaticamente se non specificato
  lon: null
raggio_km: 20
portali_attivi: [immobiliare, casa, idealista, subito, pvp_giustizia, astegiudiziarie, portaleaste, asteimmobili]
email:
  smtp_provider: gmail
  destinatari: []   # lista email, popolata dall'utente
```

Credenziali SMTP (Gmail App Password) in file separato non committato (`.env` o `secrets.yaml`, in `.gitignore`).

## Struttura cartelle

```
Case Affitto Aste Vendite/
  scraper/
    __init__.py
    common.py          # schema comune, utilities
    immobiliare.py
    casa.py
    idealista.py
    subito.py
    pvp_giustizia.py
    astegiudiziarie.py
    portaleaste.py
    asteimmobili.py
  data/
    listings.db
  site/
    generate.py        # genera build/ da SQLite
    template/           # HTML/JS/CSS statico
    build/              # output, pubblicato su GitHub Pages
  notifier/
    digest.py           # query + genera email
    email_template.html
  config.yaml
  .env                  # credenziali, gitignored
  .gitignore
  README.md
```

## Testing

- Test parsing per ogni scraper, contro fixture HTML salvate offline (no richieste live nei test).
- Test dedup logic (stesso external_id, fonte diversa → record separati; stesso fonte+id → update, non duplica).
- Test filtro raggio geografico (calcolo distanza).
- Test filtro residenziale (classificazione post-scrape).
- Test generazione digest email con dati mock (verifica solo annunci ultimi 7gg inclusi).

## Rischi noti / limiti accettati

- Scraping di portali commerciali può rompersi per cambio HTML o blocco anti-bot — richiede manutenzione occasionale.
- Sito aggiorna solo se il PC è acceso all'orario schedulato quel giorno.
- Nessuna garanzia legale sui ToS dei portali scrapati — uso personale, non commerciale, non ridistribuito come servizio a pagamento.
- Geocoding di indirizzi mancanti può richiedere un servizio esterno (es. Nominatim/OpenStreetMap, gratuito con rate limit).
