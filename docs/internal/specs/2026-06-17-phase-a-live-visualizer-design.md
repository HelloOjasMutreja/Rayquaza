# Phase A — Live Real-Time Pipeline Visualizer — Design Spec

> **INTERNAL ONLY.** Excluded from public release (see `docs/internal/README.md`).
> Status: DRAFT for review. Date: 2026-06-17.

## 1. Goal & scope

Build a desktop-feeling application that shows the LLM adversary engine working **as it
happens** — every stage of every leak, with real data, rendered as an animated pipeline
diagram. This is Phase A of the roadmap (`docs/internal/05_ROADMAP.md`).

**In scope:**
- A native, chromeless window (pywebview) rendering an animated pipeline.
- Two run sources behind one interface: **Replay** (drive the UI from existing result
  files — no Ollama, no oracle) and **Live** (drive the UI from a real engine run).
- The fishing-pipeline visualization: Ingest → Vectorize → Wait (oracle) → Refine → Save,
  with the oracle box pulsing while measuring and resolving green/red on the t-stat.
- Multiple leaks shown as multiple parallel "lines cast."
- A **benchmark-shaped data model** (targets are first-class objects) — even though only
  the existing 6 leaks are wired.

**Out of scope (later phases):** multi-LLM import/comparison/report (Phase B), benchmark
corpus/scoring/leaderboard, cloud/SSH (Phase C), `.exe` packaging (reproducibility phase —
Phase A runs via `python run.py`).

**Design stance:** benchmark-shaped foundations now, YAGNI on big features. Keep the
visualizer cleanly separable from Track B's engine (we own `viz/`; the engine stays theirs).

## 2. What the engine actually emits (ground truth for the design)

Entry point: `python track-b-engine/main.py --target <c> --cycles N [--use-mock] [--resume]`.

Per run, the engine produces these observable signals **today**:

| Signal | Source | When |
|---|---|---|
| Header lines (`Target:`, `Models:`, `Mode:`, `Starting cycle 1 of N`) | stdout | start |
| `...waiting for feedback file containing 'H001' ...` | stdout (`_poll_feedback`) | oracle should run now |
| `[Cycle 1] Hypothesis H001 → PROMOTED (t=141.091, sig=True)` | stdout | hypothesis done |
| `=== LOOP COMPLETE ===` + promoted/demoted/invalidated | stdout | end |
| Full per-hypothesis record (incl. timing dict) | `shared/findings/loop_state.json` | written after each hypothesis |
| Oracle timing JSON | `shared/feedback/timing_*<hypid>*.json` | when oracle runs |

**Gap:** the *ingest*, *vectorize*, and *refine* stage **starts** are not individually
printed inside the loop. Coarse-live can only light: start → (waiting=oracle) → result.
The granular "every box lights exactly when its stage begins" needs the event contract (§6).

The oracle is a **separate binary** (`track-a-target/targets/<dir>/harness_oracle <hypid>
50000`) that writes the timing JSON the loop polls for. `run_focused.sh` already wires this
on macOS; we replace it with a cross-platform Python orchestrator.

## 3. Architecture & component boundaries

```
┌────────────────────────── viz/ (OURS) ──────────────────────────┐
│                                                                  │
│  app.py (pywebview window + JS bridge)                           │
│      ▲ pushes RunState/StageEvent      ▼ user actions (start)    │
│  ────┼──────────────────────────────────┼───────────────────    │
│  orchestrator.py  ── selects source ──>  RunSource (interface)   │
│                                          ├─ LiveSource           │
│                                          └─ ReplaySource         │
│  events.py  (data model + normalization to StageEvent/RunState)  │
│  sources/   stdout_parser • event_contract • state_file • feedback│
│  targets.json  (benchmark-shaped registry of the 6 leaks)        │
│  web/  index.html • styles.css • pipeline.js (the diagram)       │
└──────────────────────────────────────────────────────────────────┘
            │ LiveSource launches + reads
            ▼
   track-b-engine/main.py (Track B — unchanged for coarse-live;
                            +4–6 emit() lines for granular, §6)
            │ triggers
            ▼
   track-a-target/targets/<dir>/harness_oracle  (Track A oracle binary)
```

