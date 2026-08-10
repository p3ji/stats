# Task 18 report: close the regex hole, let change findings compete

## J1 — quantity-word guard

`_QUANTITY_WORDS` in `remine/editor.py` now drops `-` from both lookarounds and
adds an optional plural suffix, exactly as specified. `one-third`, `twenty-five`,
`thirds`, `millions` all now match. `PUBLISHING_ENABLED` is set to `True`.
Added `test_hyphenated_quantity_words_fail_the_build` and
`test_plural_quantity_words_fail_the_build`; renamed
`test_rebuild_index_is_gated_off` to `test_publishing_is_enabled` asserting
`True`. `docs/remine-known-limitations.md` moved the quantity-word item from
Open to a new Closed section.

## J2a — standard errors

`prepare()` in `remine/probes.py` now attaches `SE`, `SE_MOM`, `SE_YOY` as
three independent left-merges, each tolerating an absent `se_members` entry
(column stays `NA`). Added `change_se(rows, periods_apart)` exactly as
specified (published MoM/YoY SE preferred, quadrature of level SE as
fallback). Wired into:
- `streak` — `change_se(rows.iloc[-(n+1):], n)`, span = length of the streak.
- `level_threshold` — `change_se(rows.iloc[-2:], 1)`.
- `long_run_compare` — `change_se(rows, len(rows) - 1)`, full series span.
- `gap_trend` — quadrature of `series[0].se` and `series[-1].se` (the two
  endpoint `gap_between_members` facts' own SEs), only when both are present.

`rank_reversal` and `share_of_total` were **not** given an `se` — the brief
didn't ask for it, and `rank_reversal` derives from `rank_order` facts whose
own `se` isn't threaded through `_meta`-only comparisons the way a paired
series is.

**SE coverage, before vs after** (on the regenerated brief, 40 facts):
- Before this task: only `gap_between_members` and `rank_order` ever carried
  a non-null `se` (per the brief's own framing).
- After: `gap_between_members` 2/2, `rank_order` 2/2 (unchanged, as before),
  plus `streak` 6/6 and `gap_trend` 16/16 now carry one. `long_run_compare`
  is 0/4 in this particular brief — the cube's SE series for Participation
  rate / Employment rate (Women+) doesn't reach back to 1976, so both the
  MoM/YoY and quadrature fallbacks come up `NA` for that span; the code path
  is exercised and tested (`test_long_run_compare_carries_an_se_when_the_frame_has_se_columns`
  passes against the mini fixture, which does have full SE coverage).
  `rank_reversal` (0/8) and `share_of_total` (0/2) were left out of scope, as
  above. Total: 26/40 facts in this brief now carry a non-null `se`, up from
  4/40 before (the 2 `gap_between_members` + 2 `rank_order` facts that
  survived to the top 40).

## J2b/J2c — per-probe normalisation and the change_story term

`rank()` now computes `peak[probe] = max magnitude within that probe` and
passes it to `score()` instead of a single global max. `score()` gained
`w.get("change_story", 0.0) * _change_story(fact)`, with `_CHANGE_PROBES =
{gap_trend, rank_reversal, streak, long_run_compare, share_of_total}` scoring
1.0 and everything else 0.0. `surveys.yaml` defaults rebalanced to
`magnitude 0.30, persistence 0.20, legibility 0.15, reader_scale 0.15,
change_story 0.20` (sums to 1.0), transcribed verbatim from the brief. No
other weight tuning was done.

## Tests

Added the two `test_rank.py` cases and two `test_probes.py` cases specified
in the brief, plus `test_long_run_compare_carries_an_se_when_the_frame_has_se_columns`
to satisfy "a test that a long_run_compare fact now carries an se". One
pre-existing test shifted: `test_load_config_for_unknown_cube_returns_defaults`
asserted `weights.magnitude == 0.40`; changed to `0.30` with a comment
pointing at the Task 18 rebalance — the test's intent (defaults load
correctly) is unchanged, only the value moved. `CFG` in `test_rank.py` gained
`change_story: 0.20` to match `surveys.yaml`.

`python -m pytest remine/tests/ -v` → **117 passed** (was 110 before J1's two
new tests + J2's four new tests = 116; +1 more from the long_run_compare SE
test = 117).

## Brief regeneration

Ran the verbatim script against the cached cube and the committed article
fixture. `candidates: 513`, `gated: 278`, brief written with 40 facts
(`top_n: 40`) in 52.4s.

Probe mix across all 40 facts in the brief: `rank_reversal` 8, `streak` 6,
`share_of_total` 2, `gap_trend` 16, `long_run_compare` 4, `rank_order` 2,
`gap_between_members` 2. Every single one of the 40 facts has `mentioned:
True` — the Daily's own prose names essentially every province and age
band this cube covers, so the 0.5x mention-demotion is applied uniformly and
doesn't change relative ordering within the brief.

### Top 15 (probe, cut, human, score)

1. `rank_reversal` — Geography Quebec vs Saskatchewan (Employment rate) — "Quebec moved ahead of Saskatchewan in 2025-09" — 0.4417
2. `rank_reversal` — Geography Saskatchewan vs Quebec (Employment rate) — "Saskatchewan moved ahead of Quebec in 2025-08" — 0.4296
3. `streak` — Age group 15 to 24 years (Unemployment rate) — "15 to 24 years: 3 periods of falling in a row, now 12.6%" — 0.4175
4. `streak` — Geography Quebec (Employment rate) — "Quebec: 3 periods of rising in a row, now 86.0%" — 0.4162
5. `streak` — Geography Manitoba (Employment rate) — "Manitoba: 3 periods of rising in a row, now 85.8%" — 0.4074
6. `share_of_total` — Age group 25 to 54 years (Employment) — "25 to 54 years's share of employment rose 1.6 points, from 64.9% to 66.6%" — 0.4008
7. `gap_trend` — Age group 25-54 vs 15-24 (Employment rate) — "gap between 25 to 54 years and 15 to 24 years is widening: 3.8 percentage points higher" — 0.4008
8. `long_run_compare` — Gender Women+ (Participation rate) — "Women+: 33.8 percentage points higher than in 1976-01" — 0.4008
9. `streak` — Age group 15 to 24 years (Employment rate) — "15 to 24 years: 3 periods of rising in a row, now 55.4%" — 0.3999
10. `long_run_compare` — Gender Women+ (Employment rate) — "Women+: 33.0 percentage points higher than in 1976-01" — 0.3973
11. `rank_reversal` — Geography PEI vs Quebec (Participation rate) — "Prince Edward Island moved ahead of Quebec in 2026-01" — 0.3946
12. `rank_order` — Age group 15-24 vs 25-54 (Unemployment rate) — "15 to 24 years highest at 10.5%; 25 to 54 years lowest at 4.6%" — 0.3925
13. `gap_between_members` — Age group 25-54 vs 55+ (Participation rate) — "53.6 percentage points higher" — 0.3925
14. `rank_order` — Geography Quebec vs Newfoundland and Labrador (Employment rate) — "Quebec highest at 85.6%; Newfoundland and Labrador lowest at 80.1%" — 0.3898
15. `streak` — Geography Quebec (Unemployment rate) — "Quebec: 3 periods of falling in a row, now 4.7%" — 0.3897

## Honest assessment

**Are change-based findings now present in the top 15? Yes, decisively.**
12 of the top 15 are `rank_reversal`, `streak`, `share_of_total`,
`gap_trend`, or `long_run_compare`. Only #13 (`gap_between_members`, the
retirement-age participation gap) is a pure level gap in the top 15, and it
sits at #13, not #1. The rebalance worked as intended — it did not fail to
move change findings.

