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

# Publishing is gated off until the limitations in
# docs/remine-known-limitations.md are closed — chiefly that quantity words
# written as hyphenated compounds ("one-third") still bypass the guard, which is
# how a wrong quantitative claim reached the first (withdrawn) article. bind()
# stays enabled: drafting and inspecting an article is safe, appearing on the
# public feed is not. Flip this to True once that regex is fixed and a human has
# read a bound draft end to end.
PUBLISHING_ENABLED = False

TOKEN = re.compile(r"\{\{([^{}]+)\}\}")
NUMERAL = re.compile(r"(?<![\w])(?:\d[\d,]*(?:\.\d+)?|\.\d+)(?:st|nd|rd|th)?(?![\w])")
# A number spelled in words is still a number. "nearly double" shipped a wrong
# 2.5x ratio past every digit guard in the first article.
_QUANTITY_WORDS = re.compile(
    r"(?<![\w-])("
    r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|"
    r"half|third|quarter|double|triple|twice|thrice|dozen"
    r")(?![\w-])", re.I)
YEAR = re.compile(r"^(19|20)\d{2}$")
ORDINAL = re.compile(r"^\d+(st|nd|rd|th)$")
STANCES = {"concretizes", "challenges"}
# Only these two story fields may carry {{fact_n.field}} tokens; both are
# substituted from computed facts. Every other string field in a story is
# published as typed, so it must contain neither a token nor a bare numeral.
_TOKEN_FIELDS = {"headline", "body"}
# `stance` is validated against STANCES; the others are structure, not prose.
_EXEMPT_FIELDS = {"stance", "fact_ids", "provenance"}


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
        raw_claim = story.get("differs_from_daily") or ""
        claim = raw_claim.strip().lower()
        if claim != "not discussed":
            # Every story is audited now, not only ones claiming the magic
            # string — a blank or missing differs_from_daily is exactly the
            # kind of unread-article signal this auditor exists to catch.
            if not raw_claim.strip():
                problems.append(
                    f"story {story.get('headline')!r} has an empty differs_from_daily "
                    f"— state what the Daily said about this cut, or exactly "
                    f"'not discussed'")
            continue
        for fact_id in story.get("fact_ids", []):
            for value in facts.get(fact_id, {}).get("cut", {}).values():
                for member in mentioned:
                    if member and member in str(value):
                        problems.append(
                            f"story {story.get('headline')!r} claims 'not discussed' "
                            f"but the Daily names {member!r} — re-read the article")
    return problems


