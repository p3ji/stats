# Ottawa Population Growth Map — Implementation Plan

> **Rev 1 (2026-07-10).** Sub-app of the Ottawa Global Benchmark Engine: an animated
> choropleth map of the Ottawa–Gatineau CMA showing population change by small area,
> with a play button and a manually scrubbable timeline. Lives at `/map/` on the same
> GitHub Pages site; shares the repo's conventions (no build step, static assets,
> pipeline-generated data, honest methodology notes).

## The core data trade-off (decides everything else)

"Most granular level supported" is not one answer — it's a granularity × frequency
trade-off in what StatCan actually publishes:

| Geography | Areas in Ottawa–Gatineau CMA | Frequency | Source |
| :--- | :--- | :--- | :--- |
| Census subdivision (CSD) | ~30 municipalities | **Annual** (2001–present) | Table 17-10-0155 (2021 boundaries), WDS vectors |
| **Census tract (CT)** | **~415** | **Quinquennial** (census years) | Census Profile bulk tables per census |
| Dissemination area (DA) | ~2,500 | Quinquennial | Census Profile; boundaries least stable, files largest |

**Decision: CT × census years is the MVP.** It's what people mean by "neighbourhood
level," the boundary files are manageable after simplification, and CTs are designed
for longitudinal comparability (they split along documented lineage rather than being
redrawn wholesale). DAs are the "most granular" on paper but triple the payload and
have the worst cross-census comparability — recorded as a stretch goal, not the MVP.
The annual CSD series is a possible second *mode* ("annual, coarser areas") — also
stretch.

**Timeline frames:** 2001 → 2006 → 2011 → 2016 → 2021, with **2026 landing
Feb 10, 2027** (population/dwelling counts are the first 2026 Census release). This
sub-app is deliberately census-ready: when the 2026 counts drop, they become one more
frame through the same pipeline — a concrete Phase 6 payoff from `phaseone.md`.
(1996 and earlier exist but sourcing pre-2001 CT profiles gets archaeologically
painful — cut from MVP.)

## What the animation actually shows (methodology, decided up front)

Two honest options, in order of increasing work:

1. **Population density per CT, per census year (MVP).** Each frame is that year's
   population on **that year's own CT boundaries**. No cross-census crosswalk needed —
   boundary changes appear as visible splits, which is truthful. Density (persons/km²),
   not raw count, because CT areas differ wildly (rural fringe CTs are huge); raw-count
   choropleths of unequal areas mislead.
2. **Growth rate vs. previous census (stretch).** "Which areas grew fastest" needs
   populations re-based onto a common geometry via StatCan **correspondence files**
   (CT lineage across censuses). Meaningful but a real data-engineering step — do it
   only after the MVP ships.

Like the main dashboard, the map gets a **Methodology note** in the UI: what density
is, why boundaries shift between frames, why cross-frame comparisons of a single CT
can break at split points.

---

## Phase M1: Data pipeline (`pipeline/map/`)

**Goal:** Emit one geometry + population file per census year into `map/data/`.

- **M1.1 — Boundaries.** Download CT **cartographic boundary files** per census
  vintage (2021 file confirmed available as shapefile from the 2021 Census geography
  portal; equivalents exist per prior census). Filter to CMA 505 (Ottawa–Gatineau),
  reproject to WGS84, **simplify** aggressively (shapely `simplify` or topojson
  quantization). Target: ≤ ~400 KB of GeoJSON per vintage, ~2 MB total.
- **M1.2 — Populations.** CT-level population per census year from Census Profile
  bulk tables (98-401 series for 2021; per-year equivalents for 2001–2016). These are
  the big ZIP-of-CSV downloads — **port the prototype's chunked-ZIP streaming pattern**
  (`statcan_mcp/etl_to_parquet.py`) as planned in phaseone.md; this is its first real
  use in this repo. Filter to CMA 505 CTs, keep `ctuid`, `population`, `land_area`.
- **M1.3 — Join & emit.** One `map/data/ct_<year>.geojson` per vintage with
  `population` and `density` properties baked into each feature. Plus a tiny
  `map/data/manifest.json` (years, min/max density for a stable color scale across
  all frames — the scale must NOT rescale per frame or the animation lies).
