# Multi-LLM hybrid-mode results (WSL2/x86, real oracle) — FINAL

Consolidated from isolated single-cell reruns after fixing three pipeline bugs
(see commits on `multi-llm-experiment`). Each cell = one full engine run: real
static-scan ingest, real gcc-compiled timing harness, real Welch t-test oracle,
real LLM refine verdict. Cost: $0 (all local, open-weight models).

| Target | codellama:7b | qwen2.5-coder:7b |
|---|---|---|
| kyber512_leak5 (FO memcmp) | located / confirmed (t=564.47) | located / confirmed (t=579.68) |
| kyber512_leak4 (cond. normalization) | located / confirmed (t=-317.85) | located / confirmed (t=-321.79) |
| kyber512_leak2 (poly_tomsg branch) | located / confirmed (t=-184.20) | located / confirmed (t=-110.26) |
| mldsa44_leak1 (ML-DSA memcmp) | located / confirmed (t=-589.09) | **missed** / confirmed (t=-656.23) |

7 of 8 cells: correctly located AND oracle-confirmed.
1 of 8 (qwen2.5-coder x mldsa44_leak1): oracle found a real, significant timing
signal, but the model's own category/location attribution didn't match ground
truth — a genuine, reportable finding (partial success / mis-attribution),
not a pipeline failure.

## Bugs fixed to get here (all committed on `multi-llm-experiment`)

1. **`viz/sources/stdout_parser.py`** — `_WAITING_RE` never matched the
   engine's actual log line, so `on_wait_for_oracle` never fired. Every
   "live" run silently degraded to a 600s timeout with no oracle data.
2. **`viz/orchestrator.py`** — `invoke_oracle` ran `harness_oracle` without
   `cwd=`, so its hardcoded relative output path resolved against the
   wrong directory. The oracle ran correctly and printed real, significant
   t-statistics to stdout every time, but its result file never landed
   where the engine polls for it.
3. **`track-b-engine/ingestion/ingest.py` + `sandbox/gateway/providers/ollama.py`**
   — HTTP timeouts (180s/300s) were too short for CPU-only inference on this
   machine; raised to 600s.
4. **`sandbox/run_session.py`** — stale `timing_H001_*.json` files from a
   previous cell's target were being read as the current cell's fresh oracle
   result (hypothesis ids restart from H001 every run). Now cleared before
   each cell.

## Known environment issue (not a code bug)

This WSL2 instance is capped at ~7.5GB RAM (Windows default: 50% of the
15.5GB host). Under memory pressure, Ollama's own process was OOM-killed by
the Linux kernel mid-request; the resulting HTTP 500 wasn't specifically
handled by the engine's error path, causing a fast, silent-looking failure
that needed a manual retry. `C:\Users\Ojas\.wslconfig` has been created
(memory=12GB) but needs a `wsl --shutdown` + relaunch to take effect —
not done tonight since it needed your input. After that restart this class
of failure should stop entirely.

## Also fixed tonight (unrelated, blocking prerequisite)

- Windows-side engine crashed with a `UnicodeDecodeError` on all file I/O
  (cp1252 default vs. utf-8 source) — irrelevant once running in WSL, but
  fixed regardless since it was already committed.
- `C:` drive was nearly full (0 bytes free at one point), which was the
  actual cause of WSL's repeated `Wsl/Service/E_UNEXPECTED` crashes tonight
  — fixed by clearing `npm-cache` (7.2GB, pure disposable cache).
- Ollama reinstalled properly inside WSL2 (previous binary was a broken
  partial install missing its runner libraries), pointed at your existing
  `D:\Ollama\models` — no re-download needed.
- Built the missing `harness_oracle` binaries for all 6 Track A targets
  (source existed, was just never compiled in this WSL clone).

## Next steps (need your input, not run tonight)

- AWS GPU quota (ap-south-1, g5.xlarge) was approved ~13h ago — ready
  whenever you want to run the 32B-class tier.
- Frontier API tier (Claude/GPT) — needs your API keys in
  `sandbox/secrets.local.json` (gitignored).
- Recommend `wsl --shutdown` + relaunch at your convenience to pick up the
  12GB memory ceiling before any further large local-tier runs.
