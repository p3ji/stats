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

from remine.humanize import humanize, humanize_delta

PROBES: dict[str, Callable] = {}

# StatCan's own reliability verdicts. F = too unreliable to publish,
# x = suppressed for confidentiality, E = use with caution, .. / ... = not
# available or not applicable. The spec's first gate rule is to honour these,
# and the cheapest place to honour them is before any probe can compute on
# them: a suppressed value must never reach a Fact in the first place.
_UNRELIABLE_STATUS = {"F", "x", "E", "..", "..."}


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
        return df.assign(SE=pd.NA)
    se_member = (cfg.get("se_members") or {}).get("level")
    keys = [c for c in df.columns
            if c not in {vdim, "VALUE", "VECTOR", "COORDINATE", "STATUS", "SYMBOL",
                         "TERMINATED", "DECIMALS", "DGUID"}]
    est = df[df[vdim] == cfg["value_member"]].copy()
    if se_member is not None and se_member in set(df[vdim]):
        se = df[df[vdim] == se_member][keys + ["VALUE"]].rename(columns={"VALUE": "SE"})
        est = est.merge(se, on=keys, how="left")
    else:
        est["SE"] = pd.NA
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
        if n < 2:
            continue
        f = _base("streak", dim, member, rows, cfg, [float(n), float(vals[-1])],
                  [str(p) for p in rows["REF_DATE"].tolist()])
        word = "rising" if direction > 0 else "falling"
        f.magnitude = abs(float(vals[-1] - vals[-1 - n]))
        f.statement = f"{member} has been {word} for {n} consecutive periods."
        f.human = f"{member}: {n} periods of {word} in a row, now {humanize(float(vals[-1]), f.uom, f.scalar, f.decimals)}"
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
        f = Fact(
            probe="rank_order",
            cut={f"{dim}_leader": str(top[dim]), f"{dim}_trailer": str(bottom[dim])},
            values=[float(top["VALUE"]), float(bottom["VALUE"])], periods=[str(period)],
            vectors=[str(top["VECTOR"]), str(bottom["VECTOR"])],
            uom=str(top.get("UOM", "")), scalar=str(top.get("SCALAR_FACTOR", "")),
            decimals=int(top.get("DECIMALS", 1) or 1),
            magnitude=float(top["VALUE"] - bottom["VALUE"]), legibility=_legibility(dim, cfg),
        )
        f.statement = f"In {period}, {top[dim]} ranked highest and {bottom[dim]} lowest."
        f.human = (f"{top[dim]} highest at {humanize(float(top['VALUE']), f.uom, f.scalar, f.decimals)}; "
                   f"{bottom[dim]} lowest at {humanize(float(bottom['VALUE']), f.uom, f.scalar, f.decimals)}")
        f.meta = {"leader": str(top[dim]), "trailer": str(bottom[dim])}
        facts.append(f)
    return facts


@probe("rank_reversal")
def rank_reversal(df, dim, cfg):
    ordered = rank_order(df, dim, cfg)
    ordered.sort(key=lambda f: f.periods[-1])
    facts = []
    for prev, cur in zip(ordered, ordered[1:]):
        if prev.meta["leader"] == cur.meta["leader"]:
            continue
        f = Fact(
            probe="rank_reversal",
            cut={f"{dim}_leader": str(cur.meta["leader"]),
                 f"{dim}_overtook": str(prev.meta["leader"])},
            values=cur.values, periods=[prev.periods[-1], cur.periods[-1]],
            vectors=cur.vectors, uom=cur.uom, scalar=cur.scalar, decimals=cur.decimals,
            magnitude=cur.magnitude, legibility=cur.legibility,
        )
        f.statement = (f"{cur.meta['leader']} overtook {prev.meta['leader']} "
                       f"between {prev.periods[-1]} and {cur.periods[-1]}.")
        f.human = f"{cur.meta['leader']} moved ahead of {prev.meta['leader']} in {cur.periods[-1]}"
        f.meta = {"from": prev.meta["leader"], "to": cur.meta["leader"]}
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
        direction = "widening" if change > 0 else "narrowing"
        swap = f" {lo} led at the start of this period and {hi} leads now." if lead_changed else ""
        f.statement = (f"The gap between {hi} and {lo} has been {direction} "
                       f"since {series[0].periods[-1]}.{swap}")
        f.human = f"gap between {hi} and {lo} is {direction}: {humanize_delta(change, f.uom, f.scalar, f.decimals)}"
        f.meta = {"direction": direction, "high": hi, "low": lo, "lead_changed": lead_changed}
        facts.append(f)
    return facts


@probe("share_of_total")
def share_of_total(df, dim, cfg):
    aggregates = set((cfg.get("aggregate_members") or {}).get(dim, []))
    facts = []
    for period, chunk in df.groupby("REF_DATE"):
        chunk = chunk[~chunk[dim].isin(aggregates)]
        total = float(chunk["VALUE"].sum())
        if total == 0 or len(chunk) < 2:
            continue
        for _, row in chunk.iterrows():
            share = float(row["VALUE"]) / total * 100
            f = Fact(
                probe="share_of_total", cut={dim: str(row[dim])},
                values=[share, float(row["VALUE"])], periods=[str(period)],
                vectors=[str(row["VECTOR"])], uom=str(row.get("UOM", "")),
                scalar=str(row.get("SCALAR_FACTOR", "")),
                decimals=int(row.get("DECIMALS", 1) or 1),
                magnitude=share, legibility=_legibility(dim, cfg),
            )
            f.statement = f"In {period}, {row[dim]} accounted for {share:.1f}% of the total."
            f.human = f"{row[dim]} is {share:.1f}% of the total"
            f.meta = {"share": share}
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
        f.statement = f"{member} moved {word} {crossed[0]:g} in {f.periods[-1]}."
        f.human = f"{member} crossed {humanize(float(crossed[0]), f.uom, f.scalar, 0)}"
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
        f.statement = (f"{member} changed by {change:.1f} between "
                       f"{f.periods[0]} and {f.periods[-1]}.")
        f.human = f"{member}: {humanize_delta(change, f.uom, f.scalar, f.decimals)} than in {f.periods[0]}"
        f.meta = {"from_period": f.periods[0], "to_period": f.periods[-1]}
        facts.append(f)
    return facts


def run_probes(df: pd.DataFrame, dimensions: list[str], cfg: dict) -> list[Fact]:
    facts: list[Fact] = []
    for name, fn in PROBES.items():
        for dim in dimensions:
            if dim not in df.columns or df[dim].nunique() < 2:
                continue
            try:
                facts.extend(fn(df, dim, cfg))
            except Exception as exc:  # a broken probe must not sink the run
                print(f"  probe {name} failed on {dim}: {exc}")
    return facts
