# stats (Open Stats Lab) — Agent Guide

> Single source of truth for *how to work on this repo*. Claude and Antigravity both read this (`CLAUDE.md` → `@AGENTS.md`; `GEMINI.md` → pointer). Keep it short.

**Brain note (goals, backlog, full context):** [statcan_codr.md](file:///H:/My%20Drive/Brain2_backup/Projects/statcan_codr.md)
**GitHub:** `https://github.com/p3ji/stats`
**Live site:** `https://p3ji.github.io/stats/`
**Work in `Projects\stats` — it is the only clone.** The old `Projects\statcan_codr` clone was deleted 2026-07-27; its gitignored `.claude/settings.local.json` was copied here first, so nothing is left behind. If a `statcan_codr` folder reappears, it is a stale re-clone — do not work in it.
**Naming:** repo/URL, public brand, and local folder are all `stats` / **Open Stats Lab** (repo renamed 2026-07-19 from `statcan_codr`). The Brain note file may still be named `statcan_codr.md`, and the planned Python library keeps the `statcan_codr` name; those are fine to leave.
**Plan of record:** `docs/phaseone.md` · Visibility study: `docs/visibility.md` (query bank: `visibility/queries.yaml`)
**Stack:** Python (pipeline) + plain HTML/JS + DuckDB-Wasm (site, no build step)

## Run / build / test
- Refresh benchmark data: `python pipeline/extract.py` — pulls all `status: confirmed` cells in `pipeline/indicators.yaml` from live APIs, validates, writes `public/data/global_cities.parquet`. Requires `pip install -r pipeline/requirements.txt`.
- Preview the site locally: `python -m http.server 8081` from the repo root (or use the `dashboard` config in `.claude/launch.json`), then open `http://localhost:8081/`.
- No build step for the site — HTML/JS/CSS are served as-is.
- Rebuild the crawlable table mirrors: `python visibility/mirror/build_mirror.py` — fetches the TREATMENT tables in `visibility/mirror/manifest.yaml` from WDS and writes `tables/*.html` + `tables/index.html` + `sitemap.xml`. Never mirrors the control tables (see `docs/mirror_experiment.md`).
- Build Remine fact briefs for a Daily release: `python remine/generate.py --date YYMMDD`
  — scrapes The Daily, pulls the cited cube from WDS, computes candidate facts, writes
  `remine/briefs/`. Draft with the `remine-editorial` skill, then bind with
  `python remine/editor.py --brief B --draft D --out remine/articles/F.json`.
  `/remine YYMMDD` runs the whole loop. Tests: `python -m pytest remine/tests/`.

## Site layout
- Root `index.html` is a **homepage** linking to the sub-apps. Deploy uses GitHub Actions (`upload-pages-artifact` with `path: .`), which serves the whole repo, so sub-apps live in their own folders:
  - `/benchmark/` — Ottawa Global Benchmark dashboard (`benchmark/index.html` + `app.js` + `style.css`; its DuckDB fetch uses `../public/data/global_cities.parquet`).
  - `/tables/` — crawlable StatCan table mirrors (visibility experiment, generated).
  - `/map/` — Ottawa population map (planned, see `docs/popmap.md`).
  - `/remine/` — re-mined Daily articles (`remine/index.html` + `article.html` + `app.js`;
    reads `remine/articles/*.json`). Unrelated to the visibility study.

## Conventions & gotchas
- **A root `index.html` must exist** (currently the homepage). The Actions deploy serves subfolders fine, but if Pages is ever switched to "Deploy from a branch", only repo root and `/docs` are valid sources — keep the entry point at root. `pipeline/extract.py`'s `OUTPUT_PATH` writes `public/data/global_cities.parquet` at repo root (kept there; the moved dashboard reaches it via `../public/`).
- **`mcp-statcan`'s bulk-fetch tools are broken** (`get_bulk_vector_data_by_range`, `get_changed_series_data_from_vector` throw HTTP 404/406 on valid vectors). `extract.py` bypasses the MCP entirely and calls StatCan WDS / FRED / ABS SDMX / Statistics Finland PxWeb directly via `requests`.
- **`mcp-statcan` needs one-time interactive approval** in a terminal `claude` session before its tools are usable — non-terminal Claude Code clients (this includes most embedded/desktop UIs) can't render that approval prompt, so MCP-dependent discovery work has to happen in an actual terminal.
- Series-level detail (exact vector/series IDs, comparability caveats, unresolved cells) lives in `pipeline/indicators.yaml`, not here — it's the manifest, not documentation to duplicate.
- Keep this file short; put goals/backlog/status/rationale in the linked Brain note, not here.
- **Remine's number contract is enforced in Python, not in its skills.** `remine/editor.py`
  fails the build on unresolved tokens, bare numerals, quantity words, and a
  `differs_from_daily` claim of "not discussed" that the mention map contradicts. Never
  relax a check to make a draft pass — fix the draft. `PUBLISHING_ENABLED` gates
  `--rebuild-index`; it is open, and should be re-gated if the pipeline changes in a way a
  reader has not reviewed (see `docs/remine-known-limitations.md`).

## Do NOT
- Commit secrets (`.env`) or large build artifacts.
- Add a FRED API key to code or commit it — the FRED fetcher deliberately uses the keyless `fredgraph.csv` endpoint instead.
