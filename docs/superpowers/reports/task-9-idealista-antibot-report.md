# Task 9 Report: Scraper Idealista.it

## Status: DONE_WITH_CONCERNS

## Step 0: feasibility check (anti-bot) — result: BLOCKED

Ran the brief's Step 0 script essentially verbatim: headless Playwright
(`chromium.launch(headless=True)`), default `new_page()` (no evasion, no
custom user-agent beyond Playwright's own defaults, no proxy), single
`page.goto('https://www.idealista.it/affitto-case/jesi-marche/', timeout=30000)`,
`page.wait_for_timeout(3000)`, then `page.content()`.

Note on script execution: my first invocation of the exact script failed
with `FileNotFoundError: /tmp/idealista_check.html` — this environment
(Windows/Git Bash) has no `/tmp`, so the brief's hardcoded output path
doesn't exist here (unrelated to the site). I re-ran with the output path
changed to the task scratchpad directory. This was a local script-path fix,
not a retry against the site to probe the block differently — the network
fetch to idealista.it itself only ran with a different outcome once (the
first attempt's `page.goto`/`page.content()` had already executed
successfully before the write failed; I did not re-fetch to "test" whether
the block was consistent). One page load, no retry loop, no rate-limit
concern.

**Result: blocked.** The returned HTML was 1499 bytes — not a results page.
Full raw HTML (captured to scratchpad, not committed — same convention as
Task 8):

```html
<html lang="it"><head><title>idealista.it</title>...
<script data-cfasync="false">var dd={'rt':'c','cid':'AHrlqAAAAAMAXvi12RpIJOUAXSkiig==', ...
'host':'geo.captcha-delivery.com', ...}</script>
<script data-cfasync="false" src="https://ct.captcha-delivery.com/c.js"></script>
<iframe src="https://geo.captcha-delivery.com/captcha/?initialCid=...&referer=https%3A%2F%2Fwww.idealista.it%2Faffitto-case%2Fjesi-marche%2F&...&dm=cd"
  sandbox="allow-scripts allow-same-origin allow-forms" ...
  title="DataDome CAPTCHA" width="100%" height="100%" ...></iframe>
</body></html>
```

Block indicators observed:
- `<title>idealista.it</title>` (not a listings-page title like "Jesi -
  Case in affitto in provincia di Ancona | idealista.it")
- Page body is a single DataDome CAPTCHA challenge iframe
  (`iframe title="DataDome CAPTCHA"`, `src` pointing at
  `geo.captcha-delivery.com/captcha/...`), no listing HTML anywhere in the
  1499-byte payload.
- `host:'geo.captcha-delivery.com'` in an inline `dd` JS object — same
  DataDome bot-mitigation product Task 8 hit on immobiliare.it.
- Byte size (1499) and structure are essentially identical to Task 8's
  immobiliare.it block (1496 bytes) — same anti-bot vendor, same challenge
  shape.

No second attempt was made against the live site. Per the task instructions
this block is the accepted, documented outcome per this project's design
spec (Idealista explicitly flagged as one of the most anti-bot-protected
portals) — no proxy, no fingerprint spoofing, no CAPTCHA-solving, no retry
was attempted.

## Path taken: fallback (Step 0 "Se blocca") — and why

Step 0 showed an unambiguous block (same DataDome signature as Task 8), so
I followed the brief's "Se blocca" branch, not "Step 1: cattura una fixture
reale":

1. Documented the block in the ledger
   (`.superpowers/sdd/2026-08-17-case-affitto-aste-vendite-fase2/progress.md`,
   new "## Task 9: Scraper Idealista.it (anti-bot)" section).
2. Implemented `scraper/idealista.py` from the brief's draft selectors, with
   `# NON VERIFICATO: cattura bloccata da anti-bot` directly above the
   `SELECTOR_*` constants, plus a module-level header comment documenting
   the Step 0 evidence and pointing to this report.
3. Wrote tests against a **hand-built synthetic fixture**
   (`fixtures/idealista_synthetic.html`, following Task 8's naming
   convention — not the brief's literal `idealista_sample.html`, which the
   brief's own "Files" section conditions on Step 0 succeeding). Both the
   fixture and the test file carry explicit top-of-file comments in Italian
   stating the data is synthetic and why.
4. Got all tests green against the synthetic fixture.
5. Did **not** add `idealista` to `portali_attivi` in `config.yaml`, nor to
   `PORTAL_TIPI`/`PORTAL_MODULES` in `scraper/run_all.py` — confirmed via
   `git diff --stat -- config.yaml scraper/run_all.py` (empty, no changes)
   before commit. Left for Task 11 to explicitly skip.

## CSS selector precision (Task 8's lesson applied proactively)

Task 8's fix round was needed because its brief draft used **attribute
substring matching** (`[class*='in-card']`), which also matched BEM child
classes like `in-card__title` (contains `in-card` as a substring). This
task's brief draft for Idealista was already written with **exact CSS
class/tag selectors**, not substring matching:

```python
SELECTOR_CARD = "article.item"
SELECTOR_TITLE = "a.item-link"
SELECTOR_PRICE = ".item-price"
SELECTOR_COMUNE = ".item-detail-char, .item-location"
SELECTOR_LINK = "a.item-link"
```

`.item`, `.item-link`, `.item-price`, etc. are standard CSS class selectors,
which match on a single, whole class **token** — not on substrings of the
`class` attribute string. I kept these selectors as-is (no rewrite needed)
and verified there is no `[class*=...]` anywhere in `scraper/idealista.py`
(confirmed via `grep -n "class\*=" scraper/idealista.py` — zero matches).

To proactively prove this is safe (rather than assuming it, and rather than
needing a review round to catch it like Task 8), I deliberately built a
collision scenario into the synthetic fixture: card 1 has a sibling element
`<span class="item-price-old">€ 750</span>` (simulating a struck-through
previous price) directly next to `<span class="item-price">€ 650</span>`.
`item-price-old` contains `item-price` as a *substring* but is a different
*class token* — an exact CSS selector `.item-price` correctly ignores it. A
dedicated regression test,
`test_selector_price_does_not_match_sibling_item_price_old_class`, asserts
`first.prezzo == 650` (not 750), and a second regression test,
`test_selector_card_matches_exactly_the_three_cards`, asserts
`len(soup.select(SELECTOR_CARD)) == 3` directly. Both pass.

## TDD evidence

RED (genuine, re-verified): temporarily moved `scraper/idealista.py` aside
(`mv scraper/idealista.py scraper/idealista.py.bak`) after writing
`tests/test_idealista.py`, ran `pytest tests/test_idealista.py -v` →
`ModuleNotFoundError: No module named 'scraper.idealista'` (matches the
brief's Step 4 expectation exactly). Restored the file
(`mv scraper/idealista.py.bak scraper/idealista.py`).

GREEN: `pytest tests/test_idealista.py -v` → **12 passed**, first attempt,
no fix round needed (12 = the brief's 4 required tests + 8 additional:
`build_search_url` rejects invalid `tipo`, exact-selector regression x2,
correct `external_id` extraction, thousands-separator price parsing,
missing-price defaults to 0, `chi_vende` never assumed, comune geocoding
wiring — same additional-test pattern Task 8 used).

Full suite: `pytest -q` → **105 passed**, 0 failed (93 prior + 12 new), run
once cleanly before staging/committing, and re-run once more after commit
as a final pristine check (also 105 passed).

## Files changed

- `scraper/idealista.py` (new) —
  `C:\Users\angel\Desktop\Progetti\Case Affitto Aste Vendite\.claude\worktrees\case-affitto-fase2\scraper\idealista.py`
  Module header documents the Step 0 block and points to this report;
  `SELECTOR_*` constants carry `# NON VERIFICATO: cattura bloccata da
  anti-bot` plus a note explaining why they're already exact-token
  selectors, not substring matches. `_external_id_from_url` uses
  `rstrip("/")` before splitting (same fix Task 8 needed to apply after
  finding a bug in its own brief's draft; this task's brief draft for
  Idealista already did `url.rstrip("/").split("/")[-1]` correctly, so no
  bug was present here — verified by inspection, not assumed).
- `fixtures/idealista_synthetic.html` (new, hand-built, NOT a real capture —
  named `*_synthetic.html`, matching Task 8's convention) —
  `C:\Users\angel\Desktop\Progetti\Case Affitto Aste Vendite\.claude\worktrees\case-affitto-fase2\fixtures\idealista_synthetic.html`
  Top-of-file HTML comment explains it's synthetic, why, and documents the
  deliberate `.item-price` / `.item-price-old` collision test case.
- `tests/test_idealista.py` (new) —
  `C:\Users\angel\Desktop\Progetti\Case Affitto Aste Vendite\.claude\worktrees\case-affitto-fase2\tests\test_idealista.py`
  12 tests: the brief's 4 required tests (adapted to point at
  `idealista_synthetic.html`) plus 8 more covering `tipo` rejection, exact
  vs. substring selector regressions (card count, sibling-class collision),
  correct `external_id`, thousands-separator price parsing, missing-price
  defaulting to 0, the deliberate `chi_vende=None` non-assumption, and
  comune geocoding wiring.

Not touched (correctly out of scope per brief — Task 11's job, and
explicitly skipped per the block per the brief's fallback instructions):
`scraper/run_all.py`, `config.yaml`.

Ledger updated: `.superpowers/sdd/2026-08-17-case-affitto-aste-vendite-fase2/progress.md`
(gitignored, not part of the commit — same convention as Task 8) — new
"## Task 9: Scraper Idealista.it (anti-bot)" section documenting the block,
the ruling, and the non-activation.

## Self-review findings

- Followed the brief's "Se blocca" fallback path faithfully: ledger
  documented, best-effort draft selectors kept (marked NON VERIFICATO),
  synthetic (not real) fixture, tests pass against synthetic fixture,
  `idealista` NOT added to any activation list, commit uses the brief's
  exact message (`feat: add Idealista scraper`).
- No bypass technique attempted at any point: single Playwright page load
  against the live site, no retries against the block itself, no proxy, no
  user-agent/fingerprint tampering beyond Playwright's own defaults, no
  CAPTCHA-solving, no alternate URLs/endpoints tried to route around the
  block. (The one incidental re-run was a local `/tmp`-path fix in my own
  verification script, not a second attempt at the network fetch's outcome
  — see Step 0 section above for the full explanation, flagged
  transparently rather than glossed over.)
- Tests are honest about data provenance: both the fixture and the test
  file's header comments explicitly state the data is hand-built/synthetic,
  not downloaded, and explain why (anti-bot block, with a pointer to this
  report).
- CSS selectors verified to use exact class-token/tag matching throughout —
  `grep -n "class\*=" scraper/idealista.py` returns zero matches (the only
  occurrences of the `[class*=...]` substring pattern anywhere in the three
  new files are inside comments *explaining what NOT to do*, referencing
  Task 8's bug, never in an actual selector definition). Proactively tested
  with a deliberate substring-collision fixture scenario (`.item-price` vs
  `.item-price-old`) rather than only asserting it in prose.
- Verified `config.yaml` and `scraper/run_all.py` are unchanged
  (`git diff --stat` empty for both) before staging/committing.
- Full suite passes pristine (105/105), run once before commit and
  re-confirmed once after commit, no flaky/dropped test.
- Only the 3 intended files (`scraper/idealista.py`,
  `fixtures/idealista_synthetic.html`, `tests/test_idealista.py`) were
  staged and committed (`git show --stat HEAD` confirms exactly these 3);
  pre-existing unstaged changes to `webapp/build/app.js`,
  `webapp/build/data.json`, `webapp/build/index.html` (unrelated generated
  build artifacts, present before this task started) were left untouched,
  same as Task 8's precedent.
- Genuine RED state re-verified by temporarily removing
  `scraper/idealista.py` and re-running the test file (not just inferred
  from writing the module afterward) — see TDD evidence above.

## Concerns

1. **Idealista.it is anti-bot protected (DataDome) and inaccessible via
   plain headless Playwright**, exactly as the project's design spec
   flagged it. This scraper cannot run against the real site as
   implemented/verified today. Task 11 must skip `idealista` when wiring up
   `portali_attivi`/`PORTAL_TIPI`/`PORTAL_MODULES` (not registered by this
   task, confirmed above).
2. **Every selector, the `build_search_url` path pattern, and the price/
   comune text format are unverified against real markup.** They are
   plausible (based on the brief's draft) and are at least demonstrably
   *safe from the specific substring-collision class of bug* that hit
   Task 8, but could still be wrong in other ways (different class names
   entirely, different nesting, price shown differently, a different site
   structure than assumed) — this can only be resolved by a future manual
   re-verification once/if the anti-bot block is no longer in the way (out
   of scope for this task).
3. **`chi_vende` is always `None`** — deliberate, same reasoning as Task 8:
   no real data available to verify whether/how Idealista exposes a
   privato/agenzia indicator. A future re-verification against real
   captured HTML should check this and update the extraction logic (and its
   test) if the site does expose such an indicator.
4. Two portals in this project (`immobiliare`, now also `idealista`) are
   both blocked by the same DataDome product on plain headless Playwright.
   If a future task ever revisits anti-bot feasibility for either, the same
   approach/findings likely transfer to both — worth investigating together
   rather than separately, though that's a call for whoever owns that
   future work, not something to speculate on further here.
