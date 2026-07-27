# Claude arm -- wave-2 Health questions, 3 runs, 2026-07-27 (A14, EXPLORATORY)

Three independent isolated agents, same 7 questions, no cross-talk. SEARCHED: yes on 21/21.

| ID | Question | Claude (3 runs) | Bing SERP |
|---|---|---|---|
| HEA-001 | mental health statistics | direct 3/3 (StatCan + CAMH/CIHI mix) | indirect (madeinca/CAMH) |
| HEA-002 | youth mental health | direct 3/3 (StatCan Daily + PHAC) | indirect (PHAC/MHRC) |
| HEA-016 | how many have a family doctor | **indirect 3/3 (OurCare/CMA, CIHI)** | **indirect (OurCare/CMA)** |
| HEA-017 | how many don't | **indirect 3/3 (OurCare/CMA)** | **indirect (OurCare/CMA)** |
| HEA-019 | unmet health care needs | direct 3/3 (StatCan tables incl. 13-10-0836-01) | indirect (StatCan as survey vehicle only) |
| HEA-024 | self-rated mental health | direct 3/3 (StatCan table 13-10-0651-01) | indirect (canada.ca/PHAC) |
| HEA-025 | does income affect health | **direct 3/3 -- 61.9 vs 70.0 years HALE** | **qualitative, NO NUMBERS** |

## The sharpest result in the study: HEA-025

Bing answers "yes, income affects health" qualitatively, with no numbers and no StatCan in
the answer. All three Claude runs independently produce StatCan's health-adjusted life
expectancy by income quintile -- **61.9 years lowest quintile vs 70.0 highest, an 8.1-year
gap** -- cited to The Daily, plus the 2019 (8.3) and 2015-17 (7.8) comparisons.

This is a rare, directly-responsive StatCan series that exactly answers the question. One
surface surfaces it three times out of three; the other gives a content-free "yes". The data
was equally available to both.

## The counter-case: HEA-016 / HEA-017

Both surfaces cite the OurCare/CMA survey and neither uses StatCan's own access-to-care
survey. Claude's runs mention StatCan's CCHS as an alternative source but still lead with
OurCare's 81%. So this is NOT a search-layer artifact -- OurCare simply owns this question in
the discourse, on every surface tested. A crawlable mirror will not fix that; it is a
question of which producer the ecosystem treats as canonical.

**This materially qualifies the wave-2 finding.** HEA-016 was recorded as the cleanest
scenario-(b) case on Bing. It is now clear that its cause is not crawlability.

## Run-to-run variability (A2 logic applied to this arm)
Citation class: stable 3/3 on all 7 questions. Values: NOT stable. HEA-001's headline came
back as 59.0% (2021), 55% (2023), and 18.3% (MHACS 2022 prevalence) across the three runs --
different measures, all correctly sourced. Same pattern as Bing: attribution is stable,
values drift.

## Behaviour worth noting
Run 3 declined to give a current unmet-needs figure at all, saying the percentages it could
find were from surveys 20+ years old under changed question wording, and pointed to the live
StatCan table instead. Run 2 warned against a "50% of Canadians don't have a family doctor"
figure in circulation as measuring something different. No Bing answer in either wave
volunteered a caveat of this kind.

## Limitations
Exploratory/secondary per A14. Claude measuring Claude. Agent SDK, not claude.ai. Mirrors are
not in this tool's search index, so this is a control surface. Coding by the study author,
not blind.
