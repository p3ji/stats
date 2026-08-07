# Remine — design spec

**Date:** 2026-08-07
**Status:** approved design, not yet implemented
**Sub-app:** `/remine/` on Open Stats Lab

## Premise

Statistics Canada collects, processes, and releases far more data than it narrates. A
Daily article is a taste: it reports the headline cut and a handful of subgroups, then
links to a table containing thousands of series nobody writes about. The table cited by
the 2026-08-07 Labour Force Survey release (14-10-0287-01) holds roughly 8,000 series —
11 geographies x 9 labour force characteristics x 3 genders x 9 age groups x 3 data
types. The article narrates on the order of a dozen.

Remine re-mines that gap. For a given release it determines what the Daily said, computes
what the same data supports saying, subtracts the first from the second, and publishes the
remainder as new articles.

**A finding is worth publishing when it concretizes a widely held assumption or challenges
one.** This is deliberately *not* anomaly detection. A large, stable, entirely unsurprising
gap is a strong story precisely because it is solid; an outlier is often just noise. The
ranking model rewards persistence rather than penalizing it.

## Non-goals (v1)

News retrieval. Scheduling or automation. French. Cross-cube joins. LLM-authored query
specs. More than one release date per run. Anything that publishes without a human in the
loop.

## Architecture

Static-site conventions of this repo apply unchanged: a Python pipeline writes committed
artifacts, the site reads them, there is no backend and no build step.

```
remine/
  discover.py      # Daily index -> release records
  footprint.py     # article prose -> what was narrated
  cube.py          # WDS metadata + full-table fetch, disk cache
  probes.py        # deterministic fact generation
  rank.py          # reliability gate, then salience score
  editor.py        # fact brief out, drafted article in, token substitution
  generate.py      # CLI orchestrator
  surveys.yaml     # per-cube config
  briefs/          # stage-5 output, gitignored
  articles/        # committed published articles (JSON)
  cache/           # downloaded cubes, gitignored
remine/index.html  # feed
remine/article.html
remine/app.js
remine/style.css
```

`remine/cache/` and `remine/briefs/` are added to `.gitignore` (cube downloads run to tens
of megabytes; `visibility/cache/` sets the precedent).

### Data flow

```
Daily index --discover--> release {date, article_url, pids[]}
article_url --footprint--> NarrativeFootprint {narrated cuts, numbers}
pid --cube--> DataFrame + CubeMeta
DataFrame --probes--> Fact[]              (numbers computed here, only here)
Fact[] + footprint --rank--> Fact[] ranked, gated, coverage-subtracted
ranked --editor(brief)--> human/LLM editorial pass
draft --editor(bind)--> Article JSON       (tokens replaced by Fact values)
Article JSON --site--> /remine/
```

## Stage 1 — discover

The Daily has no working RSS feed (`/n1/dai-quo/rss/statcan-eng.xml` and
`/n1/daily-quotidien/index-eng.htm` both 404 as of 2026-08-07; `/eng/sc/rss` is a feed
index, not the Daily). Scrape the index instead.

- Index: `https://www150.statcan.gc.ca/n1/dai-quo/index-eng.htm`
- Article URLs follow `/n1/daily-quotidien/YYMMDD/dqYYMMDD{a,b,c,...}-eng.htm`
- Product IDs appear in the article as `/t1/tbl1/en/tv.action?pid=NNNNNNNNNN` (10 digits)
  and in prose as `NN-NN-NNNN-NN`. The 8-digit cube PID is the 10-digit form minus its
  trailing two-digit view suffix (`1410028701` -> `14100287`).

Output: `Release { date, articles[ {url, title, slug, pids[]} ] }`.

Failure mode: index markup changes. `discover.py` asserts it found at least one article
and at least one PID, and fails loudly rather than silently emitting an empty release.

## Stage 2 — footprint

Determines what the Daily article actually said, so it can be subtracted.

