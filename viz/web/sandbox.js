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
