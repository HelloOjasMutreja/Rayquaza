# Experiment Log — PQ-REAPER (Root)

Append-only. One entry per experiment/run. Never edit past entries.
Format: [YYYY-MM-DD HH:MM] [A/B] Phase: <phase> | Task: <what was run> | Result: <outcome> | Next: <next step>

---

## Example entry
[YYYY-MM-DD HH:MM] [B] Phase: BX | Task: ... | Result: ... | Next: ...

---

## 2026-06-14 [B] Phase: B0 | Task: Repo scaffold + Ollama test + prompt library created | Result: pending ollama_test.py run | Next: run ollama_test.py on dummy.c, then build ingest.py

## 2026-06-14 22:11 [B] Phase: B1 | Task: Ran ingest.py on dummy.c (preprocess + stage1 analyze via codellama:7b, stream:false) | Result: 3 functions parsed, 2 flagged (check_key[key], lookup[secret]); codellama:7b returned 2 valid JSON hypotheses, both HIGH (H001 secret_dependent_branch, H002 variable_time_access); saved to shared/findings/hypotheses_20260614_221101.json. compare() not flagged (params a/b carry no secret token). | Next: feed hypotheses to stage2 refinement using mock_feedback.py output; wire stage3 vector generation.

## 2026-06-14 22:12 [B] Phase: B2 | Task: Created AFL++ baseline harness (harness.c with stub OQS_KEM_decaps), Dockerfile (ubuntu:22.04 + afl++), build.sh, run_baseline.sh, summarize_afl.py, README.md | Result: Files ready; harness not yet container-built or run (stub returns 0). liboqs A0 flags available for real link. | Next: docker build -t kyber-fuzz . ; replace stub with real liboqs; run 24h baseline → shared/findings/afl_baseline_<date>.json.
[2026-06-14 22:29] [B] Phase: B3 | Cycle: 1 | Hypothesis: H001 | Status: PROMOTED | t_stat: 93.704271 | significant: True | Next: Sweep all 256 values of key[0] to build a full timing profile.
[2026-06-14 22:32] [B] Phase: B3 | Cycle: 2 | Hypothesis: H002 | Status: PROMOTED | t_stat: 95.169611 | significant: True | Next: Verify if timing leakage persists across multiple CPU cores using cache-flushing (clflush) between operations.

## 2026-06-14 22:32 [B] Phase: B3 | Task: End-to-end 3-cycle adversary loop on dummy.c (--use-mock): ingest(codellama:7b) → vectorize(codellama:7b) → mock_feedback → refine(qwen3:8b) → log → state, all calls stream:false temp:0.2 | Result: 2 hypotheses processed (dummy.c yields 2; --cycles 3 capped by available hypotheses). H001 PROMOTED (t=93.70, sig), H002 PROMOTED (t=95.17, sig). qwen3:8b returned valid exploitation_path arrays for both. State → shared/findings/loop_state.json; vectors → shared/vectors/vec_H00{1,2}_*.c; feedback → shared/feedback/mock_timing_*.json. KNOWN LIMITATION: generated vectors do not yet compile (issue B-002) — loop mechanics verified, vector quality deferred to B4 prompt iteration. | Next: integrate real Track A timing (drop files in shared/feedback/, remove --use-mock); iterate stage3 prompt for compilable C.
