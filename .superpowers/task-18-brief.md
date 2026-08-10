# Task 18: close the regex hole, and make change findings competitive

Two jobs. The first is small and closes the last known way a wrong claim ships. The second
is the substantive one: the ranking currently surfaces the obvious.

## Background: why job 2 exists

After the age-confound fix, six of the brief's top ten findings say some version of
*people of retirement age work less than prime-age adults* — 53.6 points, 50.5 points, and
so on. True, well-gated, correctly sliced, and something every reader already knows.

The cause is structural. **Magnitude correlates with obviousness**: the largest gaps in
social data are the ones everyone understands, because that is why everyone understands
them. `score()` weights magnitude at 0.40, so it is a machine for surfacing the obvious.

Meanwhile the probes that could challenge an assumption — a gap narrowing when everyone
assumes it is widening, a rank reversal — never reach the top 40, because the magnitude of
a *change* is tiny beside the magnitude of a *level gap*, and magnitude is normalised
globally.

Three fixes below, plus using the standard-error config that was written and never read.

---

## J1 — hyphenated and plural quantity words (Critical, small)

`_QUANTITY_WORDS` in `remine/editor.py` catches bare words, but `one-third`, `twenty-five`,
`thirds` and `millions` bypass it completely. That is ordinary English, so a wrong
quantitative claim can still ship.

Replace the pattern's lookarounds and add plural forms:

```python
_QUANTITY_WORDS = re.compile(
    r"(?<![\w])("
    r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|"
    r"half|halves|third|thirds|quarter|quarters|double|triple|twice|thrice|dozen"
    r")(?:s)?(?![\w])", re.I)
```

Dropping `-` from both lookarounds is the point: `one-third` must now match on both halves.

ADD tests to `remine/tests/test_editor.py`:

```python
def test_hyphenated_quantity_words_fail_the_build():
    for phrase in ("one-third of workers", "a twenty-five point gap", "two-thirds of them"):
        with pytest.raises(BindError, match="quantity word"):
            bind(draft(story={"body": f"The gap covers {phrase}."}), BRIEF)


def test_plural_quantity_words_fail_the_build():
    for phrase in ("millions of workers", "two thirds", "several quarters"):
        with pytest.raises(BindError, match="quantity word"):
            bind(draft(story={"body": f"It affects {phrase}."}), BRIEF)
```

Then set `PUBLISHING_ENABLED = True` in `remine/editor.py` and update the
`test_rebuild_index_is_gated_off` test to assert it is now `True`, renaming it
`test_publishing_is_enabled`. Update the gate message/comment accordingly, and update
`docs/remine-known-limitations.md` to move the quantity-word item from open to closed.

---

## J2a — attach the standard errors that were configured and never read

`surveys.yaml` maps `se_members.month_over_month` and `year_over_year`, and nothing reads
them, so every time-comparison probe runs ungated.

In `remine/probes.py`'s `prepare()`, attach all three SEs as separate columns rather than
one. Keep the existing `SE` column meaning "standard error of the level" so nothing
downstream breaks, and add `SE_MOM` and `SE_YOY` using the same merge approach, each
tolerating an absent member (leave the column NA).

Then add a helper above `run_probes`:

```python
def change_se(rows, periods_apart: int) -> float | None:
    """Standard error appropriate to a change within one series.

    StatCan publishes month-to-month and year-over-year change SEs because the
    two estimates share a sample and are correlated; combining level SEs in
    quadrature overstates the error. Use the published value where the span
    matches, and fall back to the (conservative) quadrature otherwise.
    """
    last = rows.iloc[-1]
    if periods_apart == 1 and pd.notna(last.get("SE_MOM")):
        return float(last["SE_MOM"])
    if periods_apart == 12 and pd.notna(last.get("SE_YOY")):
        return float(last["SE_YOY"])
    first = rows.iloc[0]
    if pd.notna(first.get("SE")) and pd.notna(last.get("SE")):
        return float((float(first["SE"]) ** 2 + float(last["SE"]) ** 2) ** 0.5)
    return None
```

Use it to set `Fact.se` in `streak`, `level_threshold` and `long_run_compare` (each of
which compares two points of one series — pass the actual number of periods between the
endpoints). For `gap_trend`, set `se` to the quadrature of the first and last gap facts'
own `se` values when both are present. Note in your report which probes now carry an SE.

## J2b — normalise magnitude WITHIN a probe, not globally

In `remine/rank.py`, `score()` divides by a single global `max_magnitude`, so a 2-point
trend change is scored against a 53.6-point level gap and can never compete.

Change `rank()` to compute a per-probe maximum and pass that to `score()`:

```python
def rank(facts: list[Fact], mentions: dict[str, bool], cfg: dict) -> list[Fact]:
    mentioned_members = {k.split("|", 1)[1] for k, v in (mentions or {}).items() if v}
    # Normalise within each probe. Globally, the magnitude of a *change* is
    # dwarfed by the magnitude of a *level gap*, so change findings could never
    # reach the brief no matter how striking they were.
    peak: dict[str, float] = {}
    for f in facts:
        peak[f.probe] = max(peak.get(f.probe, 0.0), f.magnitude)
    for f in facts:
        f.mentioned = any(m and m in str(v) for v in f.cut.values() for m in mentioned_members)
        f.score = score(f, cfg, peak.get(f.probe, 0.0))
        if f.mentioned:
            f.score *= float(cfg.get("mention_demotion", 0.5))
    return sorted(facts, key=lambda f: f.score, reverse=True)
```

