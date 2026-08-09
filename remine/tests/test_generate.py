import pytest
from remine import generate as gen
from remine.cube import CubeMeta, Dimension
from remine.discover import DailyArticle, Release


def test_generate_writes_no_brief_when_nothing_survives_the_gate(tmp_path, monkeypatch, capsys):
    article = DailyArticle(url="http://x/dq260807a-eng.htm", title="T",
                           slug="dq260807a", pids=(14100287,), prose="words")
    meta = CubeMeta(pid=14100287, title="C", release_time="2026-08-07T08:30",
                    frequency_code=6,
                    dimensions=(Dimension("Geography", ("Ontario", "Alberta")),))
    monkeypatch.setattr(gen, "discover", lambda date: Release(date=date, articles=(article,)))
    monkeypatch.setattr(gen, "fetch_meta", lambda pid: meta)
    monkeypatch.setattr(gen, "load_config", lambda pid: {"top_n": 40, "filters": {}})
    monkeypatch.setattr(gen, "download_cube", lambda pid, rt, cache: tmp_path / "x.zip")
    monkeypatch.setattr(gen, "load_cube", lambda p, pid: None)
    monkeypatch.setattr(gen, "prepare", lambda df, cfg: None)
    monkeypatch.setattr(gen, "run_probes", lambda df, dims, cfg: [])
    monkeypatch.setattr(gen, "gate", lambda facts, df, cfg: [])
    monkeypatch.setattr(gen, "find_mentions", lambda prose, meta_, syn: {})
    monkeypatch.setattr(gen, "BRIEFS", tmp_path / "briefs")

    written = gen.generate("260807")

    assert written == []
    assert not (tmp_path / "briefs").exists() or not list((tmp_path / "briefs").glob("*.json"))
    assert "SKIPPED" in capsys.readouterr().out
