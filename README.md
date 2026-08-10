# Open Stats Lab

An independent workbench of open-data projects built on Statistics Canada's public data,
plus FRED, the Australian Bureau of Statistics, and Statistics Finland where a comparison
needs them. Everything here is static, pipeline-generated, and open.

Live site: **https://p3ji.github.io/stats/**

Open Stats Lab is a personal project. It is **not affiliated with, or endorsed by,
Statistics Canada**, and no conclusion drawn here is theirs. Official data always lives at
[statcan.gc.ca](https://www.statcan.gc.ca/).

There are three working projects in this repository and one planned. They share data
sources and conventions and nothing else.

---

## 1. The AI visibility study

**The question.** When someone asks a search engine or an AI assistant an everyday question
that Statistics Canada could answer, does the answer actually come from Statistics Canada?
And where it doesn't, why not?

**Why it might matter.** A national statistical agency can publish excellent data and still
be invisible at the moment a person asks the question, because the answer arrives through a
model or a search summary rather than through the agency's own website. If that is
happening, it is a distribution problem rather than a data problem, and it is measurable.

**How the study goes about it.** Each query in the bank gets three linked measurements:

1. *Is StatCan used?* The query runs through the target engines and the answer is coded
   `direct` (statcan.gc.ca or an official product cited), `indirect` (the cited source is
   itself built on StatCan, such as Wikipedia or a news article), or `none`. The stated
   number is separately checked against the real StatCan value, which is what makes a
   wrong-number result distinguishable from a merely uncited one.
2. *Could StatCan have answered?* The query is coded against WDS cube metadata for roughly
   8,000 tables as `fully`, `partially`, `microdata_only`, or `not_collected`. Crossing
   this with the first measurement gives the headline result: the cases that are answerable
   from published data and yet invisible in practice.
3. *Does crawlability change anything?* This is a pre-registered experiment rather than an
   observation. Tables from the "answerable but invisible" cell were randomised at the
   table level into treatment and control. Treatment tables got static, crawlable mirrors
   with the values in the markup, schema.org/Dataset metadata, and prominent attribution.
   Control tables got nothing. The design was registered before deployment so the
   comparison could not be chosen after the fact.

**Where it lives.**

- `/report/` is the plain-language findings report, with the official value, source links,
  and before-and-after screenshots side by side. Start here.
- `/tables/` holds the crawlable mirrors, which are the treatment arm of the experiment.
  They are generated, never hand-edited.
- `visibility/` holds the query bank, the audit scripts, and the analysis.
- `docs/visibility.md` is the plan of record and `docs/mirror_experiment.md` is the
  pre-registration.

Rebuild the mirrors with `python visibility/mirror/build_mirror.py`. It only ever touches
the treatment tables listed in the manifest; mirroring a control table would destroy the
experiment.

---

## 2. Remine

**The premise.** Statistics Canada publishes far more data than it describes. A Daily
article reports the headline number and a few subgroups, then links to a table holding
thousands of series nobody writes about. The table behind the July 2026 Labour Force Survey
release holds roughly 8,000 series. The article narrates about a dozen.

**What Remine does.** It reads a Daily release, computes what the same table supports
saying, and drafts the articles that were left out. A finding is worth publishing when it
concretizes a widely held assumption or challenges one. That is deliberately not anomaly
detection: a large, stable, unsurprising gap is a strong story precisely because it is
solid, so the ranking treats persistence as a point in a finding's favour.

**Numbers come from code, not from a language model.** The drafting step never types a
number. It writes tokens such as `{{fact_3.human}}`, and `remine/editor.py` substitutes the
computed value and refuses to build if anything is wrong. That refusal is the guarantee,
and it lives in Python rather than in an instruction to a model.

### The pipeline, stage by stage

1. **Discover** (`discover.py`) scrapes The Daily's index for a date, collects that day's
   articles, and extracts the product IDs of the tables each one cites. The Daily has no
   working RSS feed as of August 2026, so the index page is scraped.
2. **Mentions** (`mentions.py`) checks which of the table's dimension members the article
   names in its own text. This produces a ranking demotion, never a filter, and later
   serves as an auditor of the drafting stage's claims about what the Daily covered.
3. **Cube** (`cube.py`) fetches the table's metadata and its full data download from the
   WDS API, caching by release time so repeat runs cost nothing. Per-series fetching is not
   practical at this scale, so the bulk CSV is the access path.
4. **Probes** (`probes.py`) compute findings: persistent gaps between subgroups, gaps
   widening or narrowing, rank order and reversals, streaks, threshold crossings, shares of
   a total, and long-run comparisons. Every number that can ever appear in a published
   article originates here. Before probing, the frame is sliced so that only the dimension
   under comparison varies, and members are restricted to sets that genuinely partition the
   population, because Statistics Canada's dimensions nest by design and comparing a
   fifty-year age band with a five-year one produces an artifact rather than a finding.
5. **Rank** (`rank.py`) first drops what cannot be defended, then orders what remains. The
   gate honours Statistics Canada's own quality flags and requires a difference to exceed
   the relevant published standard error. Survivors are scored on magnitude, persistence,
   how identifiable the subgroups are to a reader, whether the finding can be stated in
   units a person feels, and whether it describes a change rather than a level.
6. **Brief and bind** (`brief.py`, `editor.py`) writes the top findings to a fact brief
   along with the Daily article's full text. The editorial pass reads that brief, selects
   findings that cohere, names the assumption each speaks to, and writes prose. The `bind`
   step substitutes the real values and fails the build on an unresolved or misattributed
   token, a bare numeral, a quantity spelled in words, or a claim that the Daily did not
   discuss something the mention map says it did.

### Using Remine on your own release

You need Python 3.11 or later. There are no API keys and no secrets of any kind.

```bash
pip install -r remine/requirements.txt
```

Build the fact briefs for a release, using the Daily's date in `YYMMDD` form:

```bash
python remine/generate.py --date 260807
```

Read the brief it writes into `remine/briefs/`. This is a real checkpoint and not a
formality. If the top findings are dull, repetitive, or mostly restate the Daily, that is
the probe library telling you it needs work, and the answer is to add or adjust a probe
rather than to publish through it.

Draft from the brief, then bind the draft against it:

```bash
python remine/editor.py --brief remine/briefs/260807-dq260807a.json \
  --draft draft.json --out remine/articles/260807-dq260807a.json
```

If `bind` fails, fix the draft rather than the check. A failure is usually telling you
something true: a number was invented, a citation points at the wrong series, or the draft
claimed novelty it had not earned.

### Adding a survey

Remine is configured per cube in `remine/surveys.yaml`. To point it at a release it has not
seen, add an entry keyed by the eight-digit product ID declaring:

- which dimension holds the estimates, and which member is the estimate itself;
- which members are aggregates rather than comparable groups, so the gate can drop
  comparisons that are true by construction;
- which members genuinely partition the population, for each dimension you want compared;
- which measures are rates and which are counts, since comparing counts across groups of
  different sizes measures group size rather than anything else;
- where the standard errors live, if the survey publishes them;
- what to hold the other dimensions at while probing one of them.

The Labour Force Survey entry for cube `14100287` is the worked example.

### Status

The pipeline is built and tested. Publishing is currently gated off in code
(`PUBLISHING_ENABLED` in `remine/editor.py`) while the probe library is tuned; see
`docs/remine-known-limitations.md`, which also records what went wrong in earlier rounds
and why the design looks the way it does. Two packaged skills (`.claude/skills/remine` and
`remine-editorial`) wrap the workflow for anyone using Claude Code in this repo, but the
pipeline runs without them and is meant to.

---

## 3. Ottawa Global Benchmark

A dashboard comparing Ottawa with Austin, Adelaide, and Helsinki on labour, housing, and
tech-sector indicators, with rebased and indexed trend charts and honest notes about what
is and is not comparable across countries. It runs DuckDB-Wasm in the browser against a
Parquet file, so there is no server.

Refresh the data with `python pipeline/extract.py`, which pulls every confirmed cell in
`pipeline/indicators.yaml` from its live source and writes
`public/data/global_cities.parquet`. Series-level detail, exact vector IDs, and
comparability caveats live in that manifest.

Lives at `/benchmark/`.

---

## 4. Ottawa population growth map (planned)

An animated census-tract choropleth of the Ottawa–Gatineau region from 2001 to 2021,
showing where the region densified. Designed in `docs/popmap.md`, not yet built.

---

## Running the site locally

There is no build step. Serve the repository root and open it:

```bash
python -m http.server 8081
```

Tests for Remine run with `python -m pytest remine/tests/` and make no network calls.

## Attribution and licence

Data comes from Statistics Canada, the Federal Reserve Bank of St. Louis (FRED), the
Australian Bureau of Statistics, and Statistics Finland, each reproduced under its own open
licence. Analysis and any conclusions are this project's own and not those of the agencies.
