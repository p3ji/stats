'use strict';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// esc() makes a URL safe to sit inside an attribute, but it does not stop a
// `javascript:` scheme from running on click. These hrefs come from the
// pipeline today, not from a draft — but nothing in the schema enforces that,
// so allow only http(s) rather than relying on it staying true.
const safeUrl = (u) => (/^https?:\/\//i.test(String(u ?? '')) ? String(u) : '#');

async function loadJson(path) {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json();
}

function fail(el, message) {
  el.innerHTML = `<p class="intro">${esc(message)}</p>`;
}

async function renderFeed() {
  const el = document.getElementById('feed');
  let items;
  try {
    items = await loadJson('articles/index.json');
  } catch (err) {
    // Without this the page renders blank on a 404 or a truncated file, which
    // looks identical to "no articles yet" and hides a real problem.
    fail(el, `Could not load the article index (${err.message}).`);
    return;
  }
  if (!items.length) {
    el.innerHTML = '<p class="intro">No articles yet.</p>';
    return;
  }
  el.innerHTML = items.map((it) => `
    <a class="card" href="article.html?a=${encodeURIComponent(it.file)}">
      <div class="eyebrow">${esc(it.date)} · re-mined from The Daily</div>
      <h2>${esc(it.headline)}</h2>
      <p class="assumption">Source release: ${esc(it.source_title)}</p>
    </a>`).join('');
}

async function renderArticle() {
  const el = document.getElementById('article');
  const file = new URLSearchParams(location.search).get('a');
  if (!file || !/^[\w.-]+\.json$/.test(file)) {
    fail(el, 'Article not found.');
    return;
  }
  let a;
  try {
    a = await loadJson(`articles/${file}`);
  } catch (err) {
    fail(el, `Could not load this article (${err.message}).`);
    return;
  }
  document.title = `${a.headline} — Remine`;
  el.innerHTML = `
    <div class="eyebrow">${esc(a.date)}</div>
    <h1 class="header-title" style="font-size:1.6rem;margin:6px 0 18px">${esc(a.headline)}</h1>
    <p class="daily-story"><strong>What the Daily reported:</strong> ${esc(a.daily_story)}
      <br><a href="${esc(safeUrl(a.source.url))}">${esc(a.source.title)}</a></p>
    ${a.stories.map(renderStory).join('')}`;
}

function renderStory(s) {
  return `
    <section class="story">
      <h2>${esc(s.headline)}</h2>
      <p class="assumption"><span class="stance">${esc(s.stance)}</span>
        ${esc(s.assumption)}</p>
      <div class="body">${esc(s.body).replace(/\n\n+/g, '</p><p>').replace(/^/, '<p>') + '</p>'}</div>
      <div class="provenance">
        <strong>Where these numbers come from.</strong>
        The Daily: ${esc(s.differs_from_daily)}.
        ${s.provenance.map((p) => `
          <div>${esc(Object.values(p.cut).join(', '))} —
            <code>${esc(p.vectors.join(', '))}</code>,
            ${esc(p.periods.join(' to '))},
            <a href="${esc(safeUrl(p.table_url))}">source table</a></div>`).join('')}
      </div>
    </section>`;
}
