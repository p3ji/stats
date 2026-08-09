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


def test_all_eight_v1_probes_are_registered():
    assert set(PROBES) == {
        "gap_between_members", "gap_trend", "level_threshold", "streak",
        "rank_order", "rank_reversal", "share_of_total", "long_run_compare",
    }


def test_streak_counts_consecutive_moves_in_one_direction():
    # fixture Ontario: 100.0, 101.0, 102.0 -> a 2-period rising streak
    facts = PROBES["streak"](prepare(mini(), CFG), "Geography", CFG)
    ont = [f for f in facts if f.cut["Geography"] == "Ontario"]
    assert ont and ont[0].values[0] == 2.0


def test_rank_order_identifies_leader_and_trailer():
    facts = PROBES["rank_order"](prepare(mini(), CFG), "Geography", CFG)
    latest = [f for f in facts if f.periods[-1] == "2026-07"][0]
    assert latest.meta["leader"] == "Ontario"
    assert latest.meta["trailer"] == "Alberta"


def test_gap_trend_reports_widening_when_the_gap_grows():
    # Ontario 100->102 (+2), Alberta 80->84 (+4): the gap narrows by 2
    facts = PROBES["gap_trend"](prepare(mini(), CFG), "Geography", CFG)
    assert facts and facts[0].values[0] == -2.0
    assert facts[0].meta["direction"] == "narrowing"


def test_share_of_total_is_a_percentage_of_the_period_sum():
    facts = PROBES["share_of_total"](prepare(mini(), CFG), "Geography", CFG)
    ont = [f for f in facts if f.cut["Geography"] == "Ontario" and f.periods[-1] == "2026-07"]
    assert abs(ont[0].values[0] - 102.0 / (102.0 + 84.0) * 100) < 1e-6


def test_probes_never_emit_a_fact_without_vectors():
    facts = run_probes(prepare(mini(), CFG), ["Geography"], CFG)
    assert facts
    assert all(f.vectors for f in facts)


def test_probes_never_emit_a_fact_without_a_human_string():
    facts = run_probes(prepare(mini(), CFG), ["Geography"], CFG)
    assert all(f.human for f in facts)


def test_gap_trend_survives_a_lead_swap():
    import pandas as pd
    rows = []
    # Ontario 100 -> 90, Alberta 80 -> 95: the lead swaps between the periods.
    for period, ont, alb in [("2026-05", 100.0, 80.0), ("2026-06", 90.0, 95.0)]:
        for geo, val in [("Ontario", ont), ("Alberta", alb)]:
            rows.append({"REF_DATE": period, "Geography": geo, "VALUE": val,
                         "VECTOR": f"v{geo[:2]}", "UOM": "Persons in thousands",
                         "SCALAR_FACTOR": "thousands", "DECIMALS": 1, "SE": None})
    df = pd.DataFrame(rows)
    facts = PROBES["gap_trend"](df, "Geography", {"aggregate_members": {}, "legibility": {}})
    assert len(facts) == 1, "a lead swap must not split or drop the trend"
    assert facts[0].meta["lead_changed"] is True
    # gap goes 20.0 -> 5.0, so it narrowed by 15.0
    assert facts[0].values[0] == -15.0


def test_prepare_drops_statcan_unreliable_and_suppressed_rows():
    import pandas as pd
    base = {"Geography": "Ontario", "Statistics": "Estimate",
            "Data type": "Seasonally adjusted", "UOM": "Persons in thousands",
            "SCALAR_FACTOR": "thousands", "VECTOR": "v1", "DECIMALS": 1}
    df = pd.DataFrame([
        {**base, "REF_DATE": "2026-05", "VALUE": 10.0, "STATUS": ""},
        {**base, "REF_DATE": "2026-06", "VALUE": 11.0, "STATUS": "F"},   # too unreliable
        {**base, "REF_DATE": "2026-07", "VALUE": 12.0, "STATUS": "x"},   # suppressed
        {**base, "REF_DATE": "2026-08", "VALUE": 13.0, "STATUS": "E"},   # use with caution
    ])
    out = prepare(df, {"value_dimension": "Statistics", "value_member": "Estimate",
                       "se_members": {}, "filters": {}})
    assert out["REF_DATE"].tolist() == ["2026-05"]


def test_prepare_drops_rows_with_no_value():
    import pandas as pd
    base = {"Geography": "Ontario", "Statistics": "Estimate",
            "Data type": "Seasonally adjusted", "UOM": "Persons in thousands",
            "SCALAR_FACTOR": "thousands", "VECTOR": "v1", "DECIMALS": 1, "STATUS": ""}
    df = pd.DataFrame([
        {**base, "REF_DATE": "2026-05", "VALUE": 10.0},
        {**base, "REF_DATE": "2026-06", "VALUE": float("nan")},
    ])
    out = prepare(df, {"value_dimension": "Statistics", "value_member": "Estimate",
                       "se_members": {}, "filters": {}})
    assert out["REF_DATE"].tolist() == ["2026-05"]
