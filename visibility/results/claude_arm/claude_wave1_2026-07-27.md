# Claude arm -- wave-1 questions, 2026-07-27 (A14, EXPLORATORY / SECONDARY)

Isolated agents. Bare questions only: no repo access, no mention of Statistics Canada,
no indication a study exists. 3 agents, 11 questions, 1 run each.

**Reachability (A14 rule 4): the mirror pages are NOT in this tool's search index.**
This arm is therefore a CONTROL SURFACE, not a treatment test.

**SEARCHED: yes on 11/11.** No answer came from parametric memory alone.

| ID | Question | Claude citation | Bing SERP (modal, 3 runs) |
|---|---|---|---|
| SOC-004 | charitable donations declining | mixed -- StatCan cited, but Fraser Institute owns the headline | indirect |
| LAB-002 | avg salary by age | **indirect** -- WealthNorth/Indeed; StatCan only as a bare domain | **none (empty)** |
| LAB-003 | avg salary by province | **direct** -- SEPH table 14-10-0222-01 + The Daily, Mar 2026 | indirect |
| SOC-001 | volunteering statistics | direct | direct |
| SOC-002 | what % volunteer | **direct** -- The Daily 250623b | **none (empty)** |
| SOC-024 | housework by gender | direct -- 2 StatCan sources | direct |
| DIG-014 | businesses using AI | direct -- 2 StatCan Analysis-in-Brief | direct |
| LAB-014 | public sector employment | mixed -- TBS + LFS + The Hub | indirect |
| SOC-010 | trust in government | **direct** -- 2 StatCan + OECD/Environics/Edelman | **none (absent)** |
| SOC-016 | how religious is Canada | **direct** -- 4 StatCan incl. Census release | **indirect (Wikipedia)** |
| SOC-005 | loneliness | direct -- 4 StatCan incl. table 45-10-0048-01 | direct |

Claude: ~7 direct, 2 mixed, 1 indirect, 0 none.
Bing:     4 direct, 4 indirect, 3 none.

## Findings

**1. The three queries where Bing fails hardest are the three where Claude cites StatCan
directly.** SOC-002 and SOC-010 render no Bing answer at all across 3 runs; SOC-016 credits
Wikipedia for census figures. All three get direct, correctly-sourced StatCan citations here.
So the failure is a property of the SEARCH-INDEX layer, not of AI answering generally. That
narrows the study's thesis usefully: the problem is not "AI ignores official statistics" but
"the SEO/search layer between the public and official statistics displaces them."

**2. Where StatCan's own table lags, BOTH surfaces fall to the same SEO site.** LAB-002 is
the only query Claude answered indirectly -- citing wealthnorth.ca, the SAME domain Bing's
answer used, and StatCan only as a bare www150 homepage with no table. Claude flagged the
problem explicitly ("StatCan's official income-by-age tables lag badly... the numbers
circulating for 2025-26 are aggregator estimates, not official figures"). Publication lag,
not crawlability, is what creates the vacuum SEO fills.

**3. Ceiling effect, as with Duck.ai.** With ~7/11 already direct, there is little headroom
for a mirror to improve citation on this surface -- reinforcing that its role here is as a
comparison, not a treatment target.

**4. Unprompted methodological caution.** Several answers volunteered caveats no Bing answer
gave: that the CSBC is self-reported; that the loneliness survey was fielded during the
pandemic and is not a clean baseline; that non-government surveys use different wording and
are not comparable; that annualizing weekly earnings is not an official statistic. One
answer told the user to pull the StatCan table directly rather than trust its own figure.

## Limitations (binding, per A14)
- EXPLORATORY. Never pooled with the A1 primary outcome.
- This is Claude measuring Claude -- a self-assessment.
- Agent SDK with a web-search tool, NOT the consumer claude.ai product.
- One run per question. No noise floor established; A2's replicate logic has not been
  applied to this arm, and the Bing data shows values drift between runs even when the
  citation class does not.
- Coding done by the same agent that ran the study (me), not blind. Unlike the wave-1
  Bing coding, this has not been through an independent blind coder.

---

## Independent blind coding (2026-07-27) and where it disagreed with me

A coder with no access to the design documents re-coded this arm from these files alone:
**15 direct, 3 indirect, 0 none** across both waves. It agreed with all seven wave-2 labels
and nine of eleven wave-1 labels. Two disagreements, both recorded rather than reconciled:

- **SOC-004** -- I wrote "mixed"; the coder called it **indirect**, on the grounds that a
  headline figure owned by a think tank with StatCan alongside is the textbook indirect case.
  The coder is right and "mixed" was me avoiding a call the rubric already decides.
- **LAB-014** -- I wrote "mixed"; the coder called it **direct** but flagged it as its weakest
  call, noting it would flip to indirect if the headline headcount came from the Treasury
  Board rather than the Labour Force Survey. Unresolved; the summary text cannot settle it.

**"mixed" is not a value in the coding rubric.** It was doing work the three-way scheme does
not allow and it hid a real asymmetry -- SOC-004 and LAB-014 are not the same kind of case.
Both are re-coded to the rubric above.

## A LIMITATION THIS EXPOSED -- raw answers were not archived for this arm

The Bing arm writes every capture's raw text to `rebaseline_evidence/` **before** any coding.
This arm does not: only these curated summaries exist. The blind coder could therefore not
verify SOC-001 independently -- it recorded that it "coded purely on the file's own assertion
rather than on evidence, which makes it not independent of the label I am supposed to be
checking."

That is correct and it is a defect in how I ran this arm, not in the coding. **Before any
future Claude-arm round, archive each agent's full response verbatim** the way
`rebaseline.py record` does for Bing. Until then, this arm's codings are weaker evidence than
the Bing arm's and must not be presented as equivalent.
