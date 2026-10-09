/* FDIC banking dashboard front end: reads data/data.json (built by fetch_data.py).
   Styling and structure follow the Financials Dashboard (ehines12/financials-dashboard). */
const COLORS = { all: '#4f8cff', cb: '#f5b642', mid: '#3ecf8e' };
const ALT = ['#4f8cff', '#b18cff'];
const CT = 'America/Chicago';
const EMBEDDED = window.__FDIC_DATA__ || null; // set by export_html.py (offline snapshot)
let DATA = null, RANGE_YEARS = 0, CHARTS = [];
const TILE_KEYS = ['roe', 'roa', 'nim', 'eff', 'nco', 'prov', 'ncl', 'dcost', 'loang', 'lev'];

const fmtNum = (v, d = 2) => v == null || isNaN(v) ? '–' : v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const toMs = s => { const [y, m, d] = s.split('-').map(Number); return Date.UTC(y, m - 1, d, 12); };
const qlabel = s => { const [y, m] = s.split('-').map(Number); return `Q${Math.floor((m - 1) / 3) + 1} ${y}`; };
const sig = v => (v > 0 ? '+' : v < 0 ? '−' : '±');
const groupLabel = k => (DATA.groups.find(g => g.key === k) || {}).label || k;
const metric = k => DATA.metrics.find(m => m.key === k);
function bp(a, b) { return a == null || b == null ? null : (a - b) * 100; }
function fmtBp(v) { if (v != null && Math.abs(v) < 0.5) return '±0 bp'; return v == null ? '–' : `${sig(v)}${fmtNum(Math.abs(v), 0)} bp`; }
function cls(pol, v) {
  if (v == null || Math.abs(v) < 0.5) return 'na';
  if (pol === 0) return 'neu';
  return (v > 0) === (pol > 0) ? 'good' : 'bad';
}

// shade NBER recessions behind the lines
const recessionPlugin = {
  id: 'recessions',
  beforeDatasetsDraw(chart) {
    const { ctx, chartArea: a, scales: { x } } = chart;
    if (!a || !x || !DATA) return;
    ctx.save();
    ctx.fillStyle = 'rgba(141,154,179,0.16)';
    DATA.recessions.forEach(([s, e]) => {
      const x0 = Math.max(x.getPixelForValue(toMs(s)), a.left), x1 = Math.min(x.getPixelForValue(toMs(e)), a.right);
      if (x1 > x0) ctx.fillRect(x0, a.top, x1 - x0, a.bottom - a.top);
    });
    ctx.restore();
  },
};
Chart.register(recessionPlugin);
Chart.defaults.color = '#8d9ab3';
Chart.defaults.font.family = '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,Helvetica,Arial,sans-serif';

function stats(g, key) {
  const pts = (DATA.series[g] || {})[key] || [];
  if (!pts.length) return null;
  const n = pts.length, at = i => (i >= 0 ? pts[i] : null);
  return { asof: pts[n - 1][0], latest: pts[n - 1][1], q: at(n - 2), y: at(n - 5) };
}
const isStale = g => (DATA.status.find(s => s.group === g) || {}).stale;

function renderTiles() {
  document.getElementById('tiles').innerHTML = TILE_KEYS.map(k => {
    const m = metric(k), s = stats('all', k);
    if (!s) return `<div class="tile"><div class="lbl">${m.title}</div><div class="val na">n/a</div></div>`;
    const chips = [['QoQ', s.q], ['YoY', s.y]].map(([lab, p]) => {
      const c = p ? bp(s.latest, p[1]) : null;
      return `<div title="vs ${p ? qlabel(p[0]) + ': ' + fmtNum(p[1]) + '%' : 'n/a'}"><span>${lab}</span><b class="${cls(m.polarity, c)}">${fmtBp(c)}</b></div>`;
    }).join('');
    const cb = m.by_group ? stats('cb', k) : null, mid = m.by_group ? stats('mid', k) : null;
    const extra = cb ? `Community banks ${fmtNum(cb.latest)}% · $10–250B ${fmtNum(mid.latest)}%` : '';
    const short = m.title.replace(/ \((annualized, )?%\)/, '').replace(' (%)', '');
    return `<div class="tile" title="${m.note}">
      <div class="lbl"><span>${short}</span>${isStale('all') ? '<span class="stale">STALE</span>' : ''}</div>
      <div class="val">${fmtNum(s.latest)}%</div>
      <div class="asof">Industry · ${qlabel(s.asof)}</div>
      ${extra ? `<div class="extra">${extra}</div>` : ''}
      <div class="chg" style="grid-template-columns:repeat(2,1fr)">${chips}</div></div>`;
  }).join('');
}

