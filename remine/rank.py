"""Stage 5 — reliability gate, then salience.

The gate drops; the score ranks. Ranking is explicitly not surprise-based:
persistence *raises* a fact's score, because a large stable gap is a stronger
story than a volatile one-month swing. Anomaly hunting would invert this and
mostly surface noise.
"""

from remine.probes import Fact

_UNRELIABLE_STATUS = {"F", "x", "..", "...", "E"}


def _uses_aggregate(fact: Fact, cfg: dict) -> bool:
    aggregates = cfg.get("aggregate_members") or {}
    members = set(fact.meta.get(k) for k in ("high", "low", "leader", "trailer"))
    members |= set(fact.cut.values())
    for names in aggregates.values():
        for name in names:
            if name in members:
                return True
            if any(isinstance(m, str) and name in m for m in members if m):
                return True
    return False


def gate(facts: list[Fact], df, cfg: dict) -> list[Fact]:
    kept = []
    for f in facts:
        if _uses_aggregate(f, cfg):
            continue                                    # true by construction
        if f.se is not None and f.magnitude <= f.se:
            continue                                    # inside the error bar
        if f.se is None and f.magnitude < float(cfg.get("min_magnitude", 0.0)):
            continue                                    # per-survey floor
        kept.append(f)
    return kept


def _persistence(fact: Fact) -> float:
    n = fact.meta.get("periods_in_streak") or len(fact.periods)
    return min(1.0, float(n) / 12.0)


def _reader_scale(fact: Fact) -> float:
    u = (fact.uom or "").lower()
    return 1.0 if ("person" in u or "dollar" in u or "percent" in u) else 0.4


def score(fact: Fact, cfg: dict, max_magnitude: float) -> float:
    w = cfg["weights"]
    magnitude = fact.magnitude / max_magnitude if max_magnitude else 0.0
    return (w["magnitude"] * magnitude
            + w["persistence"] * _persistence(fact)
            + w["legibility"] * fact.legibility
            + w["reader_scale"] * _reader_scale(fact))


def rank(facts: list[Fact], mentions: dict[str, bool], cfg: dict) -> list[Fact]:
    mentioned_members = {k.split("|", 1)[1] for k, v in (mentions or {}).items() if v}
    max_magnitude = max((f.magnitude for f in facts), default=0.0)
    for f in facts:
        f.mentioned = any(m and m in str(v) for v in f.cut.values() for m in mentioned_members)
        f.score = score(f, cfg, max_magnitude)
        if f.mentioned:
            f.score *= float(cfg.get("mention_demotion", 0.5))
    return sorted(facts, key=lambda f: f.score, reverse=True)
