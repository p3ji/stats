# Claude arm -- wave 1, THREE RUNS, raw-archived and blind-coded (A14, EXPLORATORY)

Supersedes the single-run wave-1 figures in `claude_wave1_2026-07-27.md`. Three isolated
agents, identical eleven questions, no cross-talk. Raw responses archived VERBATIM to
`raw/claude_w1_run{1,2,3}_2026-07-27.txt` **before** any coding, then coded by an agent with
no access to the design documents or to any prior analysis file.

`searched: yes` on 33/33. Nothing came from parametric memory.

## Modal citation class

| ID | Question | Claude (3 runs) | Bing SERP (3 runs) |
|---|---|---|---|
| SOC-004 | charitable donations declining | direct 2/3 | indirect 3/3 |
| LAB-002 | avg salary by age | direct 2/3 | **none 3/3** |
| LAB-003 | avg salary by province | direct 3/3 | indirect 3/3 |
| SOC-001 | volunteering statistics | direct 3/3 | direct 3/3 |
| SOC-002 | what % volunteer | direct 3/3 | **none 3/3** |
| SOC-024 | housework by gender | direct 3/3 | direct 3/3 |
| DIG-014 | businesses using AI | direct 3/3 | direct 3/3 |
| LAB-014 | public sector employment | direct 3/3 | indirect 3/3 |
| SOC-010 | trust in government | direct 3/3 | **none 3/3** |
| SOC-016 | how religious is Canada | direct 3/3 | indirect 3/3 |
| SOC-005 | loneliness | direct 3/3 | direct 3/3 |

**Claude: 11/11 modally direct. Bing: 4 direct, 4 indirect, 3 none.**

## TWO CORRECTIONS TO EARLIER CLAIMS IN THIS ARM

**1. "Roughly 7 of 11 direct" was based on ONE run and is superseded.** With three runs and
blind coding the figure is **11/11 modally direct**. The contrast with Bing is larger than
first reported, not smaller.

**2. "Citation class: stable 3/3" was WRONG for this arm.** That claim came from the wave-2
Health questions and was carried over without evidence. On wave 1 with three runs, **2 of 11
questions flip**:
- **SOC-004**: direct, direct, indirect. Run 3 leads its sources with two Fraser Institute
  commentaries and puts the StatCan Daily fourth, never naming Statistics Canada in the
  answer text -- while giving the same StatCan tax-filer numbers.
- **LAB-002**: none, direct, direct. Run 1 **refused to give any figures at all**, naming the
  authoritative StatCan table and warning that circulating numbers are blog estimates.

## THE NOISE FLOOR, AND IT CUTS THE OTHER WAY

| Arm | Citation-class flips | Noise floor |
|---|---|---|
| Bing SERP | 0/11 | 0% |
| Claude | 2/11 | **18%** |

**Claude is the NOISIER surface on attribution, not the cleaner one.** Any post-treatment
movement on this arm smaller than ~18% is indistinguishable from run-to-run variation. Bing,
whatever else is wrong with it, is deterministic on whether and whom it credits.

## Value instability (same class, different numbers)
- **LAB-003**: the top province FLIPS between runs -- run 1 Alberta $1,371/wk highest, run 2
  Ontario $1,357.26 highest. Different reference months (Mar 2026 vs Oct 2025).
- **DIG-014**: identical headline series (6.1/12.2/19.2%) but sector leaders differ
  materially -- information industries 35.6% (run 1) vs 42.3% (run 2).
- **SOC-005**: runs 1-2 give 13% with a full age gradient; run 3 gives "roughly one in ten",
  drops the gradient, and substitutes senior-specific figures.
- **LAB-014**: same 4.597M headline but opposite narrative -- run 1 stresses a 950,000-job
  run-up, run 2 says growth "largely flattened".

## Behaviour the Bing arm never showed
Two runs volunteered unprompted confidence notes naming their own weakest answers, and both
named the salary questions -- exactly where the blind coder independently found the largest
divergences. One run declined to give figures rather than repeat aggregator estimates.

## Limitations
Exploratory/secondary per A14. Claude measuring Claude. Agent SDK, not claude.ai. Mirrors are
absent from this tool's search index, so this remains a control surface. Coding is now blind
and raw-archived, closing the defect recorded in the earlier file.
