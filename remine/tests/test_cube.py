import json
from pathlib import Path

from remine.cube import parse_meta, load_cube

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_meta_reads_title_and_release_time():
    payload = json.loads((FIXTURES / "cube_meta_14100287.json").read_text(encoding="utf-8"))
    meta = parse_meta(payload)
    assert meta.pid == 14100287
    assert "Labour force characteristics" in meta.title
    assert meta.release_time.startswith("2026-")


def test_parse_meta_reads_all_dimensions_and_members():
    payload = json.loads((FIXTURES / "cube_meta_14100287.json").read_text(encoding="utf-8"))
    meta = parse_meta(payload)
    names = meta.member_names()
    assert "Canada" in names["Geography"]
    assert "Standard error of estimate" in names["Statistics"]
    assert len(meta.dimensions) == 6


def test_load_cube_reads_bom_csv_with_typed_columns():
    df = load_cube(FIXTURES / "mini_cube.zip", 99999999)
    assert list(df.columns)[:3] == ["REF_DATE", "GEO", "DGUID"]
    assert df["VALUE"].dtype.kind == "f"
    # New fixture: 4 (measure, gender) combinations x 2 geographies x 3
    # periods x 2 statistics (Estimate, SE) = 48 rows.
    assert len(df) == 48


def test_load_cube_strips_bom_from_first_column_name():
    df = load_cube(FIXTURES / "mini_cube.zip", 99999999)
    assert "﻿" not in "".join(df.columns)
