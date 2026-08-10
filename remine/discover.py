"""Stage 1 — find Daily articles for a date and the cubes they cite.

The Daily has no working RSS feed (verified 2026-08-07: the documented feed
URLs 404), so the index page is scraped instead.
"""

import html as html_mod
import re
from dataclasses import dataclass

import requests

BASE = "https://www150.statcan.gc.ca"
INDEX_URL = f"{BASE}/n1/dai-quo/index-eng.htm"

_ARTICLE_HREF = re.compile(r'href="(/n1)?(/daily-quotidien/(\d{6})/(dq\d{6}[a-z])-eng\.htm)"')
_PID_LINK = re.compile(r"tv\.action\?pid=(\d{10})")
_TITLE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_SCRIPT_STYLE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
# The whole page includes page chrome — e.g. the "Select geography" dropdown
# listing all ten provinces — which made every province read as "mentioned"
# regardless of what the article prose actually said. Extract the article
# body specifically, in order of preference, and fall back to the whole page
# only if none of these is found.
_MAIN = re.compile(r"<main\b[^>]*>(.*?)</main>", re.S | re.I)
_WB_CONT = re.compile(r'<[^>]+\bid="wb-cont"[^>]*>(.*)', re.S | re.I)
_MWSBODYTEXT = re.compile(r'<[^>]+\bclass="[^"]*\bmwsbodytext\b[^"]*"[^>]*>(.*?)</div>', re.S | re.I)
# Interactive widgets and download-button navigation embedded inside the body
# container are chrome, not prose: the province <select> and the per-table
# "Table N" download buttons both name every province without the article
# ever discussing them. Strip these before flattening to text so mentions.py
# sees only what a reader would read as narrative.
_SELECT = re.compile(r"<select\b.*?</select>", re.S | re.I)
_TABLEBTN = re.compile(r'<div\b[^>]*\bclass="[^"]*\btablebtn\b[^"]*"[^>]*>.*?</div>', re.S | re.I)


@dataclass(frozen=True)
class DailyArticle:
    url: str
    title: str
    slug: str
    pids: tuple[int, ...]
    prose: str
    body_source: str = "whole-page"


@dataclass(frozen=True)
class Release:
    date: str
    articles: tuple[DailyArticle, ...]


def _text(fragment: str) -> str:
    fragment = _SCRIPT_STYLE.sub(" ", fragment)
    fragment = _SELECT.sub(" ", fragment)
    fragment = _TABLEBTN.sub(" ", fragment)
    fragment = _TAG.sub(" ", fragment)
    fragment = html_mod.unescape(fragment)
    return re.sub(r"\s+", " ", fragment).strip()


def _extract_body(html: str) -> tuple[str, str]:
    """Return (body_fragment, source) — the article body rather than the whole page.

    The whole page includes chrome such as the "Select geography" dropdown,
    which lists every province regardless of what the article discusses. Try
    increasingly specific containers and record which one was used; fall back
    to the whole page only if none is found.
    """
    match = _MAIN.search(html)
    if match:
        return match.group(1), "main"
    match = _WB_CONT.search(html)
    if match:
        return match.group(1), "wb-cont"
    match = _MWSBODYTEXT.search(html)
    if match:
        return match.group(1), "mwsbodytext"
    return html, "whole-page"


def parse_index(html: str, date: str) -> list[str]:
    urls: list[str] = []
    for _, path, found_date, _slug in _ARTICLE_HREF.findall(html):
        if found_date != date:
            continue
        url = f"{BASE}/n1{path}"
        if url not in urls:
            urls.append(url)
    if not urls:
        raise ValueError(f"no Daily articles found for {date} — index markup may have changed")
    return urls


def parse_article(html: str, url: str) -> DailyArticle:
    pids = sorted({int(str(p)[:8]) for p in _PID_LINK.findall(html)})
    if not pids:
        raise ValueError(f"no product IDs found in {url}")
    title_match = _TITLE.search(html)
    title = _text(title_match.group(1)) if title_match else url
    title = title.split("—")[-1].strip() or title
    slug_match = re.search(r"(dq\d{6}[a-z])", url)
    slug = slug_match.group(1) if slug_match else url.rsplit("/", 1)[-1]
    body_fragment, body_source = _extract_body(html)
    return DailyArticle(url=url, title=title, slug=slug, pids=tuple(pids),
                        prose=_text(body_fragment), body_source=body_source)


def _fetch(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.encoding or "utf-8"
    return resp.text


def discover(date: str, fetch=_fetch) -> Release:
    urls = parse_index(fetch(INDEX_URL), date)
    articles = []
    for url in urls:
        try:
            articles.append(parse_article(fetch(url), url))
        except ValueError:
            continue  # articles citing no cube are not re-minable
    if not articles:
        raise ValueError(f"no article for {date} cites a cube")
    return Release(date=date, articles=tuple(articles))