**Each unit, one purpose:**
- **`app.py`** — owns the window and the Python↔JS bridge. Knows nothing about engine
  internals; only receives `RunState`/`StageEvent` and forwards user actions.
- **`orchestrator.py`** — owns a *run's lifecycle*. Chooses Replay vs Live, drives the
  source, and (Live only) triggers the oracle at the right moment. Emits normalized events.
- **`RunSource` (interface)** — `start()`, yields `StageEvent`s, `stop()`. Two
  implementations so the UI is identical whether replaying or live.
- **`sources/*`** — small parsers, each converting ONE raw signal (a stdout line, an event
  line, the state file, a feedback file) into normalized events. Independently testable.
- **`events.py`** — the data model + the rules that fold raw signals into `RunState`.
- **`web/pipeline.js`** — pure rendering: given `RunState`, draw/animate boxes. No logic
  about the engine.

This boundary means the UI can be built and demoed entirely against `ReplaySource` before
`LiveSource` exists — and `LiveSource` can be developed without touching the UI.

## 4. Data model (benchmark-shaped)

```jsonc
// Target — first-class object. targets.json is the registry (6 entries now).
{
  "id": "kyber512_leak5",
  "name": "FO comparison (memcmp)",
  "primitive": "ML-KEM (Kyber512)",
  "difficulty_tier": "obvious",            // obvious | compiler | microarch
  "focused_target": "track-b-engine/ingestion/test_targets/kyber512_leak5_focused.c",
  "oracle_dir": "kyber512_leak5",          // under track-a-target/targets/
  "ground_truth": {                        // for scoring later; display now
    "category": "nonconstant_comparison",
    "location": "crypto_kem_dec",
    "expected_significant": true
  }
}
```

```jsonc
// StageEvent — the atomic thing sources emit and the UI consumes.
{ "run_id": "...", "target_id": "kyber512_leak5", "hyp_id": "H001",
  "stage": "vectorize",                    // ingest|vectorize|wait|refine|save
  "status": "start",                       // start|active|done|fail
  "ts": 1781700000.12, "data": { /* t_stat, verdict, etc. when relevant */ } }
```

```jsonc
// RunState — aggregated current state per target, what pipeline.js renders.
{ "run_id": "...", "model_label": "codellama:7b + qwen3:8b",
  "targets": { "kyber512_leak5": {
      "stage": "wait", "stage_status": "active",
      "hyp_id": "H001", "result": null } } }
```

The `Run`/`Result` records (model, score inputs) are defined now but only minimally
populated in Phase A; they become load-bearing in Phase B/benchmark.

## 5. Pipeline stages → visual states (the fishing line)

| Stage | Fishing | Box visual | Coarse trigger (today) | Granular trigger (contract) |
|---|---|---|---|---|
| INGEST | set up the rod | fill on active | inferred at run start | `emit(ingest,…)` |
| VECTORIZE | bait the hook | fill on active | inferred after ingest | `emit(vectorize,…)` |
| WAIT (oracle) | cast & wait for the jerk | **pulsing** | `...waiting for 'H001'` line | `emit(wait,…)` + oracle run |
| REFINE | feel the bite | fill on active | inferred before result | `emit(refine,…)` |
| SAVE | reel in the fish | **green** if significant / **red** if not | `[Cycle n] … → STATUS (t=…)` | `emit(save,…, {verdict})` |

Multiple targets = multiple horizontal lines, each independently animating. The headline
moment — the oracle box snapping green on `t=141` — comes from the result signal in both
modes.

## 6. The event contract (the one Track B ask)

To light ingest/vectorize/refine precisely, define a tiny additive emitter in the engine:

```python
# helper (Track B adds once)
def emit(stage, hyp_id, **data):
    print("RAYQEVENT::" + json.dumps({"stage": stage, "hyp": hyp_id,
                                      "status": "start", "ts": time.time(), **data}),
          flush=True)
```

