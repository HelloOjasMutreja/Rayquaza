// pipeline.js — receives RunState from Python and updates the DOM.
// Called by: window.onStateUpdate(stateDict)
// Calls out to: window.pywebview.api.start_replay_all(), .stop_run()

const STAGES = ["ingest", "vectorize", "wait", "refine", "save"];
const STAGE_LABELS = {
  ingest:    "Ingest",
  vectorize: "Vectorize",
  wait:      "Wait\n(Oracle)",
  refine:    "Refine",
  save:      "Save",
};

// Registry filled when Python calls initTargets()
let targetRegistry = {};

// ── Initialise target registry from Python ──────────────────────────────────
window.initTargets = function(targets) {
  targetRegistry = {};
  targets.forEach(t => { targetRegistry[t.id] = t; });
};

// ── Main entry — called by Python on every state push ───────────────────────
window.onStateUpdate = function(state) {
  document.getElementById("model-label").textContent = state.model_label || "";
  document.getElementById("status-bar").textContent =
    state.finished ? "Run complete." : "Running…";

  const container = document.getElementById("pipeline-container");

  for (const [targetId, targetState] of Object.entries(state.targets)) {
    let row = document.getElementById("row-" + targetId);
    if (!row) {
      row = createRow(targetId);
      container.appendChild(row);
    }
    updateRow(row, targetId, targetState);
  }

  // Enable/disable stop button
  document.getElementById("btn-stop").disabled = state.finished;
  if (state.finished) {
    document.getElementById("btn-replay-all").disabled = false;
  }
};

// ── Create a fresh pipeline row for a target ────────────────────────────────
function createRow(targetId) {
  const meta = targetRegistry[targetId] || { name: targetId, difficulty_tier: "obvious" };
  const row = document.createElement("div");
  row.className = "pipeline-row";
  row.id = "row-" + targetId;

  const label = document.createElement("div");
  label.className = "target-label";
  const tierClass = "tier-" + meta.difficulty_tier;
  label.innerHTML = `
    ${escHtml(meta.name || targetId)}<br>
    <span class="tier ${tierClass}">${escHtml(meta.difficulty_tier || "")}</span>
  `;
  row.appendChild(label);

  const boxes = document.createElement("div");
  boxes.className = "pipeline-boxes";

  STAGES.forEach((stage, i) => {
    const box = document.createElement("div");
    box.className = "box";
    box.id = `box-${targetId}-${stage}`;
    box.innerHTML = `
      <span class="stage-name">${STAGE_LABELS[stage]}</span>
      <span class="hyp-label"></span>
    `;
    boxes.appendChild(box);

    if (i < STAGES.length - 1) {
      const conn = document.createElement("div");
      conn.className = "connector";
      conn.textContent = "→";
      boxes.appendChild(conn);
    }
  });

  row.appendChild(boxes);

  const badge = document.createElement("div");
  badge.className = "result-badge";
  badge.id = "badge-" + targetId;
  row.appendChild(badge);

  return row;
}

// ── Update all boxes in a row from TargetRunState ───────────────────────────
function updateRow(row, targetId, targetState) {
  const activeHypId = targetState.active_hyp;
  if (!activeHypId) return;

  const hypState = (targetState.hyps || {})[activeHypId];
  if (!hypState) return;

  const currentStageIdx = STAGES.indexOf(hypState.stage);
  const status = hypState.stage_status;

  STAGES.forEach((stage, i) => {
    const box = document.getElementById(`box-${targetId}-${stage}`);
    if (!box) return;

    const hypLabel = box.querySelector(".hyp-label");
    // Clear all state classes
    box.classList.remove("active", "pulsing", "done-ok", "done-fail");

    if (i < currentStageIdx) {
      // Past stage — show done state based on final result (only for save)
      if (stage === "save" && hypState.result) {
        box.classList.add(hypState.result.significant ? "done-ok" : "done-fail");
      } else {
        box.classList.add("done-ok");
      }
      hypLabel.textContent = "";
    } else if (i === currentStageIdx) {
      // Current stage
      if (stage === "wait" && (status === "start" || status === "active")) {
        box.classList.add("pulsing");
      } else if (status === "done") {
        if (stage === "save" && hypState.result) {
          box.classList.add(hypState.result.significant ? "done-ok" : "done-fail");
        } else {
          box.classList.add("done-ok");
        }
      } else {
        box.classList.add("active");
      }
      hypLabel.textContent = activeHypId;
    } else {
      // Future stage — idle
      hypLabel.textContent = "";
    }
  });

  // Update result badge
  const badge = document.getElementById("badge-" + targetId);
  if (badge && hypState.result) {
    const r = hypState.result;
    const verdict = (r.verdict || "").toLowerCase();
    const tStr = r.t_stat != null ? `t=${r.t_stat.toFixed(2)}` : "";
    badge.className = "result-badge " + verdict;
    badge.textContent = `${tStr} ${r.significant ? "✓" : "✗"} ${r.verdict || ""}`;
  } else if (badge) {
    badge.className = "result-badge";
    badge.textContent = "";
  }
}

// ── Speed control ─────────────────────────────────────────────────────────────
// Slider positions 0–4 map to named speeds; step_delay is passed to Python.
const SPEED_STEPS = [
  { label: "0.25×", delay: 2.4 },
  { label: "0.5×",  delay: 1.2 },
  { label: "1×",    delay: 0.6 },
  { label: "2×",    delay: 0.3 },
  { label: "4×",    delay: 0.15 },
];

function updateSpeedLabel(val) {
  document.getElementById("speed-val").textContent = SPEED_STEPS[val].label;
}

function currentStepDelay() {
  const val = parseInt(document.getElementById("speed-slider").value, 10);
  return SPEED_STEPS[val].delay;
}

// ── Button handlers — call through pywebview JS bridge ──────────────────────
function startReplayAll() {
  document.getElementById("pipeline-container").innerHTML = "";
  document.getElementById("btn-replay-all").disabled = true;
  document.getElementById("btn-stop").disabled = false;
  document.getElementById("status-bar").textContent = "Starting replay…";
  window.pywebview.api.start_replay_all(currentStepDelay());
}

function stopRun() {
  window.pywebview.api.stop_run();
}

// ── Utility ──────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
