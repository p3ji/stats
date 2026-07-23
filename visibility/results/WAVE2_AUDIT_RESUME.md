# Wave 2 baseline audit — resume marker

**Paused 2026-07-22, resume next session.** Full protocol: `docs/wave2.md`.

## What this is
Two-pass baseline audit of the 75-query wave-2 set (Health + Immigration + Population)
through **both** engines in lockstep. Pass 1 = code answer text (all queries); Pass 2 =
capture a11y/text evidence for GAP cases only (answerable + StatCan not cited/used/current).
Screenshot only gaps — see [[visibility-audit-screenshots]] rationale.

## Harness (validated, works)
- **Bing:** `https://www.bing.com/search?q=<query>` → `get_page_text` (~1500 chars). The
  inline AI answer + source rail is in the page text. 2 tool calls/query. NOTE: the
  `computer` screenshot action TIMES OUT on Bing SERPs — rely on text/a11y evidence.
- **Duck.ai:** navigate `https://duck.ai` (fresh chat per query) → `read_page` interactive
  → click textbox ref → type `"<question> What's the source?"` → click Send ref → `wait 9s`
  → `get_page_text`. Terms gate already accepted (session persists); model tier shows
  "Fast" (wave 1 used GPT-5.4-nano — not held identical, note it).

## Output files (append as you go)
- `visibility/results/baseline_bing_wave2_2026-07-22.csv`  (schema: run_date,engine,id,
  subject,arm,query_asked,answerable,citation_class,cited_sources,answer_value,statcan_value,
  statcan_vintage_cited,best_available_vintage,value_match,screenshot,note)
- `visibility/results/baseline_duckai_wave2_2026-07-22.csv` (same + a `model` column)
- Keep `arm` = `tbd` (arms are assigned AFTER the full baseline, per the pre-reg selection rule).
- In `screenshot`: `GAP:<name>` for gaps, `GAP-WEAK:` for cross-org (PHAC/CIHI), `n/a (...)` for clean.

## DONE
- Pilot (5, both engines): HEA-006, HEA-012, HEA-016, IMM-001, POP-001.
- Health / Bing: 10 of 25 — coded IDs: 001, 003, 005, 006, 012, 016, 017, 019, 022 (+006/012/016 from pilot).
  Result so far: 9 gaps, 1 clean (HEA-006 obesity, StatCan CHMS direct). Every other health query =
  intermediary (Statista/Wikipedia/madeinca/Global News/OurCare/Fraser/Health Canada) owns the number.

## TODO (in order, commit after each subject×engine batch)
1. Health / Bing — remaining 15: HEA 002,004,007,008,009,011,013,014,015,018,020,021,023,024,025.
2. Health / Duck.ai — remaining 20 (have 006,012,016 pilot... actually pilot did 006,012,016; need the other 22).
3. Immigration / Bing (24 left) + Duck.ai (24 left) — IMM-001 pilot done both.
4. Population / Bing (24 left) + Duck.ai (24 left) — POP-001 pilot done both.
5. Compile: gap pool (Bing column drives selection) → assign treatment/control arms
   (fresh seed, stratified by subject, SEPARATE from wave-1 tables) → build mirror pages.

## Finding so far (see docs/wave2.md "Pilot finding")
Bing rarely cites StatCan directly even when it has the number; Duck.ai (RAG chatbot) usually
does. Gap pool ≈ the Bing gaps. Duck.ai = already-good comparison surface (watch for displacement).
