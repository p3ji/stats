/**
 * dashboard.js
 * Statistics Canada – Field of Study × Occupation Explorer
 * 2021 Census · Table 98-10-0403-01
 *
 * Client-side SQL querying powered by DuckDB-Wasm and Parquet.
 */

// ─────────────────────────────────────────────────────────────
// Constants & Configuration
// ─────────────────────────────────────────────────────────────

// NOC 2021 Major Groups (2-digit, broad categories used for grouping)
const NOC_MAJOR_GROUPS = {
  '0': { label: 'Management', color: '#6366f1' },
  '1': { label: 'Business & Finance', color: '#0ea5e9' },
  '2': { label: 'Natural & Applied Sciences', color: '#10b981' },
  '3': { label: 'Health Occupations', color: '#f59e0b' },
  '4': { label: 'Education, Law & Social', color: '#8b5cf6' },
  '5': { label: 'Art, Culture & Sport', color: '#ec4899' },
  '6': { label: 'Sales & Service', color: '#14b8a6' },
  '7': { label: 'Trades & Transport', color: '#f97316' },
  '8': { label: 'Natural Resources', color: '#84cc16' },
  '9': { label: 'Manufacturing & Utilities', color: '#94a3b8' },
};

// CIP 2-digit series (broad fields of study)
const CIP_FIELDS = {
  '01': { label: 'Agriculture & Related Sciences', color: '#84cc16' },
  '03': { label: 'Natural Resources', color: '#22c55e' },
  '04': { label: 'Architecture', color: '#06b6d4' },
  '09': { label: 'Communication & Journalism', color: '#a78bfa' },
  '11': { label: 'Computer & Info Sciences', color: '#6366f1' },
  '13': { label: 'Education', color: '#f59e0b' },
  '14': { label: 'Engineering', color: '#0ea5e9' },
  '15': { label: 'Engineering Technology', color: '#38bdf8' },
  '19': { label: 'Family & Consumer Sciences', color: '#fb7185' },
  '22': { label: 'Legal Professions', color: '#c084fc' },
  '24': { label: 'Liberal Arts & Sciences', color: '#94a3b8' },
  '26': { label: 'Biological Sciences', color: '#4ade80' },
  '27': { label: 'Mathematics & Statistics', color: '#818cf8' },
  '40': { label: 'Physical Sciences', color: '#7dd3fc' },
  '42': { label: 'Psychology', color: '#f0abfc' },
  '43': { label: 'Security & Protective Services', color: '#fbbf24' },
  '44': { label: 'Public Admin & Social Work', color: '#34d399' },
  '45': { label: 'Social Sciences', color: '#a3e635' },
  '51': { label: 'Health Professions', color: '#f87171' },
  '52': { label: 'Business & Management', color: '#fb923c' },
  '54': { label: 'History', color: '#e879f9' },
};

// ─────────────────────────────────────────────────────────────
// Global State
// ─────────────────────────────────────────────────────────────

let db = null;
let conn = null;
let dbInitialized = false;
let charts = {};
let filteredData = []; // Fallback filtered data
let currentTableRows = [];
let sortState = { col: 3, asc: false };

// Representative embedded data (fallback)
const EMBEDDED_DATA = buildEmbeddedData();

// ─────────────────────────────────────────────────────────────
// DuckDB-Wasm Client
// ─────────────────────────────────────────────────────────────

async function initDuckDB() {
  if (dbInitialized) return conn;

  setStatus('loading', 'Initializing DuckDB-Wasm...');
  
  try {
    const duckdbObj = window.duckdb;
    if (!duckdbObj) {
      throw new Error("DuckDB-Wasm not loaded on window.");
    }
    
    // Select the optimal bundle (loads wasm binaries from jsdelivr)
    const JSDELIVR_BUNDLES = duckdbObj.getJsDelivrBundles();
    const bundle = await duckdbObj.selectBundle(JSDELIVR_BUNDLES);
    
    // Setup worker with Blob to bypass same-origin restriction
    const worker_url = URL.createObjectURL(
      new Blob([`importScripts("${bundle.mainWorker}");`], { type: 'text/javascript' })
    );
    const worker = new Worker(worker_url);
    const logger = new duckdbObj.ConsoleLogger();
    
    db = new duckdbObj.AsyncDuckDB(logger, worker);
    await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
    URL.revokeObjectURL(worker_url);
    
    conn = await db.connect();
    
    // Register the parquet file as a buffer in virtual memory
    setStatus('loading', 'Downloading Parquet database (6MB)...');
    const parquetUrl = window.location.origin + '/education_occupation.parquet';
    const response = await fetch(parquetUrl);
    if (!response.ok) {
      throw new Error(`HTTP error ${response.status} fetching Parquet file`);
    }
    const buffer = await response.arrayBuffer();
    
    setStatus('loading', 'Mounting database to memory...');
    await db.registerFileBuffer(
      'education_occupation.parquet', 
      new Uint8Array(buffer)
    );
    
    dbInitialized = true;
    console.log('DuckDB-Wasm and Parquet database mounted successfully!');
    setStatus('success', 'Database mounted (DuckDB-Wasm)');
    return conn;
  } catch (err) {
    console.error('Failed to initialize DuckDB-Wasm:', err);
    setStatus('error', 'Using representative data (DuckDB unavailable)');
    dbInitialized = false;
    return null;
  }
}

async function runQuery(sql) {
  if (!dbInitialized) {
    await initDuckDB();
  }
  if (!conn) {
    throw new Error("DuckDB not initialized.");
  }
  
  const result = await conn.query(sql);
  return result.toArray().map(row => {
    const obj = {};
    for (const key of Object.keys(row)) {
      const val = row[key];
      // Convert BigInt/HugeInt values to regular Numbers
      if (typeof val === 'bigint') {
        obj[key] = Number(val);
      } else if (val !== null && typeof val === 'object' && typeof val.toString === 'function') {
        const str = val.toString();
        if (/^-?\d+n?$/.test(str)) {
          obj[key] = Number(str.replace('n', ''));
        } else {
          obj[key] = val;
        }
      } else {
        obj[key] = val;
      }
    }
    return obj;
  });
}

// ─────────────────────────────────────────────────────────────
// Data Loading & Setup
// ─────────────────────────────────────────────────────────────

async function loadData() {
  setStatus('loading', 'Initializing database...');
  
  if (!dbInitialized) {
    await initDuckDB();
  }
  
  const warningEl = document.getElementById('fallbackWarning');
  if (dbInitialized) {
    setStatus('success', 'Connected to local Parquet database');
    if (warningEl) warningEl.style.display = 'none';
  } else {
    setStatus('error', 'Using representative data (Offline)');
    if (warningEl) warningEl.style.display = 'flex';
  }
  
  // Populate filter dropdown lists
  await populateFiltersOnce();
  
  // Update dashboard visualizations
  await updateDashboard();
}

