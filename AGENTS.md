# statcan_codr — Agent Guide

> Single source of truth for *how to work on this repo*. Claude and Antigravity both read this (`CLAUDE.md` → `@AGENTS.md`; `GEMINI.md` → pointer). Keep it short.

**Brain note (goals, backlog, full context):** `H:\My Drive\Brain2\Projects\statcan_codr.md`
**GitHub:** `https://github.com/p3ji/stats`
**Live site:** `https://p3ji.github.io/stats/`
**Naming:** public repo/URL is `stats`, public brand is **Open Stats Lab** (renamed 2026-07-19 from `statcan_codr` to avoid any impression of Statistics Canada affiliation). The **local folder** and Brain note stay `statcan_codr`; the planned Python library keeps the `statcan_codr` name. Don't "fix" those to match — the split is intentional.
**Plan of record:** `docs/phaseone.md` · Visibility study: `docs/visibility.md` (query bank: `visibility/queries.yaml`)
**Stack:** Python (pipeline) + plain HTML/JS + DuckDB-Wasm (site, no build step)

## Run / build / test
- Refresh benchmark data: `python pipeline/extract.py` — pulls all `status: confirmed` cells in `pipeline/indicators.yaml` from live APIs, validates, writes `public/data/global_cities.parquet`. Requires `pip install -r pipeline/requirements.txt`.
- Preview the site locally: `python -m http.server 8081` from the repo root (or use the `dashboard` config in `.claude/launch.json`), then open `http://localhost:8081/`.
- No build step for the site — HTML/JS/CSS are served as-is.
- Rebuild the crawlable table mirrors: `python visibility/mirror/build_mirror.py` — fetches the TREATMENT tables in `visibility/mirror/manifest.yaml` from WDS and writes `tables/*.html` + `tables/index.html` + `sitemap.xml`. Never mirrors the control tables (see `docs/mirror_experiment.md`).

## Site layout
- Root `index.html` is a **homepage** linking to the sub-apps. Deploy uses GitHub Actions (`upload-pages-artifact` with `path: .`), which serves the whole repo, so sub-apps live in their own folders:
  - `/benchmark/` — Ottawa Global Benchmark dashboard (`benchmark/index.html` + `app.js` + `style.css`; its DuckDB fetch uses `../public/data/global_cities.parquet`).
  - `/tables/` — crawlable StatCan table mirrors (visibility experiment, generated).
  - `/map/` — Ottawa population map (planned, see `docs/popmap.md`).

## Conventions & gotchas
- **A root `index.html` must exist** (currently the homepage). The Actions deploy serves subfolders fine, but if Pages is ever switched to "Deploy from a branch", only repo root and `/docs` are valid sources — keep the entry point at root. `pipeline/extract.py`'s `OUTPUT_PATH` writes `public/data/global_cities.parquet` at repo root (kept there; the moved dashboard reaches it via `../public/`).
- **`mcp-statcan`'s bulk-fetch tools are broken** (`get_bulk_vector_data_by_range`, `get_changed_series_data_from_vector` throw HTTP 404/406 on valid vectors). `extract.py` bypasses the MCP entirely and calls StatCan WDS / FRED / ABS SDMX / Statistics Finland PxWeb directly via `requests`.
- **`mcp-statcan` needs one-time interactive approval** in a terminal `claude` session before its tools are usable — non-terminal Claude Code clients (this includes most embedded/desktop UIs) can't render that approval prompt, so MCP-dependent discovery work has to happen in an actual terminal.
- Series-level detail (exact vector/series IDs, comparability caveats, unresolved cells) lives in `pipeline/indicators.yaml`, not here — it's the manifest, not documentation to duplicate.
- Keep this file short; put goals/backlog/status/rationale in the linked Brain note, not here.

## Do NOT
- Commit secrets (`.env`) or large build artifacts.
- Add a FRED API key to code or commit it — the FRED fetcher deliberately uses the keyless `fredgraph.csv` endpoint instead.