Parse the article body and extract, for every numeric claim in prose, the cut it belongs
to: which geography, which subgroup members, which reference period, which measure. Cuts
are resolved against the cube's dimension member names, so "youth aged 15 to 24" binds to
the `Age group` member `15 to 24 years`.

Three coverage levels:

| level | meaning |
|---|---|
| `narrated` | the cut and a value for it appear in a sentence |
| `adjacent` | the cut appears in the article's own data tables but not in prose |
| `unnarrated` | the cube supports it, the article never touches it |

**Bias toward over-subtraction.** If the parser cannot decide whether a cut was narrated,
it counts as narrated. Publishing something the Daily already said is the worse failure —
it makes the whole premise look wrong.

Also captured: the article's own headline story, in one sentence, for contrast in the
published piece.

This stage is the most likely to need iteration and the most valuable to test against
fixtures. It ships with hand-labelled fixture articles.

## Stage 3 — cube

- `POST /t1/wds/rest/getCubeMetadata` with `[{"productId": NNNNNNNN}]` returns dimensions,
  members, `releaseTime`, footnotes, and correction flags.
- `GET /t1/wds/rest/getFullTableDownloadCSV/{pid}/en` returns a JSON envelope whose
  `object` is a zip URL (`https://www150.statcan.gc.ca/n1/tbl/csv/{pid}-eng.zip`). The zip
  holds `{pid}.csv` and `{pid}_MetaData.csv`.

Per-vector fetching is not viable at this scale; the full-table download is the access
path. Verified columns:

```
REF_DATE, GEO, DGUID, <one column per non-geo dimension>, UOM, UOM_ID,
SCALAR_FACTOR, SCALAR_ID, VECTOR, COORDINATE, VALUE, STATUS, SYMBOL,
TERMINATED, DECIMALS
```

CSVs are UTF-8 with BOM — read with `encoding="utf-8-sig"`. Downloads are cached by PID
and `releaseTime`, so re-runs against an unchanged release cost nothing.

The existing `pipeline/extract.py` WDS conventions are followed where they apply, but
`cube.py` is separate: `extract.py` pulls named vectors for a fixed manifest, `cube.py`
pulls whole cubes for exploration. Different jobs, no shared code worth forcing.

## Stage 4 — probes

Every number that will ever appear in a Remine article is computed here. The LLM stage
computes nothing.

```python
Fact = {
  "probe": str,                 # which probe emitted it
  "cut": {dim: member, ...},    # fully qualified position in the cube
  "values": [float],            # computed values
  "periods": [str],             # reference periods, one per value
  "vectors": [str],             # source vector IDs
  "uom": str, "scalar": str, "decimals": int,
  "magnitude": float,           # normalized within indicator
  "se": float | None,           # standard error of the reported difference
  "legibility": float,
  "coverage": "narrated" | "adjacent" | "unnarrated",
  "statement": str,             # neutral machine-written description
}
```

v1 probe library:

| probe | finds |
|---|---|
| `gap_between_members` | persistent difference between two members of one dimension |
| `gap_trend` | that gap widening or narrowing over time |
| `level_threshold` | a series crossing a round, legible number |
| `streak` | n consecutive periods moving one direction |
| `rank_order` | who leads and trails a dimension |
| `rank_reversal` | a lead change that has held |
| `share_of_total` | a member's contribution to its aggregate, and its change |
| `long_run_compare` | vs. pre-pandemic, or the same month N years back |

Probes are pure functions registered in a dict keyed by name. **The registry is the
documented extension point** for the later LLM-authored query-spec path: a query spec
resolves to the same `Fact` shape and flows through the identical downstream stages, so
adding it requires no restructuring. Not built in v1.

## Stage 5 — reliability gate, then salience

### Gate (drops; does not rank)

1. Drop any data point whose `STATUS`/`SYMBOL` marks it suppressed, too unreliable to
   publish, or confidential.
2. Where the cube exposes standard errors, require the reported difference to exceed the
   relevant one. In the LFS cube, `Statistics` is a dimension with members `Estimate`,
   `Standard error of estimate`, `Standard error of month-to-month change`, and `Standard
   error of year-over-year change` — the agency's own error bars, in the same download.
   `surveys.yaml` maps each cube to the SE member appropriate to each comparison type.