async function populateFiltersOnce() {
  let fosSet = [];
  let nocSet = [];
  
  const curFos = document.getElementById('fosFilter')?.value || 'all';
  const curNoc = document.getElementById('nocFilter')?.value || 'all';
  
  if (dbInitialized) {
    try {
      // Query 2-digit CIP fields and 4-digit CIP subfields
      const fosRows = await runQuery(`
        SELECT DISTINCT fieldOfStudy 
        FROM 'education_occupation.parquet' 
        WHERE regexp_matches(fieldOfStudy, '^[0-9]{2}\\. ') 
           OR regexp_matches(fieldOfStudy, '^[0-9]{2}\\.[0-9]{2}\\s') 
        ORDER BY fieldOfStudy
      `);
      
      // Query 1-digit NOC groups and 5-digit NOC unit groups
      const nocRows = await runQuery(`
        SELECT DISTINCT occupation 
        FROM 'education_occupation.parquet' 
        WHERE regexp_matches(occupation, '^[0-9]\\s') 
           OR regexp_matches(occupation, '^[0-9]{5}\\s') 
        ORDER BY occupation
      `);
      
      const fosEl = document.getElementById('fosFilter');
      const nocEl = document.getElementById('nocFilter');
      
      if (fosEl && nocEl) {
        // Populate Field of Study dropdown using `<optgroup>`
        let fosHtml = '<option value="all">All Fields</option>';
        let currentOptGroup = null;
        
        for (const row of fosRows) {
          const f = row.fieldOfStudy;
          if (f.match(/^[0-9]{2}\. /)) {
            // It's a 2-digit parent category
            if (currentOptGroup) fosHtml += `</optgroup>`;
            fosHtml += `<optgroup label="${escHtml(f)}">`;
            currentOptGroup = f;
            
            // Add the parent category as the first select option inside the group
            fosHtml += `<option value="${escHtml(f)}" ${f === curFos ? 'selected' : ''}>[All] ${escHtml(f)}</option>`;
          } else if (f.match(/^[0-9]{2}\.[0-9]{2}\s/)) {
            // It's a 4-digit subfield
            fosHtml += `<option value="${escHtml(f)}" ${f === curFos ? 'selected' : ''}>${escHtml(f)}</option>`;
          }
        }
        if (currentOptGroup) fosHtml += `</optgroup>`;
        fosEl.innerHTML = fosHtml;
        
        // Populate Occupation dropdown using `<optgroup>`
        let nocHtml = '<option value="all">All Occupations</option>';
        currentOptGroup = null;
        
        for (const row of nocRows) {
          const n = row.occupation;
          if (n.match(/^[0-9]\s/)) {
            // It's a 1-digit broad category
            if (currentOptGroup) nocHtml += `</optgroup>`;
            nocHtml += `<optgroup label="${escHtml(n)}">`;
            currentOptGroup = n;
            
            // Add the parent category as the first select option inside the group
            nocHtml += `<option value="${escHtml(n)}" ${n === curNoc ? 'selected' : ''}>[All] ${escHtml(n)}</option>`;
          } else if (n.match(/^[0-9]{5}\s/)) {
            // It's a 5-digit unit group
            nocHtml += `<option value="${escHtml(n)}" ${n === curNoc ? 'selected' : ''}>${escHtml(n)}</option>`;
          }
        }
        if (currentOptGroup) nocHtml += `</optgroup>`;
        nocEl.innerHTML = nocHtml;
        
        return; // Options successfully built from DuckDB
      }
    } catch (e) {
      console.warn("Failed to query filters from DuckDB, using fallback", e);
    }
  }
  
  // Fallback to Embedded preview list
  fosSet = [...new Set(EMBEDDED_DATA.map(d => d.fieldOfStudy))].sort();
  nocSet = [...new Set(EMBEDDED_DATA.map(d => d.occupation))].sort();
  
  const fosEl = document.getElementById('fosFilter');
  const nocEl = document.getElementById('nocFilter');
  if (!fosEl || !nocEl) return;
  
  fosEl.innerHTML = '<option value="all">All Fields</option>' +
    fosSet.map(f => `<option value="${f}" ${f===curFos?'selected':''}>${f}</option>`).join('');
  nocEl.innerHTML = '<option value="all">All Occupations</option>' +
    nocSet.map(n => `<option value="${n}" ${n===curNoc?'selected':''}>${n}</option>`).join('');
}

// Helper filter mappings
function mapGenderFilter(genderFilter) {
  switch (genderFilter) {
    case '2': return 'Men+';
    case '3': return 'Women+';
    default: return 'Total - Gender';
  }
}

function mapEduFilter(eduFilter) {
  switch (eduFilter) {
    case 'bachelor': return "Bachelor's degree";
    case 'master': return "Master's degree";
    case 'phd': return "Earned doctorate";
    case 'college': return "College, CEGEP or other non-university certificate or diploma";
    case 'trade': return "Apprenticeship or trades certificate or diploma";
    default: return "Total - Highest certificate, diploma or degree";
  }
}

// ─────────────────────────────────────────────────────────────
// Dashboard Update
// ─────────────────────────────────────────────────────────────

