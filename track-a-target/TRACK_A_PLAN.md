# Track A Plan — Crypto & Systems

Owner: Ojas. Tag all my tracking entries [A].

## Phase A0 — Foundations & Setup (Days 1-3)
Goal: repo, environment, liboqs building, Kyber round-trip working.
Outcome: liboqs compiles; Kyber512 keygen->encaps->decaps verified; first EXPERIMENT_LOG entry.

## Phase A1 — Understanding the Target (Days 4-7)
Goal: deep-read Kyber's liboqs implementation; map where secrets flow in Decaps.
Outcome: note in docs/ mapping secret flow; 3-5 candidate leak locations in ISSUES.md.

## Phase A2 — Timing Harness (Week 2, Days 8-11)
Goal: build high-resolution decapsulation timing measurement with low noise floor.
Outcome: working harness in harness/; SYNC entry that Track B can integrate.

## Phase A3 — Weakened Target (Week 2-3, Days 12-16)
Goal: fork Kyber, inject 2-3 documented vulnerabilities, verify measurable timing diff.
Outcome: weakened variants + ground truth in shared/benchmark/; SYNC entry for Track B. 
FIRST MAJOR INTEGRATION MILESTONE.

## Phase A4 — Running Attacks & Measurement (Weeks 3-5)
Goal: run B's engine + AFL++ against targets; collect timing; statistical analysis.
Outcome: results tables; per-run EXPERIMENT_LOG entries.

## Phase A5 — Extension & Hardening (Weeks 6-7)
Goal: add Dilithium target; realistic SAG scenario; robustness checks.
Outcome: Dilithium ground truth; end-to-end scenario with measured attacker cost.

## Phase A6 — Synthesis & Write-up (Week 8)
Goal: classified technical report half; hand clean results to shared/analysis/.
Outcome: report complete; datasets + plots handed off; codebase documented.
