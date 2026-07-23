# Mirror experiment — Wave 2 pre-registration

**Registered 2026-07-22, before any wave-2 baseline audit.** Extends the wave-1 design in
[`mirror_experiment.md`](mirror_experiment.md) to more StatCan subjects. Shared method
(treatment mechanism, coding schema, engines, re-audit cadence) is inherited from wave 1;
only the deltas are recorded here.

## Pilot finding (2026-07-22, n=5) — the gap is surface-specific

A 5-query pilot (HEA-006, HEA-012, HEA-016, IMM-001, POP-001) run through both engines the
same day showed a sharp per-engine split:

- **Bing inline AI answer: 4/5 gaps.** Even where StatCan publishes the figure, Bing's
  answer served it via SEO farms / aggregators — `madeinca.ca` (immigrants), Wikipedia/
  Worldometer (population, no AI box at all), the OurCare/CMA survey (family doctor).
- **Duck.ai (chatbot + web search): 0/5 gaps.** It cited StatCan *directly* on 4/5,
  naming the exact table on POP-001 (`17-10-0009-01`), the exact census count on IMM-001,
  and the 82.8% regular-provider rate on HEA-016.
- **Both engines miss identically on HEA-012 (opioid deaths)** — but that's PHAC's
  surveillance, not a StatCan product, i.e. a cross-org case, not underutilization.

Implication for the experiment: the visibility gap is largely a **Bing/SERP-AI surface**
phenomenon; the retrieval-augmented chatbot already uses StatCan well. So (a) the wave-2
**gap pool / treatment candidates are essentially the Bing-side gaps**, and (b) Duck.ai is
better read as an *already-good comparison surface* — the place to watch for treatment
**displacement** (mirror cited instead of StatCan), not for new citations. `value_match`
and `citation_class` are therefore coded **per engine**, and gap-selection keys off the
Bing column. Caveat: n=5, one day, Duck.ai on its default "Fast" model tier (wave 1 used
GPT-5.4-nano — model not held identical; note when comparing across waves). The full
75-query audit tests whether this holds.

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

Applied to all 75 wave-2 queries, as a **two-pass protocol** (refined 2026-07-22, before
any evidence was captured — this deliberately narrows wave 1's "screenshot every query"
rule):

- **Engines:** Bing Copilot Search (primary) and Duck.ai (GPT-5.x-nano, web search on),
  fresh session per query.
- **Pass 1 — triage (all 75 queries, text only).** Pull the answer text, code the extended
  value-match schema (`citation_class`, `cited_sources`, `answer_value`, `statcan_value`,
  `statcan_vintage_cited`, `best_available_vintage`, `value_match`, `note`) →
  `visibility/results/baseline_<engine>_wave2_<date>.csv`. No screenshot at this stage.
- **Pass 2 — evidence (gap cases only).** Capture evidence **only** for queries where
  treatment could plausibly change the outcome: coded answerable (`fully`/`partially`)
  **and** baseline `citation_class` ∈ {`none`, `indirect`} **or** `value_match` ∈
  {`no_number`, `match_stale`, `mismatch_risk`}. **Primary evidence is the captured answer
  text + accessibility tree** (`<engine>_<ID>_<date>.yml`/`.txt` under
  `visibility/results/baseline_evidence/`) — durable, diffable, and reliably capturable;
  the full-page PNG is an optional extra for presentation (the in-app screenshot tool times
  out on heavy SERPs, so PNGs are best-effort, grabbed for the strongest examples). **Rationale:** where StatCan's figure is already cited *and* used *and* current
  (`direct` + `match_current`), mirroring the table cannot move the outcome, so there is no
  "after" for a "before" screenshot to pair with — capturing it wastes effort and adds no
  evidentiary value. The gap cases are exactly the mirror-treatment candidates, so evidence
  is spent only where a before/after contrast can exist.
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
