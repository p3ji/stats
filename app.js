/**
 * Ottawa Global Benchmark Engine — dashboard client
 * DuckDB-Wasm querying a local Parquet file (dashboard bootstrap pattern
 * adapted from the statcan_mcp prototype).
 */

const INDICATOR_LABELS = {
  unemployment_rate: 'Unemployment Rate',
  participation_rate: 'Participation Rate',
  tech_sector_employment_share: 'Tech Sector Employment Share (NAICS 54 / equivalent)',
  shelter_cpi: 'Shelter / Housing Cost Index',
};

const CITY_LABELS = { ottawa: 'Ottawa', austin: 'Austin', adelaide: 'Adelaide', helsinki: 'Helsinki' };

let db, conn, dbInitialized = false;
let indexChart, deltaChart;

function setStatus(state, text) {
  document.querySelector('.badge-dot').className = `badge-dot ${state}`;
  document.getElementById('dataStatusText').textContent = text;
}

async function initDuckDB() {
  if (dbInitialized) return conn;
  setStatus('loading', 'Initializing DuckDB-Wasm…');

  const duckdbObj = window.duckdb;
  const bundle = await duckdbObj.selectBundle(duckdbObj.getJsDelivrBundles());
  const worker_url = URL.createObjectURL(
    new Blob([`importScripts("${bundle.mainWorker}");`], { type: 'text/javascript' })
  );
  const worker = new Worker(worker_url);
  const logger = new duckdbObj.ConsoleLogger();
  db = new duckdbObj.AsyncDuckDB(logger, worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  URL.revokeObjectURL(worker_url);

  conn = await db.connect();

  setStatus('loading', 'Downloading benchmark data…');
  const response = await fetch('public/data/global_cities.parquet');
  if (!response.ok) throw new Error(`HTTP ${response.status} fetching parquet`);
  const buffer = await response.arrayBuffer();
  await db.registerFileBuffer('global_cities.parquet', new Uint8Array(buffer));
  await conn.query(`CREATE VIEW benchmarks AS SELECT * FROM read_parquet('global_cities.parquet')`);

  dbInitialized = true;
  setStatus('success', 'Connected (DuckDB-Wasm)');
  return conn;
}

async function query(sql) {
  const result = await conn.query(sql);
  return result.toArray().map((row) => {
    const obj = {};
    for (const key of Object.keys(row)) {
      const val = row[key];
      obj[key] = typeof val === 'bigint' ? Number(val) : val;
    }
    return obj;
  });
}

function formatDateUTC(date) {
  const d = new Date(date);
  return d.toISOString().slice(0, 10);
}

function rebaseToIndex(rows, sharedAnchorDate) {
  const sorted = [...rows]
    .sort((a, b) => new Date(a.ref_date) - new Date(b.ref_date))
    .filter((r) => new Date(r.ref_date) >= new Date(sharedAnchorDate));
  if (!sorted.length) return { anchorDate: null, points: [] };
  const anchor = sorted[0].value;
  return {
    anchorDate: sorted[0].ref_date,
    points: sorted.map((r) => ({ x: r.ref_date, y: (r.value / anchor) * 100 })),
  };
}

function alignForDelta(peerIndexed, ottawaIndexed) {
  // For each peer point, find Ottawa's most recent indexed value at or before that date.
  const ottawaSorted = [...ottawaIndexed].sort((a, b) => new Date(a.x) - new Date(b.x));
  return peerIndexed
    .map((p) => {
      const candidates = ottawaSorted.filter((o) => new Date(o.x) <= new Date(p.x));
      if (!candidates.length) return null;
      const nearestOttawa = candidates[candidates.length - 1];
      return { x: p.x, y: nearestOttawa.y - p.y };
    })
    .filter(Boolean);
}

function renderCharts(indicator, peer, ottawaRows, peerRows) {
  const ottawaMin = Math.min(...ottawaRows.map((r) => new Date(r.ref_date)));
  const peerMin = Math.min(...peerRows.map((r) => new Date(r.ref_date)));
  const sharedAnchorDate = new Date(Math.max(ottawaMin, peerMin));

  const ottawaIdx = rebaseToIndex(ottawaRows, sharedAnchorDate);
  const peerIdx = rebaseToIndex(peerRows, sharedAnchorDate);
  const baseNote = `Base date for this comparison: ${formatDateUTC(sharedAnchorDate)} (first date both cities have data). See <a href="#methodology">Methodology</a> for how the base date is chosen and what indexing does and doesn't fix.`;

  const ctx1 = document.getElementById('indexChart');
  if (indexChart) indexChart.destroy();
  indexChart = new Chart(ctx1, {
    type: 'line',
    data: {
      datasets: [
        { label: 'Ottawa', data: ottawaIdx.points, borderColor: '#6366f1', pointRadius: 0, tension: 0.15 },
        { label: CITY_LABELS[peer], data: peerIdx.points, borderColor: '#f59e0b', pointRadius: 0, tension: 0.15 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { x: { type: 'time', time: { unit: 'year' } }, y: { title: { display: true, text: 'Index (base = 100)' } } },
      plugins: { legend: { labels: { color: '#8891a7' } } },
    },
  });

  const delta = alignForDelta(peerIdx.points, ottawaIdx.points);
  const ctx2 = document.getElementById('deltaChart');
  if (deltaChart) deltaChart.destroy();
  deltaChart = new Chart(ctx2, {
    type: 'bar',
    data: {
      datasets: [{
        label: `Ottawa − ${CITY_LABELS[peer]} (indexed points)`,
        data: delta,
        backgroundColor: delta.map((d) => (d.y >= 0 ? '#6366f1' : '#f59e0b')),
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { x: { type: 'time', time: { unit: 'year' } }, y: { title: { display: true, text: 'Index point difference' } } },
      plugins: { legend: { display: false } },
    },
  });

  document.getElementById('caveatPanel').innerHTML = `
    <h3>Data notes for this comparison</h3>
    <p>${baseNote}</p>
  `;
}

async function loadGeoNotes(indicator, peer) {
  const rows = await query(`
    SELECT city, any_value(geo_note) AS geo_note
    FROM benchmarks WHERE indicator = '${indicator}' AND city IN ('ottawa', '${peer}')
    GROUP BY city
  `);
  const panel = document.getElementById('caveatPanel');
  const extra = rows
    .map((r) => `<p><strong>${CITY_LABELS[r.city]}:</strong> ${r.geo_note || 'No caveat recorded.'}</p>`)
    .join('');
  panel.innerHTML += extra;
}

async function updateDashboard() {
  const indicator = document.getElementById('indicatorSelect').value;
  const peer = document.getElementById('peerSelect').value;

  const rows = await query(`
    SELECT city, ref_date, value FROM benchmarks
    WHERE indicator = '${indicator}' AND city IN ('ottawa', '${peer}')
    ORDER BY ref_date
  `);
  const ottawaRows = rows.filter((r) => r.city === 'ottawa');
  const peerRows = rows.filter((r) => r.city === peer);

  const notice = document.getElementById('unavailableNotice');
  const grid = document.getElementById('chartsGrid');

  if (!ottawaRows.length || !peerRows.length) {
    const missing = !ottawaRows.length && !peerRows.length ? 'Ottawa and ' + CITY_LABELS[peer]
      : !ottawaRows.length ? 'Ottawa' : CITY_LABELS[peer];
    notice.style.display = 'block';
    notice.textContent = `${INDICATOR_LABELS[indicator]} isn't resolved yet for ${missing} — see pipeline/indicators.yaml for the discovery status. Pick a different indicator or peer city.`;
    grid.style.display = 'none';
    document.getElementById('caveatPanel').innerHTML = '';
    return;
  }

  notice.style.display = 'none';
  grid.style.display = 'grid';
  renderCharts(indicator, peer, ottawaRows, peerRows);
  await loadGeoNotes(indicator, peer);
}

async function populateIndicatorOptions() {
  const rows = await query(`SELECT DISTINCT indicator FROM benchmarks ORDER BY indicator`);
  const select = document.getElementById('indicatorSelect');
  select.innerHTML = rows
    .map((r) => `<option value="${r.indicator}">${INDICATOR_LABELS[r.indicator] || r.indicator}</option>`)
    .join('');
  select.value = 'unemployment_rate';
}

async function main() {
  try {
    await initDuckDB();
    await populateIndicatorOptions();

    const meta = await query(`SELECT max(retrieved_at) AS t FROM benchmarks`);
    document.getElementById('lastUpdated').textContent = `Data last extracted: ${meta[0].t}`;

    document.getElementById('indicatorSelect').addEventListener('change', updateDashboard);
    document.getElementById('peerSelect').addEventListener('change', updateDashboard);

    await updateDashboard();
  } catch (err) {
    console.error(err);
    setStatus('error', 'Failed to load — see console');
  }
}

main();
