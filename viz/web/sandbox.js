// sandbox.js — Phase B model import + (B-ii) comparison view.
// Loads after pipeline.js, so it augments window.initTargets to also populate the
// target dropdown, and adds the model dropdown + run wiring.

let selectedModel = "";
let modelOk = false;

// ── Model dropdown (pushed from Python via list_models) ──────────────────────
window.onModels = function (models) {
  const sel = document.getElementById("model-select");
  models.forEach((m) => {
    const o = document.createElement("option");
    o.value = m.id; o.textContent = m.label;
    sel.appendChild(o);
  });
};

// ── Target dropdown — augment pipeline.js's initTargets ──────────────────────
const _origInitTargets = window.initTargets;
window.initTargets = function (targets) {
  if (typeof _origInitTargets === "function") _origInitTargets(targets);
  const ts = document.getElementById("target-select");
  targets.filter((t) => t.focused_target).forEach((t) => {
    const o = document.createElement("option");
    o.value = t.id; o.textContent = t.name || t.id;
    ts.appendChild(o);
  });
};

function refreshRunButton() {
  const target = document.getElementById("target-select").value;
  document.getElementById("btn-run-model").disabled = !(modelOk && target);
}

document.addEventListener("DOMContentLoaded", () => {
  const modelSel = document.getElementById("model-select");
  const targetSel = document.getElementById("target-select");
  const status = document.getElementById("model-status");

  modelSel.addEventListener("change", async () => {
    selectedModel = modelSel.value;
    modelOk = false;
    if (!selectedModel) { status.textContent = ""; refreshRunButton(); return; }
    modelOk = await window.pywebview.api.model_available(selectedModel);
    status.textContent = modelOk ? selectedModel + " ready" : "no API key for " + selectedModel;
    status.style.color = modelOk ? "var(--cy)" : "var(--rd)";
    refreshRunButton();
  });

  targetSel.addEventListener("change", refreshRunButton);
});

// ── Run the selected model on the selected target (sandbox run) ──────────────
window.runModel = function () {
  const target = document.getElementById("target-select").value;
  if (!selectedModel || !target) return;
  document.getElementById("model-status").textContent = "running " + selectedModel + "…";
  window.pywebview.api.start_sandbox_run(selectedModel, target);
};

// ── B-ii: comparison view ────────────────────────────────────────────────────
const chosenRuns = new Set();

window.onRuns = function (runs) {
  chosenRuns.clear();
  const box = document.getElementById("compare-runs");
  box.innerHTML = runs.map((r) =>
    `<label class="run-chip"><input type="checkbox" value="${r.run_id}"
      onchange="toggleRun('${r.run_id}', this.checked)"> ${r.model_code}
      <span class="mono">${r.run_id}</span></label>`).join("") ||
    '<span class="mono" style="color:var(--dim)">no saved runs yet</span>';
  document.getElementById("compare-table").innerHTML = "";
};

window.toggleRun = function (id, on) {
  if (on) chosenRuns.add(id); else chosenRuns.delete(id);
  if (chosenRuns.size >= 2) window.pywebview.api.build_comparison([...chosenRuns]);
};

window.onComparison = function (comp) {
  let html = "<table class='cmp'><tr><th>Target</th>" +
    comp.models.map((m) => `<th>${m}</th>`).join("") + "</tr>";
  comp.targets.forEach((tid) => {
    html += `<tr><td>${tid}</td>` + comp.detection[tid].map((c) => {
      const mark = c.confirmed ? "✓" : (c.located ? "·loc" : "✗");
      const ts = c.t_stat == null ? "" : ` t=${c.t_stat.toFixed(1)}`;
      return `<td>${mark}${ts}</td>`;
    }).join("") + "</tr>";
  });
  html += "<tr><td>cost $</td>" + comp.efficiency.cost_usd.map((x) => `<td>${x}</td>`).join("") + "</tr>";
  html += "<tr><td>wall s</td>" + comp.efficiency.wall_seconds.map((x) => `<td>${x}</td>`).join("") + "</tr>";
  html += "<tr><td>fp-rate</td>" + comp.robustness.fp_rate.map((x) => `<td>${x}</td>`).join("") + "</tr>";
  html += "</table>";
  document.getElementById("compare-table").innerHTML = html;
};

window.toggleCompare = function () {
  const cv = document.getElementById("compare-view");
  const stage = document.getElementById("stage");
  const show = cv.style.display === "none";
  cv.style.display = show ? "" : "none";
  stage.style.display = show ? "none" : "grid";
  if (show && window.pywebview) window.pywebview.api.list_runs();
};