**Is the brief still dominated by age-band gaps?** No, not by *level* gaps.
The previous failure mode — six of the top ten being some version of "older
people work less than prime-age adults" — is gone from the top 15 entirely
in that specific form. But age bands still show up constantly, just recast
as *changes*: #3 and #9 are both about the 15–24 age group (unemployment
falling, employment rising), #6 is the 25–54 share of employment rising,
#7 is the 25–54-vs-15–24 rate gap widening, #12 is the same pair as a rank.
So the age dimension hasn't been displaced — it's still the dominant *axis*
of the brief — but the *shape* of the claim is now mostly "this is moving,"
not "this level is what everyone already knows."

**Would a Canadian reader find any of the top five worth reading?**
Partially. My honest read, fact by fact:
- #1/#2, `rank_reversal` Quebec vs Saskatchewan (Employment rate), "Quebec
  moved ahead of Saskatchewan in 2025-09" / "...in 2025-08": these two are
  the same underlying flip reported from both directions one period apart —
  Quebec overtook Saskatchewan, then (per #2) Saskatchewan had overtaken
  Quebec the month before that. Read together this is a genuinely
  interesting, non-obvious story (two provinces trading the employment-rate
  lead within a couple of months), but as two separate top-2 facts it reads
  as noise/duplication rather than one clean finding — I would use it, but
  only after collapsing the pair into a single "Quebec and Saskatchewan
  traded the provincial employment-rate lead twice in three months" claim,
  which the current dedupe logic doesn't do (it dedupes same-pair-same-cut,
  not adjacent reversals in the same pair).
- #3, `streak` "15 to 24 years: 3 periods of falling in a row, now 12.6%"
  (unemployment rate): mildly interesting — youth unemployment falling for
  three straight months is a real, checkable claim, though "3 periods" is a
  thin streak and by itself isn't much of a story.
- #4/#5, `streak` Quebec and Manitoba employment rates rising 3 periods in a
  row: same as above — plausible filler for a "labour market ticking up in
  several provinces" paragraph, not a standalone lead.
- #6, `share_of_total`, 25–54 share of employment rising 1.6 points: this is
  the most publishable fact in the top 15 on its own — it's a real
  compositional shift (prime-age workers taking a larger share of total
  employment) that isn't just restating the retirement-gap level, and a
  reader who assumes the workforce's age composition is static would learn
  something.
- Of the top five, I would put **#6** in an article as-is, and **#1+#2
  combined** (as one rank-reversal-over-time claim) as a secondary story.
  #3, #4, #5 are streak facts I'd treat as supporting colour, not headline
  material — three-month streaks in employment/unemployment rates are
  common statistical noise dressed as a trend, and none of them challenges
  a specific assumption the way the brief's stated goal (job 2's premise)
  calls for.

**Net verdict:** the structural fix worked exactly as designed — change
findings now dominate the top of the brief and the six-in-a-row "retirees
work less" pileup is gone. But the result is not yet "a set of genuinely
surprising findings." Most of the top 15 are still short, unremarkable
month-over-month movements (3-period streaks) rather than findings that
challenge a specific reader assumption; the two facts I'd actually put in an
article (#6, and #1/#2 once merged) are good, but they're 2 of 15, not a
brief that's uniformly worth reading top to bottom. That is a genuine
finding about probe design and dedupe — `rank_reversal` on the same pair one
period apart should probably collapse into one "traded the lead N times"
fact, and streak's `min` length of 2 makes very short streaks compete on
equal footing with longer, more meaningful ones — not something to fix by
retuning `change_story` or `magnitude` weights.

## Commit

```
git add -A remine/ docs/ && git commit -m "feat(remine): gate time comparisons and let change findings compete"
```
