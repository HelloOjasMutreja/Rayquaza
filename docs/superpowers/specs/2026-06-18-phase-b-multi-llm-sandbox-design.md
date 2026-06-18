# Phase B — Multi-LLM Sandbox + Comparison — Design Spec

**Date:** 2026-06-18
**Status:** Approved (brainstorming) — ready for implementation plan
**Branch:** `phase-b-sandbox`

## Goal

Run different LLMs (local Ollama + frontier APIs) against the PQC targets through the
*same* adversary-loop engine, save each run as a reproducible artifact, and compare runs
side-by-side across four axes. This is the benchmark runner in embryo — the north-star
direction — but v1 stays descriptive (no scoring formula, no leaderboard).

## Decisions locked in brainstorming

- **LLM sources:** Ollama (local) **and** API providers (Anthropic, OpenAI for v1; Gemini /
  generic endpoint are trivial follow-ons on the same interface).
- **Run model:** sequential saved runs. Run one LLM across the chosen targets, save its
  result-set as a first-class artifact, then run the next, then compare saved runs. The
  engine stays single-process. No live-parallel.
- **Comparison axes (all four):** detection outcome (located + confirmed), signal strength
  (Welch t), efficiency (wall-time, cycles, tokens, `$` cost), robustness (false-positive
  rate, autonomous vs hint-assisted).
- **Architecture:** "gateway shim" — a Track-A Ollama-compatible local HTTP server routes by
  model name to Ollama or provider APIs. The engine is nearly untouched (one env change).
- **Delivery:** two usable slices — **B-i** (run any model + save it) then **B-ii**
  (comparison view + report).
- **One model per run:** importing a model sets it as *both* the code/ingest model and the
  refine model (a run measures one LLM end-to-end). The `Run` keeps `model_code`/`model_reason`
  fields for fidelity and a future advanced split, but v1 sets both to the selected model.

## Non-goals (v1 / YAGNI)

- No composite RAYQUAZA score, no leaderboard, no held-out private set (later Benchmark phase).
- No live-parallel runs.
- No fine-grained per-call streaming UI for API models beyond what Phase A already shows.
- No provider beyond Ollama + Anthropic + OpenAI in v1.

## Architecture

All new code lives in Track A's lane: a new `sandbox/` package plus targeted extensions to
`viz/`. The only Track B (engine) change is additive and backward-compatible.

```
sandbox/
  __init__.py
  gateway/
    __init__.py
    server.py          new — local HTTP server emulating Ollama POST /api/chat + /api/tags
    router.py          new — model-name → provider routing
    providers/
      __init__.py
      base.py          new — Provider ABC: chat(messages, fmt) -> (text, usage)
      ollama.py        new — proxy to localhost:11434 (passthrough)
      anthropic.py     new — Anthropic Messages API → Ollama-shaped response
      openai.py        new — OpenAI Chat Completions API → Ollama-shaped response
    pricing.py         new — per-model $ pricing table; cost(usage) -> float
    meter.py           new — per-run token/cost accumulator (keyed by run_id)
  config.py            new — load model registry + API keys (gitignored secrets file/env)
  runstore.py          new — Run dataclass + save/load JSON artifacts under shared/runs/
  comparison.py        new — Comparison: select run_ids → per-axis table + markdown report
  run_session.py       new — orchestrates one run: launch engine via shim, fold events+cost,
                              write the Run artifact
viz/
  app.py               modify — API methods: list_models, add_api_model, start_sandbox_run,
                              list_runs, build_comparison
  web/
    sandbox.js         new — model-import panel + comparison view (extends pipeline.js)
    index.html         modify — add import panel + comparison-view mode toggle
    styles.css         modify — import panel + comparison columns
track-b-engine/
  engine/adversary_loop.py   modify (additive) — CODE_MODEL/REASON_MODEL/OLLAMA_URL from env
  ingestion/ingest.py        modify (additive) — MODEL/OLLAMA_URL from env
shared/
  runs/                new dir — saved run artifacts (committed; contain no secrets)
```

