"""Stage 5 — reliability gate, then salience.

The gate drops; the score ranks. Ranking is explicitly not surprise-based:
persistence *raises* a fact's score, because a large stable gap is a stronger
story than a volatile one-month swing. Anomaly hunting would invert this and
mostly surface noise.
"""

from remine.probes import Fact

def _uses_aggregate(fact: Fact, cfg: dict) -> bool:
    """Exact membership, never substring.

    This is a silent-drop path, so a false positive discards a real story with
    no trace. A substring test would drop any member whose name merely contains
    an aggregate's name (a geography containing "Canada", say).
    """
    aggregates = {name
                  for names in (cfg.get("aggregate_members") or {}).values()
                  for name in names}
    members = {str(v) for v in fact.cut.values()}
    members |= {str(fact.meta[k]) for k in ("high", "low", "leader", "trailer")
                if fact.meta.get(k)}
    # A pair probe's cut value may be a composite built from two members, so
    # also compare the parts a composite is built from.
    members |= {part.strip() for m in list(members) for part in m.split(" vs ")}
    return bool(members & aggregates)


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
    n = (fact.meta.get("periods_in_streak")
         or fact.meta.get("periods_observed")
         or len(fact.periods))
    return min(1.0, float(n) / 12.0)


def _reader_scale(fact: Fact) -> float:
    u = (fact.uom or "").lower()
    return 1.0 if ("person" in u or "dollar" in u or "percent" in u) else 0.4


# A level gap concretizes what a reader already believes; a change can
# challenge it. Both belong in a brief, but the spec's premise leans on the
# second, and magnitude alone will never surface it.
_CHANGE_PROBES = {"gap_trend", "rank_reversal", "streak", "long_run_compare", "share_of_total"}


def _change_story(fact: Fact) -> float:
    return 1.0 if fact.probe in _CHANGE_PROBES else 0.0


def score(fact: Fact, cfg: dict, max_magnitude: float) -> float:
    w = cfg["weights"]
    magnitude = fact.magnitude / max_magnitude if max_magnitude else 0.0
    return (w["magnitude"] * magnitude
            + w["persistence"] * _persistence(fact)
            + w["legibility"] * fact.legibility
            + w["reader_scale"] * _reader_scale(fact)
            + w.get("change_story", 0.0) * _change_story(fact))


def rank(facts: list[Fact], mentions: dict[str, bool], cfg: dict) -> list[Fact]:
    mentioned_members = {k.split("|", 1)[1] for k, v in (mentions or {}).items() if v}
    # Normalise within each probe. Globally, the magnitude of a *change* is
    # dwarfed by the magnitude of a *level gap*, so change findings could never
    # reach the brief no matter how striking they were.
    peak: dict[str, float] = {}
    for f in facts:
        peak[f.probe] = max(peak.get(f.probe, 0.0), f.magnitude)
    for f in facts:
        f.mentioned = any(m and m in str(v) for v in f.cut.values() for m in mentioned_members)
        f.score = score(f, cfg, peak.get(f.probe, 0.0))
        if f.mentioned:
            f.score *= float(cfg.get("mention_demotion", 0.5))
    return sorted(facts, key=lambda f: f.score, reverse=True)
