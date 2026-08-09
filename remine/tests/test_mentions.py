from remine.cube import CubeMeta, Dimension
from remine.mentions import find_mentions, load_config

META = CubeMeta(
    pid=1, title="t", release_time="", frequency_code=6,
    dimensions=(
        Dimension("Geography", ("Canada", "Ontario", "Alberta")),
        Dimension("Age group", ("15 years and over", "15 to 24 years")),
    ),
)


def test_member_named_in_prose_is_marked_mentioned():
    m = find_mentions("Employment rose in Ontario last month.", META, {})
    assert m["Geography|Ontario"] is True
    assert m["Geography|Alberta"] is False


def test_matching_is_case_insensitive():
    assert find_mentions("gains in ONTARIO", META, {})["Geography|Ontario"] is True


def test_synonym_maps_colloquial_phrasing_to_a_member():
    m = find_mentions("Employment among youth fell.", META, {"youth": "15 to 24 years"})
    assert m["Age group|15 to 24 years"] is True


def test_substring_of_a_longer_word_does_not_count_as_a_mention():
    # "Canada" must not be matched inside "Canadaland"
    assert find_mentions("Canadaland reported it.", META, {})["Geography|Canada"] is False


def test_every_member_gets_a_key():
    m = find_mentions("", META, {})
    assert len(m) == 5
    assert all(v is False for v in m.values())


def test_load_config_merges_cube_over_defaults():
    cfg = load_config(14100287)
    assert cfg["top_n"] == 40                      # from defaults
    assert cfg["value_member"] == "Estimate"       # from the cube entry
    assert cfg["se_members"]["level"] == "Standard error of estimate"


def test_load_config_for_unknown_cube_returns_defaults():
    cfg = load_config(99999999)
    assert cfg["weights"]["magnitude"] == 0.40
    assert cfg["se_members"] == {}