3. Cubes without SE series fall back to a per-survey minimum-magnitude floor declared in
   `surveys.yaml`, and every article built on such a cube states that caveat.
4. Drop facts whose coverage is `narrated`.

### Salience (ranks survivors)

Explicitly not surprise. Four components, weighted in `surveys.yaml`:

- **magnitude** — size of the effect, normalized within the indicator
- **persistence** — how many periods the pattern has held; **higher is better**
- **legibility** — how identifiable the subgroups are to a reader (province, age band,
  gender score high; derived aggregates and technical residuals score low)
- **reader-scale** — expressible in units a person feels (people, dollars, points)

A stable, large, legible gap therefore outranks a volatile one-month swing by
construction, which is the correction that distinguishes this design from anomaly hunting.

`adjacent` facts are ranked but marked, so the published article can be honest that the
number was in the Daily's table even though no one wrote a sentence about it.

## Stage 6 — editorial

`generate.py` stops at stage 5 and writes a **fact brief** to `remine/briefs/`: the top
~40 ranked facts as structured data with numbers already computed, plus the Daily's own
headline story for contrast, plus cube provenance.

The editorial pass then happens in a Claude Code session reading that brief. No API key,
no secret to manage (AGENTS.md forbids committing secrets), and a human in the loop by
construction. `editor.py` exposes the brief-out / draft-in interface so an API-calling
implementation can be dropped in later without touching any other stage.

The editorial output must:

- select 2–4 facts that cohere into one piece
- for each, classify it as **concretizing** or **challenging** a widely held assumption,
  and name that assumption in plain words
- write prose that references numbers **only as tokens** — `{{fact_3.values[0]}}` — never
  as literals

`editor.py bind` substitutes tokens from the `Fact` records and **fails the build on any
unresolved or unknown token**. That check is the mechanical guarantee behind "numbers come
from code, not the model". Prose containing a bare numeral that is not a token also fails,
with an allowlist for years and ordinals.

## Site

`/remine/` is a feed of cards: date, source Daily article, headline. Each article page
carries:

- the Daily's story, one line, for contrast
- 2–4 re-mined stories, each with a chart, the assumption it speaks to, and whether it
  concretizes or challenges it
- a provenance block per fact: vector IDs, reference periods, coverage level, and a link
  to the StatCan table
- the standing disclaimer that Open Stats Lab is independent and not affiliated with or
  endorsed by Statistics Canada, and that the analysis is not StatCan's

Visual language matches the existing homepage and report: same CSS variables, Inter and
Space Grotesk, dark-first with a light-scheme override. Articles are static JSON read by
`app.js`; no framework.

A homepage card is added to `index.html`.

## Testing

Probes, gate, and ranker are pure functions, unit-tested against small fixture cubes with
hand-computed expected values. The footprint parser is tested against fixture Daily
articles with hand-labelled narrated cuts, asserting the over-subtraction bias. Token
binding has a test asserting that an unresolved token and a bare numeral each fail the
build. No test makes an LLM call or a network request; network-dependent code is exercised
against cached fixtures.

## CLI

```
python remine/generate.py --date 260807              # all articles that day
python remine/generate.py --date 260807 --pid 14100287
python remine/generate.py --brief remine/briefs/260807-a.json --bind draft.md
```

## Risks

- **Footprint parsing is the hard part.** If it under-subtracts, Remine republishes the
  Daily. Mitigated by the over-subtraction bias and fixture tests, but it will need
  iteration against real articles.
- **Cube downloads are large** (60 MB for the LFS table). Mitigated by caching keyed on
  release time; cache is gitignored.
- **Legibility scoring is a heuristic** and will need tuning per survey. It lives in
  `surveys.yaml` so tuning is config, not code.
- **Publishing statistical claims under your name.** The gate, the provenance block, and
  the human editorial step are the three defences.
