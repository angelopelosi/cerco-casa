# Task 8 Report: Scraper Immobiliare.it

## Status: DONE_WITH_CONCERNS

## Step 0: feasibility check (anti-bot) — result: BLOCKED

Ran exactly the brief's Step 0 script: headless Playwright (`chromium.launch(headless=True)`),
default `new_page()` (no evasion, no custom user-agent beyond Playwright's own
defaults, no proxy), single `page.goto('https://www.immobiliare.it/affitto-case/jesi/', timeout=30000)`,
`page.wait_for_timeout(3000)`, then `page.content()`. One fetch, no retries.

**Result: blocked.** The returned HTML was 1496 bytes — not a results page.
Full raw HTML captured (saved to scratchpad, not committed since it's not a
project fixture):

```html
<html lang="en"><head><title>immobiliare.it</title>...
<script data-cfasync="false">var dd={'rt':'c','cid':'AHrlqAAAAAMAqiFhL6uRf18AXSkiig==', ...
'host':'geo.captcha-delivery.com', ...}</script>
<script data-cfasync="false" src="https://ct.captcha-delivery.com/c.js"></script>
<iframe src="https://geo.captcha-delivery.com/captcha/?initialCid=...&referer=https%3A%2F%2Fwww.immobiliare.it%2Faffitto-case%2Fjesi%2F&...&dm=cd"
  sandbox="allow-scripts allow-same-origin allow-forms" ...
  title="DataDome CAPTCHA" width="100%" height="100%" ...></iframe>
</body></html>
```

Block indicators observed:
- `<title>immobiliare.it</title>` (not a listings-page title like
  "Jesi - Affitto case ... | Immobiliare.it")
- Page body is a single DataDome CAPTCHA challenge iframe
  (`iframe title="DataDome CAPTCHA"`, `src` pointing at
  `geo.captcha-delivery.com/captcha/...`), no listing HTML anywhere in the
  1496-byte payload.
- `host:'geo.captcha-delivery.com'` in an inline `dd` JS object — DataDome's
  known bot-mitigation product.

(Minor incidental bug in the brief's own verification script, not the site:
it calls `page.title()` *after* `browser.close()`, which raises
`TargetClosedError`. This happened after `html = page.content()` had already
succeeded and the HTML had already been written to disk, so it did not
affect the evidence — the `<title>` tag content is visible directly in the
captured HTML above, "immobiliare.it".)

No second attempt was made. Per the task instructions this block is the
accepted, documented outcome from the project's own design spec — no proxy,
no fingerprint spoofing, no CAPTCHA-solving, no retry was attempted.

## Path taken: fallback (Step 0 "Se blocca") — and why

Step 0 showed a block, so I followed the brief's "Se blocca" branch, not the
"Step 1: cattura una fixture reale" branch:

1. Documented the block in the ledger
   (`.superpowers/sdd/2026-08-17-case-affitto-aste-vendite-fase2/progress.md`,
   new "## Task 8: Scraper Immobiliare.it" section) — "Task 8: bloccato da
   anti-bot, vedi nota" plus the evidence and rulings.
2. Implemented `scraper/immobiliare.py` from the brief's draft selectors,
   with `# NON VERIFICATO: cattura bloccata da anti-bot` directly above the
   `SELECTOR_*` constants, plus a module-level header comment pointing to
   this report.
3. Wrote tests against a **hand-built synthetic fixture**
   (`fixtures/immobiliare_synthetic.html`), not downloaded/real data.
   Both the fixture file and the test file carry explicit top-of-file
   comments stating this in Italian, matching the project's language
   convention (see "Files changed" below for exact wording).
4. Got all tests green against the synthetic fixture.
5. Did **not** add `immobiliare` to `portali_attivi` in `config.yaml`, nor to
   `PORTAL_TIPI`/`PORTAL_MODULES` in `scraper/run_all.py` — confirmed via
   `git diff --stat -- config.yaml scraper/run_all.py` showing no changes
   before commit. This is left for Task 11 to explicitly skip.

## Deviations from the brief's draft code (and why)

While building the synthetic fixture and exercising the draft parsing logic,
I found and fixed one genuine logic bug in the brief's draft — not a
selector/markup guess, a pure indexing bug independent of what the real site
looks like:

```python
# brief's draft:
external_id = url.rstrip("/").split("/")[-2] if url.endswith("/") else url.rstrip("/").split("/")[-1]
```

