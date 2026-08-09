import json
from pathlib import Path

from remine.brief import build_brief, write_brief
from remine.cube import CubeMeta, Dimension
from remine.discover import DailyArticle
from remine.probes import Fact

ARTICLE = DailyArticle(url="http://x/dq260807a-eng.htm", title="Labour Force Survey",
                       slug="dq260807a", pids=(14100287,), prose="Employment rose in Ontario.")
META = CubeMeta(pid=14100287, title="Labour force characteristics", release_time="2026-08-07T08:30",
                frequency_code=6, dimensions=(Dimension("Geography", ("Ontario",)),))


def a_fact() -> Fact:
    return Fact(probe="gap_between_members", cut={"Geography": "Ontario vs Alberta"},
                values=[18.0], periods=["2026-07"], vectors=["v1", "v2"],
                uom="Persons in thousands", scalar="thousands", human="about 18,000 more people",
                statement="s", magnitude=18.0, score=0.9)


def test_brief_carries_the_articles_full_prose_verbatim():
    brief = build_brief(ARTICLE, META, [a_fact()], {}, {"top_n": 40})
    assert brief["article"]["prose"] == ARTICLE.prose


def test_brief_carries_the_mention_map_for_later_cross_checking():
    brief = build_brief(ARTICLE, META, [a_fact()], {"Geography|Ontario": True}, {"top_n": 40})
    assert brief["mentions"]["Geography|Ontario"] is True


def test_brief_assigns_stable_sequential_fact_ids():
    brief = build_brief(ARTICLE, META, [a_fact(), a_fact()], {}, {"top_n": 40})
    assert [f["id"] for f in brief["facts"]] == ["fact_1", "fact_2"]


def test_brief_truncates_to_top_n():
    brief = build_brief(ARTICLE, META, [a_fact() for _ in range(50)], {}, {"top_n": 40})
    assert len(brief["facts"]) == 40


def test_brief_includes_a_link_to_the_statcan_table():
    brief = build_brief(ARTICLE, META, [a_fact()], {}, {"top_n": 40})
    assert "14100287" in brief["cube"]["table_url"]


def test_write_brief_round_trips_as_json(tmp_path: Path):
    brief = build_brief(ARTICLE, META, [a_fact()], {}, {"top_n": 40})
    path = write_brief(brief, tmp_path)
    assert path.name == "260807-dq260807a.json"
    assert json.loads(path.read_text(encoding="utf-8"))["facts"][0]["id"] == "fact_1"