function renderSummary() {
  const G = DATA.groups.map(g => g.key);
  let html = `<table class="summary"><thead><tr><th rowspan="2">Metric</th>${G.map(g => `<th class="c" colspan="5">${groupLabel(g)}</th>`).join('')}</tr><tr>` +
    G.map(() => '<th class="r gl">Latest</th><th class="r">Qtr ago</th><th class="r">Yr ago</th><th class="r">QoQ</th><th class="r">YoY</th>').join('') + '</tr></thead><tbody>';
  let sec = null;
  for (const r of DATA.summary) {
    if (r.section !== sec) { sec = r.section; html += `<tr class="grp"><td colspan="${1 + 5 * G.length}">${sec}</td></tr>`; }
    html += `<tr><td title="${metric(r.key).note}">${r.title}</td>`;
    for (const g of G) {
      const x = r.groups[g];
      if (!x) { html += '<td class="r gl na">–</td><td class="r na">–</td><td class="r na">–</td><td class="r na">–</td><td class="r na">–</td>'; continue; }
      const dq = bp(x.latest, x.q_ago), dy = bp(x.latest, x.y_ago);
      html += `<td class="r b gl" title="${qlabel(x.asof)}">${fmtNum(x.latest)}%${isStale(g) ? ' <span class="stale">STALE</span>' : ''}</td><td class="r">${fmtNum(x.q_ago)}%</td><td class="r">${fmtNum(x.y_ago)}%</td>` +
        `<td class="r ${cls(r.polarity, dq)}">${fmtBp(dq)}</td><td class="r ${cls(r.polarity, dy)}">${fmtBp(dy)}</td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  document.getElementById('summaryTable').innerHTML = html;
}

function renderLegend() {
  document.getElementById('legend').innerHTML = DATA.groups.map(g => `<span><i style="background:${COLORS[g.key]}"></i>${g.label}</span>`).join('') +
    '<span><i class="rec"></i>NBER recession</span><span>Growth charts and CET1: industry only</span>';
}

function cutoffMs() {
  if (!RANGE_YEARS) return -Infinity;
  const d = new Date(toMs(DATA.latest_date)); d.setUTCFullYear(d.getUTCFullYear() - RANGE_YEARS); return d.getTime();
}

function buildCharts() {
  CHARTS.forEach(c => c.chart.destroy()); CHARTS = [];
  document.querySelectorAll('.grid').forEach(g => g.innerHTML = '');
  // asset growth: YoY + QoQ annualized on one card
  const defs = DATA.metrics.filter(m => m.key !== 'assetq').map(m => m.key === 'assetg'
    ? { ...m, title: 'Total asset growth (%): YoY and QoQ annualized', lines: [['all', 'assetg', 'YoY'], ['all', 'assetq', 'QoQ annualized']], zero: true }
    : { ...m, lines: (m.by_group ? DATA.groups.map(g => g.key) : ['all']).map(g => [g, m.key, groupLabel(g)]), zero: /growth|roe|roa/i.test(m.title) || m.key === 'roe' || m.key === 'roa' });
  defs.forEach(def => {
    const grid = document.querySelector(`.grid[data-sec="${def.section}"]`);
    if (!grid) return;
    const card = document.createElement('div');
    card.className = 'card';
    const hasGroups = def.lines.length > 1 && def.key !== 'assetg';
    card.innerHTML = `<h3>${def.title}</h3><div class="latest"></div><div class="cv"><canvas></canvas></div><div class="note">${def.note}</div>`;
    grid.appendChild(card);
    const color = (g, j) => def.key === 'assetg' ? ALT[j] : COLORS[g];
    card.querySelector('.latest').innerHTML = def.lines.map(([g, k, lab], j) => {
      const s = stats(g, k);
      return `<i style="background:${color(g, j)}"></i>${lab}: <b>${s ? fmtNum(s.latest) + '%' : 'unavailable'}</b>${s ? ` (${qlabel(s.asof)})` : ''}${isStale(g) ? ' <span class="stale">STALE</span>' : ''}`;
    }).join('');
    const datasets = def.lines.map(([g, k, lab], j) => {
      const pts = ((DATA.series[g] || {})[k] || []).map(([d, v]) => ({ x: toMs(d), y: v }));
      const main = g === 'all' && j === 0;
      return { type: 'line', label: lab, _full: pts, data: pts, borderColor: color(g, j), backgroundColor: color(g, j),
        borderWidth: main ? 2.2 : (def.key === 'assetg' ? 1.1 : 1.6), pointRadius: 0, pointHoverRadius: 3, tension: 0, spanGaps: false, order: main ? 0 : 1 };
    });
    const chart = new Chart(card.querySelector('canvas'), {
      data: { datasets },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false, parsing: false, normalized: true,
        interaction: { mode: 'index', axis: 'x', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { title: (items) => items.length ? qlabel(new Date(items[0].parsed.x).toISOString().slice(0, 10)) : '', label: (c) => `${c.dataset.label}: ${fmtNum(c.parsed.y)}%` } },
        },
        scales: {
          x: { type: 'time', time: { unit: 'year', tooltipFormat: 'QQQ yyyy' }, grid: { display: false }, ticks: { maxTicksLimit: 9 } },
          y: { position: 'left', grid: { color: (ctx) => def.zero && ctx.tick.value === 0 ? '#5a6a8a' : '#1f2a3e' }, ticks: { maxTicksLimit: 7, callback: v => fmtNum(v, Math.abs(v) >= 20 ? 0 : 1) + '%' } },
        },
      },
    });
    CHARTS.push({ chart, def });
  });
  applyRange();
}

function applyRange() {
  const cut = cutoffMs();
  CHARTS.forEach(({ chart }) => {
    chart.data.datasets.forEach(ds => { ds.data = ds._full.filter(p => p.x >= cut); });
    const first = Math.min(...chart.data.datasets.map(ds => ds._full.length ? ds._full[0].x : Infinity));
    chart.options.scales.x.min = isFinite(cut) ? cut : first;
    chart.options.scales.x.max = toMs(DATA.latest_date) + 60 * 864e5;
    chart.update('none');
  });
}

function renderNotes() {
  const src = DATA.source;
  const rows = [
    ['Source', `FDIC BankFind Suite API, <a href="${src.api}?filters=REPDTE:${DATA.latest_date.replace(/-/g, '')}&agg_by=REPDTE&agg_sum_fields=ASSET,NETINCQ&limit=1" target="_blank" rel="noopener">${src.api}</a>. Call Report data for every FDIC-insured institution, summed by report date (agg_by=REPDTE). Field definitions: <a href="${src.fields}" target="_blank" rel="noopener">risview_properties.yaml</a>. Cross-check: <a href="${src.qbp}" target="_blank" rel="noopener">FDIC Quarterly Banking Profile</a>.`],
    ['Universe', 'All FDIC-insured institutions filing Call Reports, excluding insured U.S. branches of foreign banks (IBA=0), as in the QBP. Industry ROA, NIM and leverage ratio match the published QBP within ~1–3 bp; small residual differences in institution counts remain.'],
    ['Community banks', 'FDIC community bank flag (CB=1) for each quarter (FDIC Community Banking Study definition: based on lending/deposit activity and geographic scope, not size alone; most are under $10B).'],
    ['Banks $10B–$250B', 'Bank-level (not holding company) total assets of $10B–$250B in each quarter. Not inflation-adjusted, so the group was far smaller in the early 2000s; banks migrate between groups.'],
    ['Averages & annualization', 'avg X = (X at prior quarter-end + X at current quarter-end) / 2. Quarterly income-statement flows ×4. The FDIC uses slightly different averaging, so values can differ from the QBP by a few bp.'],
    ...DATA.metrics.map(m => [m.title, m.note]),
    ['Efficiency ratio', 'Not adjusted for amortization of intangibles (the FDIC\'s published ratio excludes it).'],
    ['Accounting breaks', 'Q1 2010: FAS 166/167 brought securitized card loans on balance sheet (loans and reserves jump). 2020–2023: CECL adoption raised reserves. CET1 from 2015; from 2020 it excludes banks electing the community bank leverage ratio (CBLR).'],
    ['Recession shading', 'NBER business-cycle dates: Mar–Nov 2001, Dec 2007–Jun 2009, Feb–Apr 2020.'],
    ['Refresh', 'GitHub Actions rebuilds this page every Monday and on demand. FDIC releases a new quarter roughly 8 weeks after quarter-end; between releases, figures change only if banks amend filings. If the API is unavailable, the previous data are shown and flagged STALE.'],
  ];
  document.getElementById('notesBox').innerHTML = `<dl>${rows.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join('')}</dl>`;
}

function renderMeta() {
  const gen = new Date(DATA.generated_utc);
  document.getElementById('updated').textContent = gen.toLocaleString('en-US', { timeZone: CT, month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' CT';
  document.getElementById('latestq').textContent = DATA.latest_quarter;
  const ok = DATA.status.filter(s => s.ok).length, bad = DATA.status.filter(s => !s.ok);
  document.getElementById('okcount').innerHTML = `${ok}/${DATA.status.length} groups OK` + (bad.length ? ` · <span class="bad">${bad.length} failed: ${bad.map(b => b.label).join(', ')}${bad.some(b => b.stale) ? ' (showing previous data, STALE)' : ''}</span>` : '');
  document.getElementById('statusTable').innerHTML = `<table class="status"><tr><th>Group</th><th>API filter</th><th>First quarter fetched</th><th>Latest quarter</th><th>Quarters</th><th>Institutions (latest)</th><th>Status</th></tr>` +
    DATA.status.map(s => `<tr><td>${s.label}</td><td><code>${(DATA.groups.find(g => g.key === s.group) || {}).filter || ''}</code></td><td>${s.first || '–'}</td><td>${s.last || '–'}</td><td>${s.quarters || '–'}</td><td>${s.institutions_latest != null ? s.institutions_latest.toLocaleString() : '–'}</td><td>${s.ok ? '<span class="good">OK</span>' : `<span class="bad">FAILED</span>${s.stale ? ' (showing previous data, STALE)' : ''}`}</td></tr>`).join('') +
    '</table><div class="note">Charts start Q1 2000; earlier quarters are fetched only so growth rates and averages exist from the start.</div>';
}

function renderAll() { renderMeta(); renderTiles(); renderSummary(); renderLegend(); buildCharts(); renderNotes(); }

async function load() {
  if (EMBEDDED) { DATA = EMBEDDED; renderAll(); document.body.dataset.ready = '1'; return; }
  const r = await fetch('data/data.json?t=' + Date.now(), { cache: 'no-store' });
  DATA = await r.json(); renderAll(); document.body.dataset.ready = '1';
}

document.getElementById('range').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  document.querySelectorAll('#range button').forEach(x => x.classList.toggle('on', x === b));
  RANGE_YEARS = +b.dataset.r; applyRange();
});
if (EMBEDDED) { document.getElementById('updLabel').textContent = 'Snapshot as of'; document.getElementById('updated').classList.add('snap'); }
load();
