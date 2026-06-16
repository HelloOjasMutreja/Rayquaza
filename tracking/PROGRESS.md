# Progress

Living snapshot of project state. Update at the end of every work session. 
Tag entries [A] (Track A) or [B] (Track B). Use ISO dates.

## Done
- 2026-06-13 [A/B] Repository scaffold created.
- 2026-06-14 [A] Phase A0: WSL2 + Ubuntu 24.04, liboqs built, Kyber512 round-trip verified.
- 2026-06-14 [B] Phase B0: Repo scaffold, directory structure, AGENTS.md Ollama rules, EXPERIMENT_LOG.md, prompt library (stage1/2/3), dummy.c test target, ollama_test.py, mock_feedback.py — all created.
- 2026-06-14 [B] Phase B1: ingest.py ingestion pipeline (CodeIngester + Hypothesis dataclass) — preprocess/analyze/save working; verified on dummy.c, codellama:7b returned 2 HIGH-confidence ranked hypotheses (2/3 functions flagged; compare() has no secret-token params).
- 2026-06-16 [A] Phase A1: Kyber decapsulation code-read complete; 5 candidate leak locations logged in ISSUES.md.
- 2026-06-16 [A] Phase A2: timing harness built and verified; baseline JSON saved to shared/feedback/.
- 2026-06-16 [A] Phase A3: LEAK-5 (memcmp FO comparison) injected and confirmed. Direct oracle measurement: mean_A=28.9ns (valid CT, full compare), mean_B=25.8ns (invalid CT, early exit), t=78.9, significant=true. Ground truth in shared/feedback/. FIRST MAJOR INTEGRATION MILESTONE.
- 2026-06-16 [A] Phase A4: LEAK-2 (poly_tomsg branch) and LEAK-4 (indcpa_dec normalization) injected and confirmed. Oracles: LEAK-2 t=-139.91, LEAK-4 t=-318.58 (both n=50000, significant=true). Three weakened targets now available in track-a-target/targets/. JSON saved to shared/feedback/.
- 2026-06-16 [A] Phase A5: MLDSA-LEAK-1 (memcmp challenge comparison in ML-DSA-44 verify) injected and confirmed. Oracle: t=116.97, significant=true (n=50000). Target: track-a-target/targets/mldsa44_leak1/. Fourth target now available.

## In Progress
- [A] LEAK-3 (Kyber512 basemul branch) — optional extension, lower priority.
- [A] Integration: run B's adversary loop against all three confirmed targets (LEAK-2/4/5).
- [B] Phase B2: AFL++ fuzzing baseline — harness.c (stub OQS_KEM_decaps), Dockerfile, build/run/summarize scripts ready. Next: build container, replace stub with real liboqs, run 24h baseline.
- [B] Phase B3: full LLM adversary loop (adversary_loop.py + main.py) — ingest→vectorize→feedback→refine→log→state cycle working end-to-end. Mock loop verified: 3-cycle run on dummy.c promoted H001 & H002 (t≈93.7/95.2, significant). READY FOR TRACK A INTEGRATION — drop real timing JSON into shared/feedback/ to replace mock (see SYNC.md). Open item: codellama:7b vectors not yet compilable (B-002), prompt iteration is Phase B4.

## Blocked
(none yet — B2 harness uses a stub and is NOT blocked; liboqs A0 build flags already delivered, see SYNC.md)
