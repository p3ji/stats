# Remine: known limitations

**Publishing status (2026-08-09): open.** `PUBLISHING_ENABLED` in `remine/editor.py` is
`True`. It was opened once both of the gate's conditions were met: the quantity-word guard
covers hyphenated compounds and plurals, a superlative guard was added, and a person read a
bound article end to end as the site renders it. Re-gate it if the pipeline changes in a way
a reader has not seen. Every serious error this project has produced was caught by a reader
rather than by a test: a ratio spelled in words, a provincial comparison that was
three-quarters age structure, and a participation rate labelled "women" when the population
was core-aged women.

Remine re-mines Statistics Canada Daily releases into short fact briefs and, from
those, published articles — every number computed from source data, never written
by a model. This note is the findings ledger from building it, moved out of a
gitignored scratch directory so it survives. It exists to gate publishing: the
open items below must close before `remine/editor.py --rebuild-index` is allowed
to put anything on the public feed (see `PUBLISHING_ENABLED` in that file).

Design spec: `docs/superpowers/specs/2026-08-07-remine-design.md`
Implementation plan: `docs/superpowers/plans/2026-08-08-remine.md`

## Open limitations

These must be closed before unattended publishing.

**The guard's false-positive rate is a deliberate trade, not a bug.** A phrase like
"one of the ten provinces" fails the build, even though it is not a quantitative
claim about the data. That's intentional: the drafter rewrites the sentence, and
no unverified quantitative claim ships. Cheaper to over-reject than to let one
through.

**`dedupe_probe_overlap` can still let a duplicate through.** It collapses two
probes describing the same comparison, but a pair whose *latest period* differs
can both survive the dedupe pass even though they describe the same underlying
comparison.

**`load_config`'s merge is shallow.** It uses a plain `dict.update`, so a future
cube that supplies only part of a nested block (e.g. `weights`) would silently
clobber the rest of that block's defaults rather than merging into it. Not a
problem with one survey configured; will be the moment a second one is added —
fix before then.

**The reliability gate doesn't cover every probe type.** It applies to
`gap_between_members` and `rank_order`, both of which compute a standard error.
The time-comparison probes — `gap_trend`, `long_run_compare`, `streak`,
`level_threshold`, `share_of_total` — leave `se` unset and fall back to the
configured `min_magnitude` floor instead. `se_members.month_over_month` and
`year_over_year` are configured in anticipation of this but not yet read by
anything.

## Closed limitations

**The quantity-word guard had gaps a native speaker would walk straight through.**
`_QUANTITY_WORDS` in `remine/editor.py` caught bare words like "double", "twice",
"half", "one", "five" — but hyphenated compounds ("one-third", "twenty-five") and
plurals ("thirds", "millions") bypassed it entirely. Closed by dropping `-` from
both lookarounds (so either half of a hyphenated compound matches) and adding an
optional plural suffix, with regression tests
(`test_hyphenated_quantity_words_fail_the_build`,
`test_plural_quantity_words_fail_the_build`). `PUBLISHING_ENABLED` is now `True`.

## Lessons that shaped the design

**1. Guard the concept, not the encoding.** Four rounds of hardening sealed off
every path a *digit* could take into published prose. The first article shipped
anyway — with a wrong ratio spelled out in English ("nearly double" for what was
actually 2.52x). A number in words is still a number; the guard had to move up a
level of abstraction to catch it.

**2. A fixture simple enough to hand-verify is simple enough to hide the bug that
only shows up at real shape.** `mini_cube.zip` varied on one dimension while the
real cube varies on six. All 85 tests against it passed — over probes that were,
it turned out, comparing unrelated series to each other. Simplicity in a test
fixture can quietly delete the exact complexity the code under test exists to
handle.

**3. When a check fires, confirm why before satisfying it.** `bind`'s "not
discussed" rejections looked like false positives at first — reworded the
sentence, they passed. They weren't false positives: the underlying scrape was
picking up a `<select>` dropdown's HTML as if it were article prose. Rewording to
make the check stop complaining would have silently retired a working auditor
instead of fixing the scrape.

**4. A level and a rate are different kinds of fact.** A level of a count (e.g.
"142,000 people") is a fact about population size. A rate or a change (e.g. "up
3.2%") is a fact about the economy. Every early artifact that read as
misleading traced back to this distinction getting blurred somewhere in the
pipeline.

**5. Holding dimensions fixed controls confounds within a dimension, not across
dimensions.** Comparing provincial employment rates on the standard 15+
denominator gave a 13.0-point gap between Alberta and Newfoundland. The same
comparison on the 25-54 prime-age band — controlling for the age structure of
each province's population — gave 3.4 points. Roughly three-quarters of the
original gap was age structure, not anything about the labour market. Fixing one
dimension (geography, in this case) says nothing about confounds riding on a
different dimension (age) unless that one is fixed too.
