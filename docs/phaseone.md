# Ottawa Global Benchmark Engine: Implementation Plan

> **Rev 2 (2026-07-09).** Key changes from Rev 1: added census reality-check and a future census-integration phase; incorporated the `statcan_mcp` prototype as prior art; widened the schema for lineage and comparability; hardened the MCP query tool; fixed deployment details (cron is UTC, commit permissions, data sanity gates).

## Status (2026-07-10): Phases 1–4 built and deployed

**Live:** https://p3ji.github.io/statcan_codr/

- **Phase 1** — [`pipeline/indicators.yaml`](../pipeline/indicators.yaml): 7 indicators, 22 of 28 (city, indicator) cells confirmed against live APIs (StatCan WDS, FRED, ABS SDMX, Statistics Finland PxWeb). Expanded 2026-07-10 beyond the original 4 (unemployment_rate, participation_rate, tech_sector_employment_share, shelter_cpi) with `employment_rate`, `new_housing_price_index`, and `population` — discovered directly against the StatCan WDS API (`getCubeMetadata` / `getSeriesInfoFromCubePidCoord`) without needing the `mcp-statcan` tool. `population` has full 4-city coverage at notably better granularity than the labour indicators — true GCCSA level for Adelaide, true municipality level for Helsinki (both better than the region-level proxies the labour-force data was stuck with). Remaining `todo`: Austin participation_rate (no MSA-level source exists in FRED/LAUS), Adelaide and Helsinki tech_sector_employment_share (no regional industry breakdown found), Helsinki shelter_cpi (Finland's CPI appears national-only), employment_rate and new_housing_price_index peer cells (Ottawa-only so far, discovery_notes record what's already known), and all four cities' postsecondary_attainment_rate (deliberately deferred to Phase 6 — census-sourced).
- **Phase 2** — [`pipeline/extract.py`](../pipeline/extract.py): fetchers for all four sources, `derived` (numerator/denominator) and `unit_multiplier` (for cross-source unit normalization, e.g. FRED population in thousands) support, validation gate, writes `public/data/global_cities.parquet` (~27 KB, 2795 rows). Bypasses `mcp-statcan`'s broken bulk-fetch tools by calling WDS/FRED/ABS/PxWeb directly with `requests`.
- **Phase 3** — not built. Skipped for this pass to prioritize shipping the dashboard; the manifest and extractor are reusable for it later.
- **Phase 4** — [`index.html`](../index.html) / [`app.js`](../app.js) / [`style.css`](../style.css) at the repo root (not a `dashboard/` subfolder — see below): DuckDB-Wasm + Chart.js, index-baseline and divergence-delta views, indicator/peer-city dropdowns, graceful "not yet available" messaging for unresolved cells, per-city `geo_note` caveats shown inline, plus a dedicated Methodology section explaining the indexing technique (base-100 rebasing, per-comparison base date, last-observation-carried-forward alignment, and what indexing does/doesn't fix). Verified locally in-browser before deploying.
- **Phase 5** — GitHub Pages via [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml). **Layout note:** the site lives at repo root, not `dashboard/`, because GitHub Pages' "Deploy from a branch" source only supports the repo root or `/docs` — keeping `index.html` at root means the site works under either Pages source mode (Actions-based or branch-based), not just the one this plan originally assumed. No scheduled re-extraction job yet — running `extract.py` and committing the refreshed Parquet is still manual.

**Known rough edges to fix before calling this done:**
- Index-baseline chart anchors both series to their **shared** overlap start date (fixed during testing — an earlier version anchored each series to its own first-ever point, which produced a meaningless comparison when one series started decades before the other).
- Mobile layout has no horizontal overflow but chart tick labels are dense on narrow screens — not tuned further.
- No scheduled sync (Phase 5.2's weekly GitHub Action) — data goes stale until someone reruns `python pipeline/extract.py` and pushes.

## Prior art: the `statcan_mcp` prototype

`C:\Users\pushp\Documents\Projects\statcan_mcp` already proved out most of the architecture on real census data (2021 Census table 98-10-0403, education × occupation × field of study):

*   **`etl_to_parquet.py`** — streams a multi-GB census bulk ZIP as chunked CSV → filters → snappy Parquet. This chunked-ZIP-streaming pattern is essential for census tables (full CSVs are enormous) and should be ported into `pipeline/` as a reusable fetcher, not rewritten.
*   **`dashboard.js` + `dashboard.html`** — DuckDB-Wasm querying a local Parquet, with NOC/CIP classification groupings. Validates the entire Phase 4 approach; reuse its DuckDB-Wasm bootstrap code.
*   **`.cursor/mcp.json`** — the working MCP config: `statcan-mcp-server` v0.7.15 (= [Aryan-Jhaveri/mcp-statcan](https://github.com/Aryan-Jhaveri/mcp-statcan), pip-installed at `C:\Users\pushp\AppData\Roaming\Python\Python314\Scripts\statcan-mcp-server.exe`, stdio transport).

What the prototype **didn't** cover — and this plan adds: multi-source international data, a harmonized long/tidy schema, a custom analytical MCP layer, and automated deploy.

## Reality check: the 2026 Census timeline

The motivation for this project is the upcoming census data, but note the release schedule — nothing ships before **Nov 18, 2026** (geographic/reference products), and the substantive tables land through 2027:

| Date | Release |
| :--- | :--- |
| Feb 10, 2027 | Population and dwelling counts |
| May 5, 2027 | Age, gender, type of dwelling |
| Jul 14, 2027 | Families, households, **income** |
| Sep 8, 2027 | Language, **housing** |
| Dec 1, 2027 | **Labour**, commuting, **education** |

So this MVP deliberately runs on **monthly/quarterly indicators** (LFS, CPI, housing price indexes) to build and battle-test the full pipeline now. The schema and pipeline are designed so census indicators (5-yearly, point-in-time) drop in later with no restructuring — see Phase 6.

---

## Phase 1: Conversational Target Discovery
**Goal:** Produce a machine-readable manifest (`pipeline/indicators.yaml`) mapping every (city, indicator) pair to an exact source series ID.

### Step 1.1: Connect the Live StatCan MCP
Use the already-installed **`statcan-mcp-server`** ([Aryan-Jhaveri/mcp-statcan](https://github.com/Aryan-Jhaveri/mcp-statcan)) — the same server the prototype ran. Register it in **this repo's `.mcp.json`** so it's testable inside Claude Code (copy the config from the prototype's `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "mcp-statcan": {
      "command": "C:\\Users\\pushp\\AppData\\Roaming\\Python\\Python314\\Scripts\\statcan-mcp-server.exe",
      "args": ["--transport", "stdio"]
    }
  }
}
```

While using it for discovery (Step 1.2), keep notes on where it falls short — those gaps are the design input for the `statcan_codr` library and custom MCP layer this repo exists to build. *(Fallback if it disappoints: [`pipeworx-io/mcp-statscan`](https://github.com/pipeworx-io/mcp-statscan), keyless and WDS-direct.)*

**Confirmed gap (found during Ottawa discovery, 2026-07-10):** `get_bulk_vector_data_by_range` and `get_changed_series_data_from_vector` both throw HTTP errors (404/406) against valid vectors on the real WDS API. `get_series_info` / `get_series_info_from_vector` work fine and were used to round-trip-verify all resolved vector IDs instead. Phase 2's `extract.py` needs bulk historical pulls — either work around this in the custom fetcher (call the WDS bulk endpoint directly rather than through this MCP) or budget time to fix upstream.

### Step 1.2: Identify Ottawa Vectors
Use the MCP to crawl the WDS registry and isolate exact Vector IDs for **Ottawa–Gatineau (CMA)** across three domains:
*   **Labour Force:** participation rate, unemployment rate, and professional/scientific/technical services employment share (NAICS 54). *(LFS 3-month moving averages at CMA level.)* **Confirmed 2026-07-10:** unemployment/participation are live monthly vectors (Table 14-10-0459), but the old monthly CMA×industry cubes are archived — NAICS-54 share is now only available as an annual derived figure (Table 14-10-0468, numerator ÷ denominator), a real frequency downgrade vs. the other two indicators. Flag this on the dashboard rather than silently resampling.
*   **Real Estate & Cost of Living:** Shelter CPI (Ottawa–Gatineau, Ontario part) and/or New Housing Price Index by CMA. *(Note: MLS benchmark prices are CREA, not StatCan.)*
*   **Demographics:** post-secondary attainment rate. **Census-sourced** — the 2021 value is the latest until Dec 2027. Store it as a static point-in-time observation, not a monthly series.

### Step 1.3: Document International Mappings
Research the equivalent series for each peer and record the exact series/dataflow IDs in the manifest:
*   **Austin, USA:** FRED API, Austin–Round Rock MSA series. *(Requires a free API key — store as env var / GitHub secret, never commit.)*
*   **Adelaide, Australia:** ABS Data API (SDMX, no key) — Greater Adelaide (GCCSA) labour force series.
*   **Helsinki, Finland:** Statistics Finland PxWeb API or Eurostat metro-region datasets (both keyless).

### Step 1.4: Record Comparability Caveats (new)
Cross-country levels are **not** directly comparable: unemployment definitions differ (e.g., Canadian LFS vs. US CPS concepts — Canadian rates run ~1 pp higher on definition alone), and CMA ≠ MSA ≠ GCCSA ≠ metro region. For each indicator, record in the manifest: geography definition, concept notes, and whether **level comparison** is defensible or only **trend/index comparison** is. The dashboard (Phase 4) leans on indexed views for exactly this reason.

**Done when:** `pipeline/indicators.yaml` exists with a resolvable series ID + geography note for every (city, indicator) pair.

---

## Phase 2: Building the Unified Local Pipeline
**Goal:** A lightweight Python script that pulls all sources, harmonizes them, and writes one Parquet file.

### Step 2.1: Implement the Extractor Script (`pipeline/extract.py`)
One fetcher per source (`statcan_wds`, `fred`, `abs_sdmx`, `pxweb`), each driven by `indicators.yaml` — no hardcoded series IDs in code. Use `requests`; keep each fetcher ~50 lines.

*Side benefit:* the `statcan_wds` fetcher is the seed of the `statcan_codr` library this repo exists for. Write it as a clean, importable module, not a script-local function.

### Step 2.2: Establish a Standardized Schema
Long/tidy format, with lineage columns so every value is traceable to its source:

| Column | Example | Notes |
| :--- | :--- | :--- |
| `city` | Ottawa | |
| `indicator` | unemployment_rate | controlled vocabulary from the manifest |
| `ref_date` | 2026-06-01 | first of period |
| `value` | 6.2 | |
| `unit` | percent | |
| `source` | statcan_wds | |
| `source_series_id` | v1234567 | vector ID / FRED ID / SDMX key |
| `geo_note` | CMA: Ottawa–Gatineau | comparability flag from Step 1.4 |
| `retrieved_at` | 2026-07-09T14:00Z | |

### Step 2.3: Validate, then Compile to Local Parquet
Before writing, run sanity checks: non-empty per (city, indicator), values within plausible ranges, `ref_date` monotonic, no regression in row count vs. the previous file. **Fail loudly rather than write a bad file** — the deploy pipeline (Phase 5) depends on this gate. Then export via `duckdb` to `public/data/global_cities.parquet` (repo root — see Phase 4's layout note).

*(Size expectation: 4 cities × ~6 indicators × ~10 years monthly ≈ a few thousand rows — well under 1 MB, not ~20 MB. Trivial to bundle and version.)*

---

## Phase 3: Setting Up Your Local Analytical SQL-MCP Server
**Goal:** A custom MCP server for conversing with the benchmark dataset — and the first real MCP authored in this repo.

### Step 3.1: Initialize FastMCP
Create `mcp-server/server.py`.

### Step 3.2: Create the Query Tool (hardened)
One flexible SQL tool, plus a tiny discovery tool so the LLM never guesses column values. Fixes vs. Rev 1: accept a **full SELECT** (not an interpolated WHERE fragment), resolve the Parquet path relative to `__file__` (Claude launches MCP servers from an arbitrary cwd), open read-only, and cap output rows.

```python
from pathlib import Path
import duckdb
from mcp.server.fastmcp import FastMCP

DATA = Path(__file__).resolve().parent.parent / "public" / "data" / "global_cities.parquet"
MAX_ROWS = 200

mcp = FastMCP("Ottawa Global Benchmarks")

def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"CREATE VIEW benchmarks AS SELECT * FROM read_parquet('{DATA.as_posix()}')")
    return con

@mcp.tool()
def list_indicators() -> str:
    """Lists available cities, indicators, units, and date ranges in the benchmarks table."""
    return _connect().execute(
        "SELECT city, indicator, unit, min(ref_date) AS from_date, max(ref_date) AS to_date, "
        "count(*) AS n FROM benchmarks GROUP BY ALL ORDER BY city, indicator"
    ).df().to_markdown(index=False)

@mcp.tool()
def query_city_benchmarks(sql: str) -> str:
    """Runs a read-only SQL SELECT against the `benchmarks` table.
    Columns: city, indicator, ref_date, value, unit, source, source_series_id, geo_note, retrieved_at.
    Example: SELECT ref_date, value FROM benchmarks
             WHERE city = 'Ottawa' AND indicator = 'unemployment_rate' ORDER BY ref_date
    """
    if not sql.lstrip().lower().startswith("select"):
        return "Error: only SELECT statements are allowed."
    df = _connect().execute(sql).df()
    truncated = len(df) > MAX_ROWS
    out = df.head(MAX_ROWS).to_markdown(index=False)
    return out + (f"\n\n*(truncated to {MAX_ROWS} of {len(df)} rows)*" if truncated else "")
```

*(Requires `tabulate` for `to_markdown` — add it to dependencies. This is local data queried by you, so the `SELECT`-prefix guard is about tool clarity, not security.)*

### Step 3.3: Link and Chat
Register the server in `.mcp.json` (and Claude Desktop if desired). Test:
> *"Calculate the year-over-year gap in shelter-cost growth between Ottawa and Austin using the SQL tool."*

**Done when:** the model can answer that question with correct numbers, calling `list_indicators` first without being told to.

---

## Phase 4: Frontend Development & Client-Side Processing
**Goal:** A zero-latency, reactive dashboard on the exact same Parquet file.

### Step 4.1: Install DuckDB-Wasm
Scaffold a frontend app at the **repo root** (not a subfolder — GitHub Pages' branch-deploy mode only serves `/` or `/docs`) and bundle `@duckdb/duckdb-wasm`. **Start from the prototype's `dashboard.js`** — its DuckDB-Wasm bootstrap and Parquet-mounting code already work; strip the NOC/CIP-specific logic.

*Honest trade-off:* the dataset is small enough that plain JSON + JS would be lighter (DuckDB-Wasm adds a multi-MB WASM download). We keep DuckDB-Wasm anyway for SQL parity with the MCP layer, because the prototype already validated it, and because the dataset grows sharply once census tables arrive in 2027.

### Step 4.2: Build the Dropdown Slicers
Primary city (default: Ottawa) vs. comparison city (Austin, Adelaide, Helsinki).

### Step 4.3: Native Analytical Transformations
Client-side SQL over the mounted Parquet, with instant-toggle charts:
*   **Index Baseline:** rebase a chosen start date to 100 — growth velocities side-by-side. *(This is the default view: index comparisons dodge the cross-country definition problem from Step 1.4.)*
*   **Divergence Delta:** bar chart of the Ottawa-vs-peer gap over time.
*   Surface `geo_note` as a caveat footnote on every chart that compares raw levels.

---

## Phase 5: $0 Deployment and Automation
**Goal:** Live on the web with automated updates at zero cost.

### Step 5.1: Deploy to Vercel
Push to GitHub and deploy — this project uses GitHub Pages (see Phase 4's layout note on why `index.html` lives at repo root); the Parquet ships as a static asset in `public/`. *(Vercel would work equally well if ever needed for preview deployments — no code changes required, just point it at the repo.)*

### Step 5.2: Create a GitHub Action Sync Pipeline
Weekly Action (data is monthly, so weekly is already generous):
*   **Cron is UTC:** Monday 9:00 AM Ottawa time = `0 13 * * 1` (EDT) / `0 14 * * 1` (EST) — pick one and note the drift, or just run `0 14 * * 1` year-round. Scheduled runs can be delayed ~minutes; irrelevant here.
*   Workflow needs `permissions: contents: write` to auto-commit, and the FRED key as a repo secret.
*   Run `pipeline/extract.py`; the Phase 2.3 validation gate must pass, **and skip the commit entirely if the Parquet is byte-identical** (no noise commits).
*   On push, Vercel redeploys and swaps the data file with zero downtime.

---

## Phase 6 (Future): 2026 Census Integration
**Goal:** The payoff — fold census releases into the same pipeline as they land.

*   **Feb 2027** (population/dwelling counts) is the first integration test: add a `statcan_census` fetcher, emit rows with `frequency = quinquennial` into the same schema.
*   Census data ships two ways, neither of which is classic WDS vectors: the **Census Profile web data service** (per-geography lookups) and **bulk ZIP downloads** (full tables like 98-10-0403). The prototype's `etl_to_parquet.py` already solved the bulk path — chunked CSV streaming straight from the ZIP — port it as the `statcan_census` fetcher's engine.
*   Peer-city census equivalents: US ACS (Census Bureau API), ABS Census (2026 for Australia too — same year!), Statistics Finland.
*   The big releases for this project's domains: **income** (Jul 2027), **housing** (Sep 2027), **labour + education** (Dec 2027).
