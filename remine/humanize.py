"""Convert cube units into units a person feels.

Readers never see "Persons in thousands, seasonally adjusted" unless the caveat
is itself the point. Because this is deterministic and runs before drafting, an
article cannot silently fall back to raw cube units.
"""

_SCALARS = {"units": 1, "": 1, "tens": 10, "hundreds": 100,
            "thousands": 1_000, "millions": 1_000_000, "billions": 1_000_000_000}


def _scale(value: float, scalar_factor: str) -> float:
    return value * _SCALARS.get((scalar_factor or "").strip().lower(), 1)


def _round_people(n: float) -> int:
    n = abs(n)
    step = 1_000 if n >= 10_000 else 100 if n >= 1_000 else 10
    return int(round(n / step) * step)


def humanize(value: float, uom: str, scalar_factor: str, decimals: int = 1) -> str:
    u = (uom or "").strip().lower()
    if "person" in u:
        return f"about {_round_people(_scale(value, scalar_factor)):,} people"
    if "percent" in u:
        return f"{value:.{decimals}f}%"
    if "dollar" in u:
        return f"${_scale(value, scalar_factor):,.0f}"
    return f"{value:.{decimals}f} {uom}"


def humanize_delta(delta: float, uom: str, scalar_factor: str, decimals: int = 1) -> str:
    u = (uom or "").strip().lower()
    if "person" in u:
        word = "more" if delta >= 0 else "fewer"
        return f"about {_round_people(_scale(delta, scalar_factor)):,} {word} people"
    if "percent" in u:
        word = "higher" if delta >= 0 else "lower"
        return f"{abs(delta):.{decimals}f} percentage points {word}"
    if "dollar" in u:
        word = "more" if delta >= 0 else "less"
        return f"${abs(_scale(delta, scalar_factor)):,.0f} {word}"
    word = "higher" if delta >= 0 else "lower"
    return f"{abs(delta):.{decimals}f} {uom} {word}"


def humanize_delta_bare(delta: float, uom: str, scalar_factor: str, decimals: int = 1) -> str:
    """Same quantity as humanize_delta, with no trailing direction word.

    humanize_delta returns a standalone fragment ("53.6 percentage points
    higher"), which reads correctly only as a full clause. Mid-sentence, after
    something like "a difference of", the direction word is ungrammatical —
    this is the same magnitude with nothing to strip.
    """
    u = (uom or "").strip().lower()
    if "person" in u:
        return f"about {_round_people(_scale(delta, scalar_factor)):,} people"
    if "percent" in u:
        return f"{abs(delta):.{decimals}f} percentage points"
    if "dollar" in u:
        return f"${abs(_scale(delta, scalar_factor)):,.0f}"
    return f"{abs(delta):.{decimals}f} {uom}"
