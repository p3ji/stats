"""Assemble the fact brief — the handoff from deterministic stages to editorial.

The brief carries the Daily's full prose verbatim, because judging whether a
story was already told is an act of reading and happens at editorial time.
"""

import json
import re
from dataclasses import asdict
from pathlib import Path

TABLE_URL = "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={pid}01"


def build_brief(article, meta, facts, mentions, cfg) -> dict:
    top_n = int(cfg.get("top_n", 40))
    date = re.search(r"dq(\d{6})", article.slug).group(1)
    return {
        "date": date,
        "article": {"url": article.url, "title": article.title,
                    "slug": article.slug, "prose": article.prose},
        "cube": {"pid": meta.pid, "title": meta.title,
                 "release_time": meta.release_time,
                 "table_url": TABLE_URL.format(pid=meta.pid)},
        "mentions": dict(mentions or {}),
        "facts": [
            {"id": f"fact_{i}", **{k: v for k, v in asdict(f).items()
                                   if k not in {"legibility", "decimals", "scalar"}}}
            for i, f in enumerate(facts[:top_n], start=1)
        ],
    }


def write_brief(brief: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{brief['date']}-{brief['article']['slug']}.json"
    path.write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
