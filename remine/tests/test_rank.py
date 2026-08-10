from remine.probes import Fact
from remine.rank import gate, rank, score

CFG = {
    "weights": {"magnitude": 0.4, "persistence": 0.25, "legibility": 0.2, "reader_scale": 0.15},
    "mention_demotion": 0.5, "min_magnitude": 0.0,
    "aggregate_members": {"Geography": ["Canada"]},
}


def fact(**kw) -> Fact:
    base = dict(probe="gap_between_members", cut={"Geography": "Ontario vs Alberta"},
                values=[10.0], periods=["2026-07"], vectors=["v1", "v2"],
                uom="Persons in thousands", scalar="thousands", magnitude=10.0,
                se=1.0, legibility=1.0, human="about 10,000 more people",
                statement="s", meta={})
    base.update(kw)
    return Fact(**base)


def test_gate_drops_differences_not_exceeding_their_standard_error():
    kept = gate([fact(magnitude=1.0, se=2.0)], None, CFG)
    assert kept == []


def test_gate_keeps_differences_that_clear_their_standard_error():
    assert len(gate([fact(magnitude=10.0, se=1.0)], None, CFG)) == 1


def test_gate_keeps_facts_with_no_standard_error_available():
    assert len(gate([fact(se=None)], None, CFG)) == 1


def test_gate_applies_the_minimum_magnitude_floor_when_no_se_exists():
    cfg = {**CFG, "min_magnitude": 5.0}
    assert gate([fact(se=None, magnitude=1.0)], None, cfg) == []


def test_gate_drops_facts_built_on_an_aggregate_member():
    f = fact(cut={"Geography": "Canada vs Alberta"}, meta={"high": "Canada", "low": "Alberta",
                                                           "dimension": "Geography"})
    assert gate([f], None, CFG) == []


def test_persistence_raises_the_score_rather_than_lowering_it():
    volatile = fact(periods=["2026-07"])
    persistent = fact(periods=[f"2026-{m:02d}" for m in range(1, 8)])
    assert score(persistent, CFG, 10.0) > score(volatile, CFG, 10.0)


def test_a_stable_large_gap_outranks_a_volatile_one_month_swing():
    stable = fact(magnitude=9.0, periods=[f"2026-{m:02d}" for m in range(1, 8)])
    swing = fact(magnitude=10.0, periods=["2026-07"])
    ordered = rank([swing, stable], {}, CFG)
    assert ordered[0] is stable


def test_mentioned_facts_are_demoted_but_not_dropped():
    plain = fact(magnitude=10.0, cut={"Geography": "Quebec vs Nova Scotia"})
    named = fact(magnitude=10.0, cut={"Geography": "Ontario vs Alberta"})
    ordered = rank([named, plain], {"Geography|Ontario": True}, CFG)
    assert len(ordered) == 2
    assert ordered[0] is plain
    assert ordered[1].mentioned is True


def test_rank_sets_the_score_field_on_every_fact():
    ordered = rank([fact()], {}, CFG)
    assert ordered[0].score > 0


def test_periods_observed_counts_toward_persistence():
    a = fact(periods=["2026-07"])
    b = fact(periods=["2026-07"], meta={"periods_observed": 12})
    assert score(b, CFG, 10.0) > score(a, CFG, 10.0)
