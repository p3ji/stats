from pathlib import Path

import pytest

from remine.cube import load_cube
from remine.probes import PROBES, Fact, prepare, run_probes, slice_frame

FIXTURES = Path(__file__).parent / "fixtures"

CFG = {
    "value_dimension": "Statistics", "value_member": "Estimate",
    "se_members": {"level": "Standard error of estimate"},
    "filters": {"Data type": "Seasonally adjusted"},
    "aggregate_members": {}, "legibility": {"Geography": 1.0}, "min_periods": 1,
    "measure_dimension": "Labour force characteristics",
    "measures": ["Employment", "Unemployment rate"],
    "hold_at": {"Gender": "Total - Gender"},
}


def mini():
    return load_cube(FIXTURES / "mini_cube.zip", 99999999)


def sliced(measure="Employment"):
    """The slice a probe actually sees once Gender and the measure are pinned:
    2 geographies x 3 periods, one row each, for the given measure."""
    return slice_frame(prepare(mini(), CFG), CFG, measure, "Geography")


def test_prepare_keeps_only_estimate_rows_and_attaches_se():
    out = prepare(mini(), CFG)
    assert set(out["Statistics"]) == {"Estimate"}
    assert out["SE"].notna().all()
    # New fixture: 2 measures x 2 genders x 2 geographies x 3 periods = 24
    # Estimate rows; prepare() no longer collapses to a single series — that
    # is now slice_frame's job (see the `sliced()` helper above).
    assert len(out) == 24


def test_gap_between_members_is_registered():
    assert "gap_between_members" in PROBES


def test_gap_between_members_computes_the_arithmetic_difference():
    # fixture: Ontario 2026-07 = 102.0, Alberta 2026-07 = 84.0 -> gap 18.0
    facts = PROBES["gap_between_members"](sliced(), "Geography", CFG)
    latest = [f for f in facts if f.periods[-1] == "2026-07"]
    assert len(latest) == 1
    assert latest[0].values[0] == 18.0
    assert set(latest[0].cut.values()) >= {"Ontario", "Alberta"}


def test_fact_carries_vectors_and_periods_for_provenance():
    fact = PROBES["gap_between_members"](sliced(), "Geography", CFG)[0]
    assert fact.vectors and all(v.startswith("v") for v in fact.vectors)
    assert fact.periods


def test_fact_human_field_is_reader_scale():
    fact = PROBES["gap_between_members"](sliced(), "Geography", CFG)[0]
    assert "people" in fact.human


def test_fact_key_is_stable_and_order_independent_within_a_cut():
    f = PROBES["gap_between_members"](sliced(), "Geography", CFG)[0]
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
    facts = PROBES["streak"](sliced(), "Geography", CFG)
    ont = [f for f in facts if f.cut["Geography"] == "Ontario"]
    assert ont and ont[0].values[0] == 2.0


def test_rank_reversal_reports_one_fact_per_pair_not_one_per_crossing():
    import pandas as pd
    rows = []
    # A and B trade the lead three times across four periods.
    for period, a, b in [("2026-04", 10.0, 8.0), ("2026-05", 8.0, 10.0),
                         ("2026-06", 10.0, 8.0), ("2026-07", 8.0, 10.0)]:
        for geo, val in [("Alpha", a), ("Beta", b)]:
            rows.append({"REF_DATE": period, "Geography": geo, "VALUE": val,
                         "VECTOR": f"v{geo[:2]}", "UOM": "Percentage",
                         "SCALAR_FACTOR": "units", "DECIMALS": 1, "SE": None})
    df = pd.DataFrame(rows)
    facts = PROBES["rank_reversal"](df, "Geography", {"aggregate_members": {}, "legibility": {}})
    assert len(facts) == 1, "one pair trading the lead is one finding, not one per flip"
    assert facts[0].meta["crossings"] == 3
    assert "traded the lead" in facts[0].human


def test_streak_honours_the_configured_minimum_length():
    cfg = {**CFG, "min_streak_periods": 6}
    facts = PROBES["streak"](prepare(mini(), cfg), "Geography", cfg)
    assert facts == [], "the fixture's 2-period runs are below a 6-period floor"


def test_streak_still_fires_at_the_configured_floor():
    cfg = {**CFG, "min_streak_periods": 2}
    assert PROBES["streak"](prepare(mini(), cfg), "Geography", cfg)


def test_rank_order_identifies_leader_and_trailer():
    facts = PROBES["rank_order"](sliced(), "Geography", CFG)
    latest = [f for f in facts if f.periods[-1] == "2026-07"][0]
    assert latest.meta["leader"] == "Ontario"
    assert latest.meta["trailer"] == "Alberta"