For a URL like `https://www.immobiliare.it/annunci/123456789/` (ends with
`/`), this takes `[-2]` of the split, which is the static path segment
`"annunci"`, not the numeric ID `"123456789"`. Replaced with: take the last
non-empty path segment regardless of trailing slash
(`_external_id_from_url`). Covered by a new test,
`test_parse_listings_extracts_correct_external_id_from_trailing_slash_url`.

Also, per the brief's Step 2 instruction ("verifica anche se la pagina
espone un indicatore privato/agenzia... verifica sul dato reale prima di
assumere `chi_vende` sempre `"agenzia"`"): since Step 0 blocked, there was no
real data to check. `chi_vende` is left unset (defaults to `None` per the
`Listing` schema) rather than assumed — covered by
`test_parse_listings_does_not_assume_chi_vende`.

Everything else (CSS selectors, `build_search_url` path pattern, price
parsing, tipo detection via h1/title text) is kept as close to the brief's
draft as possible, since none of it could be verified either way.

## A real bug this exercise surfaced (documented as a concern, not "fixed")

While building the synthetic fixture I hit a genuine fragility in the
draft's `SELECTOR_CARD = "[class*='in-card'], [class*='listing-item']"`:
substring class matching means any *ancestor* wrapper whose class happens to
contain `"listing-item"` as a substring (e.g. a real container class like
`"listing-items"` or `"listing-items-container"`) also matches the card
selector. When that happens, `card.select_one(...)` on the wrapper resolves
to the *first* nested title/price/link in document order, producing a
duplicate "listing" for card #1 before the real per-card matches are
reached — this actually happened when my first draft of the synthetic
fixture used a wrapper class `"listing-items"`, and `listings[1]` came back
as a duplicate of card 1 instead of card 2.

