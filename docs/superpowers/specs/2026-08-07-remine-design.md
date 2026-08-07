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
  mentions.py      # cheap member-name matching -> demotion weights
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
article_url --mentions--> {member -> mentioned?}   (demotion weights only)
pid --cube--> DataFrame + CubeMeta
DataFrame --probes--> Fact[]              (numbers computed here, only here)
Fact[] + mentions --rank--> Fact[] ranked and gated
ranked + article prose --editor(brief)--> editorial pass in a Claude Code session
draft --editor(bind)--> Article JSON       (tokens replaced by Fact values)
Article JSON --site--> /remine/
```

**Where judgment lives.** Arithmetic is mechanical and happens in `probes.py`. Deciding
whether the Daily already told a story is an act of reading, and happens in the editorial
stage with the article's full prose in hand. The pipeline does not attempt to parse the
article's narrative structure; see Appendix A for the more mechanical design this replaced
and the conditions under which it should be revived.

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

## Stage 2 — mentions

The pipeline does not try to understand the Daily article. It answers one narrow,
mechanical question, and only because ranking happens before any model reads anything.

**Why this stage exists at all.** The brief carries the top ~40 facts out of thousands.
The cuts a Daily article reports are typically the largest and most legible ones —
national employment, the headline unemployment rate — which are exactly the cuts that
score highest on magnitude and legibility. Without some correction, the top of the ranked
list is where duplication concentrates, and genuinely new material is pushed off the brief
before anyone can read it.

**What it does.** String-match every dimension member name from the cube against the
article text: `Alberta`, `15 to 24 years`, `Women+`. Emit a per-member boolean. `rank.py`
uses it as a **demotion weight**, not a filter.

Nothing is dropped on this signal. It has no correctness burden because it never makes a
final call — a misfire costs a slightly worse brief, never a wrong article. Matching is
case-insensitive with a small synonym table in `surveys.yaml` for the obvious cases
("youth" -> `15 to 24 years`).

The article's prose is retained verbatim and passed into the brief. The judgment "the
Daily already said this" is made at editorial time, by reading.

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
  "mentioned": bool,            # any member of this cut named in the article text
  "statement": str,             # neutral machine-written description
  "human": str,                 # same, in reader-scale units (see Humanizing)
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
4. Drop facts that are definitional or methodological artifacts rather than findings — a
   member that is an aggregate of the members it is being compared against, a difference
   that is true by construction. `surveys.yaml` declares each cube's aggregate members.

### Salience (ranks survivors)

Explicitly not surprise. Four components, weighted in `surveys.yaml`:

- **magnitude** — size of the effect, normalized within the indicator
- **persistence** — how many periods the pattern has held; **higher is better**
- **legibility** — how identifiable the subgroups are to a reader (province, age band,
  gender score high; derived aggregates and technical residuals score low)
- **reader-scale** — expressible in units a person feels (people, dollars, points)

A stable, large, legible gap therefore outranks a volatile one-month swing by
construction, which is the correction that distinguishes this design from anomaly hunting.

Then the **mention demotion**: facts whose cut involves members named in the article are
multiplied by a configurable factor below 1. They stay on the list — sometimes the Daily
names a province while saying nothing interesting about it — but they stop crowding out
untouched material. The factor is tuned in `surveys.yaml`, starting at 0.5.

## Stage 6 — editorial

`generate.py` stops at stage 5 and writes a **fact brief** to `remine/briefs/`: the top
~40 ranked facts as structured data with numbers already computed, the **full verbatim
prose of the Daily article**, the mention map, and cube provenance.

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

### Defence against the two failure modes that matter

These are the risks most likely to make Remine worthless even when every number is
correct. Each gets a mechanical check, not just an instruction.

**Failure 1 — the editorial pass didn't actually engage with the Daily, so the "new"
story isn't new.** Three checks:

1. The draft must open with a **restatement of the Daily's own story** in one sentence,
   written from the prose in the brief. An editorial pass that can't produce it didn't
   read the article.
2. Each selected fact must carry an explicit **`differs_from_daily`** line: what the Daily
   said about this cut, or `"not discussed"`.
3. `editor.py bind` **cross-checks that line against the mention map.** If a fact is
   declared `"not discussed"` but its members were matched in the article text, the build
   flags it for human resolution. This is why `mentions.py` is worth keeping even though
   it makes no decisions — demoted to a ranking nudge, it is promoted to an auditor of the
   model's claims.

**Failure 2 — the output is technically correct and no one wants to read it.** The
salience model's legibility and reader-scale terms push against this, but they are not
sufficient. Four more:

1. **Humanizing is mechanical.** `probes.py` emits a `human` field alongside `statement`,
   converting cube units into units a person feels: `"Persons in thousands"` with
   `SCALAR_FACTOR: thousands` and a value of `47.3` becomes `"about 47,000 people"`.
   Drafts reference the humanized form. Readers never see "thousands, seasonally adjusted"
   unless the caveat is the point.
2. **The one-sentence test.** Every story must reduce to one sentence a non-specialist
   understands, and that sentence is the headline. If it can't be written, the fact is
   dropped rather than dressed up.
3. **The assumption must be a real belief**, stated in the words a person would use —
   "housing pressure is a Toronto and Vancouver problem" — not a restatement of the
   statistic. A named assumption that merely paraphrases the number is a rejected draft.
4. **A story is not a definition.** Drafts whose interest depends on a methodological or
   classification detail are rejected; the gate drops the obvious cases (rule 4 above) but
   the editorial pass is the backstop.

If v1's output still reads as technical after these, the fault is in the probe library —
it is generating findings about the data rather than about the country — and the response
is to add probes framed on people and places, not to add more editorial instruction.

## Site

`/remine/` is a feed of cards: date, source Daily article, headline. Each article page
carries:

- the Daily's story, one line, for contrast
- 2–4 re-mined stories, each with a chart, the assumption it speaks to, and whether it
  concretizes or challenges it
- a provenance block per fact: vector IDs, reference periods, what the Daily said about
  this cut (or that it did not), and a link to the StatCan table
- the standing disclaimer that Open Stats Lab is independent and not affiliated with or
  endorsed by Statistics Canada, and that the analysis is not StatCan's

Visual language matches the existing homepage and report: same CSS variables, Inter and
Space Grotesk, dark-first with a light-scheme override. Articles are static JSON read by
`app.js`; no framework.

A homepage card is added to `index.html`.

## Testing

Probes, gate, ranker, and the humanizer are pure functions, unit-tested against small
fixture cubes with hand-computed expected values. `mentions.py` is tested against a
fixture article for both matches and near-misses. Token binding has tests asserting that
an unresolved token, an unknown token, and a bare numeral each fail the build, and that a
`"not discussed"` claim contradicted by the mention map is flagged. No test makes an LLM
call or a network request; network-dependent code is exercised against cached fixtures.

## CLI

```
python remine/generate.py --date 260807              # all articles that day
python remine/generate.py --date 260807 --pid 14100287
python remine/generate.py --brief remine/briefs/260807-a.json --bind draft.md
```

## Risks

- **The re-mined story isn't actually new** because the editorial pass didn't engage with
  the Daily. The primary risk. Mitigated by the three checks in "Defence against the two
  failure modes" — required restatement, per-fact `differs_from_daily`, and the mention-map
  cross-check that catches a false "not discussed".
- **The output is correct but dull** — technically accurate findings that reveal nothing a
  reader cares about. Mitigated by mechanical humanizing, the one-sentence test, and the
  requirement that a named assumption be a real belief rather than a paraphrase. If it
  persists, the fix is new probes, not new prompt text.
- **Cube downloads are large** (60 MB for the LFS table). Mitigated by caching keyed on
  release time; cache is gitignored.
- **Legibility scoring and the mention-demotion factor are heuristics** and will need
  tuning per survey. Both live in `surveys.yaml` so tuning is config, not code.
- **Publishing statistical claims under your name.** The gate, the provenance block, and
  the human editorial step are the three defences.

## Appendix A — the mechanical footprint design (superseded)

The first version of this spec put a **`footprint.py`** between discovery and probing,
which parsed the Daily article's prose and bound every numeric claim in it to a fully
qualified cube cut — resolving "youth aged 15 to 24" to the `Age group` member `15 to 24
years` — and assigned every candidate fact one of three coverage levels:

| level | meaning |
|---|---|
| `narrated` | the cut and a value for it appear in a sentence |
| `adjacent` | the cut appears in the article's own data tables but not in prose |
| `unnarrated` | the cube supports it, the article never touches it |

Facts marked `narrated` were dropped by the gate. The parser was specified to bias toward
over-subtraction — when it could not decide, the cut counted as narrated — on the grounds
that republishing something the Daily already said discredits the premise. It was to be
tested against fixture articles with hand-labelled cuts.

**Why it was replaced.** It located judgment in the wrong place. Deciding what an article
is about is comprehension, and the editorial stage is already a model reading a brief, so
that decision is nearly free there and expensive and error-prone in a parser. The parser
was also the design's largest correctness burden and its most likely source of iteration,
in exchange for a decision that gets made again downstream anyway.

What survives is the narrow mechanical need it was over-serving: keeping already-covered
cuts from monopolizing a truncated ranked list. `mentions.py` does that with member-name
matching and a demotion weight, and is additionally reused as an auditor of the editorial
pass's `differs_from_daily` claims.

**When to revive it.** If v1's output repeatedly duplicates the Daily *despite* the
mention demotion and the cross-check — that is, if the editorial pass proves unreliable at
noticing coverage even with the full prose in front of it — then the subtraction has to
become mechanical after all. In that case restore the three coverage levels and the
gate-drop on `narrated`, keeping `mentions.py` as the cheap first pass. The `Fact` schema
change is small: `mentioned: bool` becomes `coverage: enum`. Watch for this specifically
in the first several runs; it is the failure this design trades away risk-of-complexity to
accept.
