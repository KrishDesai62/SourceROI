"use strict";
const ui = { data: null, comparison: null, excluded: new Set(), tab: "overview", filter: "all", floor: "0.85" };
const $ = id => document.getElementById(id);
const esc = v => String(v ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[ch]);
const usd = n => "$" + Number(n || 0).toFixed(3);
const pct = n => (100 * Number(n || 0)).toFixed(1) + "%";
const signed = (n, digits = 1) => (n > 0 ? "+" : "") + Number(n || 0).toFixed(digits);
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
let toastTimer;

async function request(path, body) {
  const config = body === undefined ? {} : {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)};
  const response = await fetch(path, config);
  const result = await response.json();
  if (!response.ok) throw Error(result.error || `Request failed (${response.status})`);
  return result;
}
function toast(message) {
  const el = $("toast"); el.textContent = message; el.classList.remove("hidden");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.add("hidden"), 3500);
}
function showError(error) { const el=$("error-banner");el.textContent=error.message||String(error);el.classList.remove("hidden"); }
function clearError() { $("error-banner").classList.add("hidden"); }
function sourceMeta(id) { return ui.data?.sources.find(s => s.id === id) || {name:id,color:"#7c8fa4"}; }

async function load() {
  clearError();
  const loading = $("refresh-btn"); loading.disabled = true; loading.textContent = "↻ Evaluating…";
  try {
    ui.data = await request("/api/state");
    ui.comparison = null;
    $("project-name-side").textContent = ui.data.project.name;
    render();
  } catch (err) { showError(err); }
  finally { loading.disabled = false; loading.textContent = "↻ Refresh evaluation"; }
}

