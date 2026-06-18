// pipeline.js — Rayquaza side-channel analysis console.
// Receives RunState from Python via window.onStateUpdate(state) and renders the
// instrument: specimen dock, focused investigation chamber, telemetry rail.

const STAGES = ["ingest", "vectorize", "wait", "refine", "save"];
const STAGE_DEFS = {
  ingest:    { label: "READ",        sub: "ingest" },
  vectorize: { label: "HYPOTHESIZE", sub: "vectorize" },
  wait:      { label: "MEASURE",     sub: "oracle" },
  refine:    { label: "ADJUDICATE",  sub: "refine" },
  save:      { label: "VERDICT",     sub: "save" },
};
const SPEED_STEPS = [
  { label: "0.25x", delay: 2.4 }, { label: "0.5x", delay: 1.2 },
  { label: "1x", delay: 0.6 }, { label: "2x", delay: 0.3 }, { label: "4x", delay: 0.15 },
];

let targetRegistry = {};
let TARGET_ORDER = [];
let lastState = null;
let pinnedId = null;
let focusId = null;
let chamberKey = null;
let oracleMode = "scope";
let eventLog = [];
let prevStage = {};
let runStartMs = null;
let clockTimer = null;

// ── Utilities ────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function shortId(id) { return id.replace(/^kyber512_/, "").replace(/^mldsa44_/, "mldsa·"); }
function fmtT(t) {
  if (t == null) return "—";
  const a = Math.abs(t);
  return (a >= 1000 ? Math.round(t).toString() : t.toFixed(1));
}
function el(id) { return document.getElementById(id); }

// ── Init: target registry from Python ────────────────────────────────────────
window.initTargets = function (targets) {
  targetRegistry = {};
  TARGET_ORDER = [];
  targets.forEach((t) => { targetRegistry[t.id] = t; TARGET_ORDER.push(t.id); });
  renderDock(null);
  buildTicker();
};

// ── Main entry — called on every state push ──────────────────────────────────
window.onStateUpdate = function (state) {
  if (runStartMs == null) { runStartMs = Date.now(); startClock(); }
  el("chamber-empty").style.display = "none";
  el("chamber-body").style.display = "";

  el("hud-model").textContent = state.model_label || "";
  recordEvents(state);
  computeFocus(state);
  renderHudStats(state);
  renderDock(state);
  renderChamber(state);
  renderEventLog();
  renderFindings(state);

  el("btn-stop").disabled = !!state.finished;
  if (state.finished) { el("btn-replay-all").disabled = false; stopClock(); }
  lastState = state;
};

// ── Focus selection — chamber follows the action ─────────────────────────────
function computeFocus(state) {
  if (pinnedId && state.targets[pinnedId]) { focusId = pinnedId; return; }
  let changed = null;
  for (const id of TARGET_ORDER) {
    const t = state.targets[id];
    if (!t || !t.active_hyp) continue;
    const h = t.hyps[t.active_hyp];
    const prev = lastState && lastState.targets[id] && lastState.targets[id].hyps[t.active_hyp];
    if (!prev || prev.stage !== h.stage || prev.stage_status !== h.stage_status ||
        (!prev.measurement && h.measurement) || (!prev.result && h.result)) {
      changed = id; break;
    }
  }
  if (changed) focusId = changed;
  else if (!focusId || !state.targets[focusId]) {
    focusId = TARGET_ORDER.find((id) => state.targets[id] && state.targets[id].active_hyp) ||
              TARGET_ORDER.find((id) => state.targets[id]) || null;
  }
}

// ── HUD ──────────────────────────────────────────────────────────────────────
function renderHudStats(state) {
  let done = 0, confirmed = 0;
  for (const id of TARGET_ORDER) {
    const t = state.targets[id];
    if (!t) continue;
    const res = latestResult(t);
    if (res) { done++; if (res.significant) confirmed++; }
  }
  el("stat-progress").textContent = done;
  el("stat-confirmed").textContent = confirmed;
}
function startClock() {
  stopClock();
  clockTimer = setInterval(() => {
    const s = Math.floor((Date.now() - runStartMs) / 1000);
    el("run-clock").textContent =
      String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
  }, 1000);
}
function stopClock() { if (clockTimer) { clearInterval(clockTimer); clockTimer = null; } }

