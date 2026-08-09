---
name: remine-editorial
description: Use when drafting or redrafting a Remine article from a fact brief — selecting which computed facts form a story, naming the assumption each speaks to, and writing prose whose numbers are tokens. Triggers on "draft the remine article", "redraft this brief", or being invoked by the remine skill.
---

# Remine — editorial pass

Turn one fact brief into a draft. Standalone: redraft any brief without re-running
the pipeline. That loop is the main tuning instrument for the whole project — if
drafts come out dull, the fix is usually new probes, not new prose.

**Design:** `docs/superpowers/specs/2026-08-07-remine-design.md`

## Read first

Read the whole brief, including `article.prose` — the Daily's full text. You cannot
judge what is new without knowing what was said.

## Rules

**Numbers.** Never type a number, in any field. Every number is a token:
`{{fact_3.human}}`, `{{fact_3.values[0]}}`, `{{fact_3.periods[0]}}`. Prefer `.human` — it
is already in reader-scale units. `editor.py bind` fails the build on any bare numeral, so
a typed number is not a style problem, it is a broken build. This applies to every field
you write and at any nesting depth, not just `body`: `headline`, `assumption` and
`differs_from_daily` are all published too.

**Tokens only where they belong.** Only `headline` and `body` may carry tokens.
`assumption`, `differs_from_daily`, the top-level `headline` and `daily_story` are framing
text and must contain none — including the Daily's own figures, which this pipeline never
computed and therefore cannot stand behind.

**Cite what you use.** A token may only reference a fact listed in that story's
`fact_ids`. Pulling `{{fact_7...}}` into a story that lists only `fact_1` fails the build,
because the provenance block shown to the reader would cite the wrong series.

**Restate the Daily.** `daily_story` is required and must be non-empty. A draft that
cannot say what the Daily reported did not read it.

**Selection.** Pick 2–4 facts that cohere into one piece. Coherence beats ranking:
three facts telling one story beat the three highest-scoring unrelated ones.

**The assumption.** For each story name a belief a real person holds, in the words
they would use — "housing pressure is a Toronto and Vancouver problem", "young people
are the ones struggling to find work". Mark `stance` as `concretizes` or `challenges`.
A named assumption that just paraphrases the statistic ("employment differs between
provinces") is not an assumption. Rewrite it or drop the story.

**The one-sentence test.** Every story must reduce to one sentence a non-specialist
understands, and that sentence is the headline. If you cannot write it, drop the fact
rather than dressing it up.

**`differs_from_daily`.** State what the Daily said about this cut, or exactly
`not discussed`. This is cross-checked against the mention map — a false
`not discussed` fails the bind.

**Not a definition.** If a story's interest depends on a classification or
methodology detail, drop it. That is a note, not a story.

**Voice.** Invoke the `my-voice` skill (creative mode) for the prose itself.

## Output

Write `draft.json`:

```json
{"headline": "...",
 "daily_story": "one sentence restating what the Daily reported",
 "stories": [{"headline": "...", "fact_ids": ["fact_3"],
              "assumption": "...", "stance": "concretizes",
              "differs_from_daily": "not discussed",
              "body": "prose with {{fact_3.human}} tokens"}]}
```

Then hand back for binding. Do not write article JSON directly — `bind` produces it.
