from remine.humanize import humanize, humanize_delta


def test_thousands_of_persons_becomes_whole_people():
    assert humanize(47.3, "Persons in thousands", "thousands") == "about 47,000 people"


def test_small_thousands_rounds_to_hundreds():
    assert humanize(1.2, "Persons in thousands", "thousands") == "about 1,200 people"


def test_percentage_keeps_its_own_units():
    assert humanize(6.4, "Percentage", "units") == "6.4%"


def test_dollars_get_a_currency_symbol_and_thousands_separator():
    assert humanize(64321.0, "Dollars", "units") == "$64,321"


def test_unknown_unit_falls_back_to_value_and_uom():
    assert humanize(12.5, "Widgets", "units") == "12.5 Widgets"


def test_delta_carries_an_explicit_direction_word():
    assert humanize_delta(47.3, "Persons in thousands", "thousands") == "about 47,000 more people"
    assert humanize_delta(-47.3, "Persons in thousands", "thousands") == "about 47,000 fewer people"


def test_percentage_delta_uses_percentage_points():
    assert humanize_delta(1.5, "Percentage", "units") == "1.5 percentage points higher"
    assert humanize_delta(-1.5, "Percentage", "units") == "1.5 percentage points lower"
