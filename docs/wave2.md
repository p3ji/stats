# Mirror experiment — Wave 2 pre-registration

**Registered 2026-07-22, before any wave-2 baseline audit.** Extends the wave-1 design in
[`mirror_experiment.md`](mirror_experiment.md) to more StatCan subjects. Shared method
(treatment mechanism, coding schema, engines, re-audit cadence) is inherited from wave 1;
only the deltas are recorded here.

## Motivation

Wave 1 tested 9 tables across 3 subjects (Labour, Digital economy, Society). It works as a
demonstration but is thin on **captured examples** — the concrete before/after screenshot
pairs that make the "StatCan's own numbers are invisible to answer engines" story legible.
Wave 2 widens subject coverage to gather more of those examples, same method, same rigor.

## Scope

Three subjects, **75 queries total**, all already answerability-coded in
[`visibility/queries.yaml`](../visibility/queries.yaml):

| Subject | Queries | Status before wave 2 |
|---|---|---|
| Immigration & ethnocultural diversity | 25 (IMM-001…025) | coded 2026-07-18, **never audited** |
| Population & demography | 25 (POP-001…025) | coded 2026-07-18, **never audited** |
| Health | 25 (HEA-001…025) | **new**, coded 2026-07-22 (this wave) |

Health answerability: 11 fully / 13 partially / 1 microdata-only — a staleness-heavy
subject (CCHS/vital-stats lag; opioid, smoking, diabetes headline stats fronted by
PHAC/CIHI, not a current StatCan cube). Immigration and Population lean far more "fully
answerable" (census + demographic estimates are current and granular), so the three
subjects together span the full answerability range.

## Design (deltas from wave 1)

- **Separate cohort.** Wave-2 treatment/control tables are a **distinct set** from wave 1.
  Wave-2 mirrors must not touch wave-1's 9 tables or its control group, so the running
  wave-1 experiment stays un-confounded. Wave-2 pages, if built, go in the same `tables/`
  tree with new slugs and are added to the same `sitemap.xml`.
- **Selection rule (fixed now, tables chosen after baseline).** As in wave 1, the specific
  treatment tables can't be named until the baseline audit reveals which cells are
  "answerable but invisible." The rule, fixed in advance:
  1. Baseline-audit all 75 queries (below).
  2. Gap pool = queries coded `fully`/`partially` answerable whose baseline shows
     `citation_class` of `none`/`indirect` **or** `value_match` of `no_number`/`match_stale`
     /`mismatch_risk` (i.e. StatCan has it, but the engine doesn't use it or uses a stale
     intermediary).
  3. Deduplicate to the underlying table; randomize table→arm with a fresh seeded
     `random.Random` (seed recorded at assignment time), stratified by subject.
  4. Control tables in the pool are never mirrored (wave-1 rule carries over).
- **Treatment mechanism: identical.** `build_mirror.py`-style static crawlable page per
  treatment table — values in HTML, headline sentence, schema.org/Dataset JSON-LD,
  prominent "Source: Statistics Canada, Table …" attribution, explicit not-affiliated
  notice. No other promotion beyond sitemap + the existing Bing/Google submissions.

## Baseline (to capture before any treatment)

Same protocol as wave 1's 2026-07-19 round, applied to all 75 wave-2 queries:

- **Engines:** Bing Copilot Search (primary) and Duck.ai (GPT-5.x-nano, web search on),
  fresh session per query.
- **Evidence:** full-page screenshot + accessibility-tree capture per query, stored under
  `visibility/results/baseline_evidence/` with the existing `<engine>_<ID>_<date>.png`
  scheme.
- **Coding:** the extended value-match schema (`citation_class`, `cited_sources`,
  `answer_value`, `statcan_value`, `statcan_vintage_cited`, `best_available_vintage`,
  `value_match`, `note`) → `visibility/results/baseline_<engine>_wave2_<date>.csv`.
- **Reference values:** official current value per treatment table recorded at baseline
  (from WDS) so post-treatment vintage/accuracy shifts are measurable.

## Outcomes & re-audit

Unchanged from wave 1: difference-in-differences on citation, vintage, and value-match,
treatment vs control, at T+2wk (indexing check), T+6wk, and T+12wk after wave-2 deploy
(the primary endpoint is the 12-week round; crawl/index cycles are slow). Dates set when
wave-2 pages deploy, not now.

## Threats / caveats specific to wave 2

- **Discovery push already active.** The `/stats/` site is already verified + sitemap-
  submitted to both Bing and Google (2026-07-19). Wave-2 pages inherit that, so they may
  index faster than wave-1 pages did from a cold domain — note when comparing wave-1 and
  wave-2 indexing speed.
- **Subject imbalance is intentional, not a flaw.** Immigration/Population are mostly
  `fully` answerable (should show citation *displacement* — right number, wrong credit),
  while Health is staleness-heavy (should show *stale-vintage* and *no-number* failures).
  The two failure modes are analyzed separately, not pooled.
- **Cross-org indicators.** Several Health queries (opioid deaths, diabetes surveillance,
  cancer projections, wait times) are genuinely PHAC/CIHI/Fraser-Institute territory, not
  StatCan's — those are coded `partially` and are examples of the *vacuum-filling* mode,
  not StatCan underutilization per se. Keep that distinction when reporting.
- **Coding is pilot-grade / single-coder**, same limitation as wave 1.
