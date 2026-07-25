# Mirror experiment — pre-registration

**Question:** Does making a StatCan table's *values* crawlable (static HTML + schema.org/Dataset
markup + prominent attribution, hosted on GitHub Pages) cause search and AI answer engines to
(a) cite StatCan on the matched queries, and/or (b) serve *current-vintage* numbers — relative
to matched control tables that get no mirror?

Registered **2026-07-19**, before deployment. Design decisions below were fixed before any
post-treatment measurement.

## Design

Cluster-randomized at the **table** level (queries sharing a table move together), stratified
by gap flavour. Candidate pool = the 9 tables behind the pilot's "answerable but invisible"
cells (see `docs/visibility_pilot_report.md`):

- **never_cited** (7 tables): fully answerable per goal-2 coding, StatCan not in DDG top-3
  on the matched query (2×2 gap cell, 2026-07-18).
- **stale_cited** (2 tables): StatCan cited on the matched query but via an outdated
  article while the current table stayed invisible (Bing/Duck.ai rounds).

Assignment: `random.Random(20260718)` — `sample(never_cited, 4)` + `sample(stale_cited, 1)`.

| Arm | Table | Title (short) | Matched queries |
|---|---|---|---|
| treatment | 11-10-0130 | Charitable donors | SOC-004 |
| treatment | 14-10-0064 | Employee wages (LFS) | LAB-002, LAB-003 |
| treatment | 45-10-0039 | Volunteering | SOC-001, SOC-002 |
| treatment | 45-10-0104 | Time use 2022 | SOC-024 |
| treatment | 33-10-1045 | Business AI use | DIG-014 |
| control | 14-10-0288 | Class of worker | LAB-014 |
| control | 45-10-0073 | Confidence in institutions | SOC-010 |
| control | 98-10-0353 | Religion (census) | SOC-016 |
| control | 45-10-0048 | Loneliness | SOC-005 |

**Control tables must not be mirrored, linked, or otherwise promoted until the experiment
concludes.** (`build_mirror.py` enforces the skip.)

## Treatment

`visibility/mirror/build_mirror.py` renders one static page per treatment table into
`tables/` (deployed at `https://p3ji.github.io/stats/tables/`): values in plain HTML
table markup, one headline sentence with the key figure, schema.org/Dataset JSON-LD
(`sameAs`/`isBasedOn` → canonical table; `creator` = Statistics Canada; Open Licence),
prominent "Source: Statistics Canada, Table …" attribution, explicit not-affiliated notice.
Discovery: `sitemap.xml` at site root + footer link from the dashboard index, plus
(as of 2026-07-19) manual sitemap submission to **both Bing Webmaster Tools and
Google Search Console** for `https://p3ji.github.io/stats/` — site verified via
HTML meta tag in each (`msvalidate.01` and `google-site-verification`, both in
`index.html`), sitemap submitted at `https://p3ji.github.io/stats/sitemap.xml`
in each console. This is a deliberate, symmetric crawl-discovery nudge and is
part of the treatment (not a passive-discovery-only design) — applied equally
to both engines, so it doesn't bias the Bing-vs-Google comparison. No other
promotion (no aggregator submissions, no backlink building) — record here if
that changes. Google's sitemap status showed "Couldn't fetch" immediately
after submission (2026-07-19); confirmed the sitemap itself returns 200 with
correct `Content-Type: application/xml` and no blocking `robots.txt` — likely
a normal first-attempt lag, watch for it to resolve on its own.