def test_gap_trend_reports_widening_when_the_gap_grows():
    # Ontario 100->102 (+2), Alberta 80->84 (+4): the gap narrows by 2
    facts = PROBES["gap_trend"](sliced(), "Geography", CFG)
    assert facts and facts[0].values[0] == -2.0
    assert facts[0].meta["direction"] == "narrowing"


def test_share_of_total_is_a_percentage_of_the_period_sum():
    # share_of_total now reports the CHANGE in share from the first to the last
    # period of the frame (Task 15: a share's level is a population artifact,
    # its change is a finding). Fixture: Ontario 100/101/102, Alberta 80/82/84
    # over 2026-05/06/07.
    # share_then (2026-05) = 100 / (100 + 80) * 100 = 55.555...%
    # share_now  (2026-07) = 102 / (102 + 84) * 100 = 54.838709...%
    # change = share_now - share_then = -0.7168458781362048 points
    facts = PROBES["share_of_total"](sliced(), "Geography", CFG)
    ont = [f for f in facts if f.cut["Geography"] == "Ontario"][0]
    share_then = 100.0 / (100.0 + 80.0) * 100
    share_now = 102.0 / (102.0 + 84.0) * 100
    assert abs(ont.values[0] - (share_now - share_then)) < 1e-6
    assert abs(ont.values[1] - share_now) < 1e-6
    assert abs(ont.values[2] - share_then) < 1e-6
    assert ont.periods == ["2026-05", "2026-07"]


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


def test_slice_frame_yields_one_row_per_period_and_member():
    from remine.probes import slice_frame
    cfg = {**CFG, "measure_dimension": "Labour force characteristics",
           "hold_at": {"Geography": "Canada", "Gender": "Total - Gender",
                       "Age group": "15 years and over"}}
    out = slice_frame(prepare(mini(), cfg), cfg, "Employment", "Geography")
    assert out.groupby(["REF_DATE", "Geography"]).size().max() == 1


def test_slice_frame_holds_gender_at_the_total_member():
    from remine.probes import slice_frame
    cfg = {**CFG, "measure_dimension": "Labour force characteristics",
           "hold_at": {"Gender": "Total - Gender"}}
    out = slice_frame(prepare(mini(), cfg), cfg, "Employment", "Geography")
    assert set(out["Gender"]) == {"Total - Gender"}


def test_run_probes_refuses_a_slice_that_still_has_duplicate_rows():
    # No hold_at, so Gender and the measure dimension both still vary: exactly
    # the condition that made the pipeline compare unrelated series.
    cfg = {**CFG, "hold_at": {}, "measures": [], "measure_dimension": None}
    with pytest.raises(ValueError, match="rows per"):
        run_probes(prepare(mini(), cfg), ["Geography"], cfg)


def test_run_probes_rejects_a_measure_that_is_also_an_aggregate():
    cfg = {**CFG, "measures": ["Employment"],
           "aggregate_members": {"Labour force characteristics": ["Employment"]}}
    with pytest.raises(ValueError, match="aggregate_members"):
        run_probes(prepare(mini(), cfg), ["Geography"], cfg)


def test_window_keeps_only_the_most_recent_periods():
    from remine.probes import window
    out = window(prepare(mini(), CFG), {"window_periods": 2}, "streak")
    assert sorted(out["REF_DATE"].unique()) == ["2026-06", "2026-07"]


def test_window_gives_long_run_compare_the_full_history():
    from remine.probes import window
    out = window(prepare(mini(), CFG), {"window_periods": 2}, "long_run_compare")
    assert len(sorted(out["REF_DATE"].unique())) == 3


def test_facts_record_which_measure_they_describe():
    cfg = {**CFG, "measure_dimension": "Labour force characteristics",
           "measures": ["Employment"],
           "hold_at": {"Gender": "Total - Gender", "Age group": "15 years and over"}}
    facts = run_probes(prepare(mini(), cfg), ["Geography"], cfg)
    assert facts
    assert all(f.meta["measure"] == "Employment" for f in facts)
    assert all(f.cut.get("Labour force characteristics") == "Employment" for f in facts)


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


def test_partition_drops_members_outside_the_comparable_set():
    from remine.probes import partition
    cfg = {"comparable_members": {"Geography": ["Ontario"]}}
    out = partition(prepare(mini(), CFG), "Geography", cfg)
    assert set(out["Geography"]) == {"Ontario"}


def test_partition_is_a_no_op_when_none_is_configured():
    from remine.probes import partition
    before = prepare(mini(), CFG)
    assert len(partition(before, "Geography", {})) == len(before)