Track B drops **4–6 one-line calls** at stage boundaries in `adversary_loop.py`
(`ingest`, `vectorize`, before `wait_for_feedback`, `refine`, after `save`). No behavior
change. We consume lines prefixed `RAYQEVENT::` from the same stdout pipe we already read —
**no new file plumbing**. Until those lines exist, `stdout_parser` falls back to coarse
inference. Logged as a Track A→B handoff in `tracking/SYNC.md`.

## 7. Liveness, and why we are never blocked

- **Milestone A1 — Replay (first deliverable):** full animated UI driven by existing
  `shared/findings/loop_state_kyber512_leak{2,4,5}.json` + their `timing_*.json`. No Ollama,
  no oracle, no engine changes. This is fully demoable and is the development surface for the
  whole frontend.
- **Milestone A2 — Live coarse:** `LiveSource` launches the engine subprocess (unbuffered),
  parses existing stdout beats, triggers the oracle, watches feedback/state. Real-time, zero
  Track B changes.
- **Milestone A3 — Live granular:** consume `RAYQEVENT::` lines once Track B adds them.
  Pure upgrade; no UI rework.

## 8. Cross-platform reality (Windows-first)

The user runs Windows. Ollama runs natively on Windows. **But the oracle binaries are
Linux/ARM ELF**, so in Live mode on Windows the oracle step must run via **WSL2**
(`wsl bash -c "cd … && ./harness_oracle …"`). The orchestrator abstracts oracle invocation
behind a small `run_oracle(target, hyp_id)` that picks native vs WSL2 per platform.
**Replay mode has no oracle dependency** — which is exactly why A1 (Replay) is the first
milestone and the safest demo path on any machine.

## 9. Error handling

| Failure | Behavior |
|---|---|
| Ollama not running (Live) | UI shows engine-failed banner; suggest `ollama serve`; run ends cleanly |
| Oracle binary missing/unbuilt | mark WAIT box `fail`; surface "oracle not built for <target>"; continue other targets |
| Feedback timeout (600s) | WAIT box `fail` (timeout); reflect the engine's own skip |
| Malformed stdout / event line | parser ignores unrecognized lines (never crash the UI) |
| loop_state.json mid-write | tolerate partial reads; use last-good snapshot |

## 10. Module layout

```
viz/
  __init__.py
  app.py                 # pywebview window + JS bridge
  orchestrator.py        # run lifecycle; selects source; triggers oracle (Live)
  events.py              # Target/StageEvent/RunState model + folding rules
  targets.json           # benchmark-shaped registry of the 6 leaks
  sources/
    __init__.py
    base.py              # RunSource interface
    replay.py            # ReplaySource (A1)
    live.py              # LiveSource (A2/A3): subprocess + oracle
    stdout_parser.py     # stdout beats + RAYQEVENT:: lines -> StageEvent
    state_file.py        # loop_state.json -> records
    feedback.py          # shared/feedback timing JSON -> result
  web/
    index.html
    styles.css
    pipeline.js          # renders RunState as animated pipeline
run.py                   # top-level entry: `python run.py`
```

`viz/` is a new top-level package, clearly ours, importing nothing from `track-b-engine`
except by launching `main.py` as a subprocess (process boundary, not code coupling).

## 11. Testing

- **Unit:** each `sources/*` parser against captured fixtures (real stdout transcripts,
  the committed `loop_state_*.json`, real `timing_*.json`). Pure functions, fast.
- **Replay integration:** A1 runs end-to-end from committed fixtures in CI without Ollama.
- **Live (manual):** A2/A3 verified on WSL2 where the oracle binaries build, plus a Windows
  run with Ollama native + oracle via WSL2.

## 12. Open questions for review

1. **Window/diagram aesthetic** — do you want me to mock the pipeline layout visually
   (boxes, colors, motion) before coding the frontend, or is the §5 description enough to
   start and iterate live?
2. **Target tiers** — the 3-tier labels (obvious / compiler / microarch) — keep these names
   or prefer different language for the demo audience?
3. **Replay-first** — confirm you're happy that the **first visible deliverable is Replay
   (A1)**, with live wire (A2/A3) immediately after. It's the fastest path to something on
   screen and the safest demo anywhere.
```