async function updateDashboard() {
  const fosFilter    = document.getElementById('fosFilter')?.value    || 'all';
  const nocFilter    = document.getElementById('nocFilter')?.value    || 'all';
  const eduFilter    = document.getElementById('eduFilter')?.value    || 'all';
  const genderFilter = document.getElementById('genderFilter')?.value || '1';
  
  setStatus('loading', 'Querying database...');
  
  try {
    const genderVal = mapGenderFilter(genderFilter);
    const eduVal = mapEduFilter(eduFilter);
    
    // Escape single quotes for SQL insertion
    const genderValEsc = genderVal.replace(/'/g, "''");
    const eduValEsc    = eduVal.replace(/'/g, "''");
    const fosFilterEsc = fosFilter.replace(/'/g, "''");
    const nocFilterEsc = nocFilter.replace(/'/g, "''");
    
    let stats = {};
    let sankeyFlows = [];
    let heatmapData = [];
    let topOccData = [];
    let topFOSData = [];
    let alignmentData = [];
    let tableData = [];
    
    if (dbInitialized) {
      // 1. STATS CARDS
      let totalQ = "";
      if (fosFilter === 'all' && nocFilter === 'all') {
        totalQ = `
          SELECT CAST(SUM(count) AS INTEGER) as total
          FROM 'education_occupation.parquet'
          WHERE gender = '${genderValEsc}'
            AND education = '${eduValEsc}'
            AND fieldOfStudy = 'Total - Major field of study - Classification of Instructional Programs (CIP) 2021'
            AND occupation = 'Total - Occupation - Unit group - National Occupational Classification (NOC) 2021'
        `;
      } else if (fosFilter !== 'all' && nocFilter === 'all') {
        totalQ = `
          SELECT CAST(SUM(count) AS INTEGER) as total
          FROM 'education_occupation.parquet'
          WHERE gender = '${genderValEsc}'
            AND education = '${eduValEsc}'
            AND fieldOfStudy = '${fosFilterEsc}'
            AND occupation = 'Total - Occupation - Unit group - National Occupational Classification (NOC) 2021'
        `;
      } else if (fosFilter === 'all' && nocFilter !== 'all') {
        totalQ = `
          SELECT CAST(SUM(count) AS INTEGER) as total
          FROM 'education_occupation.parquet'
          WHERE gender = '${genderValEsc}'
            AND education = '${eduValEsc}'
            AND fieldOfStudy = 'Total - Major field of study - Classification of Instructional Programs (CIP) 2021'
            AND occupation = '${nocFilterEsc}'
        `;
      } else {
        totalQ = `
          SELECT CAST(SUM(count) AS INTEGER) as total
          FROM 'education_occupation.parquet'
          WHERE gender = '${genderValEsc}'
            AND education = '${eduValEsc}'
            AND fieldOfStudy = '${fosFilterEsc}'
            AND occupation = '${nocFilterEsc}'
        `;
      }
      
      const totalRes = await runQuery(totalQ);
      const totalWorkers = totalRes[0]?.total || 0;
      
      let fosCountQ = "";
      if (fosFilter === 'all') {
        fosCountQ = `
          SELECT CAST(COUNT(DISTINCT fieldOfStudy) AS INTEGER) as total_fos
          FROM 'education_occupation.parquet'
          WHERE gender = '${genderValEsc}'
            AND education = '${eduValEsc}'
            AND regexp_matches(fieldOfStudy, '^[0-9]{2}\\. ')
            AND count > 0
        `;
      } else if (fosFilter.match(/^[0-9]{2}\. /)) {
        const fosCode = fosFilter.match(/^\d{2}/)[0];
        fosCountQ = `
          SELECT CAST(COUNT(DISTINCT fieldOfStudy) AS INTEGER) as total_fos
          FROM 'education_occupation.parquet'
          WHERE gender = '${genderValEsc}'
            AND education = '${eduValEsc}'
            AND regexp_matches(fieldOfStudy, '^${fosCode}\\.[0-9]{2} ')
            AND count > 0
        `;
      } else {
        fosCountQ = `SELECT 1 as total_fos`;
      }
      
      let nocCountQ = "";
      if (nocFilter === 'all') {
        nocCountQ = `
          SELECT CAST(COUNT(DISTINCT occupation) AS INTEGER) as total_noc
          FROM 'education_occupation.parquet'
          WHERE gender = '${genderValEsc}'
            AND education = '${eduValEsc}'
            AND regexp_matches(occupation, '^[0-9]\\s')
            AND count > 0
        `;
      } else if (nocFilter.match(/^[0-9]\s/)) {
        const nocCode = nocFilter.match(/^\d/)[0];
        nocCountQ = `
          SELECT CAST(COUNT(DISTINCT occupation) AS INTEGER) as total_noc
          FROM 'education_occupation.parquet'
          WHERE gender = '${genderValEsc}'
            AND education = '${eduValEsc}'
            AND regexp_matches(occupation, '^${nocCode}[0-9]{4}\\s')
            AND count > 0
        `;
      } else {
        nocCountQ = `SELECT 1 as total_noc`;
      }
      
      const fosCountRes = await runQuery(fosCountQ);
      const nocCountRes = await runQuery(nocCountQ);
      
      stats = {
        totalWorkers: totalWorkers,
        totalFOS: fosCountRes[0]?.total_fos || 0,
        totalOcc: nocCountRes[0]?.total_noc || 0,
        matchPct: '—'
      };
      
      // 2. SANKEY FLOWS & HEATMAP (Unified query builder based on selections)
      let srcExpr = "";
      let srcFilterExpr = "";
      if (fosFilter === 'all') {
        srcExpr = "fieldOfStudy";
        srcFilterExpr = "regexp_matches(fieldOfStudy, '^[0-9]{2}\\. ')";
      } else if (fosFilter.match(/^[0-9]{2}\. /)) {
        const fosCode = fosFilter.match(/^\d{2}/)[0];
        srcExpr = "fieldOfStudy";
        srcFilterExpr = `regexp_matches(fieldOfStudy, '^${fosCode}\\.[0-9]{2} ')`;
      } else {
        srcExpr = "fieldOfStudy";
        srcFilterExpr = `fieldOfStudy = '${fosFilterEsc}'`;
      }

      let tgtExpr = "";
      let tgtFilterExpr = "";
      if (nocFilter === 'all') {
        tgtExpr = "occupation";
        tgtFilterExpr = "regexp_matches(occupation, '^[0-9]\\s')";
      } else if (nocFilter.match(/^[0-9]\s/)) {
        const nocCode = nocFilter.match(/^\d/)[0];
        tgtExpr = "occupation";
        tgtFilterExpr = `regexp_matches(occupation, '^${nocCode}[0-9]{4}\\s')`;
      } else {
        tgtExpr = "occupation";
        tgtFilterExpr = `occupation = '${nocFilterEsc}'`;
      }

      sankeyFlows = await runQuery(`
        SELECT ${srcExpr} as src, ${tgtExpr} as tgt, CAST(SUM(count) AS INTEGER) as val
        FROM 'education_occupation.parquet'
        WHERE gender = '${genderValEsc}'
          AND education = '${eduValEsc}'
          AND ${srcFilterExpr}
          AND ${tgtFilterExpr}
        GROUP BY src, tgt
      `);
      
      if (sankeyFlows.length > 0) {
        const sortedFlows = [...sankeyFlows].sort((a, b) => b.val - a.val);
        const topFlowVal = sortedFlows[0].val;
        const flowsSum = sortedFlows.reduce((sum, f) => sum + f.val, 0);
        stats.matchPct = flowsSum > 0 ? `${((topFlowVal / flowsSum) * 100).toFixed(1)}%` : '—';
      }
      
      heatmapData = sankeyFlows;
      
      // 3. TOP OCCUPATIONS CHART
      let topOccQ = "";
      if (fosFilter === 'all') {
        topOccQ = `
          SELECT occupation, CAST(SUM(count) AS INTEGER) as val
          FROM 'education_occupation.parquet'
          WHERE gender = '${genderValEsc}'
            AND education = '${eduValEsc}'
            AND fieldOfStudy = 'Total - Major field of study - Classification of Instructional Programs (CIP) 2021'
            AND regexp_matches(occupation, '^[0-9]\\s')
          GROUP BY occupation
          ORDER BY val DESC
          LIMIT 10
        `;
      } else {
        topOccQ = `
          SELECT occupation, CAST(SUM(count) AS INTEGER) as val
          FROM 'education_occupation.parquet'
          WHERE gender = '${genderValEsc}'
            AND education = '${eduValEsc}'
            AND fieldOfStudy = '${fosFilterEsc}'
            AND regexp_matches(occupation, '^[0-9]{5}\\s')
          GROUP BY occupation
          ORDER BY val DESC
          LIMIT 10
        `;
      }
      topOccData = await runQuery(topOccQ);
      
      // 4. TOP FIELDS OF STUDY CHART
      let topFosQ = "";
      if (nocFilter === 'all') {
        topFosQ = `
          SELECT fieldOfStudy, CAST(SUM(count) AS INTEGER) as val
          FROM 'education_occupation.parquet'
          WHERE gender = '${genderValEsc}'
            AND education = '${eduValEsc}'
            AND occupation = 'Total - Occupation - Unit group - National Occupational Classification (NOC) 2021'
            AND regexp_matches(fieldOfStudy, '^[0-9]{2}\\. ')
          GROUP BY fieldOfStudy
          ORDER BY val DESC
          LIMIT 8
        `;
      } else {
        topFosQ = `
          SELECT fieldOfStudy, CAST(SUM(count) AS INTEGER) as val
          FROM 'education_occupation.parquet'
          WHERE gender = '${genderValEsc}'
            AND education = '${eduValEsc}'
            AND occupation = '${nocFilterEsc}'
            AND regexp_matches(fieldOfStudy, '^[0-9]{2}\\.[0-9]{2}\\s')
          GROUP BY fieldOfStudy
          ORDER BY val DESC
          LIMIT 8
        `;
      }
      topFOSData = await runQuery(topFosQ);
      
      // 5. ALIGNMENT CHART
      const alignmentQ = `
        SELECT fieldOfStudy, occupation, CAST(SUM(count) AS INTEGER) as val
        FROM 'education_occupation.parquet'
        WHERE gender = '${genderValEsc}'
          AND education = '${eduValEsc}'
          AND regexp_matches(fieldOfStudy, '^[0-9]{2}\\. ')
          AND regexp_matches(occupation, '^[0-9]\\s')
        GROUP BY fieldOfStudy, occupation
      `;
      alignmentData = await runQuery(alignmentQ);
      
      // 6. DATA TABLE (Unified query builder)
      let tableFieldExpr = "";
      let tableFieldFilter = "";
      if (fosFilter === 'all') {
        tableFieldExpr = "fieldOfStudy";
        tableFieldFilter = "regexp_matches(fieldOfStudy, '^[0-9]{2}\\. ')";
      } else if (fosFilter.match(/^[0-9]{2}\. /)) {
        const fosCode = fosFilter.match(/^\d{2}/)[0];
        tableFieldExpr = "fieldOfStudy";
        tableFieldFilter = `regexp_matches(fieldOfStudy, '^${fosCode}\\.[0-9]{2} ')`;
      } else {
        tableFieldExpr = "fieldOfStudy";
        tableFieldFilter = `fieldOfStudy = '${fosFilterEsc}'`;
      }

      let tableOccExpr = "";
      let tableOccFilter = "";
      let nocCodeExpr = "";
      if (nocFilter === 'all') {
        tableOccExpr = "occupation";
        tableOccFilter = "regexp_matches(occupation, '^[0-9]\\s')";
        nocCodeExpr = "regexp_extract(occupation, '^([0-9])', 1)";
      } else if (nocFilter.match(/^[0-9]\s/)) {
        const nocCode = nocFilter.match(/^\d/)[0];
        tableOccExpr = "occupation";
        tableOccFilter = `regexp_matches(occupation, '^${nocCode}[0-9]{4}\\s')`;
        nocCodeExpr = "regexp_extract(occupation, '^([0-9]{5})', 1)";
      } else {
        tableOccExpr = "occupation";
        tableOccFilter = `occupation = '${nocFilterEsc}'`;
        nocCodeExpr = "regexp_extract(occupation, '^([0-9]{5})', 1)";
      }

      tableData = await runQuery(`
        SELECT ${tableFieldExpr} as fieldOfStudy, ${tableOccExpr} as occupation, 
               CAST(SUM(count) AS INTEGER) as count, ${nocCodeExpr} as nocCode
        FROM 'education_occupation.parquet'
        WHERE gender = '${genderValEsc}'
          AND education = '${eduValEsc}'
          AND ${tableFieldFilter}
          AND ${tableOccFilter}
        GROUP BY fieldOfStudy, occupation
      `);
      
      setStatus('success', `Live Database · SQL execution in milliseconds`);
    } else {
      // Fallback fallback mode
      filteredData = EMBEDDED_DATA.filter(d => {
        if (fosFilter !== 'all' && d.fieldOfStudy !== fosFilter) return false;
        if (nocFilter !== 'all' && d.occupation !== nocFilter) return false;
        return true;
      });
      
      const totalWorkers = filteredData.reduce((s, d) => s + d.count, 0);
      const fosCount = new Set(filteredData.map(d => d.fieldOfStudy)).size;
      const nocCount = new Set(filteredData.map(d => d.occupation)).size;
      const maxRow = filteredData.reduce((a, b) => (a.count > b.count ? a : b), { count: 0 });
      
      stats = {
        totalWorkers: totalWorkers,
        totalFOS: fosCount,
        totalOcc: nocCount,
        matchPct: totalWorkers > 0 ? `${((maxRow.count / totalWorkers) * 100).toFixed(1)}%` : '—'
      };
      
      sankeyFlows = filteredData.map(d => ({ src: d.fieldOfStudy, tgt: d.occupation, val: d.count }));
      heatmapData = sankeyFlows;
      
      const occAgg = {};
      for (const d of filteredData) occAgg[d.occupation] = (occAgg[d.occupation] || 0) + d.count;
      topOccData = Object.entries(occAgg).map(([k, v]) => ({ occupation: k, val: v })).sort((a,b)=>b.val-a.val).slice(0, 10);
      
      const fosAgg = {};
      for (const d of filteredData) fosAgg[d.fieldOfStudy] = (fosAgg[d.fieldOfStudy] || 0) + d.count;
      topFOSData = Object.entries(fosAgg).map(([k, v]) => ({ fieldOfStudy: k, val: v })).sort((a,b)=>b.val-a.val).slice(0, 8);
      
      alignmentData = EMBEDDED_DATA.map(d => ({ fieldOfStudy: d.fieldOfStudy, occupation: d.occupation, val: d.count }));
      
      tableData = filteredData.map(d => ({ fieldOfStudy: d.fieldOfStudy, occupation: d.occupation, count: d.count, nocCode: d.nocCode }));
    }
    
    // Render elements
    renderStats(stats);
    renderSankeyChart(sankeyFlows);
    renderHeatmapChart(heatmapData);
    renderTopOcc(topOccData, fosFilter);
    renderTopFOS(topFOSData, nocFilter);
    renderAlignment(alignmentData);
    renderTableData(tableData);
    
  } catch (err) {
    console.error("Error updating dashboard visuals:", err);
    setStatus('error', `Database query execution failed: ${err.message}`);
  }
}

// ─────────────────────────────────────────────────────────────
// Component Rendering
// ─────────────────────────────────────────────────────────────

function renderStats(stats) {
  setText('totalWorkers', stats.totalWorkers > 0 ? formatNum(stats.totalWorkers) : '—');
  setText('totalFOS', stats.totalFOS || '—');
  setText('totalOcc', stats.totalOcc || '—');
  setText('fieldMatch', stats.matchPct);
}

function renderSankeyChart(flows) {
  const container = document.getElementById('sankeyContainer');
  if (!container) return;
  container.innerHTML = '';

  const sortedFlows = [...flows]
    .map(f => ({ src: f.src, tgt: f.tgt, value: f.val || f.value || 0 }))
    .filter(f => f.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 60);

  if (sortedFlows.length === 0) {
    container.innerHTML = '<div class="chart-placeholder"><p>No data to display</p></div>';
    return;
  }

  const W = container.clientWidth || 900;
  const H = 400;
  const margin = { top: 10, right: 200, bottom: 10, left: 200 };

  const svg = d3.select(container)
    .append('svg')
    .attr('width', W)
    .attr('height', H)
    .attr('viewBox', `0 0 ${W} ${H}`)
    .style('overflow', 'visible');

  const nodeNames = [...new Set([...sortedFlows.map(f => f.src), ...sortedFlows.map(f => f.tgt)])];
  const nodeIndex = Object.fromEntries(nodeNames.map((n, i) => [n, i]));

  const sankeyData = {
    nodes: nodeNames.map(n => ({ name: n })),
    links: sortedFlows.map(f => ({
      source: nodeIndex[f.src],
      target: nodeIndex[f.tgt],
      value:  f.value
    }))
  };

  const sankey = d3.sankey()
    .nodeWidth(16)
    .nodePadding(10)
    .extent([[margin.left, margin.top], [W - margin.right, H - margin.bottom]]);

  const { nodes, links } = sankey(sankeyData);

  function nodeColor(d) {
    if (d.x0 >= W / 2) {
      return nocColor(d.name);
    } else {
      return fosColor(d.name);
    }
  }

  const tooltip = d3.select('#d3Tooltip');

  svg.append('g')
    .selectAll('path')
    .data(links)
    .join('path')
    .attr('d', d3.sankeyLinkHorizontal())
    .attr('stroke', d => nodeColor(d.source))
    .attr('stroke-width', d => Math.max(1, d.width))
    .attr('fill', 'none')
    .attr('opacity', 0.25)
    .on('mouseover', function(event, d) {
      d3.select(this).attr('opacity', 0.6);
      tooltip.classed('visible', true)
        .html(`<div class="tooltip-label">${d.source.name}</div>
               <div class="tooltip-value">→ ${d.target.name}</div>
               <div class="tooltip-value">${formatNum(d.value)} workers</div>`);
    })
    .on('mousemove', event => {
      tooltip.style('left', (event.clientX + 14) + 'px')
             .style('top',  (event.clientY - 30) + 'px');
    })
    .on('mouseout', function() {
      d3.select(this).attr('opacity', 0.25);
      tooltip.classed('visible', false);
    });

  const nodeG = svg.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g');

  nodeG.append('rect')
    .attr('x', d => d.x0)
    .attr('y', d => d.y0)
    .attr('height', d => Math.max(2, d.y1 - d.y0))
    .attr('width', d => d.x1 - d.x0)
    .attr('fill', d => nodeColor(d))
    .attr('rx', 3)
    .attr('opacity', 0.9)
    .on('mouseover', function(event, d) {
      tooltip.classed('visible', true)
        .html(`<div class="tooltip-label">${d.name}</div>
               <div class="tooltip-value">${formatNum(d.value)} workers</div>`);
    })
    .on('mousemove', event => {
      tooltip.style('left', (event.clientX + 14) + 'px')
             .style('top',  (event.clientY - 30) + 'px');
    })
    .on('mouseout', () => tooltip.classed('visible', false));

  nodeG.append('text')
    .attr('x', d => d.x0 < W / 2 ? d.x0 - 6 : d.x1 + 6)
    .attr('y', d => (d.y0 + d.y1) / 2)
    .attr('dy', '0.35em')
    .attr('text-anchor', d => d.x0 < W / 2 ? 'end' : 'start')
    .attr('font-size', '11px')
    .attr('font-family', 'Inter, sans-serif')
    .attr('fill', '#94a3b8')
    .text(d => {
      const maxLen = 26;
      return d.name.length > maxLen ? d.name.slice(0, maxLen) + '…' : d.name;
    });

  const legendEl = document.getElementById('sankeyLegend');
  if (legendEl) {
    legendEl.innerHTML =
      `<div class="legend-item"><div class="legend-dot" style="background:#10b981"></div>Field of Study</div>` +
      `<div class="legend-item"><div class="legend-dot" style="background:#6366f1"></div>Occupation Group</div>`;
  }
}

function renderHeatmapChart(data) {
  const canvas = document.getElementById('heatmapChart');
  if (!canvas) return;

  const fosFields = [...new Set(data.map(d => d.src))].sort();
  const nocGroups = [...new Set(data.map(d => d.tgt))].sort();

  const topFOS = fosFields.slice(0, 10);
  const topNOC = nocGroups.slice(0, 8);

  const matrix = {};
  const rowtotals = {};
  for (const d of data) {
    if (!topFOS.includes(d.src) || !topNOC.includes(d.tgt)) continue;
    const k = `${d.src}||${d.tgt}`;
    matrix[k] = (matrix[k] || 0) + d.val;
    rowtotals[d.src] = (rowtotals[d.src] || 0) + d.val;
  }

  const pctMatrix = {};
  for (const k of Object.keys(matrix)) {
    const fos = k.split('||')[0];
    pctMatrix[k] = rowtotals[fos] ? (matrix[k] / rowtotals[fos]) * 100 : 0;
  }

  const maxPct = Math.max(...Object.values(pctMatrix), 1);

  if (charts.heatmap) { charts.heatmap.destroy(); }

  const datasets = topNOC.map((noc, ni) => ({
    label: noc,
    data: topFOS.map(fos => {
      const pct = pctMatrix[`${fos}||${noc}`] || 0;
      return { x: ni, y: topFOS.indexOf(fos), r: Math.max(3, (pct / maxPct) * 22) };
    }),
    backgroundColor: hexWithAlpha(nocColor(noc), 0.75),
    borderColor:     hexWithAlpha(nocColor(noc), 1),
    borderWidth: 1,
  }));

  charts.heatmap = new Chart(canvas, {
    type: 'bubble',
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      animation: { duration: 600 },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => {
              const { x, y } = ctx.raw;
              const fos = topFOS[y];
              const noc = topNOC[x];
              const pct = pctMatrix[`${fos}||${noc}`] || 0;
              return `${fos} → ${noc}: ${pct.toFixed(1)}%`;
            }
          },
          backgroundColor: '#161b27',
          borderColor: 'rgba(99,102,241,0.3)',
          borderWidth: 1,
          titleColor: '#f0f4ff',
          bodyColor: '#94a3b8',
        }
      },
      scales: {
        x: {
          type: 'linear',
          min: -0.5,
          max: topNOC.length - 0.5,
          ticks: {
            stepSize: 1,
            color: '#64748b',
            font: { size: 10, family: 'Inter' },
            callback: v => topNOC[v]?.slice(0, 12) || '',
            maxRotation: 45,
          },
          grid: { color: 'rgba(255,255,255,0.04)' },
        },
        y: {
          type: 'linear',
          min: -0.5,
          max: topFOS.length - 0.5,
          ticks: {
            stepSize: 1,
            color: '#64748b',
            font: { size: 10, family: 'Inter' },
            callback: v => topFOS[v]?.slice(0, 20) || '',
          },
          grid: { color: 'rgba(255,255,255,0.04)' },
        }
      }
    }
  });
}