### Component responsibilities

**`gateway/server.py`** — binds a localhost port, serves `POST /api/chat` and `GET /api/tags`
with the same request/response shapes the engine already expects from Ollama. On `/api/chat`
it calls `router.route(model)` to get a Provider, invokes `provider.chat(...)`, records usage
in the meter, and returns an Ollama-shaped response. Supports the `format:"json"` field the
refine step uses. Runs in a daemon thread started by `run_session`.

**`gateway/router.py`** — maps a model name to a Provider instance: names known to Ollama
(`codellama:7b`, `qwen3:8b`, `llama3:*`, …) → `OllamaProvider`; `claude-*` → `AnthropicProvider`;
`gpt-*`/`o*` → `OpenAIProvider`. Unknown → error.

**`providers/base.py`** — `Provider.chat(messages, fmt) -> ChatResult(text, usage)` where
`usage = {prompt_tokens, completion_tokens}`. Each concrete provider translates the
Ollama-style `messages` array to its own API and the response back to plain text + usage.

**`pricing.py`** — `PRICES[model] = (in_per_mtok, out_per_mtok)`; `cost(model, usage) -> float`.
Ollama (local) models cost 0. Unknown models cost 0 with a flagged `cost_estimated: false`.

**`meter.py`** — accumulates `{calls, prompt_tokens, completion_tokens, cost}` per run_id;
the gateway increments it; `run_session` reads the total at run end.

**`config.py`** — loads the model registry (built-in defaults + user-added API models) and API
keys from `sandbox/secrets.local.json` (gitignored) or env vars `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`. Never returns keys into artifacts or logs.

**`runstore.py`** — the `Run` dataclass and JSON (de)serialization under `shared/runs/`.

```python
@dataclass
class TargetResult:
    target_id: str
    located: bool            # named correct category + location (vs targets.json ground truth)
    confirmed: bool          # oracle returned significant under the model's vector
    t_stat: float | None
    cycles: int              # adversary-loop cycles spent on this target
    wall_seconds: float
    autonomous: bool         # found without the static-scan mandatory-findings hint
    verdict: str             # PROMOTED / INVALIDATED / ...

@dataclass
class Run:
    run_id: str
    model_code: str          # model used for ingest/vectorize stages
    model_reason: str        # model used for refine stage
    provider: str            # "ollama" | "anthropic" | "openai" | mixed
    targets: list[TargetResult]
    started_at: float
    ended_at: float
    tokens: dict             # {prompt, completion}
    cost_usd: float
    cost_estimated: bool
    fp_rate: float           # promoted-but-not-located / promoted
    notes: str
```

**`comparison.py`** — given a list of run_ids, loads the Runs and produces a per-axis
side-by-side structure + a markdown report. Reuses `track-a-target/analysis/compare_llm_vs_afl.py`
conventions (located vs confirmed split) so the LLM-vs-LLM and LLM-vs-AFL framings stay
consistent.

**`run_session.py`** — the orchestration unit for one run:
1. resolve the selected model(s) and start the gateway on a free port,
2. launch the engine subprocess (reuse `viz.sources.live.LiveSource`) with env
   `OLLAMA_URL=http://localhost:<port>`, `RAYQ_CODE_MODEL`, `RAYQ_REASON_MODEL`,
3. fold the engine's StageEvents (Phase A) into RunState for the live UI **and** accumulate
   per-target results,
4. on finish, read the meter totals, compute `located`/`confirmed`/`fp_rate`, write the Run
   artifact via `runstore`, stop the gateway.

Data sources for the per-target axes: `confirmed`, `t_stat`, `verdict`, and `cycles` come from
the engine's StageEvents (Phase A `stdout_parser`) and the oracle result. `located`
(category + location match vs `viz/targets.json` ground truth) and `autonomous` come from the
loop_state JSON the engine writes to `shared/findings/loop_state_kyber512_*.json` at finish —
stdout does not carry category/location, so `run_session` reads that file to derive `located`.

### Engine change (additive, backward-compatible)

