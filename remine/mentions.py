"""Stage 2 — which dimension members does the Daily article name?

This exists only because ranking happens before any model reads anything: the
cuts a Daily reports are usually the biggest and most legible, so without a
correction they crowd genuinely new material off a truncated brief.

Nothing is dropped on this signal. It is a ranking demotion, and later an
auditor of the editorial pass's `differs_from_daily` claims.
"""

import re
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent / "surveys.yaml"


def load_config(pid: int, path: Path | None = None) -> dict:
    raw = yaml.safe_load((path or CONFIG_PATH).read_text(encoding="utf-8"))
    cfg = dict(raw.get("defaults", {}))
    cfg.update(raw.get("cubes", {}).get(int(pid), {}))
    return cfg


def _mentioned(needle: str, prose_lower: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(needle.lower())}(?![\w-])", prose_lower) is not None


def find_mentions(prose: str, meta, synonyms: dict[str, str]) -> dict[str, bool]:
    prose_lower = prose.lower()
    hits: dict[str, bool] = {}
    for dim in meta.dimensions:
        for member in dim.members:
            hits[f"{dim.name}|{member}"] = _mentioned(member, prose_lower)
    for phrase, member in (synonyms or {}).items():
        if not _mentioned(phrase, prose_lower):
            continue
        for key in hits:
            if key.split("|", 1)[1] == member:
                hits[key] = True
    return hits