// ── Dock ─────────────────────────────────────────────────────────────────────
function latestResult(tstate) {
  if (!tstate || !tstate.hyps) return null;
  let res = null;
  for (const k of Object.keys(tstate.hyps)) { if (tstate.hyps[k].result) res = tstate.hyps[k].result; }
  return res;
}
function renderDock(state) {
  const list = el("dock-list");
  list.innerHTML = TARGET_ORDER.map((id) => {
    const reg = targetRegistry[id];
    const t = state && state.targets[id];
    const tier = reg.difficulty_tier || "obvious";
    let dot = "var(--dim)", status = "queued", statusColor = "var(--mut)", pulse = "";
    if (t && t.active_hyp) {
      const h = t.hyps[t.active_hyp];
      const res = latestResult(t);
      if (res) {
        if (res.significant) { dot = "var(--gn)"; status = "confirmed · t " + fmtT(res.t_stat); statusColor = "var(--gn)"; }
        else { dot = "var(--rd)"; status = "cleared · t " + fmtT(res.t_stat); statusColor = "var(--rd)"; }
      } else {
        dot = "var(--cy)"; pulse = "pulse";
        const sd = STAGE_DEFS[h.stage];
        status = "▮ " + sd.label.toLowerCase() + (h.measurement ? " · t " + fmtT(h.measurement.t_stat) : "");
        statusColor = "var(--cy)";
      }
    }
    const cls = ["spec", id === focusId ? "active" : "", id === pinnedId ? "pinned" : ""].join(" ");
    return `<div class="${cls}" onclick="pinFocus('${id}')">
      <div class="spec-top">
        <span class="spec-id"><span class="spec-dot ${pulse}" style="background:${dot}"></span><span class="mono">${shortId(id)}</span></span>
        <span class="tier tier-${tier}">${tier}</span>
      </div>
      <div class="spec-sub"><span class="spec-prim">${escHtml(reg.evidence ? reg.evidence.file : reg.primitive)}</span></div>
      <div class="spec-status mono" style="color:${statusColor}">${escHtml(status)}</div>
    </div>`;
  }).join("");
}
window.pinFocus = function (id) {
  pinnedId = (pinnedId === id) ? null : id;
  focusId = id;
  if (lastState) { renderDock(lastState); renderChamber(lastState, true); }
};

// ── Chamber ──────────────────────────────────────────────────────────────────
function renderChamber(state, force) {
  if (!focusId) return;
  const t = state.targets[focusId];
  if (!t || !t.active_hyp) return;
  const hyp = t.hyps[t.active_hyp];
  const reg = targetRegistry[focusId];
  const key = [focusId, hyp.stage, hyp.measurement ? 1 : 0, hyp.result ? 1 : 0].join("|");
  if (key === chamberKey && !force) return;
  chamberKey = key;

  let content;
  if (hyp.stage === "ingest") content = viewRead(reg, hyp);
  else if (hyp.stage === "vectorize") content = viewHypothesize(reg, hyp);
  else if (hyp.stage === "wait") content = viewMeasure(reg, hyp, false);
  else if (hyp.stage === "refine") content = viewMeasure(reg, hyp, true);
  else content = viewVerdict(reg, hyp);

  el("chamber-body").innerHTML =
    stageRailHTML(hyp.stage) + hypLineHTML(reg, hyp) + content;

  if (hyp.stage === "wait" || hyp.stage === "refine") {
    if (hyp.measurement) { animateT(hyp.measurement.t_stat, hyp.measurement.significant); }
  }
}

function stageRailHTML(stageKey) {
  const idx = STAGES.indexOf(stageKey);
  let html = '<div class="stage-rail">';
  STAGES.forEach((s, i) => {
    const d = STAGE_DEFS[s];
    const cls = i < idx ? "done" : (i === idx ? "cur" : "");
    const mark = i < idx ? "✓ " : (i === idx ? "● " : "○ ");
    html += `<span class="st ${cls}">${mark}${d.label}<span class="sub">${d.sub}</span></span>`;
    if (i < STAGES.length - 1) {
      const segCls = (i + 1) < idx ? "done" : ((i + 1) === idx ? "lit" : "");
      html += `<span class="seg ${segCls}"></span>`;
    }
  });
  return html + "</div>";
}

function hypLineHTML(reg, hyp) {
  const txt = hyp.hypothesis_text || "Probing " + (reg.name || reg.id) + " for a timing side channel.";
  const loc = hyp.location ? ` <span style="color:var(--dim)">· ${escHtml(hyp.location)}</span>` : "";
  return `<div class="hyp-line"><span class="tag">${hyp.hyp_id}</span>${escHtml(txt)}${loc}</div>`;
}