**Treatment URL change (2026-07-19):** the site was renamed from
`p3ji.github.io/statcan_codr/` to `p3ji.github.io/stats/` (repo `statcan_codr` → `stats`,
public brand "Open Stats Lab") to remove any impression of Statistics Canada affiliation.
This happened **the same day as deployment, before any indexing** (the T+2w indexing check
hadn't run), so the treatment pages have only ever been discoverable at the `/stats/` URL —
the rename does not confound the experiment. The final canonical treatment URLs are
`https://p3ji.github.io/stats/tables/<slug>.html`.

**Template strengthened for attribution (2026-07-25):** `build_mirror.py` was upgraded to
bias credit toward Statistics Canada, and all pages regenerated. Each page now (a) leads
with a prominent "Official source: Statistics Canada, Table X" block explicitly asking
readers/engines to attribute StatCan and not the mirror; (b) adds a "How to cite" line with
the table's DOI; (c) enriches the schema.org/Dataset so every ownership field —
`creator`, `publisher`, `sourceOrganization`, `includedInDataCatalog`, and a nested
`isBasedOn` dataset with the DOI — is Statistics Canada, while the mirror is marked only as
`sdPublisher` (the structured-data host, not the data owner). Applied before any indexing
(T+2w check not yet run), so it doesn't confound wave 1; it directly targets the
pre-registered "mirror cited *instead of* StatCan" risk by pushing engines to credit the
official source. This strengthened template is the standard for wave 2 and beyond.

## Baseline (captured before deploy)

- `visibility/results/ddg_2026-07-18.csv` — DDG organic, all 100 pilot queries.
- `visibility/results/bing_ai_sample_2026-07-18.csv`, `duckai_sample_2026-07-18.csv`.
- `visibility/results/baseline_bing_copilot_2026-07-19.csv` and
  `baseline_duckai_2026-07-19.csv` — **all 11 experiment queries through both surfaces**
  (Bing Copilot Search; Duck.ai GPT-5.4-nano with web search, terms accepted by user
  2026-07-19), with the extended value-match schema and full-page screenshots in
  `visibility/results/baseline_evidence/` (PNG + accessibility-tree YML per query —
  the "photo evidence" arm).
- Official reference values: treatment values embedded in the mirror pages (build log)
  plus `visibility/results/reference_values_control.json` for control tables.

### Extended coding schema (added 2026-07-19)

Prior rounds coded only citation lineage (`direct`/`indirect`/`none`) and vintage. Added:

- `answer_value` — the number(s) the engine actually served.
- `statcan_value` — official current value (WDS, fetch date recorded).
- `value_match` — `match_current` | `match_stale` (a real StatCan number, outdated
  vintage) | `different_metric` (StatCan-lineage but not comparable 1:1) |
  `mismatch` / `mismatch_risk` (number contradicts official value) | `unverifiable` |
  `no_number`.

This captures the case where an engine *doesn't cite StatCan yet serves a StatCan-derived
number via an indexable intermediary* (Fraser/CRA 17.1%, canadavisuals 4.55M,
imaginecanada 32%) — credit lost, lineage intact — as distinct from true misinformation
(theralist "40% lonely" vs official 13.4% always/often).

## Outcomes (per matched query, per engine)

Primary, treatment vs control difference-in-differences from baseline:

1. **Citation**: does statcan.gc.ca (or the mirror) appear as a source? (`direct` /
   `indirect` / `none`; mirror citations tracked separately — a mirror citation is
   *displacement*, not a StatCan citation.)
2. **Vintage**: `statcan_vintage_cited` vs `best_available_vintage` — does the served
   number's vintage move to current?
3. **Value match**: distribution of `value_match` categories.

Secondary: does the mirror page itself get indexed (site: queries) and crawled
(GitHub Pages has no log access — check Bing Webmaster/Google Search Console if enrolled).

## Re-audit protocol

- Same 11 queries, same phrasing, same engines (Bing Copilot Search primary; DDG organic
  re-run via `run_audit_ddg.py`; Duck.ai if consented), fresh sessions, screenshots saved
  with the same naming scheme (`<engine>_<ID>_<date>.png`).
- **T+2 weeks** (~2026-08-02): indexing check only (site:p3ji.github.io/stats/tables).
- **T+6 weeks** (~2026-08-30): full re-audit round 1.
- **T+12 weeks** (~2026-10-11): full re-audit round 2 (crawl/index cycles are slow;
  round 2 is the primary endpoint).

## Interpretation rules (fixed in advance)

- Improvement on treatment but not control queries → supports the crawlability mechanism.
- Improvement on both arms → secular drift (engines changed), not treatment effect.
- Mirror cited *instead of* StatCan → mechanism confirmed but displacement realized;
  report as its own outcome, evidence for "StatCan should do this on its own domain."
- n=9 tables: this is a demonstration experiment — report counts and concrete
  before/after screenshot pairs, not significance tests.

## Threats / caveats

- New domain-path with zero authority; 12 weeks may undercount Google-side effects.
- **Discovery push is deliberate, not passive**: both Bing Webmaster Tools and Google
  Search Console got a verified site + submitted sitemap (2026-07-19). This is uniform
  across the two consoles, so it doesn't bias a Bing-vs-Google comparison, but it does
  mean the design measures "crawlable + actively submitted," not "crawlable and left to
  be found naturally." Note this distinction if the experiment is ever generalized to
  "would this work with zero outreach."
- The dashboard site itself is low-traffic; discovery depends on sitemap + crawl, which
  is the mechanism under test (crawlability, not popularity).
- Bing Copilot Search answers are nondeterministic; single-shot per re-audit (same as
  baseline) — treat individual flips cautiously, look at the pattern across 11 queries.
- DIG-014's matched table (33-10-1045, Q3-2025 planned-use) is one quarter behind the
  Q2-2026 analytical article already in circulation; vintage outcome for this query
  compares against the article layer, not the mirror.
