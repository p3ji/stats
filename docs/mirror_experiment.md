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
- **3 runs per query on Bing, modal coding** (amendment A2); Duck.ai 1 run. Code blind to
  arm (A3). Re-fetch StatCan reference values and rebuild the mirrors first (A8).
- Wave-2 clock (deployed 2026-07-25): index check ~**2026-08-08**, round 1 ~**2026-09-05**,
  primary endpoint ~**2026-10-17**.
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

## Methodology audit and amendments (2026-07-25)

Full design audit run **before any post-treatment measurement exists** (treatment deployed
2026-07-25; first re-audit not due until ~2026-08-08). Nothing here is a post-hoc change to
a rule after seeing results — no results exist yet. Amendments A1–A9 are binding from now.

### A1. Primary outcome and endpoint (was under-specified — multiplicity risk)

Three outcomes × 2 engines × 2 waves × 3 timepoints ≈ 36 chances for a spurious "win."
Fixed now:

- **Primary outcome:** change in `citation_class` to `direct` (statcan.gc.ca cited as a
  source), **Bing Copilot only**, **treatment vs control**, **at T+12 weeks**.
- **Secondary:** vintage shift, `value_match` distribution, Duck.ai, the T+6wk round.
- Everything else is exploratory and must be labelled as such when reported.

Rationale for Bing-only primary: Duck.ai already cites StatCan on ~90% of queries — a
**ceiling effect**, no room to improve. Duck.ai's job is to detect *displacement* (mirror
cited instead of StatCan), not to test the citation hypothesis.

### A2. Quantify the noise floor — add replicates (URGENT)

**This sharpens an existing caveat rather than raising a new one.** The original threats
list already noted that Bing answers are nondeterministic and that the design is single-shot
("treat individual flips cautiously, look at the pattern across 11 queries"). Nondeterminism
is not itself the flaw — it is expected. The flaw is **measuring a variable draw with a
single draw, with no estimate of its variance**, which leaves "treat cautiously" as a
judgment made *after* seeing results — precisely where bias enters.

Baseline is **exactly one run per query** (verified: 1 row per ID). Separately, **16 of 60**
wave-2 rows had *no AI answer box at all* — there the outcome variable doesn't merely vary,
it intermittently fails to exist.

Why the magnitude decides the conclusion: if 2 of 5 treatment tables flip to `direct` at
T+12 and 0 of 4 controls do, that is a signal **if** unprompted flips are rare (~5%), and
**nothing** if a query flips category ~30% of the time on its own (≈1.5 flips expected among
5 tables by chance). Identical data, opposite readings — and no internal feature of the data
distinguishes them. Only a measured noise floor does, which converts "look at the pattern"
into a threshold fixed in advance.

- **From now on: 3 runs per query per timepoint** (Bing/primary), fresh session each,
  coded independently; the **modal** coding is the query's value. Duck.ai stays 1 run
  (secondary).
- **URGENT / time-limited:** capture **2 additional baseline replicates now**, before the
  mirrors are indexed (index check ~Aug 8). The pages are live but not yet crawled, so
  extra runs today are still *pre-treatment*. This (a) firms up the baseline via majority
  vote and (b) yields a **noise floor** — how often a query changes category with no
  intervention at all. Without that number we cannot say whether any post-treatment change
  is real. **This window closes once the pages are indexed.**

### A3. Code blind to arm

Coding `citation_class`/`value_match` involves judgment, and the coder knows which tables
are treatment — a live bias risk in the direction of the hypothesis. From the next round:
strip arm/table labels from captured answer text, shuffle, code, then re-join on query ID.

### A4. Indexing is a gating manipulation check, not a secondary outcome

If the treatment pages are never indexed, the study cannot test crawlability at all — it
tests whether a new GitHub Pages subpath gets crawled. Pre-committed reading:

- **Pages indexed + no citation change** → evidence *against* the crawlability mechanism.
- **Pages not indexed** → **null by non-exposure**, an inconclusive test of the mechanism.
  Must be reported that way, never as "crawlability doesn't work."

### A5. Pre-specified handling of "no AI answer box"

Common (16/60) and volatile. Rules fixed now: no box = `no_number`, and it counts as
**StatCan not cited** for the primary outcome. A box appearing/disappearing between rounds
is **not** itself a treatment effect — it is a surface change, reported separately. With A2
replicates, a query is "no box" only if the majority of its runs show none.

### A6. Unit of analysis is the table, not the query

Randomization is clustered at the table level and queries within a table are not
independent (2–3 queries can ride on one table). Analyse at the **table** level.
Effective n: **9 tables (5T/4C) wave 1, 8 tables (5T/3C) wave 2**. This is a
demonstration experiment: report counts, per-table detail, and concrete before/after
pairs. **No p-values, no significance claims** — the design cannot support them.

### A7. Wave-2 Population is descriptive only

Wave-2 strata are Health 3T/2C, Immigration 1T/1C, **Population 1T/0C**. Population has
**no control**, so any change there is inseparable from secular drift — report it as an
illustration, never as evidence. Immigration at 1T/1C is nearly as weak. Realistically
**wave 2 is a Health experiment** with two anecdotal side subjects; say so when reporting.

### A8. Refresh reference values and rebuild mirrors before each re-audit

`value_match`/vintage compare the served number against StatCan's current value, which
moves as StatCan publishes. Before each re-audit: re-fetch official values (record fetch
date) and re-run `build_mirror.py`. Otherwise "stale" becomes ambiguous, and the mirrors —
public pages that name Statistics Canada as the official source — would themselves drift
into serving outdated figures.

### A9. Score only questions StatCan can actually answer

Queries where StatCan publishes no comparable figure (cross-org: PHAC opioid deaths,
Cancer Society projections) **fail the entry test and are excluded from denominators
before scoring**, not carried as a category. They cannot measure whether an engine uses
StatCan data. Applied to the wave-2 Health scorecard 2026-07-25 (25 tested → **19 scored**).
Cross-org counts are still reported separately as the "vacuum-filling" finding.

### Design features that are sound (checked, no change needed)

- **Selection-on-baseline is handled.** Tables enter the pool *because* they showed a gap
  (an extreme value), so regression to the mean predicts improvement even with no
  treatment — but treatment and control are drawn from the **same** pool, so RTM hits both
  arms and the difference-in-differences absorbs it. This is precisely why the control arm
  must stay un-mirrored.
- **Secular drift** (engines change between July and October) is absorbed by the same DiD.
- **Displacement** (mirror cited *instead of* StatCan) was pre-registered as its own
  outcome rather than counted as success, and the 2026-07-25 attribution-strengthened
  template actively pushes credit to StatCan.

### Known residual limitations (accept and disclose, not fixable)

- **Underpowered by construction** (9 + 8 tables). Can demonstrate and illustrate; cannot
  estimate an effect size.
- **Single coder, pilot-grade**, even with A3 blinding — no second-rater reliability check.
- **Wave-1 discovery environment changed mid-flight**: wave-2 pages were added to the same
  site/sitemap on 2026-07-25, after wave-1 baseline. This affects wave-1 *treatment*
  exposure only (controls are not on the site) and pushes toward more crawling, not toward
  spurious citations — but wave-1 treatment is not held perfectly constant. Logged here.
- **Not generalizable to "crawlable and left to be found"** — sitemaps were actively
  submitted to both consoles (see below).

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
