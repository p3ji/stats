# Ottawa Global Benchmark Engine: Implementation Plan

## Phase 1: Conversational Target Discovery
**Goal:** Map out the exact datasets and fields needed to build identical socio-economic profiles for Ottawa and its peer group.

### Step 1.1: Connect the Live StatCan MCP
Add `pranaviate/statscan-mcp` to your local Claude Desktop configuration file (`claude_desktop_config.json`).

### Step 1.2: Identify Ottawa Vectors
Use Claude to crawl the live WDS registry and isolate the exact vector string coordinates or Vector IDs for the Ottawa-Gatineau (CMA) geography across three core domains:
*   **Labor Force:** Participation rate, unemployment rate, and high-tech sector employment shares (NAICS 54).
*   **Real Estate & Cost of Living:** Shelter CPI or benchmark housing prices.
*   **Demographics:** Post-secondary education attainment rates.

### Step 1.3: Document International Mappings
Research equivalent open data endpoints for your target international peers. Map out:
*   **Austin, USA:** FRED API (Federal Reserve Economic Data) for Austin-Round Rock MSA indicators.
*   **Adelaide, Australia:** Australian Bureau of Statistics (ABS) data sheets or API.
*   **Helsinki, Finland:** Eurostat or Statistics Finland open databases.

---

## Phase 2: Building the Unified Local Pipeline
**Goal:** Write a lightweight Python script that hits the respective global APIs, extracts the rows relevant to our four target cities, and groups them into a standardized format.

### Step 2.1: Implement the Extractor Script (`/pipeline/extract.py`)
Use `requests` to pull Ottawa data via StatCan WDS, Austin data via the FRED API, and Adelaide/Helsinki data via their respective open APIs or static file downloads.

### Step 2.2: Establish a Standardized Schema
Standardize coordinates and metadata definitions from different countries into a single, clean table structure. Your rows will not use raw StatCan coordinate codes. Instead, format them cleanly for database queries:

| City | Indicator | Ref_Date | Value | Unit |
| :--- | :--- | :--- | :--- | :--- |
| Ottawa | Unemployment Rate | 2026-06-01 | 6.2 | Percent |
| Austin | Unemployment Rate | 2026-06-01 | 3.8 | Percent |
| Adelaide | Unemployment Rate | 2026-06-01 | 4.9 | Percent |

### Step 2.3: Compile to Local Parquet
Use Python's `duckdb` module to export this unified dataframe into a highly compressed local file: `/dashboard/public/data/global_cities.parquet`.

---

## Phase 3: Setting Up Your Local Analytical SQL-MCP Server
**Goal:** Build your own custom MCP server to converse directly with this targeted city dataset.

### Step 3.1: Initialize FastMCP
Create a local Python script: `/mcp-server/server.py`.

### Step 3.2: Create the Ultimate Query Tool
Instead of writing 15 separate metadata tools, give your server a single, highly flexible tool that exposes your local file to an LLM via standard SQL:

```python
import duckdb
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Ottawa Global Benchmarks")

@mcp.tool()
def query_city_benchmarks(sql_query: str) -> str:
    """Executes a SQL query against the global cities dataset. 
    Available columns: City, Indicator, Ref_Date, Value, Unit.
    Example sql_query: "City = 'Ottawa' AND Indicator = 'Unemployment Rate'"
    """
    con = duckdb.connect()
    # Direct query over the local compressed file
    result = con.execute(f"SELECT * FROM './dashboard/public/data/global_cities.parquet' WHERE {sql_query}").df()
    return result.to_markdown()
```

### Step 3.3: Link and Chat
Add this local server to Claude Desktop. You can now test your analysis layer directly via chat: 
> *"Claude, calculate the year-over-year gap in housing costs between Ottawa and Austin using my SQL tool."*

---

## Phase 4: Frontend Development & Client-Side Processing
**Goal:** Build a zero-latency, reactive visual dashboard on top of the exact same dataset.

### Step 4.1: Install DuckDB-Wasm
Scaffold a frontend web app inside `/dashboard` and bundle `@duckdb/duckdb-wasm`.

### Step 4.2: Build the Dropdown Slicers
Create simple UI selectors: Primary City (Default: Ottawa) vs. Comparison City (Dropdown: Austin, Adelaide, Helsinki).

### Step 4.3: Native Analytical Transformations
Write native client-side SQL calculations that pull from the `global_cities.parquet` file mounted in the user's browser. Implement instant toggle charts for:
*   **Index Baseline:** Set a specific start date to 100 to show growth velocities side-by-side.
*   **Divergence Delta:** A bar chart displaying the variance gap between Ottawa and the chosen peer over time.

---

## Phase 5: $0 Deployment and Automation
**Goal:** Ship the application to the live web with fully automated updates at zero cost.

### Step 5.1: Deploy to Vercel
Push the `/dashboard` code to GitHub and deploy to Vercel. Because the Parquet file is tiny (~20 MB) and bundled directly in your repository's `/public` folder, it deploys as a static asset.

### Step 5.2: Create a GitHub Action Sync Pipeline
Write a GitHub Action that runs every Monday morning at 9:00 AM EST.
The runner executes your Python pipeline script to grab fresh data for Ottawa and Austin, compiles the brand new `global_cities.parquet` file, auto-commits it back to your GitHub repository, and pushes it.
Vercel detects the push and silently swaps out the old data file on production without any web downtime.
