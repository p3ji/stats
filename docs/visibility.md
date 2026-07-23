# StatCan AI/Search Visibility Study — plan of record

**Question:** To what extent do popular search tools and generative AI answer engines use
Statistics Canada data when answering everyday questions StatCan could answer — and where
they don't, why not?

**Pilot scope (decided 2026-07-18):** three subjects — **Labour**, **Digital economy and
society**, **Society and community**. 100 queries in `visibility/queries.yaml`.
Labour is the high-volume, well-published control; the other two are survey-rich areas
(GSS, CIUS, CSS) where the underutilization thesis predicts the biggest gaps.

## Study design

Three linked measurements per query:

1. **Is StatCan used?** Run each query through the target engines; code the answer:
   - `direct` — statcan.gc.ca (or an official StatCan product) cited
   - `indirect` — cited source itself relies on StatCan (Wikipedia, news, aggregators)
   - `none` — no StatCan lineage
   - plus `answer_correct` — does the stated number match the actual StatCan value?
     (mismatch = the misinformation-counter measure)
2. **Could StatCan have answered?** Code against WDS cube metadata (~8,000 tables):
   `fully` (published table at needed granularity) / `partially` (indicator exists but
   not at the asked disaggregation/geography) / `microdata_only` (collected but not
   published) / `not_collected`. The 2×2 of (used × answerable) is the headline result;
   the "answerable but not cited" cell is the underutilization gap.
3. **Why not?** Attribute each miss to a barrier (checklist below).

### Target engines (pilot)

Google (organic + AI Overview), Bing/Copilot, Perplexity, ChatGPT, Claude, Gemini.
Pilot may start with 2–3; Perplexity's API returns citations natively and is the
easiest to automate. Manual runs are acceptable at n=100.

### Intent taxonomy (in queries.yaml)

`point` / `trend` / `comparison` / `disaggregated` / `integration`. The `probe` field
tags queries constructed to test a specific underutilization mechanism:
`unpublished_indicator`, `shallow_disaggregation`, `no_integration`.

## Barriers checklist — empirical status

Verified 2026-07-18 (re-verify before publishing; robots.txt and page tech change):

| Barrier | Status | Evidence |
|---|---|---|
| StatCan blocks AI crawlers | **No** — refuted | Neither statcan.gc.ca nor www150 robots.txt names GPTBot/ClaudeBot/Google-Extended/CCBot/PerplexityBot |
| Table data invisible to non-JS crawlers | **Yes** — confirmed | t1/tbl1 pages render all data client-side; no-JS crawler sees filter UI, zero values (checked PID 1810000401) |
| Bulk files blocked from crawling | **Yes** — confirmed | www150 robots.txt disallows `.csv`, `.xls`, `.txt`; 2s crawl-delay for all agents |
| No schema.org/Dataset markup | **Yes** — confirmed | No JSON-LD and no meta description on table pages → invisible to Google Dataset Search, nothing machine-readable to cite |
| Presence in AI training data | Untested | Check Common Crawl index for www150 t1/tbl1 URLs |
| Terminology mismatch (official vocab vs user phrasing) | Untested | Compare query bank phrasing vs matching table titles during goal-2 coding |

Mechanism hypothesis: answer engines can't see StatCan's numbers, so they cite
secondary sources (Wikipedia, news, commercial aggregators) that quote StatCan
second-hand — losing freshness, granularity, and sometimes accuracy.

## Query bank provenance

`source: autocomplete` queries are verbatim/lightly-normalized Google autocomplete
completions collected 2026-07-18 via `suggestqueries.google.com` (client=firefox).
Notable: users natively ask for disaggregation ("by province", "by city", "by age",
"for immigrants", "in seniors") — demand-side evidence for the disaggregation thesis.
`source: curated` queries fill designed cells (probes, integration questions).

## Pipeline (planned)

Mirrors the repo pattern: `visibility/run_audit.py` → `visibility/results/*.parquet`
→ DuckDB-Wasm dashboard page ("StatCan visibility index": citation rate by subject ×
engine × intent). Not yet built.

## Status

- [x] Query bank (100 queries, 3 subjects) — `visibility/queries.yaml`
- [x] Barriers spot-checks (robots.txt, table-page rendering, Dataset markup)
- [x] Goal-2 coding: all 100 queries coded vs WDS cube list (2026-07-18) —
      results and headline findings in `docs/visibility_pilot_report.md`
      (47 fully / 38 partially / 11 microdata_only / 4 not_collected)
- [x] Engine audit (goal 1) round 1, 2026-07-18: DDG organic all 100 queries
      (`visibility/run_audit_ddg.py` → `results/ddg_2026-07-18.csv`; StatCan rank-1
      45%, top-3 69%) + Bing AI-answer sample n=12 (`results/bing_ai_sample_*.csv`;
      3/12 direct citations). Analysis: `visibility/analyze.py`. Google/Perplexity
      blocked by bot checks — need API key or manual runs.
- [x] Chatbot audit round 1, 2026-07-18: Duck.ai (GPT-5.4-nano, auto web search),
      n=10 fresh-chat sessions → `results/duckai_sample_2026-07-18.csv`. 8/10 direct
      StatCan citations, but all via the article layer (never tables); staleness
      inherits from article vintage. Perplexity is Cloudflare-blocked; ChatGPT/
      Claude/Gemini/Copilot need accounts or API keys.
- [x] Mirror experiment set up (2026-07-19): treatment/control assignment over the 9
      gap-cell tables, crawlable pages built (`visibility/mirror/` → `tables/`,
      sitemap.xml), pre-registration in `docs/mirror_experiment.md`. Awaiting deploy.
- [x] Baseline evidence round (2026-07-19): all 11 experiment queries through Bing
      Copilot Search with screenshots (`visibility/results/baseline_evidence/`) and
      extended value-match coding (`results/baseline_bing_copilot_2026-07-19.csv`).
      Duck.ai run completed same day after user accepted the terms gate
      (`results/baseline_duckai_2026-07-19.csv`).
- [ ] Extend chatbot audit (more models/surfaces, full 100, correctness coding)
- [ ] Common Crawl presence check for t1/tbl1 URLs
- [ ] Dashboard
- [~] **Wave 2** (2026-07-22): widen subject coverage for more captured examples.
      Query bank extended to Health (25 new, HEA-001…025) alongside the already-coded
      Immigration (25) and Population (25) — 75-query wave-2 audit set. Pre-registration
      in `docs/wave2.md` (separate cohort from wave 1; selection rule fixed, tables
      chosen after baseline). Next: run the 75-query baseline audit (Bing Copilot +
      Duck.ai, screenshots + value-match coding) → derive gap pool → assign arms →
      build mirrors.

Tooling: `visibility/fetch_cubes.py` (cube list → `visibility/cache/`, gitignored),
`visibility/search_cubes.py` (title keyword search). WDS gotcha: in
getAllCubesListLite, `archived: "2"` = current, `"1"` = archived/inactive.