def test_dedupe_keeps_one_fact_per_cut_and_counts_the_periods():
    from remine.probes import dedupe
    def f(period):
        return Fact(probe="gap_between_members", cut={"Geography_high": "Ontario",
                    "Geography_low": "Alberta"}, values=[1.0], periods=[period],
                    vectors=["v1"], human="h", statement="s")
    out = dedupe([f("2026-05"), f("2026-06"), f("2026-07")])
    assert len(out) == 1
    assert out[0].periods == ["2026-07"], "should keep the most recent"
    assert out[0].meta["periods_observed"] == 3


def test_dedupe_keeps_distinct_cuts_apart():
    from remine.probes import dedupe
    def f(hi):
        return Fact(probe="gap_between_members", cut={"Geography_high": hi,
                    "Geography_low": "Alberta"}, values=[1.0], periods=["2026-07"],
                    vectors=["v1"], human="h", statement="s")
    assert len(dedupe([f("Ontario"), f("Quebec")])) == 2


def test_cross_member_probes_are_skipped_for_count_measures():
    cfg = {**CFG, "measure_dimension": "Labour force characteristics",
           "measures": ["Employment"], "rate_measures": ["Unemployment rate"],
           "count_measures": ["Employment"],
           "hold_at": {"Gender": "Total - Gender", "Age group": "15 years and over"}}
    facts = run_probes(prepare(mini(), cfg), ["Geography"], cfg)
    assert not [f for f in facts if f.probe == "gap_between_members"], \
        "a gap between raw counts mostly measures group size"


def test_cross_member_probes_run_for_rate_measures():
    cfg = {**CFG, "measure_dimension": "Labour force characteristics",
           "measures": ["Unemployment rate"], "rate_measures": ["Unemployment rate"],
           "count_measures": ["Employment"],
           "hold_at": {"Gender": "Total - Gender", "Age group": "15 years and over"}}
    facts = run_probes(prepare(mini(), cfg), ["Geography"], cfg)
    assert [f for f in facts if f.probe == "gap_between_members"]


def test_share_of_total_reports_the_change_in_share_not_the_level():
    cfg = {**CFG, "measure_dimension": "Labour force characteristics",
           "measures": ["Employment"], "count_measures": ["Employment"],
           "rate_measures": ["Unemployment rate"],
           "hold_at": {"Gender": "Total - Gender", "Age group": "15 years and over"}}
    facts = [f for f in run_probes(prepare(mini(), cfg), ["Geography"], cfg)
             if f.probe == "share_of_total"]
    assert facts, "expected a share-change fact"
    for f in facts:
        assert len(f.periods) == 2, "a change spans two periods"
        assert "point" in f.human or "%" in f.human
        assert f.meta["direction"] in {"rose", "fell"}


def test_long_run_compare_carries_an_se_when_the_frame_has_se_columns():
    cfg = {**CFG, "measure_dimension": "Labour force characteristics",
           "measures": ["Employment"], "rate_measures": ["Employment"],
           "hold_at": {"Gender": "Total - Gender", "Age group": "15 years and over"}}
    facts = [f for f in run_probes(prepare(mini(), cfg), ["Geography"], cfg)
             if f.probe == "long_run_compare"]
    assert facts
    assert any(f.se is not None for f in facts)


def test_change_se_prefers_the_published_mom_value_over_quadrature():
    import pandas as pd
    from remine.probes import change_se
    rows = pd.DataFrame([
        {"SE": 1.0, "SE_MOM": 0.3, "SE_YOY": pd.NA},
        {"SE": 2.0, "SE_MOM": 0.3, "SE_YOY": pd.NA},
    ])
    # span of one period: published MoM SE (0.3) wins over quadrature of the
    # level SEs (sqrt(1^2 + 2^2) ~= 2.236)
    assert change_se(rows, 1) == 0.3


def test_change_se_falls_back_to_quadrature_when_the_span_does_not_match():
    import pandas as pd
    from remine.probes import change_se
    rows = pd.DataFrame([
        {"SE": 1.0, "SE_MOM": 0.3, "SE_YOY": pd.NA},
        {"SE": 2.0, "SE_MOM": 0.3, "SE_YOY": pd.NA},
    ])
    assert abs(change_se(rows, 5) - (1.0 ** 2 + 2.0 ** 2) ** 0.5) < 1e-9


def test_rate_only_probes_are_skipped_for_count_measures():
    cfg = {**CFG, "measure_dimension": "Labour force characteristics",
           "measures": ["Employment"], "count_measures": ["Employment"],
           "rate_measures": ["Unemployment rate"],
           "hold_at": {"Gender": "Total - Gender", "Age group": "15 years and over"}}
    facts = run_probes(prepare(mini(), cfg), ["Geography"], cfg)
    assert not [f for f in facts if f.probe in {"long_run_compare", "level_threshold", "streak"}]
