# Remine

Statistics Canada publishes far more data than it describes. A Daily article reports the
headline number and a few subgroups, then links to a table holding thousands of series that
nobody writes about. The table cited by the July 2026 Labour Force Survey release holds roughly
8,000 series (11 geographies, 9 labour force characteristics, 3 genders, 9 age groups, 3 data
types). The article narrates about a dozen of them.

Remine reads a Daily release, computes what the same table supports saying, and drafts the
articles that were left out. The data has already been mined once, by the people who released
it. Remine goes back through the same material for value that was not extracted the first time.

## What counts as a finding

A finding is worth publishing when it concretizes a widely held assumption or challenges one.

This is deliberately not anomaly detection. Anomaly hunting surfaces the volatile and the odd,
which is frequently just noise, and it misses the confirming half of the goal entirely. A large,
stable, unsurprising gap is a strong story precisely because it is solid. Remine's ranking
therefore treats persistence as a point in a finding's favour rather than against it.

## How it works

Six stages. The first five are deterministic Python. The sixth is where a person does the
editorial work, with a model assisting under supervision.

1. **Discover** scrapes The Daily's index for a given date, collects that day's articles, and
   extracts the product IDs of the tables each one cites. (The Daily has no working RSS feed as
   of August 2026, so the index page is scraped instead.)
2. **Mentions** checks which of the table's dimension members the article names in its prose
   (e.g. "Alberta", "15 to 24 years"). This produces a ranking demotion, not a filter. Nothing
   is ever dropped on this signal.
3. **Cube** fetches the table's metadata and its full data download from Statistics Canada's WDS
   API, caching by release time so repeat runs against an unchanged release cost nothing.
   Per-series fetching is not practical at this scale, so the bulk CSV is the access path.
4. **Probes** enumerate findings across the table: persistent gaps between subgroups, gaps
   widening or narrowing, threshold crossings, streaks, rank order and reversals, shares of a
   total, and long-run comparisons. Every number that will ever appear in a published article is
   computed here and nowhere else.
5. **Rank** first drops what cannot be defended, then orders what remains. The reliability gate
   honours Statistics Canada's own quality flags, and for surveys that publish standard errors
   it requires a reported difference to exceed the relevant one. Survivors are scored on
   magnitude, persistence, how legible the subgroups are to a reader, and whether the finding
   can be stated in units a person feels.
6. **Brief and bind** writes the top findings to a fact brief, along with the Daily article's
   full text. The editorial pass reads that brief, selects the findings that cohere into a
   piece, names the assumption each one speaks to, and writes the prose. A final `bind` step
   substitutes the real numbers and refuses to build if anything is wrong.

## The number contract

Every number in a published Remine article comes from stage 4, not from a language model. The
drafting step never writes a numeral. It writes tokens (`{{fact_3.human}}`), and `editor.py`
substitutes the computed values.

Three checks enforce this, and all three live in Python rather than in instructions to a model:

- An unresolved or unknown token fails the build, so a reference to a fact that does not exist
  cannot ship.
- A bare numeral in the prose fails the build, with an allowlist for years and ordinals. Without
  this, the token contract could be sidestepped by simply typing a number.
- Each finding must declare what the Daily said about that cut, or state `not discussed`. A
  `not discussed` claim is cross-checked against the mention map from stage 2, so a draft that
  did not genuinely engage with the source article gets caught.

Published articles carry the vector IDs and reference periods behind each claim, so a reader can
check any number against the source table.

## Using it

You need Python 3.11 or later and the dependencies in `requirements.txt` (`pandas`, `pyyaml`,
`requests`). There are no API keys to configure, and no secrets of any kind.

```bash
pip install -r requirements.txt
```

Build the fact briefs for a release, using the Daily's date in `YYMMDD` form:

```bash
python remine/generate.py --date 260807
```

Read the brief it writes to `remine/briefs/`. This is a real checkpoint rather than a formality.
If the top findings are dull or mostly restate the Daily, that is the probe library telling you
it needs work, and the response is to adjust the weights in `surveys.yaml` or add a probe.
Publishing from a weak brief produces a weak article.

Draft from the brief, then bind the draft against it:

```bash
python remine/editor.py --brief remine/briefs/260807-dq260807a.json \
  --draft draft.json --out articles/260807-dq260807a.json
```

If `bind` fails, fix the draft rather than the check. A failure is usually telling you something
true: a number was invented, or the draft claimed novelty it had not earned.

Two packaged skills wrap this loop for anyone working in the repo with Claude Code. `/remine
260807` runs the whole sequence, and `remine-editorial` handles the writing pass alone, which is
what you want when redrafting an article without regenerating its brief. The pipeline runs
perfectly well without either of them, and it is meant to: the guarantees live in the Python, so
the scripts have to stand on their own.

Adding a survey means adding an entry to `surveys.yaml`: which dimension holds the estimates,
which members are aggregates rather than comparable groups, where the standard errors live, and
how legible each dimension is to a reader.

## Status

In development. Stages 1 and 3 (discovery and cube access) are implemented and tested. The probe
library, ranking, brief assembly, and the binding step are specified but not yet built, so the
usage instructions above describe the intended interface rather than working commands. The design
document and the implementation plan are in `docs/`.

## Attribution

Data comes from Statistics Canada and is reproduced under the Statistics Canada Open Licence.
The analysis is not Statistics Canada's, and neither is any conclusion drawn here. This project
is independent and is not affiliated with or endorsed by Statistics Canada. Official data lives
at [statcan.gc.ca](https://www.statcan.gc.ca/).
