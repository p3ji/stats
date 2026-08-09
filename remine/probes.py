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