function renderTopOcc(data, selectedFOS) {
  const canvas = document.getElementById('topOccChart');
  if (!canvas) return;

  const sorted = [...data].sort((a, b) => b.val - a.val).slice(0, 10);

  if (charts.topOcc) charts.topOcc.destroy();

  const label = selectedFOS !== 'all' ? selectedFOS : 'All Fields';

  charts.topOcc = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: sorted.map(d => d.occupation.length > 22 ? d.occupation.slice(0, 22) + '…' : d.occupation),
      datasets: [{
        label: `Workers from ${label}`,
        data:  sorted.map(d => d.val),
        backgroundColor: sorted.map(d => hexWithAlpha(nocColor(d.occupation), 0.7)),
        borderColor:     sorted.map(d => nocColor(d.occupation)),
        borderWidth: 1.5,
        borderRadius: 5,
        borderSkipped: false,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 500 },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: ctx => ` ${formatNum(ctx.raw)} workers` },
          backgroundColor: '#161b27',
          borderColor: 'rgba(99,102,241,0.3)',
          borderWidth: 1,
          titleColor: '#f0f4ff',
          bodyColor: '#94a3b8',
        }
      },
      scales: {
        x: {
          ticks: { color: '#64748b', font: { size: 11 }, callback: v => formatNum(v) },
          grid: { color: 'rgba(255,255,255,0.05)' }
        },
        y: {
          ticks: { color: '#94a3b8', font: { size: 10, family: 'Inter' } },
          grid: { display: false }
        }
      }
    }
  });
}