def _walk_strings(value, path: str):
    """Yield (path, text) for every string anywhere inside value, keys included.

    Checking only top-level strings left prose reachable by nesting it in a
    list or dict, which shipped unresolved tokens and bare numerals into the
    published JSON. There must be nowhere to hide a string. A raw numeric leaf
    (e.g. a story field {"count": 4000}) bypassed every string check entirely,
    and dict keys were never walked at all (e.g. {"53.6 points": "yes"}).
    """
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, bool):
        return
    elif isinstance(value, (int, float)):
        # A story field has no business carrying a raw number; it would bypass
        # every check and be published as typed.
        raise BindError(f"numeric value {value!r} at {path} — publish numbers via a "
                        f"{{{{fact_n.field}}}} token, never as a raw field value")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield f"{path}.<key>", str(key)
            yield from _walk_strings(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            yield from _walk_strings(item, f"{path}[{i}]")


def _no_numerals(text: str, where: str) -> None:
    bare = check_bare_numerals(text)
    if bare:
        raise BindError(f"bare numeral(s) {bare} in {where} — every number must be a "
                        f"{{{{fact_n.field}}}} token so it comes from computed data")


def _no_quantity_words(text: str, where: str) -> None:
    found = sorted({m.group(0).lower() for m in _QUANTITY_WORDS.finditer(TOKEN.sub(" ", text or ""))})
    if found:
        raise BindError(
            f"quantity word(s) {found} in {where} — a number spelled in words is still a "
            f"number and is not checked against the data; use a {{{{fact_n.field}}}} token "
            f"or rewrite without the comparison")


def _no_tokens(text: str, where: str) -> None:
    if TOKEN.search(text or ""):
        raise BindError(f"{where} is framing text and cannot carry fact tokens")


def bind(draft: dict, brief: dict) -> dict:
    facts = {f["id"]: f for f in brief["facts"]}
    if not (draft.get("daily_story") or "").strip():
        raise BindError("daily_story is required — restate what the Daily reported")
    stories = draft.get("stories") or []
    if not 2 <= len(stories) <= 4:
        raise BindError(f"expected 2-4 stories, got {len(stories)}")

    # Framing text is published too, so it is held to the same standard. It
    # carries no tokens because it makes no claim about our computed data —
    # including the Daily's own headline number here would publish a figure
    # this pipeline never verified.
    for field in ("headline", "daily_story"):
        _no_numerals(draft.get(field, ""), f"draft {field!r}")
        _no_quantity_words(draft.get(field, ""), f"draft {field!r}")
        _no_tokens(draft.get(field, ""), f"draft {field!r}")

    problems = check_differs_from_daily(draft, brief.get("mentions", {}), facts)
    if problems:
        raise BindError("; ".join(problems))

    bound = []
    for story in stories:
        label = story.get("headline")
        if not (story.get("assumption") or "").strip():
            raise BindError(f"story {label!r} names no assumption")
        if story.get("stance") not in STANCES:
            raise BindError(f"story {label!r} has stance "
                            f"{story.get('stance')!r}; expected one of {sorted(STANCES)}")
        # Check every string field by default rather than an enumerated list.
        # Enumerating invites a slow leak: each new field a drafter adds is
        # unguarded until someone remembers it, and `assumption` was exactly
        # that leak. Default-deny, with the two token-bearing fields named.
        for field, value in story.items():
            if field in _EXEMPT_FIELDS:
                continue
            for path, text in _walk_strings(value, field):
                _no_numerals(text, f"story {label!r} {path}")
                _no_quantity_words(text, f"story {label!r} {path}")
                if field not in _TOKEN_FIELDS:
                    _no_tokens(text, f"story {label!r} {path}")

        # A token may only cite a fact the story itself claims as a source.
        # Otherwise a story could show fact_7's number under fact_1's
        # provenance block, and the audit trail would point at the wrong series.
        allowed = set(story.get("fact_ids", []))

        def _resolve(match, _allowed=allowed, _label=label):
            token = match.group(1).strip()
            fact_id = token.partition(".")[0]
            if fact_id not in _allowed:
                raise BindError(
                    f"story {_label!r} uses {{{{{token}}}}} but does not list "
                    f"{fact_id} in fact_ids — its provenance would cite the wrong series")
            return resolve_token(token, facts)

        bound.append({
            **story,
            "headline": TOKEN.sub(_resolve, story.get("headline", "")),
            "body": TOKEN.sub(_resolve, story.get("body", "")),
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


ARTICLES_DIR = Path(__file__).parent / "articles"
INDEX_FIELDS = ("file", "date", "headline", "source_title", "source_url")


def rebuild_index(articles_dir: Path = ARTICLES_DIR) -> list[dict]:
    """Regenerate index.json from the bound articles themselves.

    The feed's headline is rendered straight from this file and never passed
    through bind(), so a hand-typed index.json can drift from — or simply
    misquote — the article it is supposed to summarize. Generating it from
    each article's own bound fields closes that gap.
    """
    entries = []
    for path in sorted(articles_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        article = json.loads(path.read_text(encoding="utf-8"))
        entries.append({
            "file": path.name,
            "date": article.get("date", ""),
            "headline": article.get("headline", ""),
            "source_title": article.get("source", {}).get("title", ""),
            "source_url": article.get("source", {}).get("url", ""),
        })
    entries.sort(key=lambda e: e["date"], reverse=True)
    index_path = articles_dir / "index.json"
    index_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    return entries


def main() -> None:
    ap = argparse.ArgumentParser(description="Bind a Remine draft against its fact brief")
    ap.add_argument("--brief", type=Path)
    ap.add_argument("--draft", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--rebuild-index", action="store_true",
                    help="regenerate remine/articles/index.json from the bound articles "
                         "there, instead of binding a draft")
    args = ap.parse_args()

    if args.rebuild_index:
        if not PUBLISHING_ENABLED:
            raise SystemExit(
                "publishing is gated off: see docs/remine-known-limitations.md. "
                "bind still works — set PUBLISHING_ENABLED = True in remine/editor.py "
                "once the quantity-word guard covers hyphenated compounds and a human "
                "has read a bound draft.")
        entries = rebuild_index()
        print(f"index.json <- {len(entries)} article(s)")
        return

    if not (args.brief and args.draft and args.out):
        raise SystemExit("--brief, --draft and --out are required unless --rebuild-index is set")
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
