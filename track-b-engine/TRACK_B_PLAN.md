# Track B Plan — AI & Attack Engine

Owner: Vedanth. Tag all entries [B]. (Maintained by Track B; do not edit from Track A.)

## Phase B0 (Days 1-3): Repo setup, Ollama connection verified.
- Directory scaffold, AGENTS.md Ollama rules, EXPERIMENT_LOG.md.
- dummy.c test target with 3 known vulnerability patterns.
- ollama_test.py: POST to codellama:7b, validate JSON output.
- Prompt library created (stage1/2/3).
- mock_feedback.py: synthetic timing data matching Track A harness schema.
- Status: DONE 2026-06-14

## Phase B1 (Days 4-7): Prompt library, ingestion pipeline.
- Build ingest.py: reads any C file → calls stage1_analysis.txt → parses JSON hypotheses.
- Validate prompt output quality on dummy.c (all 3 patterns detected).
- Build stage2 refinement loop using mock_feedback.py output.
- Build stage3 vector generator: hypothesis → compilable C timing test.
- Status: IN PROGRESS

## Phase B2 (Week 2): AFL++ baseline on clean Kyber.
- Needs: A0 build flags (DELIVERED).
- Set up AFL++ with liboqs Kyber512 decaps as target.
- Collect baseline coverage and crash stats (no LLM guidance).
- This is the control condition for the research comparison.

## Phase B3 (Week 2-3): Full adversary loop (depends on Track A harness).
- Needs: A2 timing harness, A3 weakened targets.
- Wire engine: ingest.py → stage1 → stage2 (real timing from A2) → stage3 → vector → A2 → loop.
- First real timing measurement on deliberately-weakened Kyber.

## Phase B4 (Weeks 3-5): Run engine on all targets, iterate prompts.
- Run full loop on all A3 targets. Log every run to EXPERIMENT_LOG.md.
- Iterate prompt templates based on false positive/negative rates.
- Compare LLM-guided vs AFL++ baseline coverage and time-to-find.

## Phase B5 (Weeks 6-7): Extend to Dilithium.
- Needs: A5 Dilithium target.
- Adapt ingestion and prompts for Dilithium signature scheme.
- Optional: quantum-inspired mutation layer for AFL++.

## Phase B6 (Week 8): Research paper draft and statistical analysis.
- Lead paper draft in shared/analysis/.
- Joint statistical analysis: LLM-guided vs baseline across all targets.
- Write up: methodology, results, limitations, future work.
