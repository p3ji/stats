'use strict';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function renderFeed() {
  const el = document.getElementById('feed');
  const items = await fetch('articles/index.json').then((r) => r.json());
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
    el.innerHTML = '<p class="intro">Article not found.</p>';
    return;
  }
  const a = await fetch(`articles/${file}`).then((r) => r.json());
  document.title = `${a.headline} — Remine`;
  el.innerHTML = `
    <div class="eyebrow">${esc(a.date)}</div>
    <h1 class="header-title" style="font-size:1.6rem;margin:6px 0 18px">${esc(a.headline)}</h1>
    <p class="daily-story"><strong>What the Daily reported:</strong> ${esc(a.daily_story)}
      <br><a href="${esc(a.source.url)}">${esc(a.source.title)}</a></p>
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
            <a href="${esc(p.table_url)}">source table</a></div>`).join('')}
      </div>
    </section>`;
}