// READ — code view
function viewRead(reg, hyp) {
  const ev = reg.evidence;
  if (!ev) return `<div class="oracle"><div class="acquiring mono">reading source…</div></div>`;
  const lines = ev.code.map((c) => {
    const suspect = c.kind === "suspect";
    const tag = suspect ? `<span class="suspect-tag">◄ ${escHtml(ev.suspect_label)}</span>` : "";
    return `<div class="cl ${suspect ? "suspect" : ""}"><span class="num">${c.n}</span><span class="code k-${c.kind}">${escHtml(c.text)}</span>${tag}</div>`;
  }).join("");
  return `
    <div class="code-meta">
      <span class="who"><b>codellama:7b</b> · reading <span class="file">${escHtml(ev.file)}</span></span>
      <span class="mono" style="color:var(--mut);font-size:10px;">candidate sites <span style="color:var(--am)">5</span> · focus <span style="color:var(--rd)">${escHtml(ev.file)}:${ev.highlight_line}</span></span>
    </div>
    <div class="codeblock"><div class="scanline"></div>${lines}</div>`;
}

// HYPOTHESIZE — probe being written
function viewHypothesize(reg, hyp) {
  const ev = reg.evidence || {};
  return `
    <div class="code-meta"><span class="who"><b>codellama:7b</b> · writing timing probe</span></div>
    <div class="oracle" style="display:flex;flex-direction:column;justify-content:center;gap:14px;">
      <div class="mono pulse" style="font-size:11px;color:var(--cy);">▮ generating differential test vector…</div>
      <div style="display:flex;gap:24px;">
        <div><div style="font-size:10px;color:var(--mut)">condition A</div><div class="mono" style="font-size:13px;color:var(--am);margin-top:3px;">${escHtml(ev.condition_a || "—")}</div></div>
        <div><div style="font-size:10px;color:var(--mut)">condition B</div><div class="mono" style="font-size:13px;color:var(--cy);margin-top:3px;">${escHtml(ev.condition_b || "—")}</div></div>
      </div>
    </div>`;
}

// MEASURE / ADJUDICATE — oracle panel
function viewMeasure(reg, hyp, adjudicating) {
  const m = hyp.measurement;
  const ev = reg.evidence || {};
  const who = adjudicating ? `<b style="color:var(--am)">qwen3:8b</b> · weighing evidence` : `oracle · measuring`;
  const samples = m ? `<b>${(m.run_count || 50000).toLocaleString()}</b> samples` : `acquiring…`;
  const vizArea = m ? oracleVizHTML(reg, m) : `<div class="acquiring mono pulse" style="padding:48px 0;text-align:center;">▮ oracle running · sampling timings…</div>`;
  return `
    <div class="oracle">
      <div class="oracle-head">
        <span class="title">${who}</span>
        <span class="toggle">
          <span class="seg2 ${oracleMode === "distribution" ? "on" : ""}" onclick="setOracleMode('distribution')">distribution</span>
          <span class="seg2 ${oracleMode === "scope" ? "on" : ""}" onclick="setOracleMode('scope')">scope</span>
        </span>
        <span class="samples mono">${m ? '<span style="color:var(--cy)">●</span> ' : ''}${samples}</span>
      </div>
      <div id="oracle-viz">${vizArea}</div>
    </div>
    ${m ? statStripHTML(reg, m) : ""}`;
}

window.setOracleMode = function (mode) {
  oracleMode = mode;
  if (!focusId || !lastState) return;
  const t = lastState.targets[focusId];
  const hyp = t && t.active_hyp ? t.hyps[t.active_hyp] : null;
  if (!hyp || !hyp.measurement) return;
  const viz = el("oracle-viz");
  if (viz) viz.innerHTML = oracleVizHTML(targetRegistry[focusId], hyp.measurement);
  document.querySelectorAll(".toggle .seg2").forEach((n) => {
    n.classList.toggle("on", n.textContent.trim() === mode);
  });
};

function oracleVizHTML(reg, m) {
  return oracleMode === "scope" ? scopeSVG(reg, m) : distributionSVG(reg, m, 560, 168, false);
}