I fixed this in my own fixture (renamed the wrapper to
`"risultati-ricerca"`, which doesn't collide) since I have full control over
synthetic data, but I did **not** touch the loose selector itself in
`scraper/immobiliare.py`, since I have no real markup to justify a specific
fix or to know whether the real site's wrapper class would actually collide.
This is flagged explicitly as a concern below and in the code/fixture
comments, for whoever eventually re-verifies this scraper against real data.

## TDD evidence

RED: `pytest tests/test_immobiliare.py -v` before creating
`scraper/immobiliare.py` failed with
`ModuleNotFoundError: No module named 'scraper.immobiliare'` (matches the
brief's Step 4 expectation exactly).

GREEN (after implementation, one iteration): 9/10 passed, 1 failed
(`test_parse_listings_extracts_correct_external_id_from_trailing_slash_url`
initially failed for an unrelated reason — the wrapper-class selector
collision described above, diagnosed against the synthetic fixture itself,
not the implementation code). Fixed by renaming the fixture's wrapper div
class from `listing-items` to `risultati-ricerca`. Re-ran:
`pytest tests/test_immobiliare.py -v` → **10 passed**.

Manually dumped all 3 parsed synthetic listings (fonte/external_id/tipo/
titolo/prezzo/url/comune/lat/lon/chi_vende), ran `Listing.validate()` on all
3 (all pass), confirmed all 3 `.id` values are unique.

Full suite: `pytest -v` → **92 passed**, 0 failed, run once cleanly after
implementation, before committing (82 prior + 10 new).

## Files changed

- `scraper/immobiliare.py` (new) —
  `C:\Users\angel\Desktop\Progetti\Case Affitto Aste Vendite\.claude\worktrees\case-affitto-fase2\scraper\immobiliare.py`
  Module header explicitly documents the Step 0 block and points to this
  report; `SELECTOR_*` constants carry `# NON VERIFICATO: cattura bloccata
  da anti-bot`.
- `fixtures/immobiliare_synthetic.html` (new, hand-built, NOT a real
  capture — named `*_synthetic.html`, not `*_sample.html`, to distinguish it
  from every other portal's real captured fixture in this project) —
  `C:\Users\angel\Desktop\Progetti\Case Affitto Aste Vendite\.claude\worktrees\case-affitto-fase2\fixtures\immobiliare_synthetic.html`
  Carries a large top-of-file HTML comment explaining it's synthetic, why,
  and the wrapper-class-collision note above.
- `tests/test_immobiliare.py` (new) —
  `C:\Users\angel\Desktop\Progetti\Case Affitto Aste Vendite\.claude\worktrees\case-affitto-fase2\tests\test_immobiliare.py`
  10 tests: the brief's 4 required tests (adapted to point at
  `immobiliare_synthetic.html` instead of `immobiliare_sample.html`, since
  the brief's "Files" section only calls for the latter "solo se lo Step 0
  conferma accesso") plus 6 more covering `tipo` rejection, the external_id
  bug fix, thousands-separator price parsing, missing-price defaulting to 0,
  the deliberate `chi_vende=None` non-assumption, and comune geocoding
  wiring.

Not touched (correctly out of scope per brief — Task 11's job, and
explicitly skipped per the block per the brief's fallback instructions):
`scraper/run_all.py`, `config.yaml`.

Ledger updated: `.superpowers/sdd/2026-08-17-case-affitto-aste-vendite-fase2/progress.md`
(gitignored, not part of the commit — same convention as prior tasks) — new
"## Task 8: Scraper Immobiliare.it" section documenting the block, the
ruling, and the non-activation.

## Self-review findings

- Followed the brief's "Se blocca" fallback path faithfully: ledger
  documented, best-effort draft selectors kept (marked NON VERIFICATO),
  synthetic (not real) fixture, tests pass against synthetic fixture,
  `immobiliare` NOT added to any activation list, commit uses the brief's
  exact message.
- No bypass technique attempted at any point: single Playwright fetch, no
  retries, no proxy, no user-agent/fingerprint tampering beyond Playwright's
  own defaults (same as the `fetch.py` helper used elsewhere in this
  project), no CAPTCHA-solving, no alternate URLs/endpoints tried to route
  around the block.
- Tests are honest about data provenance: both the fixture and the test
  file's header comments explicitly state the data is hand-built/synthetic,
  not downloaded, and explain why (anti-bot block, with a pointer to this
  report).
- Verified `config.yaml` and `scraper/run_all.py` are unchanged
  (`git diff --stat` empty for both) before staging/committing.
- Full suite passes pristine (92/92), run once at the end before commit, no
  flaky/dropped test.
- Only the 3 intended files (`scraper/immobiliare.py`,
  `fixtures/immobiliare_synthetic.html`, `tests/test_immobiliare.py`) were
  staged and committed; pre-existing unstaged changes to
  `webapp/build/app.js`, `webapp/build/data.json`, `webapp/build/index.html`
  (unrelated generated build artifacts, present before this task started)
  were left untouched, same as Task 7's precedent.
- One deviation from the brief's literal file list worth calling out
  explicitly: the brief's Step 3 test draft imports the fixture as
  `fixtures/immobiliare_sample.html`; I used
  `fixtures/immobiliare_synthetic.html` instead, because the brief's own
  "Files" section conditions creation of the `_sample.html` name on Step 0
  succeeding ("Create: `fixtures/immobiliare_sample.html` (solo se lo Step 0
  conferma accesso)") — using the same filename convention as real captures
  for hand-built data risked a future reader mistaking it for a real
  capture, which the top-level task instructions explicitly asked me to
  avoid ("be explicit about this in the fixture/test").

## Concerns

1. **Immobiliare.it is anti-bot protected (DataDome) and inaccessible via
   plain headless Playwright.** This scraper cannot run against the real
   site as implemented/verified today. Task 11 must skip `immobiliare` when
   wiring up `portali_attivi`/`PORTAL_TIPI`/`PORTAL_MODULES` (not registered
   by this task, confirmed above).
2. **Every selector, the `build_search_url` path pattern, and the price/
   comune text format are unverified against real markup.** They are
   plausible (based on the brief's draft, itself presumably derived from
   general knowledge of the site's naming conventions), but could be wrong
   in any number of ways (different class names, different nesting, price
   shown differently, etc.) — this can only be resolved by a future manual
   re-verification once/if the anti-bot block is no longer in the way (out
   of scope for this task).
3. **Wrapper-class selector fragility, documented but not fixed**: `[class*='in-card'], [class*='listing-item']` matches on substring, so any real
   ancestor wrapper class containing `"listing-item"` (or `"in-card"`) as a
   substring would cause the same duplicate-first-card bug I hit while
   building the synthetic fixture (see "A real bug this exercise surfaced"
   above). Left as-is since fixing it would mean guessing at real markup
   structure with zero evidence; flagged for whoever re-verifies this
   scraper against real data.
4. **`chi_vende` is always `None`** — deliberate, per the brief's own
   instruction not to assume `"agenzia"` without real-data verification.
   A future re-verification against real captured HTML should check this
   and update the extraction logic (and its test) if the site does expose a
   privato/agenzia indicator.
5. Small thing: the brief's own Step 0 verification script (not something I
   wrote) has a bug — `page.title()` is called after `browser.close()`,
   which raises. Didn't affect the evidence (title was already visible in
   the captured HTML, and the HTML file had already been written before the
   failing call), but worth flagging in case this exact script is reused for
   Task 9 (idealista.it, likely with the same anti-bot concern) verbatim.

## Addendum: review fix (Important finding)

Review found that `SELECTOR_CARD = "[class*='in-card'], [class*='listing-item']"`
did raw **substring** matching on the `class` attribute, not per-token
matching. Running `soup.select(SELECTOR_CARD)` against the committed
`fixtures/immobiliare_synthetic.html` returned **9 matches instead of the
intended 3 cards**, because the BEM child classes `in-card__title` and
`in-card__location` (2 each × 3 cards = 6) also contain the substring
`"in-card"` and match the same selector as their parent card wrapper. This
correction supersedes/refines the original report's diagnosis of the
selector-fragility concern (Concern #3 above and the "A real bug this
exercise surfaced" section), which framed the risk only as an
*ancestor-wrapper* naming collision (e.g. "listing-items" vs
"listing-item"). That ancestor-wrapper risk is real too, but it was not
the collision actually present in the committed fixture/code — the one
review caught is a **child-class** collision (`in-card__title`/
`in-card__location` containing their parent's `in-card` substring), which
existed in every one of the 3 real cards, not just a hypothetical wrapper
name. It produced no visible bug only because the 6 spurious child-class
matches are leaf elements with no nested title/link, so the existing
`if not (title_el and link_el...)` guard filtered them out — an accident
of the synthetic fixture's structure, not a guarantee of the selector
logic (exactly as the reviewer described it).

**Fix applied** (`scraper/immobiliare.py`): switched all four selectors
from attribute-substring matching to exact CSS class-token matching:

```python
# before (substring match — matches "in-card__title" too):
SELECTOR_CARD = "[class*='in-card'], [class*='listing-item']"
SELECTOR_TITLE = "[class*='in-card__title']"
SELECTOR_PRICE = "[class*='in-price']"
SELECTOR_COMUNE = "[class*='in-card__location']"

# after (exact class-token match):
SELECTOR_CARD = ".in-card, .listing-item"
SELECTOR_TITLE = ".in-card__title"
SELECTOR_PRICE = ".in-price"
SELECTOR_COMUNE = ".in-card__location"
```

This fixes the collision without any assumption about real markup beyond
what the brief's draft already assumed (the BEM naming convention itself) —
per the reviewer's point, there's no real-markup risk being traded away
here, it's a strictly safer selector for the same assumed convention.

**Verification**: re-ran `soup.select(SELECTOR_CARD)` against
`fixtures/immobiliare_synthetic.html` directly — now returns exactly
**3 matches** (the 3 real card wrappers, confirmed by printing each match's
`class` attribute: all three are `['in-card', 'in-realEstateCard']`, none of
the 6 child-class leaves).

**Regression test added**: `test_selector_card_matches_exactly_the_three_cards_not_child_classes`
in `tests/test_immobiliare.py` — asserts `len(soup.select(SELECTOR_CARD)) == 3`
directly against the fixture, so a future accidental reintroduction of
substring matching (or a fixture edit that reintroduces the collision) is
caught without needing to reason through `parse_listings`' downstream guard.

Also updated the fixture's header comment
(`fixtures/immobiliare_synthetic.html`) to correctly attribute the
collision to child BEM classes (not just the ancestor-wrapper naming risk),
consistent with the reviewer's accurate diagnosis.

**Verification commands run:**
- `python -m pytest tests/test_immobiliare.py -v` → 11 passed (10 original +
  1 new regression test)
- `python -m pytest -q` (full suite) → **93 passed**, 0 failed

**Files changed in this fix:**
- `scraper/immobiliare.py` — 4 `SELECTOR_*` constants switched from
  substring to exact-class-token matching, expanded comment explaining why.
- `fixtures/immobiliare_synthetic.html` — header comment corrected to
  describe the child-class collision accurately (in addition to the
  already-mitigated ancestor-wrapper naming risk).
- `tests/test_immobiliare.py` — added `BeautifulSoup` import and one new
  regression test.

No changes to `config.yaml` or `scraper/run_all.py` (still correctly out of
scope / not activated, unchanged by this fix).