function render() {
  if (!ui.data) return;
  renderSources(); renderOverview(); renderTasks(); renderRegressions(); setTab(ui.tab);
}
function renderSources() {
  $("source-toggles").innerHTML = ui.data.sources.map(s => {
    const selected = ui.excluded.has(s.id);
    return `<button class="source-switch ${selected?'selected':''}" data-source="${esc(s.id)}" aria-pressed="${selected}" title="${selected?'Restore':'Exclude'} ${esc(s.name)}"><span class="source-label"><span class="source-dot" style="background:${esc(s.color||'#789')}" ></span><span><b>${esc(s.name)}</b><small>${usd(s.price_per_query_usd)} / lookup</small></span></span><span class="switch"></span></button>`;
  }).join("");
  for (const el of $("source-toggles").querySelectorAll("[data-source]")) {
    el.addEventListener("click", () => {
      const id = el.dataset.source;
      if (ui.excluded.has(id)) ui.excluded.delete(id); else ui.excluded.add(id);
      renderSources();
    });
  }
}
function metricCard(label, value, footer, symbol, footerClass = "note") {
  return `<div class="metric-card"><div class="metric-title">${esc(label)}<span class="metric-icon">${symbol}</span></div><div class="metric-value">${esc(value)}</div><div class="metric-foot ${footerClass}">${esc(footer)}</div></div>`;
}
function renderOverview() {
  const m = ui.data.report.metrics;
  $("metric-grid").innerHTML = [
    metricCard("Task accuracy",pct(m.accuracy),`${m.passed} / ${m.task_count} benchmark questions`,"◎","good"),
    metricCard("Modeled source cost",usd(m.estimated_total_source_cost_usd),"Total per 22-question run · synthetic", "＄"),
    metricCard("Modeled source latency",`${m.mean_modeled_source_latency_ms.toFixed(0)} ms`,"Average per task · parallel fan-out", "◷"),
    metricCard("Evidence found",pct(m.grounded_rate),"Answered with a cited source file", "▤"),
    metricCard("Measured solve time",`${m.mean_measured_local_compute_ms.toFixed(2)} ms`,"Local CPU per task · offline agent", "⌁"),
  ].join("");
  const impacts = ui.data.ablations.sources;
  const max = Math.max(1,...impacts.map(i=>i.lost_tasks.length));
  $("impact-bars").innerHTML = impacts.map(row => {
    const s = sourceMeta(row.source_id);
    return `<div class="impact-row"><div class="impact-name"><span class="source-dot" style="background:${esc(s.color)}"></span><span title="${esc(s.name)}">${esc(s.name)}</span></div><div class="bar-rail"><div class="bar-fill" style="width:${(100*row.lost_tasks.length/max).toFixed(1)}%;background:${esc(s.color)}"></div></div><div class="impact-score">${row.lost_tasks.length} <small>tasks</small></div></div>`;
  }).join("");
  $("document-impact").innerHTML = ui.data.ablations.documents.slice(0,7).map(row => {
    const s = sourceMeta(row.source_id);
    return `<div class="file-impact-row"><button data-doc="${esc(row.doc_id)}"><b>${esc(row.title)}</b><small>${esc(s.name)}</small></button><span class="file-badge ${row.lost_tasks.length===0?'zero':''}">${row.lost_tasks.length} impacted</span></div>`;
  }).join("");
  for (const el of $("document-impact").querySelectorAll("[data-doc]")) el.addEventListener("click",()=>openDocument(el.dataset.doc));
  renderComparison();renderPortfolio();renderFacts();
}
function renderComparison() {
  const panel = $("experiment-panel");
  if (!ui.comparison) {$("experiment-status").textContent="NO EXPERIMENT";panel.className="experiment-placeholder";panel.innerHTML='<div class="placeholder-icon">⌁</div><h3>Ready to test a change</h3><p>Select one or more sources on the left to see what changes in accuracy, cost and modeled latency.</p>';return;}
  const c=ui.comparison, before=c.baseline.metrics, after=c.alternate.metrics, delta=c.diff;
  $("experiment-status").textContent = c.alternate.configuration.exclude_sources.length ? "ABLATION COMPLETE" : "BASELINE RUN";
  panel.className = "";
  const accuracyDiff = delta.delta_accuracy_pct_points;
  const costSaved = -delta.delta_cost_usd;
  panel.innerHTML = `<div class="compare-summary"><div class="compare-number"><small>Accuracy</small><strong>${pct(after.accuracy)}</strong><em class="${accuracyDiff<0?'down':accuracyDiff>0?'up':'neutral'}">${signed(accuracyDiff)} percentage points</em></div><div class="compare-number"><small>Estimated spend per run</small><strong>${usd(after.estimated_total_source_cost_usd)}</strong><em class="${costSaved>0?'up':costSaved<0?'down':'neutral'}">${costSaved>=0?'Saved ':'Added '}${usd(Math.abs(costSaved))}</em></div></div><div class="compare-detail"><div>Lost correct answers: <b class="${delta.lost_count?'down':''}">${delta.lost_count}</b></div><div>Gained correct answers: <b class="${delta.gained_count?'up':''}">${delta.gained_count}</b></div><div>Mean modeled latency: <b>${after.mean_modeled_source_latency_ms.toFixed(1)} ms</b> <small>(${signed(delta.delta_latency_ms)} ms)</small></div><div>Measured local solve: <b>${after.mean_measured_local_compute_ms.toFixed(2)} ms/task</b> <small>(too fast for robust latency comparisons)</small></div><div>Excluded datasets: <b>${c.alternate.configuration.exclude_sources.map(id=>esc(sourceMeta(id).name)).join(", ")||"None"}</b></div></div><div class="panel-note">Comparisons are on synthetic, curated questions with an extractive agent. Prices and source latencies are simulated. Results do not generalize automatically to production.</div>`;
}
function renderPortfolio() {
  const result=ui.data.portfolio[ui.floor];
  const best=result?.best;
  for(const b of $("quality-picker").querySelectorAll("[data-floor]"))b.classList.toggle("active",b.dataset.floor===ui.floor);
  if(!best) {$("portfolio-result").innerHTML='<div class="no-results">No configuration meets that accuracy target.</div>';return;}
  const full=ui.data.report.metrics.estimated_total_source_cost_usd;
  const saving = full - best.cost_usd;
  $("portfolio-result").innerHTML = `<div class="portfolio-choice"><div class="portfolio-choice-value">${pct(best.accuracy)}<small> accuracy</small></div><div style="margin-left:auto;text-align:right;color:#53d3af;font-size:13px;font-weight:800">${usd(best.cost_usd)}<br><small style="font-size:10px;font-weight:400;color:#89a3b9">${usd(saving)} modeled savings</small></div></div><div class="portfolio-subtitle">Best modeled cost across ${result.configurations_tested} tested source combinations</div><div class="portfolio-tags">${best.source_ids.map(id=>`<span class="portfolio-tag">${esc(sourceMeta(id).name)}</span>`).join('')}</div><button id="try-config" class="try-config">Run this configuration ↗</button>`;
  $("try-config").addEventListener("click",()=>{ui.excluded=new Set(ui.data.sources.map(s=>s.id).filter(id=>!best.source_ids.includes(id)));renderSources();compare();});
}
function renderFacts() {
  const rows=ui.data.ablations.facts.filter(x=>x.lost_tasks.length).slice(0,6);
  $("fact-impact").innerHTML=rows.map(x=>`<div class="file-impact-row"><button data-doc="${esc(x.doc_id)}"><div class="fact-field">${esc(x.field)} <span class="fact-value">${esc(x.value)}</span></div><small>${esc(x.title)}</small></button><span class="file-badge">${x.lost_tasks.length} impacted</span></div>`).join('')||'<div class="no-results">No tested field affects a benchmark task.</div>';
  for(const el of $("fact-impact").querySelectorAll("[data-doc]"))el.addEventListener("click",()=>openDocument(el.dataset.doc));
}
function renderTasks() {
  const tasks = ui.comparison ? ui.comparison.alternate.tasks : ui.data.report.tasks;
  const filtered = tasks.filter(t => ui.filter === "all" || (ui.filter === "pass" ? t.correct : !t.correct));
  $("task-rows").innerHTML = filtered.map(t=>{
    const sources=t.queried_source_ids.map(id=>esc(sourceMeta(id).name)).join(", ")||"No matched source";
    const evidence=t.citation_doc_ids.length ? t.citation_doc_ids.map(id => `<button class="task-doc-link" data-doc="${esc(id)}">${esc(id.split("::").at(-1))} ↗</button>`).join("<br>") : "<span style='color:#8d7e8a'>No cited evidence</span>";
    return `<tr><td><span class="task-id">${esc(t.id)}</span><span class="task-cat">${esc(t.category)}</span></td><td><div class="task-question">${esc(t.question)}</div><div class="task-answers">Agent: <strong>${esc(t.actual)}</strong><br>Expected: ${esc(t.expected)}</div></td><td><div class="task-source">${sources}</div>${evidence}</td><td><span class="pill ${t.correct?'pass':'fail'}">${t.correct?'✓ Correct':'× Incorrect'}</span></td></tr>`;
  }).join("") || `<tr><td colspan="4" style="text-align:center;color:#92a7be;padding:38px">No tasks match this filter.</td></tr>`;
  for(const el of $("task-rows").querySelectorAll("[data-doc]"))el.addEventListener("click",()=>openDocument(el.dataset.doc));
  for(const el of document.querySelectorAll("[data-filter]"))el.classList.toggle("active",el.dataset.filter===ui.filter);
}
function renderRegressions() {
  const area = $("regression-content");
  if (!ui.data.has_baseline) {
    area.innerHTML = `<div class="panel files-changed"><h2>No saved baseline yet</h2><p style="font-size:12px;color:#91a9c4;line-height:1.8">Click <b>Save baseline</b> in the toolbar. After that, edit a source file in VS Code and click Refresh evaluation. SourceROI will compare current results to the saved source snapshots.</p></div>`;return;
  }
  const r=ui.data.baseline, d=r.diff;
  const fileNames=[...r.files_changed.map(k=>({key:k,label:"Changed"})),...r.files_added.map(k=>({key:k,label:"Added"})),...r.files_removed.map(k=>({key:k,label:"Removed"}))];
  const status = fileNames.length ? "Detected source changes" : "Source files unchanged";
  area.innerHTML = `<div class="panel ci-result"><h3>Regression status</h3><div class="big ${d.lost_count?'down':'up'}">${d.lost_count?`${d.lost_count} failed`:'No new failures'}</div><p>Previously correct tasks that are now incorrect.</p></div><div class="panel ci-result"><h3>Accuracy change</h3><div class="big ${d.delta_accuracy_pct_points<0?'down':'up'}">${signed(d.delta_accuracy_pct_points)} pp</div><p>From ${pct(r.baseline_metrics.accuracy)} to ${pct(r.current_metrics.accuracy)}.</p></div><div class="panel ci-result"><h3>Files changed</h3><div class="big">${fileNames.length}</div><p>Compared with your locally saved SHA-256 fingerprints.</p></div><div class="panel files-changed"><h2>${status}</h2>${fileNames.length ? fileNames.map(v=>`<div class="changed-file">${esc(v.label)}: ${esc(v.key)}</div>`).join(""):'<p style="font-size:12px;color:#839bb8">Edit a Markdown document, save it, and refresh the page to see the change here.</p>'}${d.lost_task_ids.length ? `<p style="font-size:12px;color:#ffadba;margin-top:14px">Newly failed tasks: ${esc(d.lost_task_ids.join(", "))}</p>`:""}<p style="font-size:10px;color:#67829f">Baseline saved ${esc(new Date(r.baseline_created_at).toLocaleString())}</p></div>`;
}
async function compare() {
  if (!ui.data) return;
  clearError();
  const btn = $("compare-btn"); btn.disabled=true;btn.textContent="Running…";
  try {
    ui.comparison=await request("/api/compare",{exclude_sources:[...ui.excluded]});
    renderOverview();renderTasks();setTab("overview");toast("Comparison complete · " + ui.comparison.diff.lost_count + " tasks lost");
  } catch(err) {showError(err);} finally {btn.disabled=false;btn.innerHTML="<span>▶</span> Run comparison";}
}
async function saveBaseline() {
  const btn = $("save-btn");btn.disabled=true;
  try {await request("/api/save-baseline",{});toast("Baseline saved locally");await load();setTab("changes");}
  catch(err){showError(err);}finally{btn.disabled=false;}
}
function setTab(tab) {
  ui.tab=tab;
  for(const el of document.querySelectorAll(".nav-item"))el.classList.toggle("active",el.dataset.tab===tab);
  for(const name of ["overview","tasks","changes"])$(name+"-view").classList.toggle("hidden",tab!==name);
  const metadata={overview:["Overview","Your data, measured.","See which datasets actually help your AI agent—and what changes when you remove them."],tasks:["Task inspector","Follow the evidence.","Review every evaluated question, retrieved source, and correctness result."],changes:["Data CI / regressions","Protect every data change.","Catch source-related failures by comparing edited datasets with a saved baseline."]};
  const [crumb,title,subtitle]=metadata[tab];$("crumb-current").textContent=crumb;$("view-heading").textContent=title;$("view-subtitle").textContent=subtitle;
}
async function openDocument(id) {
  try {const doc=await request("/api/document/"+encodeURIComponent(id));$("modal-title").textContent=doc.title;$("modal-path").textContent=doc.path;$("modal-body").textContent=doc.content;$("document-modal").classList.remove("hidden");}
  catch(err){showError(err);}
}
function closeModal(){$("document-modal").classList.add("hidden");}
function bindEvents() {
  $("compare-btn").addEventListener("click",compare);
  $("reset-btn").addEventListener("click",()=>{ui.excluded.clear();ui.comparison=null;renderSources();renderComparison();renderTasks();toast("Source selection cleared");});
  $("refresh-btn").addEventListener("click",load);
  $("save-btn").addEventListener("click",saveBaseline);
  $("open-tasks-btn").addEventListener("click",()=>setTab("tasks"));
  for(const el of document.querySelectorAll("[data-tab]"))el.addEventListener("click",()=>setTab(el.dataset.tab));
  for(const el of document.querySelectorAll("[data-filter]"))el.addEventListener("click",()=>{ui.filter=el.dataset.filter;renderTasks();});
  $("close-modal").addEventListener("click",closeModal);
  for(const el of document.querySelectorAll("[data-floor]"))el.addEventListener("click",()=>{ui.floor=el.dataset.floor;renderPortfolio();});
  $("document-modal").addEventListener("click",event=>{if(event.target===$("document-modal"))closeModal();});
  document.addEventListener("keydown",event=>{if(event.key==="Escape")closeModal();});
}
bindEvents(); load();
