from pathlib import Path

from remine.cube import load_cube
from remine.probes import PROBES, Fact, prepare, run_probes

FIXTURES = Path(__file__).parent / "fixtures"

CFG = {
    "value_dimension": "Statistics", "value_member": "Estimate",
    "se_members": {"level": "Standard error of estimate"},
    "filters": {"Data type": "Seasonally adjusted"},
    "aggregate_members": {}, "legibility": {"Geography": 1.0}, "min_periods": 1,
}


def mini():
    return load_cube(FIXTURES / "mini_cube.zip", 99999999)


def test_prepare_keeps_only_estimate_rows_and_attaches_se():
    out = prepare(mini(), CFG)
    assert set(out["Statistics"]) == {"Estimate"}
    assert out["SE"].notna().all()
    assert len(out) == 6  # 2 geographies x 3 periods


def test_gap_between_members_is_registered():
    assert "gap_between_members" in PROBES


def test_gap_between_members_computes_the_arithmetic_difference():
    # fixture: Ontario 2026-07 = 102.0, Alberta 2026-07 = 84.0 -> gap 18.0
    facts = PROBES["gap_between_members"](prepare(mini(), CFG), "Geography", CFG)
    latest = [f for f in facts if f.periods[-1] == "2026-07"]
    assert len(latest) == 1
    assert latest[0].values[0] == 18.0
    assert set(latest[0].cut.values()) >= {"Ontario", "Alberta"}


def test_fact_carries_vectors_and_periods_for_provenance():
    fact = PROBES["gap_between_members"](prepare(mini(), CFG), "Geography", CFG)[0]
    assert fact.vectors and all(v.startswith("v") for v in fact.vectors)
    assert fact.periods


def test_fact_human_field_is_reader_scale():
    fact = PROBES["gap_between_members"](prepare(mini(), CFG), "Geography", CFG)[0]
    assert "people" in fact.human


def test_fact_key_is_stable_and_order_independent_within_a_cut():
    f = PROBES["gap_between_members"](prepare(mini(), CFG), "Geography", CFG)[0]
    assert f.key() == f.key()
    assert f.probe in f.key()


def test_run_probes_returns_facts_from_the_registry():
    df = prepare(mini(), CFG)
    meta_dims = ["Geography"]
    facts = run_probes(df, meta_dims, CFG)
    assert facts and all(isinstance(f, Fact) for f in facts)