`adversary_loop.py` and `ingest.py` read their model names and Ollama URL from environment
variables, defaulting to today's hardcoded values:

```python
OLLAMA_URL   = os.environ.get("RAYQ_OLLAMA_URL", "http://localhost:11434/api/chat")
CODE_MODEL   = os.environ.get("RAYQ_CODE_MODEL", "codellama:7b")
REASON_MODEL = os.environ.get("RAYQ_REASON_MODEL", "qwen3:8b")
```

(ingest.py: `MODEL = os.environ.get("RAYQ_CODE_MODEL", "codellama:7b")` and the same URL var.)
No behaviour change when the vars are unset. Logged as a Track A→B sync note in `tracking/SYNC.md`.

## Data flow

```
import model (UI) → config registry
        │
        ▼
start run → run_session: gateway up → engine subprocess (env: shim URL + model names)
        │                                   │
        │            engine calls /api/chat │→ router → provider (ollama|anthropic|openai)
        │                                   │                    │ usage → meter
        ▼                                   ▼
   Phase A console animates live      oracle confirms (existing)
        │
        ▼
run finished → fold totals (meter) + per-target results → Run artifact in shared/runs/
        │
        ▼  (repeat for next model)
comparison view → select runs → per-axis table + markdown report
```

## UI

Extends the existing instrument console (`viz/web/`):

- **Model-import panel** (left of, or above, the specimen dock): a dropdown of Ollama models
  auto-detected via the gateway's `/api/tags`, plus "Add API model" (provider + model name +
  paste key, validated with a cheap ping). Selecting a model shows "Model X selected" and
  enables Run.
- **Run view:** unchanged — the instrument console drives the live run for the selected model;
  the HUD model label shows the active model + provider.
- **Comparison view** (new mode, toggled from the HUD): pick 2–4 saved runs → one column per
  model → rows for the four axes (detection per target, t-stat, time/cost, fp-rate) →
  "Generate report" writes a markdown summary to `shared/runs/`.

## Error handling

- Provider failure (bad key, rate-limit, network, malformed) → gateway returns an
  Ollama-shaped error object; the engine's existing retry/robustness path handles it; the
  cycle is marked failed in the run; UI surfaces the error; the session never crashes.
- Missing/invalid API key → import panel blocks with a clear message; a cheap validation ping
  runs before the model can be selected for a run.
- Ollama not running → existing check (local models only).
- Oracle timeout → existing handling.
- Optional per-run `$` cap in config; the meter aborts the run if exceeded and marks it capped.

## Testing (TDD)

- **gateway/router:** model-name → provider routing (table-driven).
- **providers:** request translation + response normalization for Anthropic and OpenAI using
  recorded/mock HTTP responses (no real API calls, no keys in tests). Ollama provider tested
  against a mock `/api/chat`.
- **pricing/meter:** cost math and per-run accumulation.
- **runstore:** Run ↔ JSON round-trip; `located`/`confirmed`/`fp_rate` derivation from a
  synthetic event+oracle fixture.
- **comparison:** per-axis table + report generation from saved-run fixtures.
- **Manual integration:** one Ollama run + one Anthropic run end-to-end on a single target,
  then open the comparison view.

## Security

- API keys live only in a gitignored `sandbox/secrets.local.json` or env vars; loaded by
  `config.py`; never written to run artifacts, comparison reports, or logs (only token counts
  and `$` cost are recorded).
- `shared/runs/` artifacts are committed and must contain no secrets — enforced by keeping keys
  out of the `Run` dataclass entirely.
- `.gitignore` entry for `sandbox/secrets.local.json`.

## Delivery slices

- **B-i — run any model, save it:** `config`, `gateway` (Ollama + Anthropic + OpenAI),
  `pricing`/`meter`, engine env change, `runstore`, `run_session`, model-import panel.
  Usable alone: import a model, run it live on the targets, get a saved Run artifact.
- **B-ii — compare:** `comparison`, the comparison-view UI mode, report generation.
  Builds on the artifacts B-i produces.

Each slice gets its own implementation-plan section and ships independently.
