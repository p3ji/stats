---
name: remine
description: Use when re-mining a Statistics Canada Daily release into new articles — running the Remine pipeline for a date, drafting the articles, binding them, and publishing to /remine/. Triggers on "remine 260807", "re-mine today's Daily", "run Remine".
---

# Remine — release workflow

Turns one Daily release into published re-mined articles.

**Design:** `docs/superpowers/specs/2026-08-07-remine-design.md`

## The boundary that matters

Python carries the checks; this skill carries the procedure. Never work around a
failure from `editor.py` by editing the check, loosening it, or hand-writing the
output JSON. A bind failure is information — usually that the draft did not
actually engage with the Daily article.

## Steps

1. **Generate briefs.**
   `python remine/generate.py --date <YYMMDD>`
   Briefs land in `remine/briefs/`. If no facts survive the gate, stop and report —
   do not lower the gate to produce output.

2. **Draft each article.** For each brief, invoke the `remine-editorial` skill with
   that brief's path. Runs in the main session so the user sees the drafting.

3. **Bind each draft.**
   `python remine/editor.py --brief remine/briefs/<f>.json --draft <draft>.json --out remine/articles/<f>.json`

4. **Resolve any bind failure by fixing the draft**, not the checker:
   - *bare numeral* — replace the literal with a `{{fact_n.field}}` token
   - *unknown fact / unknown field* — check the brief for the real id and field
   - *claims 'not discussed' but the Daily names X* — re-read the Daily prose in the
     brief; either the claim is wrong, or the mention is incidental and the
     `differs_from_daily` line should say what the Daily actually said about it

5. **Update the feed.** Add the new article to `remine/articles/index.json` (newest
   first): `{"file","date","headline","source_title","source_url"}`.

6. **Verify the site renders** — start the `dashboard` config in `.claude/launch.json`
   and open `/remine/`. Confirm each story shows its numbers, assumption, and
   provenance block.

7. **Commit** the article JSON and the updated index. Never commit `remine/briefs/`
   or `remine/cache/` — both are gitignored.
