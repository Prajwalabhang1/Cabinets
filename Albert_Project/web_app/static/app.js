/*
===========================================================================
  app.js — ItalianKB Cabinet Estimator Dashboard (Production v2.0)
===========================================================================
  Features:
  - Dynamic project selection (any number of projects)
  - 5-step New Project wizard (upload PDFs, price list, configure)
  - Pipeline SSE streaming with live logs
  - Cabinet schedule accordion with crop previews
  - Job costing sheet + donut chart
  - Developer overlay + JSON inspector
  - Toast notifications, search filter, clipboard copy
===========================================================================
*/
"use strict";

// ─────────────────────────────────────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────────────────────────────────────
let projects    = [];      // full list from /api/projects
let active      = null;    // current {id, name, config, ...}
let donutChart  = null;
let activeSSE   = null;    // live EventSource during pipeline run
let systemHealth = null;
let activeStatus = null;
let activeValidation = null;

// Wizard state
const wiz = {
  step:      1,
  pdfFiles:  [],       // [{file, unitType, isAda}]
  xlFile:    null,
  projectId: null,     // set after /create
};

// ─────────────────────────────────────────────────────────────────────────────
// DOM SHORTCUTS
// ─────────────────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

// Sidebar
const projectSel  = $('project-select');
const configForm  = $('config-form');
const newProjBtn  = $('new-project-btn');
const delProjBtn  = $('delete-project-btn');
const projInfoCard= $('project-info-card');
const infClient   = $('inf-client');
const infAddress  = $('inf-address');
const infFinish   = $('inf-finish');
const infDoor     = $('inf-door');
const infUnits    = $('inf-units');

// Header
const projTitle   = $('display-project-name');
const projMeta    = $('display-project-meta');
const runBtn      = $('run-btn');
const skipAiTog   = $('skip-ai-toggle');
const statusChip  = $('pipeline-status-chip');
const statusDot   = $('status-dot');
const statusText  = $('status-text');
const readinessBanner = $('readiness-banner');

// KPI
const kpiSell  = $('stat-selling');
const kpiGP    = $('stat-gp');
const kpiMat   = $('stat-material');
const kpiRate  = $('stat-rate');
const kpiCabs  = $('stat-cabs');
const kpiCtrs  = $('stat-ctrs');
const kpiAI    = $('stat-aicost');
const kpiCalls = $('stat-aicalls');

// Downloads
const dlPdf  = $('dl-pdf');
const dlXlsx = $('dl-xlsx');

// Console
const consolePanel = $('console-panel');
const consoleBar   = $('console-bar');
const consoleBody  = $('console-body');
const cnslToggle   = $('cnsl-toggle');
const cnslClear    = $('cnsl-clear');
const dotInd       = $('dot-ind');

// Crop tooltip
const cropTip    = $('crop-tip');
const cropTipImg = $('crop-tip-img');

// Dev tab
const devUnitSel  = $('dev-unit-sel');
const overlayCont = $('overlay-container');
const jsonViewer  = $('json-viewer');

// Wizard
const wizOverlay  = $('wizard-overlay');
const wizClose    = $('wizard-close');
const wizNext     = $('wizard-next');
const wizBack     = $('wizard-back');
const wizCreate   = $('wizard-create');
const wizSubtitle = $('wizard-subtitle');

const pdfDropzone  = $('pdf-dropzone');
const pdfFileInput = $('pdf-file-input');
const pdfFileList  = $('pdf-file-list');
const xlDropzone   = $('xl-dropzone');
const xlFileInput  = $('xl-file-input');
const xlFileInfo   = $('xl-file-info');
const xlFileName   = $('xl-file-name');
const xlRemoveBtn  = $('xl-file-remove');

// ─────────────────────────────────────────────────────────────────────────────
// BOOT
// ─────────────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initConsole();
  initCropTip();
  initJsonControls();
  initWizard();
  loadHealth();
  loadProjects();

  runBtn.addEventListener('click', handleRunPipeline);
  skipAiTog?.addEventListener('change', renderReadiness);
  $('demo-mode-toggle')?.addEventListener('change', renderReadiness);
});

async function loadHealth() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    systemHealth = await res.json();
    renderReadiness();
    const aiMsg = systemHealth.ai?.openrouter_key_configured
      ? `Vision ready: ${systemHealth.ai.primary_model}`
      : 'Vision key missing: live AI runs will require OPENROUTER_API_KEY or Skip Vision AI.';
    syslog(aiMsg);
  } catch (e) {
    systemHealth = null;
    log(`[WARN] Health check failed: ${e.message}`, 'warn');
  }
}