function renderTopFOS(data, selectedNOC) {
  const canvas = document.getElementById('topFOSChart');
  if (!canvas) return;

  const sorted = [...data].sort((a, b) => b.val - a.val).slice(0, 8);
  const total  = sorted.reduce((s, d) => s + d.val, 0);

  if (charts.topFOS) charts.topFOS.destroy();

  const label = selectedNOC !== 'all' ? selectedNOC : 'All Occupations';
  const colors = sorted.map(d => fosColor(d.fieldOfStudy));

  charts.topFOS = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: sorted.map(d => d.fieldOfStudy.length > 28 ? d.fieldOfStudy.slice(0, 28) + '…' : d.fieldOfStudy),
      datasets: [{
        data: sorted.map(d => d.val),
        backgroundColor: colors.map(c => hexWithAlpha(c, 0.8)),
        borderColor: colors,
        borderWidth: 1.5,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '62%',
      animation: { duration: 500 },
      plugins: {
        legend: {
          position: 'right',
          labels: {
            color: '#94a3b8',
            font: { size: 10, family: 'Inter' },
            boxWidth: 12,
            padding: 8,
          }
        },
        tooltip: {
          callbacks: {
            label: ctx => {
              const pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
              return ` ${formatNum(ctx.raw)} (${pct}%)`;
            }
          },
          backgroundColor: '#161b27',
          borderColor: 'rgba(99,102,241,0.3)',
          borderWidth: 1,
          titleColor: '#f0f4ff',
          bodyColor: '#94a3b8',
        }
      }
    }
  });
}