// ── Oracle visualizations from summary stats ─────────────────────────────────
function domainOf(m) {
  const sdA = Math.sqrt(Math.max(m.variance_A || 1, 0.25));
  const sdB = Math.sqrt(Math.max(m.variance_B || 1, 0.25));
  const lo = Math.min(m.mean_A - 3 * sdA, m.mean_B - 3 * sdB);
  const hi = Math.max(m.mean_A + 3 * sdA, m.mean_B + 3 * sdB);
  return { lo, hi, sdA, sdB };
}
function gaussPath(mean, sd, x2px, baseY, height, lo, hi) {
  const pts = [];
  const N = 60;
  for (let i = 0; i <= N; i++) {
    const x = lo + (hi - lo) * (i / N);
    const y = baseY - height * Math.exp(-0.5 * Math.pow((x - mean) / sd, 2));
    pts.push(x2px(x).toFixed(1) + "," + y.toFixed(1));
  }
  return "M" + pts.join(" L");
}
function distributionSVG(reg, m, W, H, mini) {
  const { lo, hi, sdA, sdB } = domainOf(m);
  const padL = 20, padR = 20, baseY = H - 28, height = H - 74;
  const x2px = (x) => padL + (x - lo) / (hi - lo) * (W - padL - padR);
  const pA = gaussPath(m.mean_A, sdA, x2px, baseY, height, lo, hi);
  const pB = gaussPath(m.mean_B, sdB, x2px, baseY, height, lo, hi);
  const aLbl = mini ? "" : `<text x="${x2px(m.mean_A).toFixed(0)}" y="36" text-anchor="middle" font-family="var(--mono)" font-size="9" fill="#F2B33C">A · ${escHtml(reg.evidence ? reg.evidence.condition_a.split(" · ")[0] : "A")}</text>`;
  const bLbl = mini ? "" : `<text x="${x2px(m.mean_B).toFixed(0)}" y="50" text-anchor="middle" font-family="var(--mono)" font-size="9" fill="#3DE0D4">B · ${escHtml(reg.evidence ? reg.evidence.condition_b.split(" · ")[0] : "B")}</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Timing distributions for condition A and B, separated by the timing signal.">
    <line x1="${padL - 6}" y1="${baseY}" x2="${W - padR + 6}" y2="${baseY}" stroke="#1E2636" stroke-width="1"/>
    <path d="${pA} Z" fill="#F2B33C" fill-opacity="0.10"/>
    <path d="${pA}" fill="none" stroke="#F2B33C" stroke-width="1.5"/>
    <path d="${pB} Z" fill="#3DE0D4" fill-opacity="0.12"/>
    <path d="${pB}" fill="none" stroke="#3DE0D4" stroke-width="1.5"/>
    ${aLbl}${bLbl}
  </svg>`;
}
function scopeSVG(reg, m) {
  const W = 560, H = 176;
  const { lo, hi, sdA, sdB } = domainOf(m);
  const x0 = 30, x1 = 540, topY = 40, botY = 150;
  const y2px = (ns) => botY - (ns - lo) / (hi - lo) * (botY - topY);
  const yA = y2px(m.mean_A), yB = y2px(m.mean_B);
  const sdpx = Math.min(10, Math.abs(y2px(m.mean_A) - y2px(m.mean_A + Math.sqrt(m.variance_A || 1))));
  const N = 96, step = (x1 - x0) / N;
  let pts = [];
  for (let i = 0; i <= N; i++) {
    const block = Math.floor(i / 6) % 2;
    const base = block ? yB : yA;
    const y = base + (Math.random() * 2 - 1) * (sdpx * 0.7 + 1);
    pts.push((x0 + i * step).toFixed(1) + "," + y.toFixed(1));
  }
  const evA = reg.evidence ? reg.evidence.condition_a.split(" · ")[0] : "A";
  const evB = reg.evidence ? reg.evidence.condition_b.split(" · ")[0] : "B";
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Oscilloscope trace of raw latencies toggling between two bands, revealing the leak as a periodic signal.">
    <g stroke="#141a26" stroke-width="0.5">
      <line x1="30" y1="40" x2="540" y2="40"/><line x1="30" y1="70" x2="540" y2="70"/><line x1="30" y1="100" x2="540" y2="100"/><line x1="30" y1="130" x2="540" y2="130"/>
      <line x1="115" y1="30" x2="115" y2="152"/><line x1="200" y1="30" x2="200" y2="152"/><line x1="285" y1="30" x2="285" y2="152"/><line x1="370" y1="30" x2="370" y2="152"/><line x1="455" y1="30" x2="455" y2="152"/>
    </g>
    <line x1="30" y1="${yA.toFixed(1)}" x2="540" y2="${yA.toFixed(1)}" stroke="#F2B33C" stroke-width="0.5" stroke-dasharray="2 4" opacity="0.5"/>
    <line x1="30" y1="${yB.toFixed(1)}" x2="540" y2="${yB.toFixed(1)}" stroke="#3DE0D4" stroke-width="0.5" stroke-dasharray="2 4" opacity="0.5"/>
    <text x="544" y="${(yA + 3).toFixed(1)}" font-family="var(--mono)" font-size="9" fill="#caa44e">${m.mean_A.toFixed(1)} ns · A</text>
    <text x="544" y="${(yB + 3).toFixed(1)}" font-family="var(--mono)" font-size="9" fill="#4fb8b0">${m.mean_B.toFixed(1)} ns · B</text>
    <polyline points="${pts.join(" ")}" fill="none" stroke="#3DE0D4" stroke-width="1.4" stroke-linejoin="round"/>
    <line x1="30" y1="28" x2="30" y2="152" stroke="#bdfcf6" stroke-width="1" opacity="0.85">
      <animate attributeName="x1" values="30;540;30" dur="4s" repeatCount="indefinite"/>
      <animate attributeName="x2" values="30;540;30" dur="4s" repeatCount="indefinite"/>
    </line>
  </svg>`;
}

function statStripHTML(reg, m) {
  const sig = m.significant;
  const t = m.t_stat;
  const pct = Math.max(2, Math.min(100, Math.abs(t) / Math.max(200, Math.abs(t)) * 100)).toFixed(0);
  const col = sig ? "var(--gn)" : "var(--rd)";
  const border = sig ? "#1c3b3a" : "#3b1c22";
  const delta = Math.abs(m.mean_A - m.mean_B).toFixed(1);
  return `
    <div class="stat-strip">
      <div class="tcard" style="border-color:${border}">
        <div><div class="lbl">WELCH t</div><div class="tval" id="tval" style="color:${col}">${fmtT(t)}</div></div>
        <div class="tgauge">
          <div class="bar"><div class="fill" style="width:${pct}%;background:${col}"></div><div class="thresh" style="left:2%"></div></div>
          <div class="cap"><span>|t| ≥ 4 threshold</span><span style="color:${col}">${sig ? "significant" : "below threshold"}</span></div>
        </div>
      </div>
      <div class="mcard"><div><div class="lbl">mean A</div><div class="mv" style="color:var(--am)">${m.mean_A.toFixed(1)}<span style="font-size:9px;color:var(--mut)"> ns</span></div></div>
        <div><div class="lbl">mean B</div><div class="mv" style="color:var(--cy)">${m.mean_B.toFixed(1)}<span style="font-size:9px;color:var(--mut)"> ns</span></div></div></div>
      <div class="mcard"><div><div class="lbl">Δ signal</div><div class="mv">${delta}<span style="font-size:9px;color:var(--mut)"> ns</span></div></div></div>
    </div>`;
}

function animateT(target, sig) {
  const node = el("tval");
  if (!node || target == null) return;
  const big = Math.abs(target) >= 1000;
  let v = 0, steps = 24, i = 0;
  const iv = setInterval(() => {
    i++; v = target * (i / steps);
    node.textContent = big ? Math.round(v).toString() : v.toFixed(1);
    if (i >= steps) { clearInterval(iv); node.textContent = fmtT(target); }
  }, 22);
}

// VERDICT
function viewVerdict(reg, hyp) {
  const r = hyp.result || {};
  const m = hyp.measurement;
  const sig = r.significant;
  const cls = sig ? "confirmed" : "cleared";
  const badge = sig ? "CONFIRMED" : "CLEARED";
  const verdict = r.verdict || (sig ? "PROMOTED" : "INVALIDATED");
  const mA = r.mean_A != null ? r.mean_A : (m ? m.mean_A : null);
  const mB = r.mean_B != null ? r.mean_B : (m ? m.mean_B : null);
  const delta = (mA != null && mB != null) ? Math.abs(mA - mB).toFixed(1) + " ns" : "—";
  const n = m && m.run_count ? m.run_count.toLocaleString() : "50,000";
  const side = m
    ? distributionSVG(reg, m, 300, 120, true) + `<div class="cap">→ written to findings ledger</div>`
    : `<div class="cap" style="margin:auto">${sig ? "→ written to findings ledger" : "model refines and retries"}</div>`;
  return `
    <div class="verdict">
      <div class="verdict-main ${cls}">
        <div style="display:flex;align-items:center;gap:9px;">
          <span class="vbadge ${cls}">${badge}</span>
          <span class="mono" style="font-size:10px;color:var(--mut)">${sig ? "leak detected · " : "no signal · "}${escHtml(verdict.toLowerCase())}</span>
        </div>
        <div class="vt ${cls}">t ${fmtT(r.t_stat)}</div>
        <div class="vsub">Welch · n=${n} · ${sig ? "p ≪ 0.001" : "|t| below 4"}</div>
        <div class="vmeans">
          <div><div class="lbl">mean A</div><div class="mv" style="color:var(--am)">${mA != null ? mA.toFixed(1) + " ns" : "—"}</div></div>
          <div><div class="lbl">mean B</div><div class="mv" style="color:var(--cy)">${mB != null ? mB.toFixed(1) + " ns" : "—"}</div></div>
          <div><div class="lbl">Δ signal</div><div class="mv">${delta}</div></div>
        </div>
      </div>
      <div class="verdict-side">${side}</div>
    </div>`;
}

// ── Event log ────────────────────────────────────────────────────────────────
function recordEvents(state) {
  const now = runStartMs ? ((Date.now() - runStartMs) / 1000).toFixed(1) : "0.0";
  for (const id of TARGET_ORDER) {
    const t = state.targets[id];
    if (!t || !t.active_hyp) continue;
    const h = t.hyps[t.active_hyp];
    const key = id + "/" + h.hyp_id;
    const sig = h.stage + ":" + h.stage_status;
    if (prevStage[key] !== sig) {
      prevStage[key] = sig;
      const lbl = STAGE_DEFS[h.stage].label;
      const done = h.stage_status === "done";
      eventLog.push({ t: now, txt: shortId(id) + " " + lbl + (done ? " ✓" : ""), cur: !done });
      if (eventLog.length > 7) eventLog.shift();
    }
  }
}
function renderEventLog() {
  el("event-log").innerHTML = eventLog.map((e) =>
    `<div class="ev ${e.cur ? "cur" : ""}"><span class="t">${e.t}</span> ${escHtml(e.txt)}</div>`).join("");
}

// ── Findings ledger ──────────────────────────────────────────────────────────
function renderFindings(state) {
  const items = [];
  let confirmed = 0;
  for (const id of TARGET_ORDER) {
    const t = state.targets[id];
    if (!t) continue;
    const res = latestResult(t);
    if (!res) continue;
    if (res.significant) confirmed++;
    items.push({ id, sig: res.significant, t: res.t_stat });
  }
  el("findings-count").textContent = items.length;
  el("findings").innerHTML = items.map((f) =>
    `<div class="finding ${f.sig ? "" : "cleared"}"><span class="fid">${shortId(f.id)}</span><span class="ft">t ${fmtT(f.t)}</span></div>`
  ).join("") || `<div class="mono" style="font-size:10px;color:var(--dim)">none yet</div>`;
}

// ── Ticker ───────────────────────────────────────────────────────────────────
function buildTicker() {
  const block = "26.0  25.8  28.9  29.1  25.9  28.7  26.1  29.3  25.7  28.8  26.0  29.0  25.8  28.9  26.2  29.1  25.9  28.6  ";
  el("ticker-track").textContent = block + block;
}

// ── Controls ─────────────────────────────────────────────────────────────────
function updateSpeedLabel(val) { el("speed-val").textContent = SPEED_STEPS[val].label; }
function currentStepDelay() { return SPEED_STEPS[parseInt(el("speed-slider").value, 10)].delay; }

function startReplayAll() {
  lastState = null; pinnedId = null; focusId = null; chamberKey = null;
  eventLog = []; prevStage = {}; runStartMs = null;
  el("chamber-body").innerHTML = ""; el("event-log").innerHTML = "";
  el("btn-replay-all").disabled = true; el("btn-stop").disabled = false;
  window.pywebview.api.start_replay_all(currentStepDelay());
}
function stopRun() { window.pywebview.api.stop_run(); }