- **M1.4 — Validation gate** (same ethos as `extract.py`): every vintage non-empty,
  CT counts in plausible range (300–500), CMA total population within ~2% of the
  published CMA figure (cross-check against the `population` indicator already in
  `global_cities.parquet`), no null geometries.

**Done when:** `python pipeline/map/build_map_data.py` produces all vintages from
scratch, passing validation, with total payload ≤ ~3 MB.

**Dependency note:** this needs `geopandas` (or `pyshp` + `shapely` if we want to
stay lighter) — pipeline-only, never shipped to the browser. Add to
`pipeline/requirements.txt`.

## Phase M2: Map sub-app (`map/index.html`, `map/map.js`, `map/map.css`)

**Goal:** The interactive map, matching the main dashboard's look and no-build rules.

- **M2.1 — Rendering: Leaflet (CDN) + canvas renderer** for the CT polygons, over a
  light grey basemap (CARTO "Positron" raster tiles — free with attribution, and the
  muted style keeps the choropleth readable). Decision note: MapLibre GL would give
  smoother tweening but drags in vector-tile styling complexity; Leaflet + canvas
  handles 415 polygons × 5 frames trivially. Fallback if tiles are ever a problem:
  render with **no basemap at all** (the CT mesh itself reads fine as a city shape).
- **M2.2 — Timeline control.** One slider (range input) whose stops are census years,
  plus Play/Pause. Play advances frames on a timer (~2s/frame) with a **short crossfade
  between frames** (fade polygons' fill via canvas alpha) — smooth *feel* without
  fabricating intermediate data. Scrubbing snaps to the nearest census year and says
  so ("2016 Census"). No fake interpolated years: this is a data product, and
  inventing 2013 populations would contradict the methodology stance the dashboard
  just took.
- **M2.3 — Interaction.** Hover/tap a CT → tooltip with CT id, population, density,
  and (where lineage allows) change vs. previous frame. Fixed color scale + legend
  (from `manifest.json`). Ottawa/Gatineau split visible; label the bi-provincial CMA
  properly.
- **M2.4 — Chrome.** Same header style as the main dashboard, link back to `/`, a
  link *to* the map from the main dashboard ("Explore the population map →"), and the
  Methodology note (M-section above).

**Done when:** locally served, play animates 2001→2021 smoothly, scrub works on
desktop and at 375px mobile width, tooltips correct, no console errors.

## Phase M3: Verify & deploy

- Local browser verification (same drill as the dashboard: snapshot, console, mobile
  viewport, spot-check known facts — e.g. Barrhaven/Kanata-fringe CTs should visibly
  densify across frames; downtown CTs should be near-flat).
- Deploys automatically with the existing Pages workflow — `map/` is just another
  static folder in the artifact. Update `AGENTS.md` (build command for map data) and
  `docs/phaseone.md` status.
- Total new payload budget: ≤ ~3.5 MB including Leaflet — acceptable for a
  deliberate "explore" page (it's not on the main dashboard's critical path).

## Phase M4 (stretch, in rough priority order)

1. **2026 Census frame** — Feb 10, 2027, first real census-integration test.
2. **Growth-rate view** — correspondence-file crosswalk onto 2021 CT geometry;
   adds a "% change since previous census" toggle.
3. **Annual mode** — CSD-level annual estimates (17-10-0155) as a second layer:
   coarser areas, but yearly motion.
4. **DA-level detail** — behind a zoom threshold (load DA geojson only when zoomed
   in), which sidesteps the payload problem.

## Risks / open questions (answers can change the plan)

- **Pre-2011 CT profile sourcing:** 2016/2021 bulk downloads are well-known; 2001/2006
  CT-level profiles exist but live in older archive formats. Budget discovery time in
  M1.2; if 2001/2006 prove painful, ship MVP with 2011→2021 (three frames) and extend
  backward later — the pipeline shape doesn't change.
- **Boundary-file licensing:** StatCan open licence requires attribution — add to the
  map footer alongside the CARTO/OSM tile attribution.
- **Color scale choice:** density is heavy-tailed (downtown ~10k/km² vs. rural ~10/km²)
  — use a log or quantile scale, decided during M2 with real data on screen.