function renderAlignment(data) {
  const canvas = document.getElementById('alignmentChart');
  if (!canvas) return;

  const fosGroups = {};
  for (const d of data) {
    if (!fosGroups[d.fieldOfStudy]) fosGroups[d.fieldOfStudy] = { total: 0, max: 0, topOcc: '' };
    fosGroups[d.fieldOfStudy].total += d.val;
    if (d.val > fosGroups[d.fieldOfStudy].max) {
      fosGroups[d.fieldOfStudy].max = d.val;
      fosGroups[d.fieldOfStudy].topOcc = d.occupation;
    }
  }

  const alignments = Object.entries(fosGroups)
    .map(([fos, g]) => ({ fos, pct: g.total > 0 ? (g.max / g.total) * 100 : 0, topOcc: g.topOcc }))
    .sort((a, b) => b.pct - a.pct)
    .slice(0, 10);

  if (charts.alignment) charts.alignment.destroy();

  charts.alignment = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: alignments.map(d => d.fos.length > 20 ? d.fos.slice(0,20)+'…' : d.fos),
      datasets: [{
        label: '% in primary occupation',
        data:  alignments.map(d => parseFloat(d.pct.toFixed(1))),
        backgroundColor: alignments.map(d => hexWithAlpha(fosColor(d.fos), 0.7)),
        borderColor:     alignments.map(d => fosColor(d.fos)),
        borderWidth: 1.5,
        borderRadius: 5,
        borderSkipped: false,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 500 },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            afterLabel: (ctx) => {
              const d = alignments[ctx.dataIndex];
              return d ? `Top occ: ${d.topOcc}` : '';
            },
            label: ctx => ` ${ctx.raw}% concentration`
          },
          backgroundColor: '#161b27',
          borderColor: 'rgba(99,102,241,0.3)',
          borderWidth: 1,
          titleColor: '#f0f4ff',
          bodyColor: '#94a3b8',
        }
      },
      scales: {
        x: {
          ticks: { color: '#64748b', font: { size: 9, family: 'Inter' }, maxRotation: 45 },
          grid: { display: false }
        },
        y: {
          min: 0,
          max: 100,
          ticks: { color: '#64748b', font: { size: 11 }, callback: v => `${v}%` },
          grid: { color: 'rgba(255,255,255,0.05)' }
        }
      }
    }
  });
}

function renderTableData(data) {
  // Add percentage calculations to rows relative to total for that Field of Study
  const rows = data.map(d => {
    const totalForFOS = data
      .filter(r => r.fieldOfStudy === d.fieldOfStudy)
      .reduce((s, r) => s + r.count, 0);
    const pct = totalForFOS > 0 ? (d.count / totalForFOS) * 100 : 0;
    return { ...d, pct };
  }).sort((a, b) => b.count - a.count);

  currentTableRows = rows;
  
  // Render table with search query
  applyTableFilterAndSort(document.getElementById('tableSearch')?.value || '');
}

