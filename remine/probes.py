"""Stage 4 — deterministic fact generation.

Every number that reaches a published article originates here. The editorial
stage computes nothing; it selects and narrates.

Probes are pure functions registered in PROBES. That registry is the documented
extension point for the later LLM-authored query-spec path: a query spec resolves
to the same Fact shape and flows through identical downstream stages.
"""

from dataclasses import dataclass, field
from itertools import combinations
from typing import Callable

import pandas as pd

from remine.humanize import humanize, humanize_delta, humanize_delta_bare

PROBES: dict[str, Callable] = {}

# StatCan's own reliability verdicts. F = too unreliable to publish,
# x = suppressed for confidentiality, E = use with caution, .. / ... = not
# available or not applicable. The spec's first gate rule is to honour these,
# and the cheapest place to honour them is before any probe can compute on
# them: a suppressed value must never reach a Fact in the first place.
_UNRELIABLE_STATUS = {"F", "x", "E", "..", "..."}

# long_run_compare exists to reach back before the window; everything else is
# making a claim about now.
_FULL_HISTORY_PROBES = {"long_run_compare"}

# Comparing members only makes sense for rates: a gap between two groups' raw
# counts mostly measures how many people are in each group.
_CROSS_MEMBER_PROBES = {"gap_between_members", "gap_trend", "rank_order", "rank_reversal"}
# share_of_total normalises by construction, so it is the one cross-member probe
# that belongs on counts and is meaningless on rates (shares of a rate do not add up).
_SHARE_PROBES = {"share_of_total"}

# A level, or a raw-count change, is dominated by population growth. Only rates
# make these probes say something about the labour market rather than the
# size of the country.
_RATE_ONLY_PROBES = {"long_run_compare", "level_threshold", "streak"}


def probe(name: str):
    def wrap(fn):
        PROBES[name] = fn
        return fn
    return wrap


@dataclass
class Fact:
    probe: str
    cut: dict[str, str]
    values: list[float]
    periods: list[str]
    vectors: list[str]
    uom: str = ""
    scalar: str = ""
    decimals: int = 1
    magnitude: float = 0.0
    se: float | None = None
    legibility: float = 0.5
    mentioned: bool = False
    statement: str = ""
    human: str = ""
    # The same quantity as `human`, with no direction word ("53.6 percentage
    # points" rather than "53.6 percentage points higher"). `human` reads as
    # a whole clause; `bare` is for use mid-sentence, e.g. after "a
    # difference of", where the direction word is ungrammatical.
    bare: str = ""
    score: float = 0.0
    meta: dict = field(default_factory=dict)

    def key(self) -> str:
        cut = ";".join(f"{k}={v}" for k, v in sorted(self.cut.items()))
        return f"{self.probe}::{cut}::{self.periods[-1] if self.periods else ''}"