async function loadProjectStatus(projectId) {
  try {
    const res = await fetch(`/api/projects/${projectId}/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    activeStatus = await res.json();
    renderReadiness();
  } catch (e) {
    activeStatus = null;
    log(`[WARN] Status check failed: ${e.message}`, 'warn');
    renderReadiness();
  }
}

function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function renderReadiness() {
  if (!readinessBanner) return;
  const pills = [];
  const issues = [];

  const aiReady = !!systemHealth?.ai?.openrouter_key_configured;
  pills.push({label: aiReady ? 'Vision key set' : 'Vision key missing', state: aiReady ? 'ok' : 'warn'});

  if (activeStatus) {
    const pdfReady = !!activeStatus.ready_to_run;
    const priceReady = !!activeStatus.price_list_ok;
    const outputsReady = !!(activeStatus.has_pdf && activeStatus.has_excel);
    pills.push({label: pdfReady ? 'PDF inputs ready' : 'PDF inputs missing', state: pdfReady ? 'ok' : 'err'});
    pills.push({label: priceReady ? 'Price list ready' : 'Price list missing', state: priceReady ? 'ok' : 'warn'});
    pills.push({label: outputsReady ? 'Outputs generated' : 'Outputs not generated', state: outputsReady ? 'ok' : 'warn'});
    if (!pdfReady) issues.push('Upload at least one valid unit PDF before running.');
    if (!priceReady) issues.push('Upload a price list or use the default catalog.');
    if (!aiReady && !skipAiTog.checked) issues.push('Add OPENROUTER_API_KEY in .env or enable Skip Vision AI.');
  } else if (active) {
    issues.push('Checking project readiness...');
  } else {
    issues.push('Select an existing project or create a fresh uploaded project.');
  }

  if (activeValidation) {
    const validationOk = activeValidation.status === 'PASS';
    pills.push({
      label: validationOk ? 'Validation pass' : `${activeValidation.flag_count || 0} validation flags`,
      state: validationOk ? 'ok' : 'warn',
    });
    if (!validationOk && activeValidation.flags?.length) {
      issues.push(activeValidation.flags.slice(0, 2).join(' | '));
    }
  }

  const hasError = pills.some(p => p.state === 'err');
  const hasWarn = pills.some(p => p.state === 'warn') || issues.length > 0;
  const state = hasError ? 'err' : hasWarn ? 'warn' : 'ok';
  const title = state === 'ok' ? 'Production readiness: ready' :
                state === 'err' ? 'Production readiness: blocked' :
                'Production readiness: attention needed';
  const detail = issues.length ? issues.join(' ') : 'Inputs, outputs, price data, and validation are ready.';

  readinessBanner.className = `readiness-banner glass ${state}`;
  readinessBanner.style.display = 'flex';
  readinessBanner.innerHTML = `
    <div>
      <div class="ready-title">${esc(title)}</div>
      <div class="ready-detail">${esc(detail)}</div>
    </div>
    <div class="ready-pills">
      ${pills.map(p => `<span class="ready-pill ${p.state}">${esc(p.label)}</span>`).join('')}
    </div>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// TABS
// ─────────────────────────────────────────────────────────────────────────────
function initTabs() {
  $$('.tab-btn').forEach(btn => btn.addEventListener('click', () => {
    $$('.tab-btn').forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected','false'); });
    $$('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    btn.setAttribute('aria-selected','true');
    const pane = $(btn.dataset.tab);
    if (pane) pane.classList.add('active');
    if (btn.dataset.tab === 'tab-costing' && donutChart) donutChart.resize();
  }));
}

// ─────────────────────────────────────────────────────────────────────────────
// LOAD PROJECTS
// ─────────────────────────────────────────────────────────────────────────────
async function loadProjects() {
  try {
    const res = await fetch('/api/projects');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    projects = await res.json();

    projectSel.innerHTML = '<option value="" disabled selected>Choose a project…</option>';
    projects.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.name}  (${p.id})`;
      projectSel.appendChild(opt);
    });

    projectSel.onchange = () => {
      const p = projects.find(x => x.id === projectSel.value);
      if (p) selectProject(p);
    };

    // Auto-select the first project if available
    if (projects.length >= 1) {
      projectSel.value = projects[0].id;
      selectProject(projects[0]);
    }

    syslog(`Loaded ${projects.length} project(s).`);
  } catch (e) {
    log(`[ERROR] Could not load projects: ${e.message}`, 'err');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SELECT PROJECT
// ─────────────────────────────────────────────────────────────────────────────
function selectProject(proj) {
  active = proj;
  activeStatus = null;
  activeValidation = null;
  const cfg = proj.config;

  projTitle.textContent = proj.name;
  projMeta.textContent  = `ID: ${proj.id}  •  Rev: ${cfg.revision || '1.0'}  •  ${cfg.client_name || cfg.owner || ''}`;

  runBtn.disabled = false;
  delProjBtn.style.display = 'block';
  statusChip.style.display = 'flex';
  projInfoCard.style.display = 'block';

  infClient.textContent  = cfg.client_name || cfg.owner || '—';
  infAddress.textContent = (cfg.project_address || cfg.address || '—').substring(0, 45);
  infFinish.textContent  = cfg.cabinet_finish || cfg.finish || '—';
  infDoor.textContent    = cfg.door_style || '—';
  infUnits.textContent   = Object.keys(cfg.unit_plan_pdfs || {}).join(', ') || '—';

  renderConfigForm(cfg);

  dlPdf.href  = `/api/projects/${proj.id}/download/pdf`;
  dlXlsx.href = `/api/projects/${proj.id}/download/excel`;

  // Dev unit selector — replace node to clear stale listeners
  const newSel = devUnitSel.cloneNode(false);
  newSel.id = 'dev-unit-sel';
  newSel.className = 'ctrl-input-sm';
  newSel.innerHTML = '<option value="" disabled selected>Choose unit…</option>';
  Object.keys(cfg.unit_plan_pdfs || {}).forEach(u => {
    const o = document.createElement('option');
    o.value = u; o.textContent = u;
    newSel.appendChild(o);
  });
  devUnitSel.replaceWith(newSel);
  newSel.addEventListener('change', () => loadOverlay(proj.id, newSel.value));

  overlayCont.innerHTML = '<p class="hint-text" style="padding:16px">Select a unit above to view region overlay.</p>';
  jsonViewer.textContent = '// Load results to see JSON output.';
  resetKPIs();
  renderReadiness();
  loadProjectStatus(proj.id);

  loadResults(proj.id);
  syslog(`Project selected: ${proj.name}`);
}

// ─────────────────────────────────────────────────────────────────────────────
// CONFIG FORM (sidebar)
// ─────────────────────────────────────────────────────────────────────────────
function renderConfigForm(cfg) {
  configForm.innerHTML = `
    <div class="cf-group"><label for="cfg-gp">Target GP %</label>
      <input id="cfg-gp" class="ctrl-input" type="number" step="0.01" min="0.01" max="0.9" value="${cfg.gp_target_pct ?? 0.35}"></div>
    <div class="cf-group"><label for="cfg-comm">Commission %</label>
      <input id="cfg-comm" class="ctrl-input" type="number" step="0.005" min="0" max="0.5" value="${cfg.commission_pct ?? 0.05}"></div>
    <div class="cf-group"><label for="cfg-bond">Bond %</label>
      <input id="cfg-bond" class="ctrl-input" type="number" step="0.005" min="0" max="0.1" value="${cfg.bond_pct ?? 0.015}"></div>
    <div class="cf-group"><label for="cfg-rate">EUR / USD</label>
      <input id="cfg-rate" class="ctrl-input" type="number" step="0.01" min="0.5" max="3.0" value="${cfg.eur_usd_rate ?? 1.09}"></div>
    <div class="cf-group"><label for="cfg-rev">Revision</label>
      <input id="cfg-rev" class="ctrl-input" type="text" value="${cfg.revision ?? '1.0'}"></div>
    <button class="btn-save-cfg" id="save-cfg-btn">💾 Save & Recalculate</button>
  `;
  $('save-cfg-btn').addEventListener('click', saveConfig);
}

async function saveConfig() {
  if (!active) return;
  const btn = $('save-cfg-btn');
  btn.textContent = 'Saving…'; btn.disabled = true;
  const updated = {
    ...active.config,
    gp_target_pct:  parseFloat($('cfg-gp').value),
    commission_pct: parseFloat($('cfg-comm').value),
    bond_pct:       parseFloat($('cfg-bond').value),
    eur_usd_rate:   parseFloat($('cfg-rate').value),
    revision:       $('cfg-rev').value,
  };
  try {
    const res = await fetch(`/api/projects/${active.id}/save-config`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(updated),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    active.config = updated;
    toast('✅ Config saved — recalculating…');
    syslog('Config saved. Refreshing costing…');
    loadResults(active.id);
  } catch (e) {
    toast('❌ Save failed: ' + e.message, 'err');
  } finally {
    btn.textContent = '💾 Save & Recalculate'; btn.disabled = false;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// DELETE PROJECT
// ─────────────────────────────────────────────────────────────────────────────
delProjBtn.addEventListener('click', async () => {
  if (!active) return;
  if (!confirm(`Delete project "${active.name}" (${active.id}) and all its outputs?\n\nThis cannot be undone.`)) return;
  try {
    const res = await fetch(`/api/projects/${active.id}`, {method:'DELETE'});
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    toast(`🗑 Project ${active.id} deleted.`);
    active = null;
    delProjBtn.style.display = 'none';
    projInfoCard.style.display = 'none';
    statusChip.style.display = 'none';
    runBtn.disabled = true;
    projTitle.textContent = 'Select a Project';
    projMeta.textContent  = 'No project loaded';
    await loadProjects();
  } catch (e) {
    toast('❌ Delete failed: ' + e.message, 'err');
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// PIPELINE RUNNER (SSE)
// ─────────────────────────────────────────────────────────────────────────────
function handleRunPipeline() {
  if (!active) return;
  if (activeSSE) { activeSSE.close(); activeSSE = null; }

  consoleBody.innerHTML = '';
  consolePanel.classList.add('expanded');
  cnslToggle.textContent = '▼ Collapse';
  consoleBar.setAttribute('aria-expanded', 'true');

  setStatus('running', 'Running…');
  runBtn.disabled = true;
  runBtn.innerHTML = '<span class="spinner"></span> Running…';
  activeValidation = null;
  renderReadiness();

  syslog('Connecting to pipeline stream…');

  const demoTog = $('demo-mode-toggle');
  const useDemoMode = demoTog ? demoTog.checked : false;
  const url = `/api/projects/${active.id}/run?skip_ai=${skipAiTog.checked}&demo=${useDemoMode}`;
  const es   = new EventSource(url);
  activeSSE  = es;

  es.onmessage = ev => {
    try {
      const d = JSON.parse(ev.data);
      if (d.log) logLine(d.log);
      if (d.done) {
        es.close(); activeSSE = null;
        restoreRunBtn();
        if (d.success) {
          setStatus('done', 'Complete');
          toast('✅ Pipeline complete! Results updated.');
          loadResults(active.id);
        } else {
          setStatus('error', 'Failed');
          toast('❌ Pipeline failed — check logs below.', 'err');
          loadProjectStatus(active.id);
        }
      }
    } catch { /* ignore keep-alive bytes */ }
  };

  es.onerror = () => {
    if (!activeSSE) return;  // already closed by done event
    es.close(); activeSSE = null;
    restoreRunBtn();
    setStatus('error', 'Connection lost');
    log('[ERROR] SSE connection dropped.', 'err');
  };
}

function restoreRunBtn() {
  runBtn.disabled = false;
  runBtn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg> Run Pipeline';
}

function setStatus(state, text) {
  statusDot.className = 'status-dot';
  if (state === 'running') statusDot.classList.add('running');
  else if (state === 'done')  statusDot.classList.add('done');
  else if (state === 'error') statusDot.classList.add('error');
  statusText.textContent = text;
  dotInd.className = 'dot-ind';
  if (state === 'running') dotInd.classList.add('active');
  else if (state === 'done')  dotInd.classList.add('success');
  else if (state === 'error') dotInd.classList.add('error');
}

// ─────────────────────────────────────────────────────────────────────────────
// LOAD RESULTS
// ─────────────────────────────────────────────────────────────────────────────
async function loadResults(projectId) {
  try {
    const res = await fetch(`/api/projects/${projectId}/results`);
    if (res.status === 404) {
      activeValidation = null;
      if (active) loadProjectStatus(active.id);
      renderReadiness();
      resetKPIs();
      $('accordion-container').innerHTML = `
        <div class="empty-card">
          <div class="empty-icon">⚡</div>
          <div class="empty-msg">No cabinet schedules yet.<br/>Click <strong>Run Pipeline</strong> to process the uploaded drawings.</div>
        </div>`;
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    activeValidation = data.validation || null;
    if (active) loadProjectStatus(active.id);
    renderReadiness();

    if (data.outputs?.pdf_ready)  dlPdf.classList.remove('disabled');
    if (data.outputs?.xlsx_ready) dlXlsx.classList.remove('disabled');

    fillKPIs(data);
    renderSchedules(data.unit_schedules, projectId);
    renderCostSheet(data.costing, data.config);
    renderDonut(data.costing);
    renderPerCab(data.costing);
    renderDevMetrics(data.metrics);
    jsonViewer.textContent = JSON.stringify(data, null, 2);

    if (data.validation?.status === 'REVIEW') {
      log(`[WARN] Validation needs review: ${data.validation.flag_count} flag(s).`, 'warn');
    }
    syslog(`Results loaded — ${data.costing.total_cabinet_count} cabinets, selling price ${fmtUSD(data.costing.selling_price)}.`);
    setStatus('done', 'Results ready');
  } catch (e) {
    log(`[ERROR] Loading results: ${e.message}`, 'err');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// KPI CARDS
// ─────────────────────────────────────────────────────────────────────────────
function fillKPIs(data) {
  const c = data.costing, m = data.metrics;
  kpiSell.textContent  = fmtUSD(c.selling_price);
  kpiGP.textContent    = `GP: ${(c.gp_pct*100).toFixed(1)}%  •  Profit ${fmtUSD(c.gross_profit)}`;
  kpiMat.textContent   = fmtUSD(c.material_cost);
  kpiRate.textContent  = `EUR/USD: ${data.config.eur_usd_rate || '1.09'}`;
  kpiCabs.textContent  = c.total_cabinet_count.toLocaleString();
  kpiCtrs.textContent  = `${c.containers_needed} Container(s)`;
  kpiAI.textContent    = fmtUSD(m.total_cost_usd, 4);
  kpiCalls.textContent = `${m.api_calls} Model Calls`;
}

function resetKPIs() {
  [kpiSell,kpiGP,kpiMat,kpiRate,kpiCabs,kpiCtrs,kpiAI,kpiCalls].forEach(e=>e.textContent='—');
  dlPdf.classList.add('disabled'); dlXlsx.classList.add('disabled');
  $('cost-tbody').innerHTML = '';
  if (donutChart) { donutChart.destroy(); donutChart = null; }
}

// ─────────────────────────────────────────────────────────────────────────────
// SCHEDULES ACCORDION
// ─────────────────────────────────────────────────────────────────────────────
function renderSchedules(schedules, projectId) {
  const container = $('accordion-container');
  container.innerHTML = '';

  if (!schedules || Object.keys(schedules).length === 0) {
    container.innerHTML = `<div class="empty-card"><div class="empty-icon">🗂️</div><div class="empty-msg">No schedules found. Run the pipeline to generate them.</div></div>`;
    return;
  }

  const filterBar = $('sched-filter-bar');
  if (filterBar) filterBar.style.display = 'flex';

  Object.entries(schedules).forEach(([unit, sched]) => {
    const group = document.createElement('div');
    group.className = 'unit-group glass';

    const totalCabs  = sched.elevations.reduce((s,ev) => s + ev.cabinets.length, 0);
    const needsReview= sched.review_flags?.length > 0;
    const isADA      = sched.is_ada;

    group.innerHTML = `
      <div class="unit-hdr">
        <div class="unit-hdr-l">
          <span class="unit-name">${unit}</span>
          ${needsReview ? '<span class="badge badge-warn">⚠ Needs Review</span>' : '<span class="badge badge-ok">✓ Approved</span>'}
          ${isADA ? '<span class="badge badge-ada">ADA</span>' : ''}
        </div>
        <div class="unit-hdr-r">
          <span>${sched.elevations.length} elevation(s)</span>
          <span>${totalCabs} cabinet(s)</span>
          <span class="arrow-ico">▼</span>
        </div>
      </div>
      <div class="unit-body">
        ${needsReview ? `<div class="flag-box"><div class="flag-box-title">Review Flags</div><ul class="flag-list">${sched.review_flags.map(f=>`<li>${f}</li>`).join('')}</ul></div>` : ''}
        ${sched.elevations.map(ev => buildElevHTML(ev, unit, projectId)).join('')}
      </div>`;

    group.querySelector('.unit-hdr').addEventListener('click', () => group.classList.toggle('open'));
    container.appendChild(group);
  });

  // Auto-open first unit
  const first = container.querySelector('.unit-group');
  if (first) first.classList.add('open');

  bindCropBtns();

  const s = $('sched-search');
  if (s) { s.oninput = e => {
    const q = e.target.value.toLowerCase();
    $$('.sched-table tbody tr').forEach(tr => { tr.style.display = !q || tr.textContent.toLowerCase().includes(q) ? '' : 'none'; });
  }; }
}

function buildElevHTML(ev, unit, projectId) {
  const conf     = (ev.avg_confidence * 100).toFixed(0);
  const cropName = `${unit.replace(/[\s-]/g,'_')}_${ev.elevation_label}.png`;
  const cropUrl  = `/api/projects/${projectId}/crops/${cropName}`;

  const rows = ev.cabinets.map(cab => {
    const wCm = (cab.width_in).toFixed(1);
    const hCm = (cab.height_in).toFixed(1);
    const dCm = (cab.depth_in).toFixed(1);
    const wIn = (cab.width_in).toFixed(1);
    const c   = Math.round(cab.confidence * 100);
    const col = c >= 90 ? 'var(--success)' : c >= 70 ? 'var(--warn)' : 'var(--danger)';
    return `<tr>
      <td class="mono">${cab.item_num}</td>
      <td>${cab.cabinet_type}${cab.is_ada?' <span class="badge badge-ada" style="font-size:8px">ADA</span>':''}</td>
      <td class="mono">${cab.code || '—'}</td>
      <td class="mono num">${wCm}"</td><td class="mono num">${hCm}"</td><td class="mono num">${dCm}"</td>
      <td class="mono num">${wIn}"</td>
      <td class="mono num">${cab.quantity}</td>
      <td><div class="conf-bar"><span class="conf-pct" style="color:${col}">${c}%</span><span class="conf-pip"><span class="conf-fill" style="width:${c}%;background:${col}"></span></span></div></td>
      <td style="font-size:10.5px;color:var(--text-3)">${cab.notes || ''}</td>
      <td><button class="crop-btn" data-crop="${cropUrl}" title="Preview crop">🖼️</button></td>
    </tr>`;
  }).join('');

  return `<div class="elev-section">
    <div class="elev-title-bar">
      <h4>${ev.elevation_label}</h4>
      <div class="elev-meta"><span>Avg Conf: <strong>${conf}%</strong></span><span>${ev.cabinets.length} items</span></div>
    </div>
    <div style="overflow-x:auto">
      <table class="sched-table">
        <thead><tr><th>#</th><th>Type</th><th>Code</th><th class="num">W cm</th><th class="num">H cm</th><th class="num">D cm</th><th class="num">W in</th><th class="num">Qty</th><th>Conf</th><th>Notes</th><th>Crop</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  </div>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// COSTING SHEET
// ─────────────────────────────────────────────────────────────────────────────
function renderCostSheet(c, cfg) {
  const tbody = $('cost-tbody');
  const gp   = (c.gp_pct*100).toFixed(1);
  const comm = (c.commission_pct*100).toFixed(1);
  const bond = (c.bond_pct*100).toFixed(1);
  const rows = [
    {l:'1. Cabinet Material Cost',         r:'Price-matched from ItalianKB Excel',           v:c.material_cost},
    {l:'2. Local Use Tax (7.5%)',           r:'7.5% × material',                              v:c.local_use_tax},
    {l:'3. Ocean Freight',                  r:`${c.containers_needed} container(s) × $4,500`, v:c.ocean_freight},
    {l:'4. Inland Delivery',                r:'Flat rate logistics',                           v:c.inland_delivery},
    {l:'5. Installation Labor',             r:`${c.total_cabinet_count} cabinets × $85`,       v:c.installation},
    {l:'6. Local Warehousing',              r:'2.0% × material',                              v:c.warehousing},
    {l:'7. Material Protection',            r:'0.5% × material',                              v:c.material_protection},
    {l:'8. Inland Transit Insurance',       r:'0.8% × material',                              v:c.insurance},
    {l:'9. Miscellaneous Allowance',        r:'Flat allowance',                               v:c.misc_allowance},
    {l:'PRE-MARGIN SUBTOTAL',               r:'— Sum of 1–9 —',                               v:c.pre_margin_total, sub:true},
    {l:`Commission (${comm}%)`,             r:`${comm}% × Selling Price`,                     v:c.selling_price*c.commission_pct},
    {l:`Performance Bond (${bond}%)`,       r:`${bond}% × Selling Price`,                     v:c.selling_price*c.bond_pct},
    {l:`Gross Profit (${gp}% Target)`,      r:`${gp}% × Selling Price`,                       v:c.gross_profit},
    {l:'TOTAL ESTIMATED PROJECT PRICE',     r:'Pre-Margin ÷ (1 − GP% − Comm% − Bond%)',       v:c.selling_price, tot:true},
  ];
  tbody.innerHTML = rows.map(r => `
    <tr class="${r.sub?'subtotal-row':''} ${r.tot?'total-row':''}">
      <td>${r.l}</td>
      <td style="color:var(--text-3);font-size:10.5px">${r.r}</td>
      <td class="num" style="font-family:var(--font-mono)">${fmtUSD(r.v)}</td>
    </tr>`).join('');
}

// ─────────────────────────────────────────────────────────────────────────────
// DONUT CHART
// ─────────────────────────────────────────────────────────────────────────────
function renderDonut(c) {
  const canvas = $('donut-chart');
  if (!canvas) return;
  if (typeof Chart === 'undefined') {
    syslog('[WARN] Chart.js library is not loaded. Skipping chart.');
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
    ctx.font = '14px Inter';
    ctx.textAlign = 'center';
    ctx.fillText('Chart library offline', canvas.width / 2, canvas.height / 2);
    return;
  }
  const ctx = canvas.getContext('2d');
  if (donutChart) donutChart.destroy();
  const transport = c.ocean_freight + c.inland_delivery;
  const taxIns    = c.local_use_tax + c.insurance;
  const whProt    = c.warehousing + c.material_protection + c.misc_allowance;
  const commBond  = c.selling_price * c.commission_pct + c.selling_price * c.bond_pct;
  donutChart = new Chart(ctx, {
    type:'doughnut',
    data:{
      labels:['Materials','Freight & Delivery','Tax & Insurance','Warehousing & Protection','Installation','Commission & Bond','Gross Profit'],
      datasets:[{
        data:[c.material_cost, transport, taxIns, whProt, c.installation, commBond, c.gross_profit],
        backgroundColor:['hsl(258,80%,62%)','hsl(208,80%,56%)','hsl(178,70%,44%)','hsl(38,90%,54%)','hsl(318,78%,60%)','hsl(5,80%,56%)','hsl(148,72%,44%)'],
        borderWidth:1.5, borderColor:'rgba(0,0,0,.3)', hoverBorderColor:'#fff',
      }],
    },
    options:{
      responsive:true, maintainAspectRatio:false, cutout:'62%',
      plugins:{
        legend:{position:'right', labels:{color:'rgba(255,255,255,.7)', font:{family:'Inter',size:10.5}, boxWidth:10, padding:10}},
        tooltip:{callbacks:{label:ctx=>{
          const tot = ctx.dataset.data.reduce((a,b)=>a+b,0);
          return ` ${ctx.label}: ${fmtUSD(ctx.raw)} (${((ctx.raw/tot)*100).toFixed(1)}%)`;
        }}},
      },
    },
  });
}

function renderPerCab(c) {
  $('pc-cost').textContent = fmtUSD(c.cost_per_cabinet);
  $('pc-sell').textContent = fmtUSD(c.sell_per_cabinet);
  $('pc-ctrs').textContent = `${c.containers_needed}`;
  $('pc-gp').textContent   = `${(c.gp_pct*100).toFixed(1)}%`;
}

// ─────────────────────────────────────────────────────────────────────────────
// DEVELOPER METRICS
// ─────────────────────────────────────────────────────────────────────────────
function renderDevMetrics(m) {
  $('dev-model-prim').textContent = m.primary_model;
  $('dev-model-fall').textContent = m.fallback_model;
  $('dev-tok-in').textContent     = m.input_tokens.toLocaleString();
  $('dev-tok-out').textContent    = m.output_tokens.toLocaleString();
  $('dev-api-calls').textContent  = m.api_calls.toLocaleString();
}

// ─────────────────────────────────────────────────────────────────────────────
// REGION OVERLAY
// ─────────────────────────────────────────────────────────────────────────────
async function loadOverlay(projectId, unitType) {
  overlayCont.innerHTML = '<div class="loading-msg"><span class="spinner"></span>Rendering PDF thumbnail…</div>';
  try {
    const regRes = await fetch(`/api/projects/${projectId}/regions/${encodeURIComponent(unitType)}`);
    if (!regRes.ok) throw new Error(`Region API: HTTP ${regRes.status}`);
    const regData = await regRes.json();

    overlayCont.innerHTML = '';
    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'position:relative;width:100%;height:100%;overflow:auto;min-height:220px';
    overlayCont.appendChild(wrapper);

    const img = document.createElement('img');
    img.src = `/api/projects/${projectId}/pdf-pages/${encodeURIComponent(unitType)}`;
    img.alt = `PDF thumbnail for ${unitType}`;
    img.style.cssText = 'max-width:100%;display:block;';
    wrapper.appendChild(img);

    img.onload = () => {
      const scX = img.clientWidth  / regData.page_w;
      const scY = img.clientHeight / regData.page_h;
      regData.regions.forEach(r => {
        const [x0,y0,x1,y1] = r.bbox;
        const box = document.createElement('div');
        box.className = 'zone-box';
        box.style.cssText = `left:${x0*scX}px;top:${y0*scY}px;width:${(x1-x0)*scX}px;height:${(y1-y0)*scY}px`;
        box.title = `${r.region_type} | "${r.label}" | ${(r.confidence*100).toFixed(0)}%`;
        box.innerHTML = `<span class="zone-tag">${r.region_type} ${(r.confidence*100).toFixed(0)}%</span>`;
        box.onclick = () => syslog(`[DEV] Zone: ${r.region_type} — "${r.label}"`);
        wrapper.appendChild(box);
      });
    };
    img.onerror = () => { wrapper.innerHTML += '<p class="hint-text" style="padding:8px;color:var(--danger)">PDF thumbnail unavailable.</p>'; };
  } catch (e) {
    overlayCont.innerHTML = `<p class="hint-text" style="padding:16px;color:var(--danger)">Error: ${e.message}</p>`;
    log(`[ERROR] Overlay: ${e.message}`, 'err');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// JSON CONTROLS
// ─────────────────────────────────────────────────────────────────────────────
function initJsonControls() {
  $('json-copy-btn')?.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(jsonViewer.textContent);
      toast('📋 JSON copied!');
    } catch { toast('❌ Clipboard copy failed', 'err'); }
  });
  $('json-top-btn')?.addEventListener('click', () => {
    jsonViewer.parentElement.scrollTop = 0;
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// CROP TOOLTIP
// ─────────────────────────────────────────────────────────────────────────────
function initCropTip() {
  document.addEventListener('mousemove', e => {
    if (cropTip.style.display !== 'block') return;
    const w = 290, g = 18;
    let x = e.pageX + g, y = e.pageY + g;
    if (x + w > window.innerWidth) x = e.pageX - w - g;
    if (y + cropTip.offsetHeight > window.innerHeight) y = e.pageY - cropTip.offsetHeight - g;
    cropTip.style.left = `${x}px`; cropTip.style.top = `${y}px`;
  });
}

function bindCropBtns() {
  $$('.crop-btn').forEach(btn => {
    btn.onmouseenter = e => {
      const url = btn.dataset.crop;
      if (!url) return;
      cropTipImg.src = url;
      cropTip.style.display = 'block';
    };
    btn.onmouseleave = () => { cropTip.style.display = 'none'; cropTipImg.src = ''; };
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// CONSOLE
// ─────────────────────────────────────────────────────────────────────────────
function initConsole() {
  consoleBar.addEventListener('click', toggleConsole);
  cnslToggle.addEventListener('click', e => { e.stopPropagation(); toggleConsole(); });
  cnslClear.addEventListener('click', e => {
    e.stopPropagation();
    consoleBody.innerHTML = '';
    syslog('Logs cleared.');
  });
}

function toggleConsole() {
  const open = consolePanel.classList.toggle('expanded');
  cnslToggle.textContent = open ? '▼ Collapse' : '▲ Expand';
  consoleBar.setAttribute('aria-expanded', String(open));
}

function syslog(msg) { logLine('[SYSTEM] ' + msg, 'sys'); }

function log(msg, type) { logLine(msg, type || (msg.startsWith('[ERROR]') ? 'err' : msg.startsWith('[WARN]') ? 'warn' : 'sys')); }

function logLine(text, type = '') {
  const line = document.createElement('div');
  line.className = 'log-line' + (type ? ' log-' + type : '');
  line.textContent = text;
  consoleBody.appendChild(line);
  consoleBody.scrollTop = consoleBody.scrollHeight;
}

// ─────────────────────────────────────────────────────────────────────────────
// TOAST
// ─────────────────────────────────────────────────────────────────────────────
let _toastT = null;
function toast(msg, type = 'ok') {
  const el = $('toast');
  el.textContent = msg;
  el.style.borderColor = type === 'err' ? 'var(--danger-bdr)' : 'var(--border-hi)';
  el.classList.add('show');
  clearTimeout(_toastT);
  _toastT = setTimeout(() => el.classList.remove('show'), 3200);
}

// ─────────────────────────────────────────────────────────────────────────────
// ════════════════════════════════════════════════════════════════════════
//   5-STEP NEW PROJECT WIZARD
// ════════════════════════════════════════════════════════════════════════
// ─────────────────────────────────────────────────────────────────────────────
const STEP_SUBTITLES = [
  '', // 0 unused
  'Step 1 of 5 — Project Information',
  'Step 2 of 5 — Upload Architectural PDFs',
  'Step 3 of 5 — Unit Counts',
  'Step 4 of 5 — Price List (optional)',
  'Step 5 of 5 — Financial Parameters & Review',
];

function initWizard() {
  newProjBtn.addEventListener('click', openWizard);
  wizClose.addEventListener('click', closeWizard);
  wizOverlay.addEventListener('click', e => { if (e.target === wizOverlay) closeWizard(); });
  wizNext.addEventListener('click', wizardNext);
  wizBack.addEventListener('click', wizardBack);
  wizCreate.addEventListener('click', wizardCreate);

  // PDF dropzone
  pdfDropzone.addEventListener('click', () => pdfFileInput.click());
  pdfDropzone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') pdfFileInput.click(); });
  pdfDropzone.addEventListener('dragover', e => { e.preventDefault(); pdfDropzone.classList.add('drag-over'); });
  pdfDropzone.addEventListener('dragleave', () => pdfDropzone.classList.remove('drag-over'));
  pdfDropzone.addEventListener('drop', e => {
    e.preventDefault(); pdfDropzone.classList.remove('drag-over');
    handlePdfFiles([...e.dataTransfer.files]);
  });
  pdfFileInput.addEventListener('change', () => handlePdfFiles([...pdfFileInput.files]));

  // Excel dropzone
  xlDropzone.addEventListener('click', () => xlFileInput.click());
  xlDropzone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') xlFileInput.click(); });
  xlDropzone.addEventListener('dragover', e => { e.preventDefault(); xlDropzone.classList.add('drag-over'); });
  xlDropzone.addEventListener('dragleave', () => xlDropzone.classList.remove('drag-over'));
  xlDropzone.addEventListener('drop', e => {
    e.preventDefault(); xlDropzone.classList.remove('drag-over');
    const f = e.dataTransfer.files[0];
    if (f) setXlFile(f);
  });
  xlFileInput.addEventListener('change', () => { if (xlFileInput.files[0]) setXlFile(xlFileInput.files[0]); });
  xlRemoveBtn.addEventListener('click', () => { wiz.xlFile = null; xlFileInfo.style.display = 'none'; xlDropzone.style.display = 'flex'; });
}

function openWizard() {
  // Reset wizard state
  Object.assign(wiz, { step:1, pdfFiles:[], xlFile:null, projectId:null });
  pdfFileList.innerHTML = '';
  wizOverlay.style.display = 'flex';
  gotoStep(1);
}

function closeWizard() {
  wizOverlay.style.display = 'none';
}

function gotoStep(n) {
  wiz.step = n;
  for (let i = 1; i <= 5; i++) {
    const s = $(`step-${i}`);
    if (s) s.style.display = i === n ? '' : 'none';
  }
  wizSubtitle.textContent = STEP_SUBTITLES[n];

  // Update pip states
  $$('.step-pip').forEach(pip => {
    const sn = parseInt(pip.dataset.step);
    pip.classList.remove('active', 'done');
    if (sn === n) pip.classList.add('active');
    else if (sn < n) pip.classList.add('done');
  });

  wizBack.style.display   = n > 1 ? '' : 'none';
  wizNext.style.display   = n < 5 ? '' : 'none';
  wizCreate.style.display = n === 5 ? '' : 'none';

  // Populate step 3 unit count form when arriving
  if (n === 3) buildUnitCountsForm();
  // Populate review box on step 5
  if (n === 5) buildReviewBox();
}

function wizardNext() {
  if (wiz.step === 1 && !validateStep1()) return;
  if (wiz.step === 2 && wiz.pdfFiles.length === 0) {
    toast('⚠ Please upload at least one architectural PDF.', 'err'); return;
  }
  gotoStep(wiz.step + 1);
}

function wizardBack() { gotoStep(wiz.step - 1); }

function validateStep1() {
  const name = $('w-proj-name').value.trim();
  const id   = $('w-proj-id').value.trim();
  if (!name) { toast('⚠ Project Name is required.', 'err'); $('w-proj-name').focus(); return false; }
  if (!id)   { toast('⚠ Project ID is required.', 'err'); $('w-proj-id').focus(); return false; }
  return true;
}

// ── Handle PDF files ──────────────────────────────────────────────────────────
function handlePdfFiles(files) {
  files.forEach(file => {
    if (!file.name.toLowerCase().endsWith('.pdf')) return;
    // Auto-derive unit type from filename (remove extension, sanitize)
    const rawName = file.name.replace(/\.pdf$/i,'').replace(/[_\-\s]+/g,' ').trim();
    wiz.pdfFiles.push({ file, unitType: rawName, isAda: /ada/i.test(rawName) });
  });
  renderPdfFileList();
  pdfFileInput.value = '';
}

function renderPdfFileList() {
  pdfFileList.innerHTML = '';
  wiz.pdfFiles.forEach((item, idx) => {
    const row = document.createElement('div');
    row.className = 'file-row';
    row.innerHTML = `
      <span class="file-row-icon">📄</span>
      <span class="file-row-name" title="${item.file.name}">${item.file.name}</span>
      <span class="file-row-size">${(item.file.size/1024).toFixed(1)} KB</span>
      <label class="file-row-ada"><input type="checkbox" class="ada-chk" data-idx="${idx}" ${item.isAda?'checked':''}/> ADA</label>
      <input type="text" class="ctrl-input-sm file-row-unit unit-name-inp" data-idx="${idx}" value="${item.unitType}" placeholder="Unit type (e.g. A1)" style="min-width:100px"/>
      <button class="file-row-del" data-idx="${idx}">✕</button>`;
    pdfFileList.appendChild(row);
  });

  $$('.unit-name-inp').forEach(inp => inp.addEventListener('input', e => {
    const i = parseInt(e.target.dataset.idx);
    wiz.pdfFiles[i].unitType = e.target.value.trim();
  }));
  $$('.ada-chk').forEach(chk => chk.addEventListener('change', e => {
    const i = parseInt(e.target.dataset.idx);
    wiz.pdfFiles[i].isAda = e.target.checked;
  }));
  $$('.file-row-del').forEach(btn => btn.addEventListener('click', e => {
    const i = parseInt(e.currentTarget.dataset.idx);
    wiz.pdfFiles.splice(i, 1);
    renderPdfFileList();
  }));
}

function setXlFile(file) {
  wiz.xlFile = file;
  xlFileName.textContent = file.name;
  xlFileInfo.style.display = 'flex';
  xlDropzone.style.display = 'none';
}

// ── Step 3: Unit counts form ──────────────────────────────────────────────────
function buildUnitCountsForm() {
  const grid = $('unit-counts-form');
  grid.innerHTML = '';
  wiz.pdfFiles.forEach(item => {
    if (!item.unitType) return;
    const div = document.createElement('div');
    div.className = 'uc-group';
    div.innerHTML = `
      <div class="uc-label">
        ${item.unitType}
        ${item.isAda ? '<span class="badge badge-ada" style="font-size:8px">ADA</span>' : ''}
      </div>
      <input type="number" class="ctrl-input uc-input" id="uc-${encodeURIComponent(item.unitType)}"
             min="1" max="999" value="1" placeholder="# of units"/>`;
    grid.appendChild(div);
  });
}

// ── Step 5: Review box ────────────────────────────────────────────────────────
function buildReviewBox() {
  const box = $('wizard-review');
  const units = wiz.pdfFiles.map(f => f.unitType).filter(Boolean);
  const counts = {};
  wiz.pdfFiles.forEach(f => {
    const el = $(`uc-${encodeURIComponent(f.unitType)}`);
    counts[f.unitType] = el ? parseInt(el.value) || 1 : 1;
  });

  box.innerHTML = `
    <h4>Project Review</h4>
    <div class="review-row"><span>Project Name</span><strong>${$('w-proj-name').value}</strong></div>
    <div class="review-row"><span>Project ID</span><strong>${$('w-proj-id').value}</strong></div>
    <div class="review-row"><span>Client</span><strong>${$('w-client').value || '—'}</strong></div>
    <div class="review-row"><span>Address</span><strong>${$('w-address').value || '—'}</strong></div>
    <div class="review-row"><span>Unit Types</span><strong>${units.join(', ') || '—'}</strong></div>
    <div class="review-row"><span>Unit Counts</span><strong>${Object.entries(counts).map(([u,c])=>`${u}×${c}`).join(', ')}</strong></div>
    <div class="review-row"><span>Price List</span><strong>${wiz.xlFile ? wiz.xlFile.name : 'Default ItalianKB Level 1'}</strong></div>
    <div class="review-row"><span>Target GP</span><strong>${($('w-gp')?.value||'0.35')*100}%</strong></div>
    <div class="review-row"><span>Commission</span><strong>${($('w-comm')?.value||'0.05')*100}%</strong></div>
    <div class="review-row"><span>EUR/USD Rate</span><strong>${$('w-rate')?.value||'1.09'}</strong></div>
  `;
}

// ── Create project + upload files ─────────────────────────────────────────────
async function wizardCreate() {
  // Gather unit counts
  const unitCounts = {};
  const adaUnits   = [];
  wiz.pdfFiles.forEach(f => {
    const el = $(`uc-${encodeURIComponent(f.unitType)}`);
    unitCounts[f.unitType] = el ? parseInt(el.value) || 1 : 1;
    if (f.isAda) adaUnits.push(f.unitType);
  });

  const projectId   = $('w-proj-id').value.trim();
  const projectName = $('w-proj-name').value.trim();

  // Step A: Create project config
  wizCreate.disabled = true;
  wizCreate.innerHTML = '<span class="spinner"></span> Creating…';
  syslog('Creating project config…');

  try {
    const createRes = await fetch('/api/projects/create', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        project_id:      projectId,
        project_name:    projectName,
        client_name:     $('w-client').value,
        architect:       $('w-architect').value,
        project_address: $('w-address').value,
        cabinet_finish:  $('w-finish').value,
        door_style:      $('w-door').value,
        drawn_by:        $('w-drawn').value,
        revision:        $('w-rev').value,
        unit_counts:     unitCounts,
        ada_units:       adaUnits,
        gp_target_pct:   parseFloat($('w-gp')?.value || 0.35),
        commission_pct:  parseFloat($('w-comm')?.value || 0.05),
        bond_pct:        parseFloat($('w-bond')?.value || 0.015),
        eur_usd_rate:    parseFloat($('w-rate')?.value || 1.09),
      }),
    });
    if (!createRes.ok) {
      const err = await createRes.json();
      throw new Error(err.detail || `HTTP ${createRes.status}`);
    }
    syslog(`Project "${projectName}" created.`);

    // Step B: Upload PDFs one by one
    for (const item of wiz.pdfFiles) {
      if (!item.unitType || !item.file) continue;
      wizCreate.innerHTML = `<span class="spinner"></span> Uploading ${item.unitType}…`;
      syslog(`Uploading PDF for unit: ${item.unitType}…`);
      const fd = new FormData();
      fd.append('unit_type', item.unitType);
      fd.append('is_ada', String(item.isAda));
      fd.append('file', item.file);
      const upRes = await fetch(`/api/projects/${projectId}/upload-pdf`, { method:'POST', body:fd });
      if (!upRes.ok) {
        const err = await upRes.json();
        throw new Error(`Upload failed for ${item.unitType}: ${err.detail}`);
      }
      syslog(`PDF uploaded: ${item.unitType} (${(item.file.size/1024).toFixed(1)} KB)`);
    }

    // Step C: Upload price list (optional)
    if (wiz.xlFile) {
      wizCreate.innerHTML = '<span class="spinner"></span> Uploading price list…';
      syslog('Uploading price list…');
      const fd = new FormData();
      fd.append('file', wiz.xlFile);
      const xlRes = await fetch(`/api/projects/${projectId}/upload-price-list`, { method:'POST', body:fd });
      if (!xlRes.ok) {
        syslog(`[WARN] Price list upload failed — will use default.`);
      } else {
        syslog('Price list uploaded.');
      }
    }

    syslog('All files uploaded. Launching pipeline…');
    closeWizard();
    toast(`✅ Project "${projectName}" created! Starting pipeline…`);

    // Reload project list and auto-select the new project
    await loadProjects();
    const newProj = projects.find(p => p.id === projectId);
    if (newProj) {
      projectSel.value = projectId;
      selectProject(newProj);
    }

    // Auto-run pipeline (with AI, not skip)
    if (active && active.id === projectId) {
      // short delay so UI settles
      setTimeout(() => {
        skipAiTog.checked = false;
        handleRunPipeline();
      }, 600);
    }

  } catch (e) {
    toast(`❌ ${e.message}`, 'err');
    log(`[ERROR] Wizard: ${e.message}`, 'err');
    wizCreate.disabled = false;
    wizCreate.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg> Create & Run Pipeline';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// FORMATTERS
// ─────────────────────────────────────────────────────────────────────────────
function fmtUSD(val, digits = 2) {
  if (val == null || isNaN(val)) return '—';
  return new Intl.NumberFormat('en-US', {
    style:'currency', currency:'USD',
    minimumFractionDigits:digits, maximumFractionDigits:digits,
  }).format(val);
}

function mmToIn(mm) {
  if (!mm) return '—';
  const ins = mm / 25.4;
  const whole = Math.floor(ins);
  const frac = ins - whole;
  const FRACS = [
    [0,''], [1/16,'1/16"'], [1/8,'⅛"'], [3/16,'3/16"'],
    [1/4,'¼"'], [5/16,'5/16"'], [3/8,'⅜"'], [7/16,'7/16"'],
    [1/2,'½"'], [9/16,'9/16"'], [5/8,'⅝"'], [11/16,'11/16"'],
    [3/4,'¾"'], [13/16,'13/16"'], [7/8,'⅞"'], [15/16,'15/16"'],
  ];
  const best = FRACS.reduce((a,b) => Math.abs(b[0]-frac) < Math.abs(a[0]-frac) ? b : a);
  return whole + (best[1] ? ' ' + best[1] : '"');
}
