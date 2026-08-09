import pytest

from remine.editor import BindError, bind, check_bare_numerals, check_differs_from_daily, resolve_token

FACTS = {"fact_1": {"id": "fact_1", "values": [18.0], "periods": ["2026-07"],
                    "human": "about 18,000 more people", "vectors": ["v1"],
                    "cut": {"Geography": "Ontario vs Alberta"}}}

BRIEF = {"date": "260807", "article": {"url": "http://x", "title": "T", "slug": "dq260807a",
                                       "prose": "Employment rose in Ontario."},
         "cube": {"pid": 14100287, "title": "C", "release_time": "", "table_url": "http://t"},
         # Both False so the happy-path bind() succeeds. The cross-check tests
         # pass their own mention maps in directly.
         "mentions": {"Geography|Ontario": False, "Geography|Alberta": False},
         "facts": [FACTS["fact_1"]]}


def draft(**kw) -> dict:
    story = {"headline": "H", "fact_ids": ["fact_1"], "assumption": "a belief people hold",
             "stance": "concretizes", "differs_from_daily": "not discussed",
             "body": "The gap was {{fact_1.human}}."}
    story.update(kw.pop("story", {}))
    # bind() requires 2-4 stories, so pair the story under test with a second
    # valid one. Without this every fixture fails the structural check first
    # and no other assertion is ever reached.
    filler = {"headline": "H2", "fact_ids": ["fact_1"], "assumption": "another belief",
              "stance": "challenges", "differs_from_daily": "reported the national total",
              "body": "Also {{fact_1.human}}."}
    base = {"headline": "Top", "daily_story": "The Daily reported employment rose.",
            "stories": [story, filler]}
    base.update(kw)
    return base


def test_resolve_token_reads_a_humanized_field():
    assert resolve_token("fact_1.human", FACTS) == "about 18,000 more people"


def test_resolve_token_reads_an_indexed_value():
    assert resolve_token("fact_1.values[0]", FACTS) == "18.0"


def test_unknown_fact_id_fails_the_build():
    with pytest.raises(BindError, match="unknown fact"):
        resolve_token("fact_9.human", FACTS)


def test_unknown_field_fails_the_build():
    with pytest.raises(BindError, match="unknown field"):
        resolve_token("fact_1.nope", FACTS)


def test_bind_substitutes_every_token():
    out = bind(draft(), BRIEF)
    assert out["stories"][0]["body"] == "The gap was about 18,000 more people."
    assert "{{" not in out["stories"][0]["body"]


def test_unresolved_token_syntax_fails_the_build():
    with pytest.raises(BindError):
        bind(draft(story={"body": "The gap was {{fact_1.values[9]}}."}), BRIEF)


def test_a_bare_numeral_in_prose_fails_the_build():
    assert check_bare_numerals("Employment rose by 18,000 people.") == ["18,000"]


def test_years_are_allowed_as_bare_numerals():
    assert check_bare_numerals("Since 2019 the gap has held.") == []


def test_ordinals_are_allowed_as_bare_numerals():
    assert check_bare_numerals("It ranked 2nd among provinces.") == []


def test_numbers_inside_tokens_are_not_bare_numerals():
    assert check_bare_numerals("The gap was {{fact_1.values[0]}}.") == []


def test_bind_rejects_a_draft_containing_a_bare_numeral():
    with pytest.raises(BindError, match="bare numeral"):
        bind(draft(story={"body": "The gap was 18000 people."}), BRIEF)


def test_not_discussed_claim_is_flagged_when_the_member_was_mentioned():
    problems = check_differs_from_daily(draft(), {"Geography|Ontario": True}, FACTS)
    assert problems and "Ontario" in problems[0]


def test_not_discussed_claim_is_accepted_when_no_member_was_mentioned():
    assert check_differs_from_daily(draft(), {"Geography|Ontario": False}, FACTS) == []


def test_bind_fails_on_a_single_story_draft():
    one = draft()
    one["stories"] = one["stories"][:1]
    with pytest.raises(BindError, match="2-4 stories"):
        bind(one, BRIEF)


def test_bind_fails_on_more_than_four_stories():
    many = draft()
    many["stories"] = many["stories"] * 3   # six stories
    with pytest.raises(BindError, match="2-4 stories"):
        bind(many, BRIEF)


def test_bind_fails_when_the_daily_story_restatement_is_missing():
    with pytest.raises(BindError, match="daily_story"):
        bind(draft(daily_story="  "), BRIEF)


def test_bind_fails_when_a_story_names_no_assumption():
    with pytest.raises(BindError, match="assumption"):
        bind(draft(story={"assumption": ""}), BRIEF)


def test_bind_fails_on_an_unknown_stance():
    with pytest.raises(BindError, match="stance"):
        bind(draft(story={"stance": "explains"}), BRIEF)


def test_a_bare_numeral_in_a_story_headline_fails_the_build():
    with pytest.raises(BindError, match="bare numeral"):
        bind(draft(story={"headline": "Employment fell by 4,000"}), BRIEF)


def test_a_bare_numeral_in_the_daily_story_fails_the_build():
    with pytest.raises(BindError, match="bare numeral"):
        bind(draft(daily_story="The Daily reported 18,000 new jobs."), BRIEF)


def test_a_bare_numeral_in_differs_from_daily_fails_the_build():
    with pytest.raises(BindError, match="bare numeral"):
        bind(draft(story={"differs_from_daily": "the Daily gave 6.4 nationally"}), BRIEF)


def test_a_token_citing_a_fact_the_story_does_not_claim_fails_the_build():
    # body pulls fact_1 while fact_ids claims only fact_2, so the published
    # provenance block would cite the wrong series.
    brief2 = {**BRIEF, "facts": [FACTS["fact_1"], {**FACTS["fact_1"], "id": "fact_2"}]}
    with pytest.raises(BindError, match="does not list"):
        bind(draft(story={"fact_ids": ["fact_2"], "body": "It was {{fact_1.human}}."}), brief2)


def test_a_bare_numeral_in_the_assumption_fails_the_build():
    with pytest.raises(BindError, match="bare numeral"):
        bind(draft(story={"assumption": "unemployment fell by 4,000 last month"}), BRIEF)


def test_an_unrecognised_prose_field_is_still_checked():
    # The sweep is default-deny: a field nobody anticipated is guarded too.
    with pytest.raises(BindError, match="bare numeral"):
        bind(draft(story={"editors_note": "we also saw 12,000 elsewhere"}), BRIEF)


def test_a_bare_numeral_nested_in_a_dict_field_fails_the_build():
    with pytest.raises(BindError, match="bare numeral"):
        bind(draft(story={"notes": {"aside": "we also saw 12,000 elsewhere"}}), BRIEF)


def test_a_bare_numeral_nested_in_a_list_field_fails_the_build():
    with pytest.raises(BindError, match="bare numeral"):
        bind(draft(story={"asides": ["fine", "but 12,000 people moved"]}), BRIEF)


def test_a_token_nested_in_a_non_token_field_fails_the_build():
    with pytest.raises(BindError, match="cannot carry fact tokens"):
        bind(draft(story={"notes": {"aside": "see {{fact_1.human}}"}}), BRIEF)


def test_bound_article_carries_provenance_for_every_fact_used():
    out = bind(draft(), BRIEF)
    prov = out["stories"][0]["provenance"][0]
    assert prov["vectors"] == ["v1"]
    assert prov["periods"] == ["2026-07"]
    assert prov["table_url"] == "http://t"