function applyTableFilterAndSort(searchQuery = '') {
  const tbody = document.getElementById('tableBody');
  if (!tbody) return;

  let rows = currentTableRows;

  // Apply search query
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    rows = rows.filter(r =>
      r.fieldOfStudy.toLowerCase().includes(q) ||
      r.occupation.toLowerCase().includes(q)
    );
  }

  // Apply column sorting
  rows = [...rows].sort((a, b) => {
    const cols = ['fieldOfStudy', 'occupation', 'nocCode', 'count', 'pct'];
    const col  = cols[sortState.col] || 'count';
    const dir  = sortState.asc ? 1 : -1;
    if (typeof a[col] === 'string') return dir * a[col].localeCompare(b[col]);
    return dir * ((a[col] || 0) - (b[col] || 0));
  });

  const maxCount = Math.max(...rows.map(r => r.count), 1);

  tbody.innerHTML = rows.slice(0, 200).map(r => {
    const barWidth = Math.round((r.count / maxCount) * 100);
    const pctDisplay = r.pct ? r.pct.toFixed(1) + '%' : '—';
    const nocCode = r.nocCode ? `<span class="noc-badge">${r.nocCode}xx</span>` : '—';
    return `<tr>
      <td>${escHtml(r.fieldOfStudy)}</td>
      <td>${escHtml(r.occupation)}</td>
      <td>${nocCode}</td>
      <td>
        <div class="pct-bar-wrap">
          <div class="pct-bar" style="width:${barWidth * 0.6}px"></div>
          <span class="pct-text">${formatNum(r.count)}</span>
        </div>
      </td>
      <td>${pctDisplay}</td>
    </tr>`;
  }).join('');

  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="loading-row">No matching records</td></tr>';
  }
}

// Global table sort & filter bindings
window.filterTable = function(q) { applyTableFilterAndSort(q); };
window.sortTable = function(col) {
  if (sortState.col === col) sortState.asc = !sortState.asc;
  else { sortState.col = col; sortState.asc = false; }
  applyTableFilterAndSort(document.getElementById('tableSearch')?.value || '');
};

// ─────────────────────────────────────────────────────────────
// Embedded Fallback Data Construction
// ─────────────────────────────────────────────────────────────

function buildEmbeddedData() {
  const matrix = [
    { fos: '52', fosLabel: 'Business & Management',       noc: '1', nocLabel: 'Business & Finance',            count: 412000 },
    { fos: '52', fosLabel: 'Business & Management',       noc: '0', nocLabel: 'Management',                    count: 285000 },
    { fos: '52', fosLabel: 'Business & Management',       noc: '6', nocLabel: 'Sales & Service',                count: 98000  },
    { fos: '52', fosLabel: 'Business & Management',       noc: '4', nocLabel: 'Education, Law & Social',        count: 42000  },
    { fos: '52', fosLabel: 'Business & Management',       noc: '2', nocLabel: 'Natural & Applied Sciences',     count: 31000  },
    { fos: '14', fosLabel: 'Engineering',                 noc: '2', nocLabel: 'Natural & Applied Sciences',     count: 378000 },
    { fos: '14', fosLabel: 'Engineering',                 noc: '0', nocLabel: 'Management',                    count: 68000  },
    { fos: '14', fosLabel: 'Engineering',                 noc: '7', nocLabel: 'Trades & Transport',             count: 45000  },
    { fos: '14', fosLabel: 'Engineering',                 noc: '1', nocLabel: 'Business & Finance',            count: 38000  },
    { fos: '14', fosLabel: 'Engineering',                 noc: '9', nocLabel: 'Manufacturing & Utilities',      count: 22000  },
    { fos: '51', fosLabel: 'Health Professions',          noc: '3', nocLabel: 'Health Occupations',             count: 418000 },
    { fos: '51', fosLabel: 'Health Professions',          noc: '4', nocLabel: 'Education, Law & Social',        count: 28000  },
    { fos: '51', fosLabel: 'Health Professions',          noc: '6', nocLabel: 'Sales & Service',                count: 18000  },
    { fos: '51', fosLabel: 'Health Professions',          noc: '1', nocLabel: 'Business & Finance',            count: 12000  },
    { fos: '13', fosLabel: 'Education',                   noc: '4', nocLabel: 'Education, Law & Social',        count: 322000 },
    { fos: '13', fosLabel: 'Education',                   noc: '6', nocLabel: 'Sales & Service',                count: 44000  },
    { fos: '13', fosLabel: 'Education',                   noc: '0', nocLabel: 'Management',                    count: 31000  },
    { fos: '13', fosLabel: 'Education',                   noc: '5', nocLabel: 'Art, Culture & Sport',           count: 18000  },
    { fos: '11', fosLabel: 'Computer & Info Sciences',    noc: '2', nocLabel: 'Natural & Applied Sciences',     count: 267000 },
    { fos: '11', fosLabel: 'Computer & Info Sciences',    noc: '1', nocLabel: 'Business & Finance',            count: 52000  },
    { fos: '11', fosLabel: 'Computer & Info Sciences',    noc: '0', nocLabel: 'Management',                    count: 38000  },
    { fos: '11', fosLabel: 'Computer & Info Sciences',    noc: '6', nocLabel: 'Sales & Service',                count: 16000  },
    { fos: '45', fosLabel: 'Social Sciences',             noc: '4', nocLabel: 'Education, Law & Social',        count: 118000 },
    { fos: '45', fosLabel: 'Social Sciences',             noc: '0', nocLabel: 'Management',                    count: 62000  },
    { fos: '45', fosLabel: 'Social Sciences',             noc: '1', nocLabel: 'Business & Finance',            count: 58000  },
    { fos: '45', fosLabel: 'Social Sciences',             noc: '6', nocLabel: 'Sales & Service',                count: 44000  },
    { fos: '45', fosLabel: 'Social Sciences',             noc: '3', nocLabel: 'Health Occupations',             count: 22000  },
    { fos: '22', fosLabel: 'Legal Professions',           noc: '4', nocLabel: 'Education, Law & Social',        count: 82000  },
    { fos: '22', fosLabel: 'Legal Professions',           noc: '0', nocLabel: 'Management',                    count: 18000  },
    { fos: '22', fosLabel: 'Legal Professions',           noc: '1', nocLabel: 'Business & Finance',            count: 12000  },
    { fos: '26', fosLabel: 'Biological Sciences',         noc: '3', nocLabel: 'Health Occupations',             count: 68000  },
    { fos: '26', fosLabel: 'Biological Sciences',         noc: '2', nocLabel: 'Natural & Applied Sciences',     count: 58000  },
    { fos: '26', fosLabel: 'Biological Sciences',         noc: '4', nocLabel: 'Education, Law & Social',        count: 28000  },
    { fos: '26', fosLabel: 'Biological Sciences',         noc: '1', nocLabel: 'Business & Finance',            count: 22000  },
    { fos: '26', fosLabel: 'Biological Sciences',         noc: '6', nocLabel: 'Sales & Service',                count: 16000  },
    { fos: '27', fosLabel: 'Mathematics & Statistics',    noc: '2', nocLabel: 'Natural & Applied Sciences',     count: 48000  },
    { fos: '27', fosLabel: 'Mathematics & Statistics',    noc: '1', nocLabel: 'Business & Finance',            count: 38000  },
    { fos: '27', fosLabel: 'Mathematics & Statistics',    noc: '0', nocLabel: 'Management',                    count: 18000  },
    { fos: '42', fosLabel: 'Psychology',                  noc: '4', nocLabel: 'Education, Law & Social',        count: 78000  },
    { fos: '42', fosLabel: 'Psychology',                  noc: '3', nocLabel: 'Health Occupations',             count: 42000  },
    { fos: '42', fosLabel: 'Psychology',                  noc: '6', nocLabel: 'Sales & Service',                count: 28000  },
    { fos: '42', fosLabel: 'Psychology',                  noc: '1', nocLabel: 'Business & Finance',            count: 16000  },
    { fos: '09', fosLabel: 'Communication & Journalism',  noc: '5', nocLabel: 'Art, Culture & Sport',           count: 52000  },
    { fos: '09', fosLabel: 'Communication & Journalism',  noc: '4', nocLabel: 'Education, Law & Social',        count: 28000  },
    { fos: '09', fosLabel: 'Communication & Journalism',  noc: '0', nocLabel: 'Management',                    count: 18000  },
    { fos: '09', fosLabel: 'Communication & Journalism',  noc: '1', nocLabel: 'Business & Finance',            count: 14000  },
    { fos: '40', fosLabel: 'Physical Sciences',           noc: '2', nocLabel: 'Natural & Applied Sciences',     count: 62000  },
    { fos: '40', fosLabel: 'Physical Sciences',           noc: '4', nocLabel: 'Education, Law & Social',        count: 22000  },
    { fos: '40', fosLabel: 'Physical Sciences',           noc: '0', nocLabel: 'Management',                    count: 12000  },
    { fos: '01', fosLabel: 'Agriculture & Related Sciences', noc: '8', nocLabel: 'Natural Resources',           count: 52000  },
    { fos: '01', fosLabel: 'Agriculture & Related Sciences', noc: '2', nocLabel: 'Natural & Applied Sciences',  count: 28000  },
    { fos: '01', fosLabel: 'Agriculture & Related Sciences', noc: '0', nocLabel: 'Management',                  count: 18000  },
    { fos: '01', fosLabel: 'Agriculture & Related Sciences', noc: '6', nocLabel: 'Sales & Service',              count: 12000  },
    { fos: '04', fosLabel: 'Architecture',                noc: '2', nocLabel: 'Natural & Applied Sciences',     count: 42000  },
    { fos: '04', fosLabel: 'Architecture',                noc: '5', nocLabel: 'Art, Culture & Sport',           count: 12000  },
    { fos: '04', fosLabel: 'Architecture',                noc: '0', nocLabel: 'Management',                    count: 8000   },
    { fos: '44', fosLabel: 'Public Admin & Social Work',  noc: '4', nocLabel: 'Education, Law & Social',        count: 88000  },
    { fos: '44', fosLabel: 'Public Admin & Social Work',  noc: '0', nocLabel: 'Management',                    count: 38000  },
    { fos: '44', fosLabel: 'Public Admin & Social Work',  noc: '6', nocLabel: 'Sales & Service',                count: 22000  },
    { fos: '43', fosLabel: 'Security & Protective Services', noc: '4', nocLabel: 'Education, Law & Social',     count: 42000  },
    { fos: '43', fosLabel: 'Security & Protective Services', noc: '6', nocLabel: 'Sales & Service',             count: 18000  },
    { fos: '43', fosLabel: 'Security & Protective Services', noc: '7', nocLabel: 'Trades & Transport',           count: 12000  },
    { fos: '24', fosLabel: 'Liberal Arts & Sciences',     noc: '4', nocLabel: 'Education, Law & Social',        count: 68000  },
    { fos: '24', fosLabel: 'Liberal Arts & Sciences',     noc: '6', nocLabel: 'Sales & Service',                count: 48000  },
    { fos: '24', fosLabel: 'Liberal Arts & Sciences',     noc: '1', nocLabel: 'Business & Finance',            count: 28000  },
    { fos: '24', fosLabel: 'Liberal Arts & Sciences',     noc: '5', nocLabel: 'Art, Culture & Sport',           count: 18000  },
  ];

  return matrix.map(d => ({
    fieldOfStudy: d.fosLabel,
    fosCode:      d.fos,
    occupation:   d.nocLabel,
    nocCode:      d.noc,
    count:        d.count,
    education:    'Total',
  }));
}

