# Index check -- 2026-08-10 (T+16 days from deployment 2026-07-25)

Pre-registered T+2-week check. Ran 2 days late (due ~2026-08-08).

Method: DuckDuckGo as a Bing-index proxy (Bing direct served a CAPTCHA on a prior attempt
and was not solved). Cache-busted queries.

## Result: PARTIALLY INDEXED -- directory page only

| Query | Result |
|---|---|
| `site:p3ji.github.io/stats` | **1 hit** -- `/stats/tables` directory page |
| `site:p3ji.github.io/stats/tables` | **1 hit** -- same directory page only |
| `"mental-health-canada" p3ji.github.io` | **No results** |

The `/tables/` index page is indexed, with its description rendered. **No individual mirror
page is indexed** -- not the wave-1 five, not the wave-2 five.

Change since 2026-07-27, when `site:p3ji.github.io/stats` returned nothing at all. So the
crawl path opened after the sitemap resubmission (Bing Webmaster showed 14/14 URLs
discovered on 2026-07-27), but discovery has not yet become indexing for the leaf pages.

## Consequences

1. **The treatment has NOT yet reached the surface being measured.** A mirror page that is
   not indexed cannot influence a composed answer. Any outcome measured today would be
   measuring an un-delivered intervention.
2. **Round 1 (~2026-08-30) stands.** No schedule change. If leaf pages are still unindexed
   then, that is itself the finding worth recording -- "crawlable and submitted was not
   sufficient for indexing within N weeks" is a real result about the mechanism, not a null.
3. **A11 is safe.** The wave-1 re-baseline (2026-07-27, 33 captures) was captured while
   nothing was indexed, so it remains a genuine pre-treatment baseline. The window closed
   behind us, not in front.
4. **No outcome data was collected today.** The primary endpoint stays 2026-10-17. This
   check looked only at index membership, never at AI answers, so there is no peeking to
   declare.

## Next
- Repeat the index check at round 1 (~2026-08-30), leaf pages specifically.
- If still unindexed by round 1, check Bing Webmaster URL Inspection for a crawl/indexing
  verdict per URL -- that distinguishes "not crawled" from "crawled and declined", which are
  very different findings.
