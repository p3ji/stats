from pathlib import Path
import pytest
from remine.discover import parse_index, parse_article, DailyArticle

FIXTURES = Path(__file__).parent / "fixtures"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8", errors="replace")


def test_parse_index_finds_article_urls():
    urls = parse_index(read("daily_index.html"), "260807")
    assert "https://www150.statcan.gc.ca/n1/daily-quotidien/260807/dq260807a-eng.htm" in urls
    assert all("/260807/" in u for u in urls)
    assert len(urls) == len(set(urls)), "urls must be deduplicated"


def test_parse_index_raises_when_no_articles():
    with pytest.raises(ValueError, match="no Daily articles"):
        parse_index("<html><body>nothing here</body></html>", "260807")


def test_parse_article_extracts_pid_as_eight_digits():
    art = parse_article(read("dq260807a.html"), "http://x/dq260807a-eng.htm")
    # link is pid=1410028701; the cube PID drops the 2-digit view suffix
    assert 14100287 in art.pids


def test_parse_article_extracts_title_and_slug():
    art = parse_article(read("dq260807a.html"), "http://x/dq260807a-eng.htm")
    assert "Labour Force Survey" in art.title
    assert art.slug == "dq260807a"


def test_parse_article_prose_is_plain_text_without_markup():
    art = parse_article(read("dq260807a.html"), "http://x/dq260807a-eng.htm")
    assert "<" not in art.prose
    assert len(art.prose) > 500


def test_parse_article_raises_when_no_pids():
    with pytest.raises(ValueError, match="no product IDs"):
        parse_article("<html><body><h1>Title</h1><p>words</p></body></html>", "http://x/dq-eng.htm")