def prepare(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Apply configured filters, then attach the standard error as a column."""
    if "GEO" in df.columns and "Geography" not in df.columns:
        # StatCan full-table CSVs abbreviate the Geography dimension's header
        # to GEO; every other dimension keeps its WDS dimensionNameEn as-is.
        # Downstream config (legibility, probes) refers to it as "Geography".
        df = df.rename(columns={"GEO": "Geography"})
    # Honour StatCan's own reliability verdicts before anything is computed.
    if "STATUS" in df.columns:
        df = df[~df["STATUS"].fillna("").str.strip().isin(_UNRELIABLE_STATUS)]
    df = df[df["VALUE"].notna()]
    for dim, member in (cfg.get("filters") or {}).items():
        df = df[df[dim] == member]
    vdim = cfg.get("value_dimension")
    if not vdim:
        return df.assign(SE=pd.NA, SE_MOM=pd.NA, SE_YOY=pd.NA)
    se_members = cfg.get("se_members") or {}
    keys = [c for c in df.columns
            if c not in {vdim, "VALUE", "VECTOR", "COORDINATE", "STATUS", "SYMBOL",
                         "TERMINATED", "DECIMALS", "DGUID"}]
    est = df[df[vdim] == cfg["value_member"]].copy()
    for col, cfg_key in (("SE", "level"), ("SE_MOM", "month_over_month"), ("SE_YOY", "year_over_year")):
        se_member = se_members.get(cfg_key)
        if se_member is not None and se_member in set(df[vdim]):
            se = df[df[vdim] == se_member][keys + ["VALUE"]].rename(columns={"VALUE": col})
            est = est.merge(se, on=keys, how="left")
        else:
            est[col] = pd.NA
    return est


def _legibility(dim: str, cfg: dict) -> float:
    return float((cfg.get("legibility") or {}).get(dim, 0.5))


@probe("gap_between_members")
def gap_between_members(df: pd.DataFrame, dim: str, cfg: dict) -> list[Fact]:
    """Persistent difference between two members of one dimension, per period."""
    aggregates = set((cfg.get("aggregate_members") or {}).get(dim, []))
    facts: list[Fact] = []
    for period, chunk in df.groupby("REF_DATE"):
        rows = {r[dim]: r for _, r in chunk.iterrows() if r[dim] not in aggregates}
        for a, b in combinations(sorted(rows), 2):
            ra, rb = rows[a], rows[b]
            hi, lo = (ra, rb) if ra["VALUE"] >= rb["VALUE"] else (rb, ra)
            delta = float(hi["VALUE"] - lo["VALUE"])
            se = None
            if pd.notna(hi.get("SE")) and pd.notna(lo.get("SE")):
                se = float((float(hi["SE"]) ** 2 + float(lo["SE"]) ** 2) ** 0.5)
            fact = Fact(
                probe="gap_between_members",
                cut={f"{dim}_high": str(hi[dim]), f"{dim}_low": str(lo[dim])},
                values=[delta, float(hi["VALUE"]), float(lo["VALUE"])],
                periods=[str(period)],
                vectors=[str(hi["VECTOR"]), str(lo["VECTOR"])],
                uom=str(hi.get("UOM", "")), scalar=str(hi.get("SCALAR_FACTOR", "")),
                decimals=int(hi.get("DECIMALS", 1) or 1),
                magnitude=abs(delta), se=se, legibility=_legibility(dim, cfg),
            )
            fact.statement = (
                f"In {period}, {hi[dim]} exceeded {lo[dim]} by {delta:.1f} "
                f"({fact.uom.lower()})."
            )
            fact.human = humanize_delta(delta, fact.uom, fact.scalar, fact.decimals)
            fact.bare = humanize_delta_bare(delta, fact.uom, fact.scalar, fact.decimals)
            fact.meta = {"high": str(hi[dim]), "low": str(lo[dim]), "dimension": dim}
            facts.append(fact)
    return facts


def _series(df: pd.DataFrame, dim: str, cfg: dict):
    """Yield (member, sorted rows) for non-aggregate members."""
    aggregates = set((cfg.get("aggregate_members") or {}).get(dim, []))
    for member, chunk in df.groupby(dim):
        if member in aggregates:
            continue
        yield str(member), chunk.sort_values("REF_DATE")


def _base(probe_name, dim, member, rows, cfg, values, periods) -> Fact:
    last = rows.iloc[-1]
    return Fact(
        probe=probe_name, cut={dim: member}, values=values, periods=periods,
        vectors=[str(v) for v in rows["VECTOR"].unique()],
        uom=str(last.get("UOM", "")), scalar=str(last.get("SCALAR_FACTOR", "")),
        decimals=int(last.get("DECIMALS", 1) or 1),
        legibility=_legibility(dim, cfg),
    )


@probe("streak")
def streak(df, dim, cfg):
    facts = []
    for member, rows in _series(df, dim, cfg):
        vals = rows["VALUE"].tolist()
        if len(vals) < 2:
            continue
        direction = 1 if vals[-1] >= vals[-2] else -1
        n = 0
        for i in range(len(vals) - 1, 0, -1):
            if (vals[i] - vals[i - 1]) * direction > 0:
                n += 1
            else:
                break
        floor = max(2, int(cfg.get("min_streak_periods", 2)))
        if n < floor:
            continue
        f = _base("streak", dim, member, rows, cfg, [float(n), float(vals[-1])],
                  [str(p) for p in rows["REF_DATE"].tolist()])
        word = "rising" if direction > 0 else "falling"
        f.magnitude = abs(float(vals[-1] - vals[-1 - n]))
        f.se = change_se(rows.iloc[-(n + 1):], n)
        f.statement = f"{member} has been {word} for {n} consecutive periods."
        f.human = f"{member}: {n} periods of {word} in a row, now {humanize(float(vals[-1]), f.uom, f.scalar, f.decimals)}"
        f.bare = f.human
        f.meta = {"direction": word, "periods_in_streak": n}
        facts.append(f)
    return facts


@probe("rank_order")
def rank_order(df, dim, cfg):
    aggregates = set((cfg.get("aggregate_members") or {}).get(dim, []))
    facts = []
    for period, chunk in df.groupby("REF_DATE"):
        chunk = chunk[~chunk[dim].isin(aggregates)].sort_values("VALUE", ascending=False)
        if len(chunk) < 2:
            continue
        top, bottom = chunk.iloc[0], chunk.iloc[-1]
        se = None
        if pd.notna(top.get("SE")) and pd.notna(bottom.get("SE")):
            se = float((float(top["SE"]) ** 2 + float(bottom["SE"]) ** 2) ** 0.5)
        f = Fact(
            probe="rank_order",
            cut={f"{dim}_leader": str(top[dim]), f"{dim}_trailer": str(bottom[dim])},
            values=[float(top["VALUE"]), float(bottom["VALUE"])], periods=[str(period)],
            vectors=[str(top["VECTOR"]), str(bottom["VECTOR"])],
            uom=str(top.get("UOM", "")), scalar=str(top.get("SCALAR_FACTOR", "")),
            decimals=int(top.get("DECIMALS", 1) or 1),
            magnitude=float(top["VALUE"] - bottom["VALUE"]), se=se, legibility=_legibility(dim, cfg),
        )
        f.statement = f"In {period}, {top[dim]} ranked highest and {bottom[dim]} lowest."
        f.human = (f"{top[dim]} highest at {humanize(float(top['VALUE']), f.uom, f.scalar, f.decimals)}; "
                   f"{bottom[dim]} lowest at {humanize(float(bottom['VALUE']), f.uom, f.scalar, f.decimals)}")
        f.bare = f.human
        f.meta = {"leader": str(top[dim]), "trailer": str(bottom[dim])}
        facts.append(f)
    return facts


@probe("rank_reversal")
def rank_reversal(df, dim, cfg):
    """One Fact per unordered pair of members that has ever traded the lead.

    rank_order gives the leader for every period. Walking consecutive periods
    finds each crossing (a change of leader); crossings are then grouped by
    the UNORDERED pair of members involved so that a pair that trades the
    lead repeatedly (A ahead, then B, then A again) reads as one finding
    about that pair's whole history in the window, not one Fact per flip.
    """
    ordered = rank_order(df, dim, cfg)
    ordered.sort(key=lambda f: f.periods[-1])
    crossings = []  # (period, from_leader, to_leader, rank_order fact at crossing)
    for prev, cur in zip(ordered, ordered[1:]):
        if prev.meta["leader"] == cur.meta["leader"]:
            continue
        crossings.append((cur.periods[-1], prev.meta["leader"], cur.meta["leader"], cur))

    by_pair: dict[tuple[str, str], list] = {}
    for c in crossings:
        pair = tuple(sorted((c[1], c[2])))
        by_pair.setdefault(pair, []).append(c)

    facts = []
    for pair, pair_crossings in by_pair.items():
        pair_crossings.sort(key=lambda c: c[0])
        first_period = pair_crossings[0][0]
        last_period, _from_leader, current_leader, latest = pair_crossings[-1]
        other_member = pair[0] if pair[1] == current_leader else pair[1]
        n = len(pair_crossings)
        f = Fact(
            probe="rank_reversal",
            cut={f"{dim}_leader": str(current_leader), f"{dim}_overtook": str(other_member)},
            values=[float(n), latest.values[0], latest.values[1]],
            periods=[first_period, last_period],
            vectors=latest.vectors, uom=latest.uom, scalar=latest.scalar,
            decimals=latest.decimals, magnitude=latest.magnitude, legibility=latest.legibility,
        )
        times = "once" if n == 1 else f"{n} times"
        f.statement = (
            f"{current_leader} and {other_member} have traded the lead {times} "
            f"since {first_period}; {current_leader} leads now, as of {last_period}."
        )
        f.human = (
            f"{current_leader} and {other_member} have traded the lead {times} "
            f"since {first_period}; {current_leader} leads now"
        )
        f.bare = f.human
        f.meta = {"crossings": n, "leader": current_leader, "other": other_member,
                   "periods_observed": n}
        facts.append(f)
    return facts


@probe("gap_trend")
def gap_trend(df, dim, cfg):
    gaps = gap_between_members(df, dim, cfg)
    # Key on the UNORDERED pair. gap_between_members labels high/low per
    # period, so keying on "high|low" would change the key the moment the lead
    # swaps, splitting one trend into two single-entry groups that both fail
    # the len < 2 guard below — silently dropping the trend entirely. A lead
    # swap is the more newsworthy case, so that failure mode is backwards.
    by_pair: dict[tuple[str, str], list[Fact]] = {}
    for g in gaps:
        by_pair.setdefault(tuple(sorted((g.meta["high"], g.meta["low"]))), []).append(g)
    facts = []
    for _pair, series in by_pair.items():
        series.sort(key=lambda f: f.periods[-1])
        if len(series) < 2:
            continue
        change = float(series[-1].values[0] - series[0].values[0])
        if change == 0:
            continue
        hi, lo = series[-1].meta["high"], series[-1].meta["low"]
        lead_changed = any(g.meta["high"] != hi for g in series)
        f = Fact(
            probe="gap_trend", cut={f"{dim}_high": hi, f"{dim}_low": lo}, values=[change],
            periods=[series[0].periods[-1], series[-1].periods[-1]],
            vectors=series[-1].vectors, uom=series[-1].uom, scalar=series[-1].scalar,
            decimals=series[-1].decimals, magnitude=abs(change),
            legibility=series[-1].legibility,
        )
        if series[0].se is not None and series[-1].se is not None:
            f.se = float((series[0].se ** 2 + series[-1].se ** 2) ** 0.5)
        direction = "widening" if change > 0 else "narrowing"
        swap = f" {lo} led at the start of this period and {hi} leads now." if lead_changed else ""
        f.statement = (f"The gap between {hi} and {lo} has been {direction} "
                       f"since {series[0].periods[-1]}.{swap}")
        f.human = f"gap between {hi} and {lo} is {direction}: {humanize_delta(change, f.uom, f.scalar, f.decimals)}"
        f.bare = f"gap between {hi} and {lo} {direction} by {humanize_delta_bare(change, f.uom, f.scalar, f.decimals)}"
        f.meta = {"direction": direction, "high": hi, "low": lo, "lead_changed": lead_changed}
        facts.append(f)
    return facts


@probe("share_of_total")
def share_of_total(df, dim, cfg):
    """Change in a member's share of the total, first period to last.

    A share's LEVEL is almost always a population artifact: Ontario is ~39%
    of national employment every month for decades, regardless of what the
    labour market is doing. The CHANGE in that share over the window is the
    part that can actually be news.
    """
    aggregates = set((cfg.get("aggregate_members") or {}).get(dim, []))
    mdim = cfg.get("measure_dimension")
    measure_label = ""
    if mdim and mdim in df.columns and df[mdim].nunique() == 1:
        measure_label = f" of {df[mdim].iloc[0].lower()}"

    def shares(period):
        chunk = df[df["REF_DATE"] == period]
        chunk = chunk[~chunk[dim].isin(aggregates)]
        total = float(chunk["VALUE"].sum())
        if total == 0 or len(chunk) < 2:
            return None
        return {str(row[dim]): (float(row["VALUE"]) / total * 100, row)
                for _, row in chunk.iterrows()}

    periods = sorted(df["REF_DATE"].unique())
    if len(periods) < 2:
        return []
    first, last = periods[0], periods[-1]
    then, now = shares(first), shares(last)
    if not then or not now:
        return []
    facts = []
    for member in sorted(set(then) & set(now)):
        share_then, _ = then[member]
        share_now, row = now[member]
        change = share_now - share_then
        if round(change, 1) == 0.0:
            continue
        direction = "rose" if change > 0 else "fell"
        f = Fact(
            probe="share_of_total", cut={dim: member},
            values=[change, share_now, share_then], periods=[str(first), str(last)],
            vectors=[str(row["VECTOR"])], uom=str(row.get("UOM", "")),
            scalar=str(row.get("SCALAR_FACTOR", "")),
            decimals=int(row.get("DECIMALS", 1) or 1),
            magnitude=abs(change), legibility=_legibility(dim, cfg),
        )
        f.statement = (
            f"Between {first} and {last}, {member}'s share{measure_label} "
            f"{direction} {abs(change):.1f} points, from {share_then:.1f}% to {share_now:.1f}%."
        )
        f.human = f"{member}'s share{measure_label} {direction} {abs(change):.1f} points, from {share_then:.1f}% to {share_now:.1f}%"
        f.bare = f.human
        f.meta = {"share_now": share_now, "share_then": share_then, "direction": direction}
        facts.append(f)
    return facts


@probe("level_threshold")
def level_threshold(df, dim, cfg):
    facts = []
    for member, rows in _series(df, dim, cfg):
        vals = rows["VALUE"].tolist()
        if len(vals) < 2:
            continue
        prev, cur = float(vals[-2]), float(vals[-1])
        step = 10 ** max(0, len(str(int(abs(cur) or 1))) - 1)
        crossed = [t for t in (int(min(prev, cur) / step) * step + step,)
                   if min(prev, cur) < t <= max(prev, cur)]
        if not crossed:
            continue
        f = _base("level_threshold", dim, member, rows, cfg, [cur, float(crossed[0])],
                  [str(rows["REF_DATE"].iloc[-2]), str(rows["REF_DATE"].iloc[-1])])
        word = "above" if cur > prev else "below"
        f.magnitude = abs(cur - prev)
        f.se = change_se(rows.iloc[-2:], 1)
        f.statement = f"{member} moved {word} {crossed[0]:g} in {f.periods[-1]}."
        f.human = f"{member} crossed {humanize(float(crossed[0]), f.uom, f.scalar, 0)}"
        f.bare = f.human
        f.meta = {"threshold": crossed[0], "direction": word}
        facts.append(f)
    return facts


@probe("long_run_compare")
def long_run_compare(df, dim, cfg):
    facts = []
    for member, rows in _series(df, dim, cfg):
        vals = rows["VALUE"].tolist()
        if len(vals) < 2:
            continue
        first, last = float(vals[0]), float(vals[-1])
        change = last - first
        if change == 0:
            continue
        f = _base("long_run_compare", dim, member, rows, cfg, [change, first, last],
                  [str(rows["REF_DATE"].iloc[0]), str(rows["REF_DATE"].iloc[-1])])
        f.magnitude = abs(change)
        f.se = change_se(rows, len(rows) - 1)
        f.statement = (f"{member} changed by {change:.1f} between "
                       f"{f.periods[0]} and {f.periods[-1]}.")
        f.human = f"{member}: {humanize_delta(change, f.uom, f.scalar, f.decimals)} than in {f.periods[0]}"
        f.bare = humanize_delta_bare(change, f.uom, f.scalar, f.decimals)
        f.meta = {"from_period": f.periods[0], "to_period": f.periods[-1]}
        facts.append(f)
    return facts


def slice_frame(df: pd.DataFrame, cfg: dict, measure, probe_dim: str) -> pd.DataFrame:
    """Reduce the frame to one row per (period, member of probe_dim).

    Every dimension other than probe_dim is pinned to a single member, so a
    comparison across probe_dim is like-for-like. Without this the probes
    silently compare unrelated series that happen to share a key.
    """
    out = df
    mdim = cfg.get("measure_dimension")
    if mdim and measure is not None and mdim in out.columns:
        out = out[out[mdim] == measure]
    for dim, member in (cfg.get("hold_at") or {}).items():
        if dim == probe_dim or dim not in out.columns:
            continue
        out = out[out[dim] == member]
    return out


def window(df: pd.DataFrame, cfg: dict, probe_name: str) -> pd.DataFrame:
    """Limit most probes to a recent window; long-run comparison sees everything."""
    n = int(cfg.get("window_periods") or 0)
    if not n or probe_name in _FULL_HISTORY_PROBES:
        return df
    keep = sorted(df["REF_DATE"].unique())[-n:]
    return df[df["REF_DATE"].isin(keep)]


def partition(df: pd.DataFrame, dim: str, cfg: dict) -> pd.DataFrame:
    """Keep only members that genuinely partition the population.

    StatCan dimensions nest by design (15+, 15-24, 15-19 ...). Comparing a
    fifty-year band against a five-year one produces an arithmetic artifact,
    not a finding.
    """
    members = (cfg.get("comparable_members") or {}).get(dim)
    return df[df[dim].isin(members)] if members else df


def dedupe(facts: list[Fact]) -> list[Fact]:
    """Collapse one finding repeated across periods into a single fact.

    A per-period probe emits the same finding once per month, so sixty
    near-identical rows crowd out every other finding. Keep the most recent and
    record how many periods it held, which is what the ranker actually wants.
    """
    best: dict[tuple, Fact] = {}
    for f in sorted(facts, key=lambda f: f.periods[-1]):
        key = (f.probe, tuple(sorted(f.cut.items())))
        prior = best.get(key)
        f.meta["periods_observed"] = (prior.meta.get("periods_observed", 1) + 1) if prior else 1
        best[key] = f
    return list(best.values())


# gap_between_members and rank_order can both describe the exact same
# comparison (same vectors, same measure, same period) — one from each probe.
# `dedupe` above keys on (probe, cut), so the two spellings never collapse,
# and the withdrawn brief's fact_1/fact_2 were exactly this: the same finding
# under two names, which read like debug output once drafted. Scores are not
# set at this point in the pipeline, so break ties with a configured probe
# preference order rather than a score comparison.
_PROBE_PREFERENCE = ["gap_between_members", "rank_order"]


def dedupe_probe_overlap(facts: list[Fact], measure_dimension: str | None) -> list[Fact]:
    """Collapse the same comparison reported by more than one cross-member probe."""
    def rank(f: Fact) -> int:
        try:
            return _PROBE_PREFERENCE.index(f.probe)
        except ValueError:
            return len(_PROBE_PREFERENCE)

    best: dict[tuple, Fact] = {}
    for f in facts:
        if f.probe not in _PROBE_PREFERENCE:
            continue
        key = (tuple(sorted(f.vectors)), f.cut.get(measure_dimension) if measure_dimension else None,
               f.periods[-1] if f.periods else None)
        prior = best.get(key)
        if prior is None or rank(f) < rank(prior):
            best[key] = f
    kept_ids = {id(f) for f in best.values()}
    dropped = {id(f) for f in facts if f.probe in _PROBE_PREFERENCE} - kept_ids
    return [f for f in facts if id(f) not in dropped]


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


def run_probes(df: pd.DataFrame, dimensions: list[str], cfg: dict) -> list[Fact]:
    mdim = cfg.get("measure_dimension")
    measures = list(cfg.get("measures") or [None])
    aggregates = {n for names in (cfg.get("aggregate_members") or {}).values() for n in names}
    clash = {m for m in measures if m in aggregates}
    if clash:
        raise ValueError(
            f"measures {sorted(clash)} are also listed as aggregate_members; the gate "
            f"would drop every fact about them — fix surveys.yaml")

    hold = cfg.get("hold_at") or {}
    probe_dims = [d for d in dimensions if d in hold] or list(dimensions)
    facts: list[Fact] = []
    for measure in measures:
        for dim in probe_dims:
            sliced = slice_frame(df, cfg, measure, dim)
            if dim not in sliced.columns or sliced[dim].nunique() < 2:
                continue
            dupes = sliced.groupby(["REF_DATE", dim]).size().max()
            if dupes and dupes > 1:
                raise ValueError(
                    f"slice for measure={measure!r} dim={dim!r} still has {dupes} rows "
                    f"per (period, member); probes would compare unrelated series")
            for name, fn in PROBES.items():
                rates = set(cfg.get("rate_measures") or [])
                counts = set(cfg.get("count_measures") or [])
                if name in _CROSS_MEMBER_PROBES and rates and measure not in rates:
                    continue
                if name in _SHARE_PROBES and counts and measure not in counts:
                    continue
                if name in _RATE_ONLY_PROBES and rates and measure not in rates:
                    continue
                primary = cfg.get("primary_count_measure")
                if (name in _SHARE_PROBES and primary and measure in counts
                        and measure != primary):
                    continue
                frame = partition(window(sliced, cfg, name), dim, cfg)
                if frame[dim].nunique() < 2:
                    continue
                try:
                    produced = fn(frame, dim, cfg)
                except Exception as exc:   # a broken probe must not sink the run
                    print(f"  probe {name} failed on {dim} ({measure}): {exc}")
                    continue
                for f in produced:
                    f.meta["measure"] = measure
                    if mdim and measure is not None:
                        f.cut = {**f.cut, mdim: measure}
                    facts.append(f)
    return dedupe_probe_overlap(dedupe(facts), mdim)
