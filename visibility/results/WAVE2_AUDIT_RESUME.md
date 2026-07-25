# Wave 2 baseline audit — resume marker

**Paused 2026-07-23 (mid-session, low token budget), resume next session.** Full protocol: `docs/wave2.md`.

## Evidence-storage decision (2026-07-23)
No tool available this session can write a screenshot PNG to disk (`save_to_disk` on
claude-in-chrome doesn't land anywhere findable — checked Downloads, Pictures, OneDrive,
Dropbox, all Claude/Chrome AppData dirs, full-profile scan). Wave-1's `baseline_evidence/`
PNGs (1674x1221) were produced by a different/prior working path not available now. **User
decision: inline screenshots in the chat transcript are sufficient** — do NOT chase a
file-saving mechanism further unless the user raises it again. No `.yml`/`.png` files were
added to `visibility/results/baseline_evidence/` this session; the 7 Health situation-(b)
screenshots exist only in the conversation transcript (viewable there, save manually via
right-click if wanted). CSV coding remains the durable record.

## Repo housekeeping note (2026-07-23)
Two local clones exist: `C:\Users\pushp\Documents\Projects\statcan_codr` (primary working
dir, has `.claude/`, used by this agent) and `C:\Users\pushp\Documents\Projects\stats`
(user's second clone, same origin). **Always push from statcan_codr and `git pull --ff-only`
in stats before touching files there** — today's 7 wave-2 commits sat unpushed for a while
and the two clones drifted out of sync until caught. Check `git log --oneline origin/main..HEAD`
before ending a session.

## What this is
Two-pass baseline audit of the 75-query wave-2 set (Health + Immigration + Population)
through **both** engines in lockstep. Pass 1 = code answer text (all queries); Pass 2 =
capture a11y/text evidence for GAP cases only (answerable + StatCan not cited/used/current).
Screenshot only gaps — see [[visibility-audit-screenshots]] rationale.

## Harness (validated, works)
> **SURFACE WARNING (2026-07-25).** This wave used the **ordinary Bing SERP** inline AI
> module. Wave 1 used **Bing Copilot Search** (a different surface — its a11y trees show
> "Back to Bing search"). Both were mislabelled `bing_copilot`; wave-2 rows are now
> `bing_serp_ai`. **Re-audit this wave on the SERP, not Copilot Search** — mixing them
> would make the before/after difference a surface artifact. See amendment A10 in
> `docs/mirror_experiment.md`. Do not pool wave-1 and wave-2 rates.

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

## DONE (updated 2026-07-23)
- Chrome extension (claude-in-chrome) now available -> screenshots work (in-app browser timed out). save_to_disk does NOT reach the repo filesystem; screenshots are inline-only. Evidence policy: capture ALL situation-(b) cases (StatCan number ABSENT: value_match different_metric/no_number), representative only for (a) displacement.
- **Health / Bing: 25/25 COMPLETE.** 2 clean (HEA-006 obesity, HEA-020 physical activity - both recent-Daily direct cites); 7 clean situation-(b) [screenshots captured inline this session]: HEA-001,002,016,017,019,024,025; 6 cross-org GAP-WEAK (PHAC/CCS own: HEA-008,009,012,013,015,023); ~10 (a) displacement; 1 mixed (HEA-018).
- Pilot (5, both engines): HEA-006, HEA-012, HEA-016, IMM-001, POP-001.

## PROGRESS (updated 2026-07-24, later)
- **Health / Bing: 25/25 DONE.** 2 clean-direct, 7 clean-(b) [screenshots captured], 6 cross-org, ~10 displacement.
- **Immigration / Bing: 25/25 DONE.** ZERO clean-(b). 8 displacement, 4 direct, 4 direct-no-box, 4 cross-org (IRCC/UNHCR/ICC), 3 not-collected, 1 mixed.
- **Population / Bing: 10/25** (001,002,004,006,008,018,021,022,023,025). All displacement or direct-no-box, ZERO clean-(b). Census monopoly -> conclusive; remaining 15 are routine census (birth/death/life-exp-by-prov, fertility, avg age, seniors, montreal, vs-usa, etc.) that will all be displacement.
- **Duck.ai: pilot only (5).** Not started for Imm/Pop/Health-full. It's the COMPARISON surface (~90% direct citation), NOT a gap-pool source.
- Housing: PARKED.

### KEY CONCLUSION (robust): clean scenario-(b) is a HEALTH phenomenon (competing producers PHAC/CMA/CCS/Fraser). The 7 Health clean-(b) cases are the prime mirror-treatment candidates. Census subjects (Imm/Pop) = displacement only (StatCan's own numbers uncredited to SEO/Wikipedia) -> secondary treatment candidates.

### REMAINING TO LITERALLY FINISH: Population/Bing 15 routine + Duck.ai full pass (~65). Neither changes the gap pool. Decision pending: grind for completeness vs proceed to mirrors with the gap pool already determined.

## PROGRESS (updated 2026-07-24)
- **Health / Bing: 25/25 done.** 2 clean, 7 clean-(b) [screenshots captured], 6 cross-org, ~10 displacement.
- **Immigration / Bing: 9/25 done** (001,002,004,005,007,012,016,020,023). Three-way split: census-stock -> displacement (a); recent-StatCan-article topics (intl students, TFW) -> cited DIRECTLY; IRCC-owned flow -> cross-org; softer topics -> no AI box. FEW clean (b) here.
- **Population / Bing: 3/25 done** (001,018,021) — all displacement (a), census monopoly.
- Duck.ai passes for Imm/Pop: NOT started (expect mostly direct, like Health pilot).
- Housing subject: PARKED (user decision 2026-07-24 — finish the 3 pre-registered subjects first).
- Finding so far: clean (b) is a HEALTH phenomenon (competing producers PHAC/CMA/Fraser). Census subjects (Imm/Pop) are displacement; Immigration gets direct citation where StatCan has recent analytical articles.

## TODO (in order, commit after each subject×engine batch)
1. [DONE] Health / Bing — all 25 complete.
2. Health / Duck.ai — remaining 22 (pilot did 006,012,016). Expect far fewer gaps (Duck.ai cites StatCan directly).
3. Immigration / Bing (24 left) + Duck.ai (24 left) — IMM-001 pilot done both.
4. Population / Bing (24 left) + Duck.ai (24 left) — POP-001 pilot done both.
5. Compile: gap pool (Bing column drives selection) → assign treatment/control arms
   (fresh seed, stratified by subject, SEPARATE from wave-1 tables) → build mirror pages.

## Finding so far (see docs/wave2.md "Pilot finding")
Bing rarely cites StatCan directly even when it has the number; Duck.ai (RAG chatbot) usually
does. Gap pool ≈ the Bing gaps. Duck.ai = already-good comparison surface (watch for displacement).
