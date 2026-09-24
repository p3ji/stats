# Index check — 2026-08-31 (T+6 weeks from deployment)

Pre-registered T+6-week check (Round 1 milestone).

Method: DuckDuckGo as a Bing-index proxy (cache-busted queries, standardizing on the Bing index).

## Result: INDEXED — Directory page AND Leaf Pages

| Query | Result |
|---|---|
| `site:p3ji.github.io/stats/tables` | **Multiple hits** — directory page + leaf mirror pages |
| `site:p3ji.github.io/stats` | **Multiple hits** — home, report, benchmark, tables directory, and leaf pages |

### Sample of Confirmed Leaf Mirror Pages in Index:
- `https://p3ji.github.io/stats/tables/population-of-canada.html` (Wave 2)
- `https://p3ji.github.io/stats/tables/average-salary-canada.html` (Wave 1)
- `https://p3ji.github.io/stats/tables/volunteering-canada.html` (Wave 1)
- `https://p3ji.github.io/stats/tables/time-use-canada.html` (Wave 1)
- `https://p3ji.github.io/stats/tables/ai-use-businesses-canada.html` (Wave 1)
- `https://p3ji.github.io/stats/tables/charitable-donors-canada.html` (Wave 1)
- `https://p3ji.github.io/stats/tables/income-and-health-canada.html` (Wave 2)
- `https://p3ji.github.io/stats/tables/mental-health-canada.html` (Wave 2)
- `https://p3ji.github.io/stats/tables/family-doctor-canada.html` (Wave 2)

Change since 2026-08-10 (T+16 days), when only the `/stats/tables/` directory page was indexed and zero leaf pages were indexed. Discovery has now successfully converted to indexing for the leaf mirror pages.

## Consequences

1. **The treatment HAS reached the surface being measured (A4 passed).** The crawlability intervention is now physically present in the search engine's index.
2. **Round 1 re-audit proceeds.** Unlike at T+16, measuring outcomes today evaluates a live, exposed intervention rather than an undelivered one.
3. **Reference values verified (A8):** `build_mirror.py` was executed; StatCan WDS returned clean values for all 10 treatment tables, and all data values are stable relative to the 2026-07-25 deployment.

## Next
- Execute the Round 1 Re-Audit across the 26 experiment queries on the ordinary Bing SERP (`bing_serp_ai`), capturing screenshots and text evidence across 3 runs (A2).
- Perform blinded coding (A3, A15).
