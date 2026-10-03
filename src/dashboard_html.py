"""
dashboard_html.py - Builds outputs/dashboard.html, an interactive, self-contained dashboard.

No external libraries and no network access are needed: all data is embedded in the page
and the charts are drawn as inline SVG, so the file works offline (double-click to open).
"""
from __future__ import annotations

import json
import math


def _clean(obj):
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def build_dashboard(R: dict, viz: dict, path: str, policy_md: str = "") -> str:
    data = _clean({**R, "viz": viz})
    html = TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":"))).replace(
        "__POLICY__", json.dumps(policy_md))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Disaster Response Logistics Dashboard</title>
<style>
:root{
  --paper:#eef1f5; --card:#ffffff; --ink:#16212e; --muted:#5d6b7a; --line:#d7dde4;
  --serve:#14756d; --crit:#c8372d; --bb:#20405f; --amber:#d99a1c;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:"Segoe UI",system-ui,-apple-system,Roboto,"Helvetica Neue",Arial,sans-serif;
  font-size:14px;line-height:1.45;font-variant-numeric:tabular-nums}
header{background:var(--ink);color:#fff;padding:18px 28px 0}
header h1{margin:0;font-size:21px;font-weight:650;letter-spacing:.1px}
header p{margin:4px 0 14px;color:#b8c4d0;font-size:13px}
nav{display:flex;gap:4px}
nav button{background:transparent;border:0;color:#b8c4d0;font:inherit;padding:10px 16px;cursor:pointer;
  border-bottom:3px solid transparent}
nav button:hover{color:#fff}
nav button.on{color:#fff;border-bottom-color:var(--amber);font-weight:600}
nav button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--amber);outline-offset:2px}
main{padding:22px 28px 40px;max-width:1280px;margin:0 auto}
section{display:none}
section.on{display:block}
.grid{display:grid;gap:18px}
.g2{grid-template-columns:minmax(0,1.25fr) minmax(0,1fr)}
.g2e{grid-template-columns:repeat(2,minmax(0,1fr))}
@media(max-width:900px){.g2,.g2e{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:16px 18px}
.card h2{margin:0 0 4px;font-size:15px}
.card .sub{color:var(--muted);font-size:12.5px;margin:0 0 10px}
.controls{display:flex;flex-wrap:wrap;gap:14px 20px;align-items:end;margin-bottom:10px}
.controls label{display:flex;flex-direction:column;font-size:12px;color:var(--muted);gap:3px}
.controls label.inline{flex-direction:row;align-items:center;gap:6px;color:var(--ink)}
select{font:inherit;padding:5px 8px;border:1px solid var(--line);border-radius:4px;background:#fff}
input[type=range]{width:170px}
.big{font-size:54px;font-weight:700;line-height:1;color:var(--serve)}
.big small{font-size:20px;color:var(--muted);font-weight:500}
.kv{display:grid;grid-template-columns:auto auto;gap:4px 18px;justify-content:start;margin-top:12px}
.kv span:nth-child(odd){color:var(--muted)}
.kv span:nth-child(even){font-weight:600;text-align:right}
.bars .row{display:grid;grid-template-columns:190px 1fr 52px;gap:8px;align-items:center;margin:5px 0;font-size:12.5px}
.bars .track{background:#e6ebf0;height:12px;border-radius:2px;overflow:hidden}
.bars .fill{height:100%}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{padding:5px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{color:var(--muted);font-weight:600;background:#f7f9fb}
td.left,th.left{text-align:left}
.scroll{overflow-x:auto;max-height:430px;overflow-y:auto}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;margin-top:6px;color:var(--muted)}
.legend i{display:inline-block;width:18px;height:3px;vertical-align:middle;margin-right:5px}
svg text{font-family:inherit}
.tag{display:inline-block;padding:1px 7px;border-radius:3px;font-size:11.5px;font-weight:600}
.tag.ok{background:#d6ece9;color:var(--serve)} .tag.no{background:#f4dcda;color:var(--crit)}
.policy h3{margin:16px 0 4px;font-size:14.5px}
.policy p{margin:0 0 6px;max-width:78ch}
.note{color:var(--muted);font-size:12px;margin-top:8px}
</style>
</head>
<body>
<header>
  <h1>Disaster Response Logistics</h1>
  <p id="meta"></p>
  <nav id="tabs">
    <button data-tab="overview" class="on">Overview</button>
    <button data-tab="robust">Robustness</button>
    <button data-tab="algo">Algorithms</button>
    <button data-tab="policy">Policy and plans</button>
  </nav>
</header>
<main>

<section id="overview" class="on">
  <div class="grid g2">
    <div class="card">
      <h2>Network, backbone and delivery routes</h2>
      <p class="sub">Close roads with the slider. The closed roads shown are one illustrative draw; the numbers on the right are Monte Carlo means.</p>
      <div class="controls">
        <label>Strategy<select id="strat"></select></label>
        <label>Roads closed: <b id="failLbl"></b><input id="fail" type="range" min="0" max="5" step="1" value="3"></label>
        <label>Delay on every road<select id="delay"></select></label>
        <label class="inline"><input id="protect" type="checkbox"> protect backbone</label>
        <label class="inline"><input id="showBB" type="checkbox" checked> backbone</label>
        <label class="inline"><input id="showRt" type="checkbox" checked> routes</label>
      </div>
      <div id="map"></div>
      <div class="legend" id="mapLegend"></div>
    </div>
    <div class="grid" style="align-content:start">
      <div class="card">
        <h2>Delivered on time</h2>
        <p class="sub" id="cellSub"></p>
        <div class="big" id="bigNum"></div>
        <div class="kv" id="kv"></div>
      </div>
      <div class="card bars">
        <h2>All strategies at this setting</h2>
        <p class="sub">Same random disruptions for every strategy.</p>
        <div id="bars"></div>
      </div>
    </div>
  </div>
</section>

<section id="robust">
  <div class="grid g2e">
    <div class="card">
      <h2>Sensitivity: road closures x delay range</h2>
      <div class="controls">
        <label>Strategy<select id="hStrat"></select></label>
        <label>Metric<select id="hMetric">
          <option value="pct_demand">% of demand delivered</option>
          <option value="pct_critical">% of critical demand delivered</option>
          <option value="avg_latency">average latency (min)</option>
        </select></label>
      </div>
      <div id="heat"></div>
    </div>
    <div class="card">
      <h2>Service level under link failures</h2>
      <div class="controls"><label>Delay<select id="rDelay"></select></label></div>
      <div id="resChart"></div><div class="legend" id="resLegend"></div>
    </div>
    <div class="card" style="grid-column:1/-1">
      <h2>Delivered demand over time</h2>
      <p class="sub">20% of roads closed, delay up to +50%. Mean of all Monte Carlo runs.</p>
      <div id="tsChart"></div><div class="legend" id="tsLegend"></div>
    </div>
  </div>
</section>

<section id="algo">
  <div class="grid g2e">
    <div class="card"><h2>Runtime vs network size</h2><p class="sub">Log-log scale, milliseconds.</p>
      <div id="scalChart"></div><div class="legend" id="scalLegend"></div></div>
    <div class="card"><h2>Routing heuristics vs number of customers</h2><p class="sub">One depot, deadlines relaxed.</p>
      <div id="rscalChart"></div><div class="legend" id="rscalLegend"></div></div>
    <div class="card"><h2>Heuristics vs exact DP</h2><p class="sub">Average gap to the optimum on small instances.</p>
      <div class="scroll"><table id="gapTable"></table></div></div>
    <div class="card"><h2>Knapsack: DP vs greedy vs LP bound</h2><p class="sub">Average over random scenarios.</p>
      <div class="scroll"><table id="knapTable"></table></div></div>
    <div class="card"><h2>Planning safety buffer</h2><p class="sub">Robust policy, 20% closed roads, delay up to +50%.</p>
      <div id="bufChart"></div><div class="legend" id="bufLegend"></div></div>
    <div class="card"><h2>Backbone</h2><p class="sub">Spanning tree vs Steiner approximation.</p>
      <table id="bbTable"></table>
      <p class="note">Hardening study: demand delivered when closures never hit the backbone (robust policy, delay up to +25%).</p>
      <div id="hardChart"></div><div class="legend" id="hardLegend"></div></div>
  </div>
</section>

<section id="policy">
  <div class="grid g2e">
    <div class="card policy" id="policyText"><h2>Recommendations</h2></div>
    <div class="card"><h2>Delivery routes</h2><p class="sub">Nominal schedule (no disruption).</p>
      <div class="scroll"><table id="routeTable"></table></div></div>
    <div class="card" style="grid-column:1/-1"><h2>Demand decisions</h2>
      <div class="scroll"><table id="decTable"></table></div></div>
  </div>
</section>

</main>
<script>
const D = __DATA__;
const POLICY = __POLICY__;
const $ = s => document.querySelector(s);
const fmt = (x, d = 0) => (x == null ? "n/a" : x.toFixed(d));
const pk = x => (Number.isInteger(x) ? x.toFixed(1) : String(x));
const STRATS = Object.keys(D.sensitivity);
const COL = {"static":"#8c8c8c","static+buffer":"#e0a030","adaptive":"#5b8fd0",
  "adaptive+realloc":"#2f9e8f","buffer+adaptive+realloc":"#c0392b"};
const NAME = {"static":"Static plan","static+buffer":"Static, buffered plan","adaptive":"Adaptive re-routing",
  "adaptive+realloc":"Re-routing + re-allocation","buffer+adaptive+realloc":"Buffered + re-routing + re-allocation"};
const PRCOL = {1:"#c7d6e8",2:"#9dbbd8",3:"#6a9ac4",4:"#e8a33d",5:"#c8372d"};
const RTCOL = ["#1f77b4","#ff7f0e","#2ca02c","#9467bd","#8c564b","#e377c2","#17becf","#bcbd22","#d62728","#7f7f7f"];
const F = D.fail_levels, DL = D.delay_levels, V = D.viz;
const cell = (s, f, d) => D.sensitivity[s][pk(f)][pk(d)];

/* ---------- header, tabs ---------- */
const sc = D.scenario;
$("#meta").textContent = `${sc.n_nodes} nodes, ${V.edges.length} roads, ${V.depots.length} depots, ${V.demands.length} demand nodes, ${V.routes.length} vehicle routes. ${D.runs} Monte Carlo runs per setting.`;
document.querySelectorAll("#tabs button").forEach(b => b.onclick = () => {
  document.querySelectorAll("#tabs button").forEach(x => x.classList.toggle("on", x === b));
  document.querySelectorAll("main section").forEach(s => s.classList.toggle("on", s.id === b.dataset.tab));
});

/* ---------- generic SVG line chart ---------- */
function lineChart(el, o) {
  const W = o.w || 560, H = o.h || 320, m = {l: 58, r: 14, t: 12, b: 46};
  const pts = o.series.flatMap(s => s.pts);
  const xs = pts.map(p => p[0]);
  let x0 = Math.min(...xs), x1 = Math.max(...xs);
  const pos = pts.map(p => p[1]).filter(v => v > 0);
  let y0, y1;
  if (o.logy) { y0 = Math.pow(10, Math.floor(Math.log10(Math.min(...pos)))); y1 = Math.pow(10, Math.ceil(Math.log10(Math.max(...pos)))); }
  else { y0 = 0; const mx = Math.max(...pts.map(p => p[1] + (p[2] || 0))); const st = mx > 50 ? 10 : mx > 10 ? 5 : 1; y1 = Math.ceil(mx * 1.05 / st) * st; }
  const lx = v => o.logx ? Math.log(v) : v, ly = v => o.logy ? Math.log(Math.max(v, y0)) : v;
  const sx = v => m.l + (lx(v) - lx(x0)) / (lx(x1) - lx(x0) || 1) * (W - m.l - m.r);
  const sy = v => H - m.b - (ly(v) - ly(y0)) / (ly(y1) - ly(y0) || 1) * (H - m.t - m.b);
  let g = "";
  let yt = [];
  if (o.logy) for (let e = Math.log10(y0); e <= Math.log10(y1) + 1e-9; e++) yt.push(Math.pow(10, e));
  else for (let i = 0; i <= 5; i++) yt.push(y0 + (y1 - y0) * i / 5);
  yt.forEach(v => { g += `<line x1="${m.l}" x2="${W - m.r}" y1="${sy(v)}" y2="${sy(v)}" stroke="#e3e8ee"/><text x="${m.l - 6}" y="${sy(v) + 4}" text-anchor="end" font-size="11" fill="#5d6b7a">${o.logy ? (v >= 1 ? v : v) : (Math.round(v * 10) / 10)}</text>`; });
  const xt = o.xticks || [...new Set(xs)];
  xt.forEach(v => { g += `<text x="${sx(v)}" y="${H - m.b + 16}" text-anchor="middle" font-size="11" fill="#5d6b7a">${v}</text>`; });
  g += `<line x1="${m.l}" x2="${W - m.r}" y1="${H - m.b}" y2="${H - m.b}" stroke="#9aa6b2"/><line x1="${m.l}" x2="${m.l}" y1="${m.t}" y2="${H - m.b}" stroke="#9aa6b2"/>`;
  g += `<text x="${(m.l + W - m.r) / 2}" y="${H - 6}" text-anchor="middle" font-size="12" fill="#16212e">${o.xlabel}</text>`;
  g += `<text transform="translate(14 ${(m.t + H - m.b) / 2}) rotate(-90)" text-anchor="middle" font-size="12" fill="#16212e">${o.ylabel}</text>`;
  o.series.forEach(s => {
    const p = s.pts.filter(q => q[1] != null);
    g += `<polyline fill="none" stroke="${s.color}" stroke-width="2.2" ${s.dash ? 'stroke-dasharray="6 4"' : ""} points="${p.map(q => sx(q[0]) + "," + sy(q[1])).join(" ")}"/>`;
    p.forEach(q => {
      if (q[2]) g += `<line x1="${sx(q[0])}" x2="${sx(q[0])}" y1="${sy(q[1] - q[2])}" y2="${sy(q[1] + q[2])}" stroke="${s.color}" stroke-opacity=".55"/>`;
      if (!o.nodots) g += `<circle cx="${sx(q[0])}" cy="${sy(q[1])}" r="3.2" fill="${s.color}"><title>${s.name}: ${fmt(q[1], 1)}</title></circle>`;
    });
  });
  $(el).innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img">${g}</svg>`;
  if (o.legend) $(o.legend).innerHTML = o.series.map(s => `<span><i style="background:${s.color}"></i>${s.name}</span>`).join("");
}

function table(el, head, rows, leftCols = 1) {
  $(el).innerHTML = "<thead><tr>" + head.map((h, i) => `<th class="${i < leftCols ? "left" : ""}">${h}</th>`).join("") + "</tr></thead><tbody>" +
    rows.map(r => "<tr>" + r.map((c, i) => `<td class="${i < leftCols ? "left" : ""}">${c}</td>`).join("") + "</tr>").join("") + "</tbody>";
}

/* ---------- Overview ---------- */
STRATS.forEach(s => { $("#strat").add(new Option(NAME[s], s)); $("#hStrat").add(new Option(NAME[s], s)); });
$("#strat").value = "buffer+adaptive+realloc"; $("#hStrat").value = "buffer+adaptive+realloc";
DL.forEach((d, i) => { ["#delay", "#rDelay"].forEach(id => $(id).add(new Option("up to +" + Math.round(d * 100) + "%", i))); });
$("#delay").value = 1; $("#rDelay").value = 1;
$("#fail").max = F.length - 1;

function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const order = (() => { const r = rng(12345), a = V.edges.map((e, i) => i); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; })();
const bbSet = new Set(V.backbone.map(e => Math.min(e[0], e[1]) + "-" + Math.max(e[0], e[1])));
const ekey = e => Math.min(e[0], e[1]) + "-" + Math.max(e[0], e[1]);
const X = v => v, Y = v => 100 - v;

function drawMap() {
  const fi = +$("#fail").value, frac = F[fi], protect = $("#protect").checked;
  const elig = order.filter(i => !(protect && bbSet.has(ekey(V.edges[i]))));
  const nClose = Math.min(elig.length, Math.round(frac * V.edges.length));
  const closed = new Set(elig.slice(0, nClose));
  let s = "";
  V.edges.forEach((e, i) => {
    const a = V.coords[e[0]], b = V.coords[e[1]];
    if (closed.has(i)) s += `<line x1="${X(a[0])}" y1="${Y(a[1])}" x2="${X(b[0])}" y2="${Y(b[1])}" stroke="#c8372d" stroke-width=".7" stroke-dasharray="1.6 1.2"/>`;
    else s += `<line x1="${X(a[0])}" y1="${Y(a[1])}" x2="${X(b[0])}" y2="${Y(b[1])}" stroke="#cfd6de" stroke-width=".45"/>`;
  });
  if ($("#showBB").checked) V.backbone.forEach(e => { const a = V.coords[e[0]], b = V.coords[e[1]]; s += `<line x1="${X(a[0])}" y1="${Y(a[1])}" x2="${X(b[0])}" y2="${Y(b[1])}" stroke="#20405f" stroke-opacity=".38" stroke-width="1.9" stroke-linecap="round"/>`; });
  if ($("#showRt").checked) V.routes.forEach((r, k) => { s += `<polyline fill="none" stroke="${RTCOL[k % RTCOL.length]}" stroke-width=".85" stroke-linejoin="round" points="${r.path.map(n => X(V.coords[n][0]) + "," + Y(V.coords[n][1])).join(" ")}"/>`; });
  V.demands.forEach(d => {
    const c = V.coords[d.node], r = 0.9 + d.amount * 0.1;
    const tip = `Node ${d.node}: priority ${d.priority}, ${d.amount} units, ${d.population} people, deadline ${d.deadline} min. ${d.planned ? "Planned" : "Not planned"}`;
    s += d.planned
      ? `<circle cx="${X(c[0])}" cy="${Y(c[1])}" r="${r}" fill="${PRCOL[d.priority]}" stroke="#16212e" stroke-width=".4"><title>${tip}</title></circle>`
      : `<g stroke="#8a96a3" stroke-width=".5"><title>${tip}</title><line x1="${X(c[0]) - r * .7}" y1="${Y(c[1]) - r * .7}" x2="${X(c[0]) + r * .7}" y2="${Y(c[1]) + r * .7}"/><line x1="${X(c[0]) - r * .7}" y1="${Y(c[1]) + r * .7}" x2="${X(c[0]) + r * .7}" y2="${Y(c[1]) - r * .7}"/></g>`;
  });
  V.depots.forEach(n => { const c = V.coords[n]; s += `<rect x="${X(c[0]) - 1.7}" y="${Y(c[1]) - 1.7}" width="3.4" height="3.4" fill="#16212e"><title>Depot ${n}</title></rect><text x="${X(c[0]) + 2.4}" y="${Y(c[1]) - 2}" font-size="3" font-weight="700" fill="#16212e">D${n}</text>`; });
  $("#map").innerHTML = `<svg viewBox="-2 -2 104 104" width="100%" style="max-height:640px;background:#fafbfc;border:1px solid #e3e8ee;border-radius:4px" role="img" aria-label="Network map">${s}</svg>`;
  $("#mapLegend").innerHTML = `<span><i style="background:#16212e;height:8px;width:8px"></i>depot</span><span><i style="background:#20405f;opacity:.4;height:6px"></i>backbone</span><span><i style="background:#c8372d"></i>closed road (${nClose})</span><span>filled circle: served demand, size = units</span><span>cross: not planned</span>`;
}

function updateOverview() {
  const s = $("#strat").value, fi = +$("#fail").value, di = +$("#delay").value;
  const f = F[fi], d = DL[di];
  $("#failLbl").textContent = Math.round(f * 100) + "%";
  const c = cell(s, f, d), base = cell(s, 0, d);
  $("#cellSub").textContent = `${NAME[s]}, ${Math.round(f * 100)}% roads closed, delay up to +${Math.round(d * 100)}%`;
  $("#bigNum").innerHTML = `${fmt(c.pct_demand, 1)}<small>% of total demand</small>`;
  $("#kv").innerHTML = `<span>95% CI</span><span>± ${fmt(c.pct_demand_ci, 1)} pts</span>
    <span>Critical demand delivered</span><span>${fmt(c.pct_critical, 1)}%</span>
    <span>Average delivery latency</span><span>${fmt(c.avg_latency, 0)} min</span>
    <span>Resilience vs no closures</span><span>${fmt(100 * c.pct_demand / base.pct_demand, 0)}%</span>`;
  const mx = Math.max(...STRATS.map(t => cell(t, f, d).pct_demand), 1);
  $("#bars").innerHTML = STRATS.map(t => { const v = cell(t, f, d).pct_demand; return `<div class="row"><span>${NAME[t]}</span><div class="track"><div class="fill" style="width:${100 * v / mx}%;background:${COL[t]}"></div></div><b>${fmt(v, 1)}%</b></div>`; }).join("");
  drawMap();
}
["#strat", "#fail", "#delay", "#protect", "#showBB", "#showRt"].forEach(id => $(id).oninput = updateOverview);
updateOverview();

/* ---------- Robustness ---------- */
function drawHeat() {
  const s = $("#hStrat").value, met = $("#hMetric").value;
  const vals = F.map(f => DL.map(d => cell(s, f, d)[met]));
  const all = vals.flat().filter(v => v != null), vmax = Math.max(...all), vmin = met === "avg_latency" ? Math.min(...all) : 0;
  const good = met === "avg_latency" ? t => 1 - t : t => t;
  const mix = t => { const a = [242, 245, 247], b = [20, 117, 109]; return `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * t)).join(",")})`; };
  let h = `<table><thead><tr><th class="left">closed roads</th>${DL.map(d => `<th>delay +${Math.round(d * 100)}%</th>`).join("")}</tr></thead><tbody>`;
  F.forEach((f, i) => { h += `<tr><td class="left">${Math.round(f * 100)}%</td>` + DL.map((d, j) => { const v = vals[i][j], t = v == null ? 0 : good((v - vmin) / (vmax - vmin || 1)); return `<td style="background:${mix(t)};color:${t > .6 ? "#fff" : "#16212e"};text-align:center">${fmt(v, met === "avg_latency" ? 0 : 1)}</td>`; }).join("") + "</tr>"; });
  $("#heat").innerHTML = h + "</tbody></table>";
}
function drawRes() {
  const d = DL[+$("#rDelay").value];
  lineChart("#resChart", {xlabel: "roads closed (%)", ylabel: "% of demand delivered on time", xticks: F.map(f => f * 100),
    series: STRATS.map(s => ({name: NAME[s], color: COL[s], pts: F.map(f => [f * 100, cell(s, f, d).pct_demand, cell(s, f, d).pct_demand_ci])})), legend: "#resLegend"});
}
["#hStrat", "#hMetric"].forEach(id => $(id).oninput = drawHeat);
$("#rDelay").oninput = drawRes;
drawHeat(); drawRes();
lineChart("#tsChart", {xlabel: "time since response start (min)", ylabel: "cumulative % of demand delivered", w: 1100, h: 330, nodots: true,
  xticks: D.timeseries.grid.filter((g, i) => i % 5 == 0),
  series: STRATS.map(s => ({name: NAME[s], color: COL[s], pts: D.timeseries.grid.map((g, i) => [g, D.timeseries.series[s][i]])})), legend: "#tsLegend"});

/* ---------- Algorithms ---------- */
const SC = D.scalability;
const scalSeries = [["kruskal_ms", "Kruskal", "#5b8fd0"], ["prim_ms", "Prim", "#2f9e8f"], ["steiner_ms", "Steiner (KMB)", "#9467bd"],
  ["knapsack_dp_ms", "Knapsack DP", "#c0392b"], ["knapsack_greedy_ms", "Knapsack greedy", "#e0a030"], ["routing_cw_ms", "Routing: Clarke-Wright", "#17becf"], ["routing_ls_ms", "Routing: CW + local search", "#7f7f7f"], ["plan_cw_ls_ms", "Full planning", "#111111"]];
lineChart("#scalChart", {xlabel: "network nodes n", ylabel: "runtime (ms)", logx: true, logy: true,
  series: scalSeries.map(([k, n, c]) => ({name: n, color: c, pts: SC.map(r => [r.n, Math.max(r[k], 0.001)])})), legend: "#scalLegend"});
const RS = D.routing_scalability;
lineChart("#rscalChart", {xlabel: "customers served from one depot", ylabel: "runtime (ms)", logx: true, logy: true,
  series: [{name: "Clarke-Wright", color: "#17becf", pts: RS.map(r => [r.customers, r.cw_ms])},
           {name: "Local search (after CW)", color: "#7f7f7f", pts: RS.filter(r => r.ls_ms != null).map(r => [r.customers, r.ls_ms])}], legend: "#rscalLegend"});
table("#gapTable", ["customers", "CW gap %", "CW+LS gap %", "CW optimal", "CW+LS optimal", "exact DP ms"],
  D.routing_gap.map(r => [r.customers, fmt(r.cw_gap_pct, 1), fmt(r.ls_gap_pct, 1), fmt(r.cw_optimal_pct, 0) + "%", fmt(r.ls_optimal_pct, 0) + "%", fmt(r.exact_ms, 1)]));
table("#knapTable", ["nodes", "supply", "greedy loses %", "DP beats greedy", "DP to LP bound %"],
  D.knapsack_quality.map(r => [r.n, Math.round(r.stock_frac * 100) + "%", fmt(r.greedy_gap_pct, 2), fmt(r.dp_better_pct, 0) + "%", fmt(r.dp_to_bound_gap_pct, 2)]));
lineChart("#bufChart", {xlabel: "safety buffer on planned travel times (%)", ylabel: "% of demand delivered", xticks: D.buffer_sweep.map(r => r.buffer * 100),
  series: [{name: "no disruption", color: "#8c8c8c", pts: D.buffer_sweep.map(r => [r.buffer * 100, r.pct_no_disruption])},
           {name: "under stress", color: "#c0392b", pts: D.buffer_sweep.map(r => [r.buffer * 100, r.pct_stressed, r.pct_stressed_ci])}], legend: "#bufLegend"});
const B = D.backbone;
table("#bbTable", ["measure", "value"], [["Kruskal MST cost (min)", fmt(B.kruskal_cost, 1)], ["Prim MST cost (min)", fmt(B.prim_cost, 1)],
  ["Steiner backbone cost (min)", fmt(B.steiner_cost, 1)], ["Terminals (depots + critical)", B.n_terminals],
  ["Backbone vs full MST", fmt(B.steiner_vs_mst_pct, 0) + "%"], ["Backbone vs all roads", fmt(B.steiner_vs_all_pct, 0) + "%"]]);
lineChart("#hardChart", {xlabel: "roads closed (%)", ylabel: "% of demand delivered", h: 240, xticks: F.map(f => f * 100),
  series: [{name: "backbone not protected", color: "#8c8c8c", dash: true, pts: F.map((f, i) => [f * 100, D.hardening.unprotected[i]["buffer+adaptive+realloc"].pct_demand])},
           {name: "backbone protected", color: "#c0392b", pts: F.map((f, i) => [f * 100, D.hardening.protected[i]["buffer+adaptive+realloc"].pct_demand])}], legend: "#hardLegend"});

/* ---------- Policy ---------- */
let ph = "<h2>Recommendations</h2>";
POLICY.split("\n").forEach(l => { if (l.startsWith("## ")) ph += `<h3>${l.slice(3)}</h3>`; else if (l.trim() && !l.startsWith("# ")) ph += `<p>${l}</p>`; });
$("#policyText").innerHTML = ph;
const rr = [];
V.routes.forEach((r, i) => r.stops.forEach((s, k) => rr.push([k == 0 ? i + 1 : "", k == 0 ? "D" + r.depot : "", k == 0 ? r.load : "", k == 0 ? fmt(r.duration, 0) : "", s, fmt(r.arrivals[k], 0), V.demands.find(d => d.node == s).deadline])));
table("#routeTable", ["vehicle", "depot", "load", "route min", "stop", "arrival", "deadline"], rr, 2);
table("#decTable", ["node", "priority", "units", "people", "deadline (min)", "status", "reason"],
  D.decisions.map(r => [r.node, r.priority, r.amount, r.population, r.deadline, `<span class="tag ${r.status == "SERVED" ? "ok" : "no"}">${r.status}</span>`, r.reason]), 1);
</script>
</body>
</html>
"""