`score()`'s signature is unchanged; it just receives a per-probe peak.

## J2c — make "prefers change over level" an explicit, tunable policy

Rather than hide an anti-obviousness heuristic in the scoring, state the editorial
preference in config where it can be argued with.

In `remine/rank.py`, add:

```python
# A level gap concretizes what a reader already believes; a change can
# challenge it. Both belong in a brief, but the spec's premise leans on the
# second, and magnitude alone will never surface it.
_CHANGE_PROBES = {"gap_trend", "rank_reversal", "streak", "long_run_compare", "share_of_total"}


def _change_story(fact: Fact) -> float:
    return 1.0 if fact.probe in _CHANGE_PROBES else 0.0
```

Add the term to `score()`:

```python
    return (w["magnitude"] * magnitude
            + w["persistence"] * _persistence(fact)
            + w["legibility"] * fact.legibility
            + w["reader_scale"] * _reader_scale(fact)
            + w.get("change_story", 0.0) * _change_story(fact))
```

In `remine/surveys.yaml`, rebalance `defaults.weights` so the total stays 1.0:

```yaml
  weights:
    magnitude: 0.30
    persistence: 0.20
    legibility: 0.15
    reader_scale: 0.15
    change_story: 0.20
```

Use `w.get(...)` so a config without the key still works.

## Tests for J2

Add to `remine/tests/test_rank.py`:

```python
def test_magnitude_is_normalised_within_a_probe_not_globally():
    big = fact(probe="gap_between_members", magnitude=50.0)
    small = fact(probe="gap_trend", magnitude=2.0)
    ordered = rank([big, small], {}, {**CFG, "weights": {**CFG["weights"], "change_story": 0.0}})
    # Each is the peak of its own probe, so magnitude contributes equally and
    # neither is buried purely for being on a smaller scale.
    assert abs(ordered[0].score - ordered[1].score) < 1e-9


def test_a_change_finding_outranks_an_equally_scaled_level_finding():
    level = fact(probe="gap_between_members", magnitude=10.0)
    change = fact(probe="gap_trend", magnitude=10.0)
    ordered = rank([level, change], {}, CFG)
    assert ordered[0] is change
```

`CFG` in that module must include a `change_story` weight; add it matching surveys.yaml.

Add to `remine/tests/test_probes.py` a test that a `long_run_compare` fact now carries an
`se` when the frame has SE columns, and that `change_se` prefers the published MoM value
over the quadrature when the span is one period.

Existing tests may shift because scores change. Fix expected values by hand, show the
reasoning, and never change what a test asserts about.

---

## Verify

- `python -m pytest remine/tests/ -v` — all pass.
- Regenerate the brief from the committed article fixture and the cached cube (the live
  Daily index times out; use the same script as before, reproduced here):

```bash
python - <<'PY'
import json, time
from pathlib import Path
from remine.discover import parse_article
from remine.cube import parse_meta, load_cube
from remine.mentions import find_mentions, load_config
from remine.probes import prepare, run_probes
from remine.rank import gate, rank
from remine.brief import build_brief, write_brief
t0=time.time()
html = Path("remine/tests/fixtures/dq260807a.html").read_text(encoding="utf-8", errors="replace")
article = parse_article(html, "https://www150.statcan.gc.ca/n1/daily-quotidien/260807/dq260807a-eng.htm")
meta = parse_meta(json.loads(Path("remine/tests/fixtures/cube_meta_14100287.json").read_text(encoding="utf-8")))
cfg = load_config(14100287)
df = load_cube(Path("remine/cache/14100287-202608070830.zip"), 14100287)
prepared = prepare(df, cfg)
dims = [d.name for d in meta.dimensions if d.name not in (cfg.get("filters") or {}) and d.name != cfg.get("value_dimension")]
facts = run_probes(prepared, dims, cfg); print("candidates:", len(facts))
facts = gate(facts, prepared, cfg); print("gated:", len(facts))
mentions = find_mentions(article.prose, meta, cfg.get("synonyms") or {})
brief = build_brief(article, meta, rank(facts, mentions, cfg), mentions, cfg)
print("wrote", write_brief(brief, Path("remine/briefs")), "in", round(time.time()-t0,1),"s")
PY
```

- Print the top 15 with probe, cut, human, score, mentioned; plus the probe mix and how
  many carry a non-null `se`.
- **Then judge it honestly.** Are change findings now present near the top? Is the brief
  still dominated by "retirees work less than prime-age adults"? Would a Canadian reader
  find any of the top five worth reading? Name specific examples. If it is still obvious,
  say so plainly — do not tune weights until it looks better. A truthful negative is the
  useful result.

## Commit

```bash
git add -A remine/ docs/ && git commit -m "feat(remine): gate time comparisons and let change findings compete"
```