// ─────────────────────────────────────────────────────────────
// Helpers & Visual Styling
// ─────────────────────────────────────────────────────────────

function setStatus(type, text) {
  const dot  = document.querySelector('.badge-dot');
  const span = document.getElementById('dataStatusText');
  if (dot)  { dot.className = `badge-dot ${type}`; }
  if (span) { span.textContent = text; }
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function formatNum(n) {
  if (!n && n !== 0) return '—';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(0) + 'K';
  return n.toLocaleString();
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function nocColor(nocLabel) {
  if (!nocLabel || typeof nocLabel !== 'string') return '#6366f1';
  const firstChar = nocLabel.trim()[0];
  const entry = NOC_MAJOR_GROUPS[firstChar];
  if (entry) return entry.color;

  const matched = Object.values(NOC_MAJOR_GROUPS).find(v => 
    nocLabel.toLowerCase().includes(v.label.toLowerCase())
  );
  return matched ? matched.color : '#6366f1';
}

function fosColor(fosLabel) {
  if (!fosLabel || typeof fosLabel !== 'string') return '#10b981';
  const label = fosLabel.toLowerCase();
  if (label.includes('business') || label.includes('admin')) return CIP_FIELDS['52'].color;
  if (label.includes('engineering') || label.includes('architecture')) return CIP_FIELDS['14'].color;
  if (label.includes('health')) return CIP_FIELDS['51'].color;
  if (label.includes('education')) return CIP_FIELDS['13'].color;
  if (label.includes('computer') || label.includes('mathematics') || label.includes('stats')) return CIP_FIELDS['11'].color;
  if (label.includes('social') || label.includes('behavioural') || label.includes('law')) return CIP_FIELDS['45'].color;
  if (label.includes('humanities')) return CIP_FIELDS['54'].color;
  if (label.includes('visual') || label.includes('art')) return CIP_FIELDS['09'].color;
  if (label.includes('physical') || label.includes('life') || label.includes('science')) return CIP_FIELDS['40'].color;
  if (label.includes('agriculture') || label.includes('natural')) return CIP_FIELDS['01'].color;
  return '#10b981';
}

// ─────────────────────────────────────────────────────────────
// Helpers & Utility functions
// ─────────────────────────────────────────────────────────────

function hexWithAlpha(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

// ─────────────────────────────────────────────────────────────
// Event Listeners
// ─────────────────────────────────────────────────────────────

['fosFilter', 'nocFilter', 'genderFilter', 'eduFilter'].forEach(id => {
  document.getElementById(id)?.addEventListener('change', updateDashboard);
});

// Debounce window resize for D3 Sankey
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    updateDashboard();
  }, 250);
});

// ─────────────────────────────────────────────────────────────
// Chart.js Global Defaults
// ─────────────────────────────────────────────────────────────

if (window.Chart) {
  Chart.defaults.color = '#94a3b8';
  Chart.defaults.font.family = 'Inter, system-ui, sans-serif';
  Chart.defaults.font.size = 11;
}

// ─────────────────────────────────────────────────────────────
// Initialization
// ─────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadData();
});
