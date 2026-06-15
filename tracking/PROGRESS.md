# Progress

Living snapshot of project state. Update at the end of every work session. 
Tag entries [A] (Track A) or [B] (Track B). Use ISO dates.

## Done
- 2026-06-13 [A/B] Repository scaffold created.
- 2026-06-14 [A] Phase A0: WSL2 + Ubuntu 24.04, liboqs built, Kyber512 round-trip verified.
- 2026-06-14 [B] Phase B0: Repo scaffold, directory structure, AGENTS.md Ollama rules, EXPERIMENT_LOG.md, prompt library (stage1/2/3), dummy.c test target, ollama_test.py, mock_feedback.py — all created.
- 2026-06-14 [B] Phase B1: ingest.py ingestion pipeline (CodeIngester + Hypothesis dataclass) — preprocess/analyze/save working; verified on dummy.c, codellama:7b returned 2 HIGH-confidence ranked hypotheses (2/3 functions flagged; compare() has no secret-token params).
- 2026-06-16 [A] Phase A1: Kyber decapsulation code-read complete; 5 candidate leak locations logged in ISSUES.md.

## In Progress
- [A] Phase A2: build high-resolution timing harness for Kyber512 decapsulation.
- [B] Phase B2: AFL++ fuzzing baseline — harness.c (stub OQS_KEM_decaps), Dockerfile, build/run/summarize scripts ready. Next: build container, replace stub with real liboqs, run 24h baseline.
- [B] Phase B3: full LLM adversary loop (adversary_loop.py + main.py) — ingest→vectorize→feedback→refine→log→state cycle working end-to-end. Mock loop verified: 3-cycle run on dummy.c promoted H001 & H002 (t≈93.7/95.2, significant). READY FOR TRACK A INTEGRATION — drop real timing JSON into shared/feedback/ to replace mock (see SYNC.md). Open item: codellama:7b vectors not yet compilable (B-002), prompt iteration is Phase B4.

## Blocked
(none yet — B2 harness uses a stub and is NOT blocked; liboqs A0 build flags already delivered, see SYNC.md)
