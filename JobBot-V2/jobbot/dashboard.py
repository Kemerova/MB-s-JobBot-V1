"""Static HTML dashboard generated from the job database."""

from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JobBot Dashboard</title>
<style>
  :root {
    --bg: #f6f7f9; --card: #ffffff; --ink: #1f2937; --muted: #6b7280;
    --line: #e5e7eb; --accent: #2563eb; --good: #16a34a; --mid: #d97706;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
         background: var(--bg); color: var(--ink); }
  header { padding: 20px 24px 8px; }
  h1 { margin: 0 0 4px; font-size: 22px; }
  .summary { color: var(--muted); font-size: 14px; }
  .controls { display: flex; flex-wrap: wrap; gap: 10px; padding: 12px 24px;
              position: sticky; top: 0; background: var(--bg); z-index: 5;
              border-bottom: 1px solid var(--line); }
  .controls input[type="search"] { flex: 1 1 220px; min-height: 44px; padding: 8px 12px;
              border: 1px solid var(--line); border-radius: 8px; font-size: 16px; }
  .controls select, .controls label { min-height: 44px; padding: 8px 10px;
              border: 1px solid var(--line); border-radius: 8px; background: var(--card);
              font-size: 14px; display: flex; align-items: center; gap: 6px; }
  main { padding: 16px 24px 60px; display: grid; gap: 12px;
         grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px;
          padding: 16px; display: flex; flex-direction: column; gap: 8px; }
  .row1 { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
  .title { font-weight: 600; font-size: 16px; }
  .company { color: var(--muted); font-size: 14px; }
  .score { font-weight: 700; font-size: 20px; min-width: 44px; text-align: center;
           border-radius: 8px; padding: 6px 8px; }
  .score.hi { background: #dcfce7; color: var(--good); }
  .score.mid { background: #fef3c7; color: var(--mid); }
  .score.lo { background: #f3f4f6; color: var(--muted); }
  .meta { font-size: 13px; color: var(--muted); display: flex; flex-wrap: wrap; gap: 10px; }
  .fit { font-size: 14px; }
  details { font-size: 13px; }
  details summary { cursor: pointer; color: var(--accent); min-height: 30px; }
  ul { margin: 6px 0; padding-left: 18px; }
  .badge { font-size: 12px; padding: 2px 8px; border-radius: 999px;
           background: #eef2ff; color: var(--accent); text-transform: capitalize; }
  .badge.applied, .badge.interviewing, .badge.phone_screen { background: #fef3c7; color: var(--mid); }
  .badge.offer, .badge.accepted { background: #dcfce7; color: var(--good); }
  .badge.rejected { background: #fee2e2; color: #dc2626; }
  .actions { display: flex; gap: 8px; margin-top: auto; }
  .actions a, .actions button { min-height: 44px; flex: 1; display: flex; align-items: center;
           justify-content: center; border-radius: 8px; font-size: 14px; cursor: pointer;
           text-decoration: none; border: 1px solid var(--line); background: var(--card);
           color: var(--ink); }
  .actions a.apply { background: var(--accent); color: #fff; border-color: var(--accent); }
  .idtag { font-size: 12px; color: var(--muted); font-family: ui-monospace, monospace; }
  .empty { grid-column: 1 / -1; text-align: center; color: var(--muted); padding: 40px; }
</style>
</head>
<body>
<header>
  <h1>JobBot Dashboard</h1>
  <div class="summary">__SUMMARY__</div>
</header>
<div class="controls">
  <input type="search" id="q" placeholder="Search title, company, description...">
  <select id="minScore">
    <option value="0">Any score</option>
    <option value="60">60+</option>
    <option value="70" selected>70+</option>
    <option value="80">80+</option>
  </select>
  <select id="status">
    <option value="">All statuses</option>
    <option value="new">New</option>
    <option value="interested">Interested</option>
    <option value="applied">Applied</option>
    <option value="phone_screen">Phone screen</option>
    <option value="interviewing">Interviewing</option>
    <option value="offer">Offer</option>
    <option value="rejected">Rejected</option>
  </select>
  <label><input type="checkbox" id="remoteOnly"> Remote only</label>
  <select id="sort">
    <option value="score">Sort: score</option>
    <option value="date">Sort: newest</option>
    <option value="company">Sort: company</option>
  </select>
</div>
<main id="jobs"></main>
<script>
const JOBS = __JOBS_JSON__;

const els = {
  q: document.getElementById('q'),
  minScore: document.getElementById('minScore'),
  status: document.getElementById('status'),
  remoteOnly: document.getElementById('remoteOnly'),
  sort: document.getElementById('sort'),
  main: document.getElementById('jobs'),
};

function esc(s) {
  return (s ?? '').toString().replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function salary(j) {
  if (!j.salary_min && !j.salary_max) return null;
  const f = n => n ? '$' + Math.round(n).toLocaleString() : '?';
  return f(j.salary_min) + ' \\u2013 ' + f(j.salary_max);
}

function card(j) {
  const cls = j.score >= 80 ? 'hi' : j.score >= 65 ? 'mid' : 'lo';
  const lists = (label, items) => items && items.length
    ? `<strong>${label}</strong><ul>${items.map(x => '<li>' + esc(x) + '</li>').join('')}</ul>` : '';
  return `<div class="card">
    <div class="row1">
      <div>
        <div class="title">${esc(j.title)}</div>
        <div class="company">${esc(j.company)}</div>
      </div>
      <div class="score ${cls}">${j.score ?? '?'}</div>
    </div>
    <div class="meta">
      <span>${esc(j.location || '')}</span>
      ${j.is_remote ? '<span>Remote</span>' : ''}
      ${salary(j) ? '<span>' + salary(j) + '</span>' : ''}
      ${j.date_posted ? '<span>Posted ' + esc(j.date_posted) + '</span>' : ''}
      <span class="badge ${esc(j.status)}">${esc(j.status.replace('_', ' '))}</span>
    </div>
    ${j.fit_summary ? '<div class="fit">' + esc(j.fit_summary) + '</div>' : ''}
    <details><summary>Details</summary>
      ${lists('Strengths', j.strengths)}
      ${lists('Gaps', j.gaps)}
      ${lists('Tailored bullets', j.bullets)}
      <div class="idtag">id: ${j.id} \\u2014 update via: <code>python main.py status ${j.id} applied</code></div>
    </details>
    <div class="actions">
      ${j.url ? '<a class="apply" href="' + esc(j.url) + '" target="_blank" rel="noopener">View / Apply</a>' : ''}
      <button onclick="navigator.clipboard.writeText('python main.py status ${j.id} applied')">Copy status cmd</button>
    </div>
  </div>`;
}

function render() {
  const q = els.q.value.toLowerCase();
  const minScore = +els.minScore.value;
  const status = els.status.value;
  const remoteOnly = els.remoteOnly.checked;
  let jobs = JOBS.filter(j =>
    (j.score ?? 0) >= minScore &&
    (!status || j.status === status) &&
    (!remoteOnly || j.is_remote) &&
    (!q || `${j.title} ${j.company} ${j.location} ${j.description}`.toLowerCase().includes(q))
  );
  const sort = els.sort.value;
  jobs.sort((a, b) => sort === 'date'
    ? (b.date_posted || '').localeCompare(a.date_posted || '')
    : sort === 'company'
    ? (a.company || '').localeCompare(b.company || '')
    : (b.score ?? -1) - (a.score ?? -1));
  els.main.innerHTML = jobs.length
    ? jobs.map(card).join('')
    : '<div class="empty">No jobs match the current filters.</div>';
}

Object.values(els).forEach(el => {
  if (el.addEventListener) {
    el.addEventListener('input', render);
    el.addEventListener('change', render);
  }
});
render();
</script>
</body>
</html>
"""


def generate(jobs: list[dict], stats: dict, out_path: Path) -> Path:
    slim = []
    for job in jobs:
        item = dict(job)
        # keep the payload light: cap descriptions used only for text search
        if item.get("description"):
            item["description"] = item["description"][:1500]
        slim.append(item)
    summary = (
        f"{stats['total']} jobs tracked · {stats['high'] or 0} scored 70+ · "
        f"{stats['tracked'] or 0} in your application pipeline · "
        f"generated {date.today().isoformat()}"
    )
    # "</" must be escaped so a description containing "</script>" can't
    # terminate the inline script block
    jobs_json = json.dumps(slim, ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.replace("__SUMMARY__", html.escape(summary)).replace(
        "__JOBS_JSON__", jobs_json
    )
    out_path.write_text(page, encoding="utf-8")
    return out_path
