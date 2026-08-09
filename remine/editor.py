"""The enforcement point for "numbers come from code, not the model".

Skills carry procedure; this file carries the checks. Every guarantee below must
stay here: a check that lives only in skill prose is not a guarantee. These tests
run with no agent present, so drift out of Python fails the suite.

Run: python remine/editor.py --brief remine/briefs/260807-dq260807a.json \
         --draft draft.json --out remine/articles/260807-dq260807a.json
"""

import argparse
import json
import re
from pathlib import Path

TOKEN = re.compile(r"\{\{([^{}]+)\}\}")
NUMERAL = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?:st|nd|rd|th)?(?![\w])")
YEAR = re.compile(r"^(19|20)\d{2}$")
ORDINAL = re.compile(r"^\d+(st|nd|rd|th)$")
STANCES = {"concretizes", "challenges"}


class BindError(Exception):
    pass


def resolve_token(token: str, facts: dict[str, dict]) -> str:
    token = token.strip()
    fact_id, _, field = token.partition(".")
    if fact_id not in facts:
        raise BindError(f"unknown fact {fact_id!r} in token {{{{{token}}}}}")
    fact = facts[fact_id]
    name, _, index = field.partition("[")
    if name not in fact:
        raise BindError(f"unknown field {name!r} on {fact_id}")
    value = fact[name]
    if index:
        try:
            value = value[int(index.rstrip("]"))]
        except (TypeError, IndexError, ValueError) as exc:
            raise BindError(f"bad index in token {{{{{token}}}}}: {exc}") from exc
    if isinstance(value, (dict, list)):
        raise BindError(f"token {{{{{token}}}}} resolves to a structure, not a value")
    return str(value)


def check_bare_numerals(text: str) -> list[str]:
    stripped = TOKEN.sub(" ", text)
    bad = []
    for match in NUMERAL.finditer(stripped):
        raw = match.group(0)
        if YEAR.match(raw) or ORDINAL.match(raw):
            continue
        bad.append(raw)
    return bad


def check_differs_from_daily(draft: dict, mentions: dict[str, bool], facts: dict[str, dict]) -> list[str]:
    """Cross-check a 'not discussed' claim against the mention map.

    mentions.py is demoted to a ranking nudge and promoted to an auditor here: if
    the editorial pass claims the Daily did not discuss a cut whose members it
    plainly named, that is a signal the article was not actually read.
    """
    mentioned = {k.split("|", 1)[1] for k, v in (mentions or {}).items() if v}
    problems = []
    for story in draft.get("stories", []):
        claim = (story.get("differs_from_daily") or "").strip().lower()
        if claim != "not discussed":
            continue
        for fact_id in story.get("fact_ids", []):
            for value in facts.get(fact_id, {}).get("cut", {}).values():
                for member in mentioned:
                    if member and member in str(value):
                        problems.append(
                            f"story {story.get('headline')!r} claims 'not discussed' "
                            f"but the Daily names {member!r} — re-read the article")
    return problems


def bind(draft: dict, brief: dict) -> dict:
    facts = {f["id"]: f for f in brief["facts"]}
    if not (draft.get("daily_story") or "").strip():
        raise BindError("daily_story is required — restate what the Daily reported")
    stories = draft.get("stories") or []
    if not 2 <= len(stories) <= 4:
        raise BindError(f"expected 2-4 stories, got {len(stories)}")

    problems = check_differs_from_daily(draft, brief.get("mentions", {}), facts)
    if problems:
        raise BindError("; ".join(problems))

    bound = []
    for story in stories:
        if not (story.get("assumption") or "").strip():
            raise BindError(f"story {story.get('headline')!r} names no assumption")
        if story.get("stance") not in STANCES:
            raise BindError(f"story {story.get('headline')!r} has stance "
                            f"{story.get('stance')!r}; expected one of {sorted(STANCES)}")
        body = story.get("body", "")
        bare = check_bare_numerals(body)
        if bare:
            raise BindError(f"bare numeral(s) {bare} in {story.get('headline')!r} — "
                            f"every number must be a {{{{fact_n.field}}}} token")
        bound.append({
            **story,
            "body": TOKEN.sub(lambda m: resolve_token(m.group(1), facts), body),
            "provenance": [
                {"id": fid, "vectors": facts[fid]["vectors"], "periods": facts[fid]["periods"],
                 "cut": facts[fid]["cut"], "table_url": brief["cube"]["table_url"]}
                for fid in story.get("fact_ids", []) if fid in facts
            ],
        })
    return {
        "date": brief["date"], "headline": draft.get("headline", ""),
        "daily_story": draft["daily_story"], "source": brief["article"],
        "cube": brief["cube"], "stories": bound,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Bind a Remine draft against its fact brief")
    ap.add_argument("--brief", required=True, type=Path)
    ap.add_argument("--draft", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    draft = json.loads(args.draft.read_text(encoding="utf-8"))
    try:
        article = bind(draft, brief)
    except BindError as exc:
        raise SystemExit(f"BIND FAILED: {exc}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(article, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"bound -> {args.out}")


if __name__ == "__main__":
    main()
