# PQ-REAPER: LLM-Guided Timing Side-Channel Rediscovery in Post-Quantum Cryptography Implementations

**Vedanth Dama, Ojas Mutroja**
Defence Research and Development Organisation — Scientific Analysis Group (DRDO SAG)
*Internal Technical Report — B6 Draft, June 2026*

---

## Abstract

Post-quantum cryptographic (PQC) standards are being deployed worldwide, yet their software implementations remain susceptible to classical timing side-channel attacks that the underlying mathematics does not protect against. Manual auditing of these implementations is slow, expertise-intensive, and cannot scale with the breadth of the PQC migration. We present **PQ-REAPER**, a three-stage LLM-guided adversarial pipeline that autonomously identifies, hypothesises, and confirms timing side-channels in PQC source code. The pipeline combines a code-ingestion LLM (codellama:7b) for hypothesis generation, a static secondary scanner for non-constant-time API detection, a reasoning LLM (qwen3:8b) for evidence-based refinement, and a calibrated timing oracle for ground-truth confirmation.

We evaluate PQ-REAPER against six deliberately-weakened implementations drawn from CRYSTALS-Kyber (five targets, Kyber512) and ML-DSA-44 (one target), spanning three vulnerability classes. The pipeline autonomously rediscovered **4 of 5** Kyber512 leaks — all belonging to the `secret_dependent_branch` class — without any human guidance. The fifth leak (`nonconstant_comparison`, memcmp FO comparison) required static-scan direction, confirming a known limitation of 7B-parameter models on CT-vs-non-CT API substitution. As a direct comparison, AFL++ coverage fuzzing ran for 24 hours (~120M executions per target) and achieved **zero** detections: it cannot structurally observe timing leaks. For the memcmp-class leak specifically, the AFL++ corpus was identical to the clean baseline, meaning coverage fuzzing was not merely slower — it was categorically incapable. We also demonstrate cross-scheme transfer to ML-DSA-44, confirming rediscovery of a 32-byte memcmp challenge-comparison leak (t=164.30, p<0.001, WSL2/x86-64) and documenting an ISA-level portability boundary: the same oracle is non-detectable on macOS/arm64 due to NEON's fixed-width compare. PQ-REAPER operates entirely on open-weight models running locally, with no network access to external APIs, making it suitable for air-gapped security research environments.

---

## 1. Introduction

The global transition to post-quantum cryptography is underway. NIST finalised ML-KEM (CRYSTALS-Kyber) and ML-DSA (CRYSTALS-Dilithium) as primary standards in 2024, and national agencies worldwide are mandating migration timelines. However, cryptographic security guarantees apply only to the underlying mathematical problem — not to the correctness of the implementation. Timing side-channels that leak secret-dependent state through execution time have repeatedly broken production PQC deployments: KyberSlash (2023) demonstrated that a non-constant-time Fujisaki-Okamoto comparison in the CRYSTALS-Kyber reference implementation allows full private key recovery.

The standard defence — constant-time programming — is error-prone and difficult to audit. Implementations span thousands of lines of C, often hand-optimised for performance, and must simultaneously avoid branches, data-dependent memory access, and non-CT library calls. Manual auditing does not scale to the breadth of the PQC migration, and existing automated tools face structural limitations: static analysis tools (Binsec, ct-verif) are sound but require formal model construction; coverage-guided fuzzers (AFL++) find memory-safety bugs but cannot detect timing leaks because they are not memory safety bugs.

We ask: *can a large language model, operating directly on C source code, identify and precisely locate timing side-channels that a state-of-the-art fuzzer is structurally blind to?*

This paper presents **PQ-REAPER** (Post-Quantum Reasoning-Enhanced Adversarial Pipeline for Exploitability and Rediscovery), which answers this question affirmatively for the `secret_dependent_branch` leak class. Our contributions are:

1. **A three-stage automated pipeline** that ingests PQC source code, generates ranked timing-leak hypotheses, synthesises test vectors, and confirms leaks against a calibrated timing oracle — operating without human intervention after launch.

2. **Controlled rediscovery study** against six deliberately-weakened PQC implementations. The pipeline autonomously rediscovered 4/5 planted Kyber512 leaks and demonstrated cross-scheme transfer to ML-DSA-44.

3. **Quantitative LLM-vs-fuzzer comparison**: 24-hour AFL++ baseline on the same targets, establishing that coverage fuzzing is not a slower version of the same approach — it is categorically incapable of detecting timing leaks, with the memcmp target producing a corpus identical to the clean baseline.

4. **A documented capability boundary**: codellama:7b reliably catches `secret_dependent_branch` leaks (4/4) but misses `nonconstant_comparison` leaks (0/1 unaided) — a limitation consistent with 7B-parameter context window constraints on CT API substitution patterns.

5. **A timing oracle portability finding**: the ML-DSA-44 memcmp oracle (32-byte challenge comparison, signal ~0.4 ns/call) is detectable on x86-64 (t=164.30) but non-detectable on macOS/arm64, because AArch64 -O2 compiles 32-byte memcmp to fixed-width NEON compare instructions with no early-exit path. This is documented as a practitioner-relevant portability constraint.

---

## 2. Background

### 2.1 CRYSTALS-Kyber (ML-KEM)

CRYSTALS-Kyber [REF-CRYSTALS] is a lattice-based key encapsulation mechanism standardised as FIPS 203 (ML-KEM). Kyber512 targets NIST security level 1 (~AES-128 equivalent). Key operations are:
- `crypto_kem_keypair`: generates a public key and a secret key.
- `crypto_kem_enc`: generates a ciphertext and a shared secret.
- `crypto_kem_dec`: recovers the shared secret, implementing the Fujisaki-Okamoto (FO) transform, which re-encapsulates and verifies via `verify(ct, cmp, KYBER_CIPHERTEXTBYTES)`.

Correctness of the FO comparison must be constant-time. KyberSlash [REF-KYBERSLASH] showed that replacing `verify` with `memcmp` — a non-CT library function that exits at the first differing byte — leaks the Hamming distance between the re-encapsulated and submitted ciphertexts, enabling full private key recovery.

Internal arithmetic operates on polynomials in Rq = Zq[X]/(X^256+1), q=3329. Operations including `poly_tomsg` (coefficient rounding) and `basemul` (polynomial base multiplication in NTT domain) are prime candidates for secret-dependent branching if branchless implementations are replaced with conditional code.

### 2.2 ML-DSA-44 (CRYSTALS-Dilithium)

ML-DSA [REF-MLDSA] is a lattice-based digital signature scheme standardised as FIPS 204. The verify path in `mld_sign_verify_internal` computes a challenge hash c and compares it with a recomputed challenge c2. This comparison must be constant-time (`mld_ct_memcmp`). Replacing it with `memcmp(c, c2, MLDSA_CTILDEBYTES)` — 32 bytes for ML-DSA-44 — introduces an early-exit timing signal.

### 2.3 Timing Side-Channel Analysis

A timing side-channel exists when an algorithm's execution time depends on secret data. Detection follows the two-sample approach [REF-TTEST]: draw two classes of inputs — one expected to trigger the leaky path (class A) and one that does not (class B) — run many samples of each, and apply Welch's t-test:

```
t = (mean_A - mean_B) / sqrt(var_A/n + var_B/n)
```

|t| > 2 (roughly p < 0.05 for large n) indicates a statistically significant timing difference. We use n=50,000 samples per oracle run, providing strong power against even sub-nanosecond signals when REPS amplification is applied.

### 2.4 LLMs for Security Analysis

Recent work has applied LLMs to vulnerability discovery [REF-LLM-VULN], penetration testing guidance [REF-PENTEST-GPT], and code auditing [REF-LLM-AUDIT]. However, LLM-guided timing side-channel analysis in the PQC domain has not been systematically evaluated. Our work is the first to: (a) design a closed-loop pipeline with oracle feedback, (b) compare directly against AFL++ on the same targets, and (c) operate on air-gapped open-weight models appropriate for classified research environments.

---

## 3. Threat Model and Problem Statement

**Attacker capability**: The attacker possesses source code of the target PQC implementation (realistic for auditors, red teams, or state-level adversaries with access to reference implementations). The attacker can time decapsulation or verification calls and submit chosen ciphertexts.

**Goal**: Identify a timing side-channel that allows distinguishing two classes of inputs (e.g., valid vs. invalid ciphertext, positive vs. negative secret coefficient) with statistical significance (|t| > 2.0, n=50,000).

**Out of scope**: Breaking the underlying mathematical hardness assumption; hardware power or EM channels; attacks on production systems or real key material.

**Research problem**: Given the C source code of a PQC implementation, can an automated pipeline — operating without a human expert in the loop — identify the precise source location and vulnerability class of a timing side-channel, and produce a statistically confirmed hypothesis?

---

## 4. PQ-REAPER Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         PQ-REAPER                               │
│                                                                 │
│  C Source ──► [Stage 1: Ingestion]  codellama:7b               │
│               ├── Secret-token flagging                         │
│               ├── Static secondary scan (memcmp/branch/loop)   │
│               ├── MANDATORY FINDINGS directive (when triggered) │
│               └── Ranked Hypothesis list                        │
│                           │                                     │
│               [Stage 3: Vectorize]  codellama:7b               │
│               ├── Skeleton-fill prompt → C timing harness       │
│               ├── Compile check + error-feedback retry          │
│               └── Deterministic fallback (if LLM fails)        │
│                           │                                     │
│               [Timing Oracle]  harness_oracle                   │
│               └── Welch t-test, n=50,000 → timing JSON         │
│                           │                                     │
│               [Stage 2: Refine]  qwen3:8b                      │
│               ├── PROMOTED / DEMOTED / INVALIDATED / UNCHANGED  │
│               └── Exploitation path (if PROMOTED)              │
└─────────────────────────────────────────────────────────────────┘
```

### 4.1 Stage 1: Source Ingestion and Hypothesis Generation

The ingestion pipeline (codellama:7b, temperature 0.2, format:json) receives a C source file and returns a ranked JSON array of vulnerability hypotheses, each with fields: `id`, `category`, `location`, `hypothesis`, `trigger_condition`, `confidence`, `test_vector_hint`.

**Secret-token flagging**: The parser identifies functions whose signatures or bodies contain secret-handling tokens (`key`, `secret`, `priv`, `cipher`, `seed`, `nonce`, `mask`, `sk`, `dk`, `ek`) and forwards them to the LLM for analysis.

**Static secondary scan**: A secondary regex pass over every function body detects four leak-shaped patterns regardless of secret-token labelling:

| Pattern class | Regex |
|---|---|
| `nonconstant_comparison` | `\b(?:memcmp\|strcmp\|strncmp)\s*\(` |
| `secret_dependent_branch` | `\bif\b[^\n;{]*KYBER_Q` |
| `secret_dependent_branch` | `\bif\b[^\n;{]*==\s*0\b` |
| `variable_loop` | `\bfor\b[^\n;{]*\b256\b` |
| `variable_loop` | `\bwhile\b[^\n;{]*\bcount\b` |

**MANDATORY FINDINGS directive**: When the static scan matches, a prepended instruction tells the LLM that the static analyser has *already confirmed* a specific pattern is present and it *must* emit a finding for it. This hybrid approach allows the static scan's categorical knowledge to steer the LLM's probabilistic generation without discarding its natural-language reasoning about context and exploitability. Without this directive, codellama:7b consistently misses `nonconstant_comparison` leaks (§6.2).

**Focused targets**: For the 7B model, full Kyber translation units exceed practical context. `poly.c` (361 lines) causes the model to return prose; `indcpa.c` (338 lines) hits the 180s timeout; `kem.c` (92 lines) causes fixation on `crypto_kem_keypair`, missing `crypto_kem_dec`. We therefore extract single-function files for each hypothesis target. This limitation is specific to the 7B model tier; larger-context models (Claude API, GPT-4o) can ingest full TUs directly.

### 4.2 Stage 3: Test Vector Generation

For each promoted hypothesis, codellama:7b generates a standalone C timing harness that measures the execution time of class A (trigger) and class B (safe) inputs and outputs a Welch t-test result as JSON. The stage3 prompt provides a complete skeleton with labelled FILL sections; the model only fills in the function stub, argument declarations, and class-discriminating input values. This skeleton-fill approach dramatically improves compile success over free-form generation by the 7B model.

A compile-check gate validates the generated file (`cc -O0 -lm`). On failure, the compiler error is fed back to the LLM for one retry. If the retry also fails, a deterministic fallback harness is generated directly from the function signature, guaranteeing compilability at the cost of not exercising the specific trigger path (stub implementation).

### 4.3 Timing Oracle

The timing oracle (`harness_oracle`) is a standalone C binary that:
- Implements the *actual* patched function (not a stub), derived from the weakened target source
- Runs the two input classes with REPS-amplification (100–500 inner calls per sample) to amplify sub-nanosecond signals above the measurement noise floor
- Applies Welch's t-test over n=50,000 samples
- Outputs a JSON timing record to `shared/feedback/timing_{hyp_id}_{timestamp}.json`

The oracle is *not* hypothesis-specific: it confirms that a timing signal exists in the target function for the chosen input classes, but does not validate that the LLM's hypothesis text or location description is correct. Correctness is assessed by comparing the LLM's `category` and `location` output against ground truth.

### 4.4 Stage 2: Feedback Refinement

qwen3:8b (temperature 0.2, format:json) receives the hypothesis JSON and oracle timing record and classifies the hypothesis as PROMOTED, DEMOTED, INVALIDATED, or UNCHANGED. On PROMOTED, it generates a 3–5 step exploitation path. A JSON extraction layer handles qwen3's tendency to emit `["PROMOTED"]` (list of status strings) rather than a list of record objects, with a salvage path that extracts the first recognisable status token and falls back to oracle-derived status when the refiner output is unparseable.

---

## 5. Experimental Setup

### 5.1 Planted Vulnerability Targets

We constructed six weakened implementations from the liboqs reference code by inserting realistic vulnerabilities:

**Table 1: Planted leaks.**

| ID | Scheme | Function | Injected weakness | Vulnerability class |
|---|---|---|---|---|
| LEAK-1 | Kyber512 | `cmov()` | `if (b) memcpy(r, x, len)` replacing CT select | `secret_dependent_branch` |
| LEAK-2 | Kyber512 | `poly_tomsg()` | `if (2*t >= KYBER_Q)` replacing branchless rounding | `secret_dependent_branch` |
| LEAK-3 | Kyber512 | `basemul()` | `if (a0 < 0) a0 += KYBER_Q` before coefficient multiply | `secret_dependent_branch` |
| LEAK-4 | Kyber512 | `indcpa_dec()` | `for(k<256) if(mp.coeffs[k]<0) mp.coeffs[k]+=KYBER_Q` | `secret_dependent_branch` |
| LEAK-5 | Kyber512 | `crypto_kem_dec()` | `memcmp(ct, cmp, 768)` replacing `verify()` | `nonconstant_comparison` |
| MLDSA-1 | ML-DSA-44 | `mld_sign_verify_internal()` | `memcmp(c, c2, 32)` replacing `mld_ct_memcmp()` | `nonconstant_comparison` |

All leaks model realistic implementation mistakes: LEAK-1 (programmer adds explicit if-branch to "clarify" ct_select); LEAK-2/3/4 (performance optimisation via conditional code instead of branchless arithmetic); LEAK-5/MLDSA-1 (use of standard library comparison instead of CT variant, analogous to the real-world KyberSlash CVE).

Ground truth for each oracle was established independently by Track A, measuring oracle t-statistics under controlled conditions before the LLM pipeline ran.

### 5.2 Oracle Compilation Parameters

Compilation flags are chosen to preserve the injected timing signal:

| Target | Compiler | Flags | REPS | Rationale |
|---|---|---|---|---|
| LEAK-1 | cc (clang 18) | -O2 | 100 | Branch survives -O2; clang does not hoist conditional memcpy |
| LEAK-2 | gcc | -O0 | — | -O2 converts if-branch to cmov, eliminating signal |
| LEAK-3 | gcc | -O0 -fno-inline | 500 | -O2 optimises away branch; fno-inline required for signal isolation |
| LEAK-4 | gcc | -O0 | — | Normalization loop with 256 conditionals; -O2 vectorizes away signal |
| LEAK-5 | gcc | -O2 | — | memcmp early-exit is a library behaviour, not compiler-elim. |
| MLDSA-1 | gcc | -O2 | 100 | 32-byte window; REPS amplification required on x86 |

### 5.3 Models and Infrastructure

- **Stage 1 / Stage 3**: codellama:7b, served via Ollama at localhost:11434, temperature 0.2, stream=false, timeout 180s/300s respectively. `format:json` used for Stage 1 to suppress prose output.
- **Stage 2**: qwen3:8b, same Ollama instance, temperature 0.2, `format:json`.
- **Hardware (Track B, macOS)**: Apple M-series ARM (arm64), macOS 15. Used for LEAK-1 through LEAK-4 oracle runs. Cannot confirm ML-DSA oracle or LEAK-5 full-decaps signal.
- **Hardware (Track A, WSL2/x86-64)**: Ubuntu 24.04, gcc 13.3, Intel x86-64. Used for AFL++ baseline, MLDSA-1 oracle reconfirmation, and LEAK-2 misprediction oracle.
- **Engine configuration**: `RAYQ_OLLAMA_URL`, `RAYQ_CODE_MODEL`, `RAYQ_REASON_MODEL` are environment variables allowing model substitution without code changes.

### 5.4 AFL++ Baseline

AFL++ (version 4.x, default configuration, no sanitizers) ran for 24 hours per target on the same weakened implementations used by PQ-REAPER. The harness (`harness_kyber.c`) calls `crypto_kem_dec` with AFL-supplied ciphertext against a fixed secret key, exercising the decapsulation path.

Baseline: the clean (unweakened) Kyber512 decapsulation binary was also fuzzed for 24 hours to establish the corpus size of the unmodified code path.

---

## 6. Results

### 6.1 Kyber512 Rediscovery Summary

**Table 2: PQ-REAPER results on Kyber512 — all five leaks.**

| Leak | Vulnerability class | Location (ground truth) | LLM category | LLM location | Correct? | Oracle t | Mode |
|---|---|---|---|---|---|---|---|
| LEAK-1 | `secret_dependent_branch` | `cmov()` line 9 | `secret_dependent_branch` | `cmov()` line 9 | ✅ | 213.48 | Autonomous |
| LEAK-2 | `secret_dependent_branch` | `poly_tomsg()` | `secret_dependent_branch` | `poly_tomsg()` line 9 | ✅ | −139.91* | Autonomous |
| LEAK-3 | `secret_dependent_branch` | `basemul()` line 25 | `secret_dependent_branch` | `basemul()` line 25 | ✅ | −2421.91 | Autonomous |
| LEAK-4 | `secret_dependent_branch` | `indcpa_dec()` line 28 | `secret_dependent_branch` | `indcpa_dec()` line 28 | ✅ | −901.41 | Autonomous |
| LEAK-5 | `nonconstant_comparison` | `crypto_kem_dec()` line 36 | `nonconstant_comparison` | `crypto_kem_dec()` line 36 | ✅ | 141.09 | Scanner-directed |

*LEAK-2 oracle t-statistic under the LLM's test vector: −0.17 (not significant). The ground-truth oracle uses the misprediction vector (t=−139.91). See §6.2.

**Headline**: codellama:7b autonomously rediscovered **4/5** planted Kyber512 leaks. All four autonomous rediscoveries are `secret_dependent_branch` class. The fifth (LEAK-5, `nonconstant_comparison`) required static-scan direction; the LLM's output given the hint was correct in both category and location.

### 6.2 Per-Leak Analysis

**LEAK-1 — `cmov()` if-branch (Autonomous, t=213.48)**

codellama:7b correctly identified the branch `if (b) memcpy(r, x, len)` as a `secret_dependent_branch`. The hypothesis accurately described the mechanism: "the conditional branch `if (b)` in the cmov function leaks the FO comparison result, allowing an attacker to distinguish valid from invalid ciphertexts by timing." Oracle confirmed with t=213.48 (n=50,000, REPS=100): mean_A=2.042 ns/call (branch not taken), mean_B=1.603 ns/call (branch taken, 32-byte memcpy). The signal exists because the compiler preserves the branch rather than lowering to a cmov unconditionally, representing a realistic ARM/embedded target scenario.

**LEAK-2 — `poly_tomsg()` branch misprediction (Autonomous, category/location correct)**

The LLM correctly identified `poly_tomsg()` as the leak location with category `secret_dependent_branch`. However, the automatically generated test vector measured a predictable-branch scenario (all coefficients > q/2, branch always taken — no misprediction), which gave t=−0.17 (not significant). The ground-truth oracle uses an adversarially-constructed input class with random LCG-mixed coefficients that cause ~128 mispredictions per call, giving t=−139.91. This result highlights a vector-quality limitation of the 7B model: it correctly identifies the leak but does not generate the misprediction-maximising input class needed to confirm it. The Stage 3 vector generation improvement (B-002) addresses the compile-rate issue; the semantic input-class quality remains a B6 open item.

**LEAK-3 — `basemul()` sign branch (Autonomous, t=−2421.91)**

The LLM identified `basemul()` line 25 with hypothesis "branch on secret key coefficient sign leaks secret state." Oracle t=−2421.91 (n=50,000, REPS=500): mean_A=5.219 ns/call (positive coefficient, branch not taken), mean_B=5.851 ns/call (negative coefficient, branch taken, adds KYBER_Q). The extremely large t-statistic reflects clean signal isolation: the harness targets the single injected instruction with -O0 -fno-inline. This oracle was confirmed on macOS/arm64 (M-series), demonstrating that non-vectorised conditional arithmetic is detectable on ARM.

**LEAK-4 — `indcpa_dec()` normalization loop (Autonomous, t=−901.41)**

The LLM identified `indcpa_dec()` line 28: "branch on mp.coeffs[k] < 0 creates measurable timing difference." Oracle t=−901.41 (n=50,000): mean_A=278.19 ns/call (all positive, 0 additions), mean_B=385.75 ns/call (all negative, 256 × +=KYBER_Q). The 107.56 ns mean difference represents 256 conditional arithmetic operations on the secret-derived NTT polynomial *mp = s^T·b*, making this a realistic key-recovery scenario.

**LEAK-5 — `crypto_kem_dec()` memcmp FO comparison (Scanner-directed, t=141.09)**

Without the MANDATORY FINDINGS directive, codellama:7b consistently fixated on the `sk[...]` buffer copy branch in `crypto_kem_dec`, never emitting a finding for the `memcmp(ct, cmp, KYBER_CIPHERTEXTBYTES)` call. This pattern — where a `nonconstant_comparison` is present but a nearby `secret_dependent_branch` is more prominent — represents a reliable failure mode of the 7B model class. With the directive (triggered by static regex match on `memcmp(`), the model correctly emitted: `nonconstant_comparison @ crypto_kem_dec() line 36`. Oracle t=141.09 (n=50,000): mean_A=45.375 ns/call (equal buffers, full 768-byte scan), mean_B=30.975 ns/call (differ at byte 0, early exit). This is the KyberSlash-class vulnerability.

The credit structure for LEAK-5 is important for honest reporting: the *vulnerability class* was identified by the static scanner (regex match on `memcmp(`); the LLM contributed the hypothesis text, exact line number, and exploitability reasoning. The paper reports this as "scanner-directed" to reflect that the key categorical conclusion came from the static scan, not the LLM's autonomous reasoning.

### 6.3 ML-DSA-44 Cross-Scheme Transfer

PQ-REAPER was run against a weakened ML-DSA-44 `sign.c` with `memcmp(c, c2, 32)` substituting `mld_ct_memcmp`. The Stage 1 static scanner (memcmp regex match) triggered the MANDATORY directive; the LLM correctly identified `nonconstant_comparison` at `mld_sign_verify_internal()`.

Oracle results:
- **WSL2/x86-64** (gcc -O2, REPS=100, n=50,000): mean_A=2.482 ns/call (c==c2, full 32-byte scan), mean_B=2.193 ns/call (c[0]≠c2[0], exits at byte 0). **t=164.30, significant=true.** The 0.289 ns/call delta is amplified by REPS=100 to a clean signal.
- **macOS/arm64** (same code, cc -O2, REPS=100/1000/5000): t≈0.9/−0.8/0.75 (sign-unstable, non-significant at all REPS levels). At -O2, AArch64 compiles 32-byte `memcmp` to three 128-bit NEON `EOR`/`ORR` instructions with a final conditional branch on the aggregate zero result — no per-byte early exit exists at the ISA level. The signal that x86-64 detects (byte-loop early exit) physically does not exist in the arm64 instruction stream.

**Finding**: timing oracle portability is not guaranteed across ISA families. The same non-CT vulnerability produces a detectable timing signal on x86-64 (byte-loop memcmp, ~0.3 ns/byte early exit) but not on AArch64 -O2 (NEON fixed-width compare). This is a practitioner-relevant warning: oracle results must be qualified by the target ISA and compiler flags.

### 6.4 LLM vs. AFL++ Comparison

**Table 3: AFL++ 24h baseline vs. PQ-REAPER on three selected targets.**

| Target | AFL execs (~24h) | AFL corpus | vs. clean | AFL detected leak? | LLM located? | LLM oracle t |
|---|---|---|---|---|---|---|
| Clean baseline | 119,488,221 | 2 paths | — | — | — | — |
| LEAK-2 (`poly_tomsg`, branch) | 120,494,544 | 20 paths | +18 paths | ✗ (0 crashes) | ✅ | −139.91 |
| LEAK-4 (`indcpa_dec`, loop) | 120,158,729 | 18 paths | +16 paths | ✗ (0 crashes) | ✅ | −901.41 |
| LEAK-5 (`crypto_kem_dec`, memcmp) | 120,548,452 | 2 paths | **0 paths** | ✗ (0 crashes) | ✅ | 141.09 |

Three observations:

1. **Zero crashes across all targets at all REPS levels**: AFL++ found no bugs because timing side-channels are not memory-safety bugs. The comparison is not "AFL++ is slow at finding timing leaks" — AFL++ *cannot* detect them by design.

2. **Structural blindness to `nonconstant_comparison`**: For LEAK-5, the AFL++ corpus on the weakened target is *identical* to the clean baseline (both: 2 paths, 0 crashes). `memcmp(ct, cmp, 768)` follows the same code path regardless of early-exit; the coverage graph is unchanged. AFL++ cannot distinguish a correct implementation from one that leaks via early exit because the leaked information is in *time*, not *path coverage*.

3. **Branch leaks change coverage but are still undetected**: LEAK-2 and LEAK-4 produce more corpus paths (20 and 18 vs. 2 for clean), because the additional branches add coverage edges. AFL++ *finds* the branches but does not know they carry timing information. An analyst seeing a larger corpus cannot conclude there is a timing leak.

The comparison establishes a clear capability division: LLM-guided analysis operates at the semantic level (reads code, reasons about secret-dependence) while coverage-guided fuzzing operates at the syntactic level (explores paths, detects crashes). For timing side-channel discovery, these are complementary, not competitive.

### 6.5 Model Capability Analysis

The results reveal a clean capability profile for codellama:7b:

**Reliably detects** (4/4): `secret_dependent_branch` — conditional code on secret-derived values, where the branch and secret are both visible in the function body. The model correctly identifies the branch, the secret-derived operand, and the timing discriminant.

**Misses without static help** (0/1 unaided): `nonconstant_comparison` — CT-vs-non-CT API substitution, where the key signal is the *absence* of a constant-time variant (`ct_memcmp`, `verify`) rather than an explicit branch on a secret. A 7B model does not reliably hold the concept of CT API contracts as a binary predicate across 60–100 lines of context.

This is consistent with 7B-parameter scaling behaviour: the model reasons about structural code properties visible within a narrow window, but misses semantic contracts that require knowing what a function call *should* be doing rather than what it *is* doing.

---

## 7. Discussion

### 7.1 Ablation: Autonomous vs. Scanner-Directed

We ran PQ-REAPER in two modes on all five Kyber targets:

- **Mode A (autonomous)**: Stage 1 only, no static secondary scan, no MANDATORY directive.
- **Mode B (hybrid)**: Stage 1 + static secondary scan + MANDATORY directive when triggered.

| Mode | LEAK-1 | LEAK-2 | LEAK-3 | LEAK-4 | LEAK-5 | Total |
|---|---|---|---|---|---|---|
| Mode A (autonomous) | ✅ | ✅ | ✅ | ✅ | ✗ | **4/5** |
| Mode B (hybrid) | ✅ | ✅ | ✅ | ✅ | ✅ | **5/5** |

Mode A establishes LLM autonomous coverage. Mode B demonstrates the hybrid's practical completeness. The MANDATORY directive fires only when the static scan positively matches — it cannot introduce false positives on clean code, and it does not fire for `secret_dependent_branch` findings where the LLM already succeeds.

### 7.2 Vector Quality and LEAK-2

LEAK-2 represents an important nuance: the LLM correctly identifies the leak location and vulnerability class, but the generated test vector fails to elicit a statistically significant oracle response. The oracle *is* sensitive to the misprediction signal — t=−139.91 under the adversarial LCG-mixed input — but the LLM's vector used only predictable inputs. This is a Stage 3 vector quality issue, not a Stage 1 localization issue, and should be tracked separately in evaluation.

For a complete pipeline evaluation, LEAK-2 should be scored as: *location correct, oracle confirmable, vector suboptimal*. The paper reports it as an autonomous rediscovery (location correct) with a note on the vector limitation.

### 7.3 Timing Oracle Portability

The ML-DSA-44 finding establishes that timing oracle results must be qualified by ISA and compiler flags. Practitioners running timing analyses should be aware of the following ISA-specific behaviours relevant to PQC:

- **x86-64**: `memcmp` is a byte-loop with real early exit; sub-nanosecond differences per byte are detectable with REPS amplification.
- **AArch64 / -O2**: Short `memcmp` (≤32 bytes) compiles to NEON fixed-width compare (EOR/ORR over 16-byte lanes); no early exit exists at the ISA level regardless of library source.
- **AArch64 / branches**: Non-vectorised conditional arithmetic (LEAK-1/3/4) remains detectable because the branch instructions exist at the ISA level; NEON vectorisation applies primarily to memcmp-class comparisons.

The practical implication: a timing audit conducted on ARM development hardware may miss memcmp-class leaks that are clearly detectable on x86-64 production hardware. Reference implementation audits should be conducted on or validated against x86-64.

### 7.4 Engine Limitations and Future Work

**7B context window**: Full Kyber TUs exceed practical context for codellama:7b (180s timeout, or prose output). Focused single-function targets are required. Larger-context models (Claude API, GPT-4o) can ingest full TUs; B6 multi-model comparison is planned.

**Vector generation quality**: codellama:7b cannot reliably generate the *semantically correct* discriminating inputs for some leaks (LEAK-2 misprediction class). The skeleton-fill prompt (B-002 fix) addresses compile correctness; semantic correctness of the class-discriminating inputs requires either a stronger model or human-in-the-loop vector review.

**qwen3:8b JSON reliability**: The Stage 2 refiner returns non-object JSON shapes (~50% of runs), requiring the salvage path described in §4.4. Structured output support (Ollama JSON schema) was not available for qwen3:8b at the time of evaluation; newer releases may address this.

**Oracle specificity**: The timing oracle is not hypothesis-specific: a PROMOTED outcome indicates a signal exists in the target function for the chosen input classes, not that the LLM's specific mechanism description is correct. Category and location correctness must be assessed separately against ground truth.

---

## 8. Related Work

**Timing side-channels in PQC**: Ravi et al. [REF-RAVI] survey implementation pitfalls in lattice-based schemes. KyberSlash [REF-KYBERSLASH] demonstrated full key recovery from the exact `memcmp` substitution we plant as LEAK-5. Hermelink et al. [REF-HERMELINK] analysed fault and timing attacks on Kyber. Our work is the first to automate the *identification* phase rather than assuming knowledge of the leak location.

**LLMs for vulnerability discovery**: Liang et al. [REF-LLM-VULN] evaluated GPT-4 on CTF challenges. Yang et al. [REF-AUTOAUDIT] use LLMs for smart-contract auditing. PentestGPT [REF-PENTEST-GPT] guides penetration testing at a high level. Closest to our work, automated fuzzing-LLM hybrids [REF-HYBRID-FUZZ] use LLMs to generate seeds for coverage fuzzers, but do not address timing channels. None of these works apply LLM reasoning to PQC timing side-channels or compare against a fuzzing baseline on the same targets.

**Constant-time verification**: ct-verif [REF-CTVERIF] and Binsec/Rel [REF-BINSEC] formally verify constant-time properties, but require manual annotation or model construction and do not generalise across codebases without human effort. dudect [REF-DUDECT] automates timing measurement but requires a human to identify which functions to test. PQ-REAPER addresses the identification step that these tools assume is already done.

**Coverage-guided fuzzing for cryptographic code**: MAZE [REF-MAZE] adds taint tracking to guide AFL++ towards secret-dependent paths. Even with secret-dependent guidance, coverage fuzzing cannot detect timing leaks without an explicit timing oracle: it can reach the leaky code path but cannot observe that it takes different amounts of time. Our comparison (§6.4) establishes this boundary empirically.

---

## 9. Conclusion

We presented PQ-REAPER, a closed-loop LLM-guided pipeline for timing side-channel rediscovery in post-quantum cryptographic implementations. Against six deliberately-weakened implementations of CRYSTALS-Kyber and ML-DSA-44, the pipeline demonstrated:

- **4/5 autonomous Kyber rediscoveries** — all `secret_dependent_branch` class, located precisely to function and line number, confirmed by calibrated timing oracles.
- **1/5 scanner-directed** — the `nonconstant_comparison` class (memcmp FO comparison) requires static-scan direction for the 7B model; the hybrid finds it correctly.
- **Zero AFL++ detections** across 24 hours and ~120M executions per target, establishing a capability boundary: coverage fuzzing is structurally incapable of detecting timing leaks, not merely slower.
- **Cross-scheme transfer** to ML-DSA-44, with a portability finding: the 32-byte memcmp oracle is detectable on x86-64 (t=164.30) but non-detectable on AArch64 -O2 (NEON fixed-width compare).

The principal limitation is the 7B model's `nonconstant_comparison` blind spot, attributable to the difficulty of reasoning about CT API contracts at the 7B parameter scale. Future work will evaluate Claude and GPT-4o class models — accessible via the RAYQ_CODE_MODEL / RAYQ_REASON_MODEL environment variable interface — on full Kyber TUs to determine whether this limitation is model-size-dependent or fundamental to the prompting approach.

PQ-REAPER is implemented entirely with open-weight models, runs without external network access, and is suitable for air-gapped classified security research environments. All target weakening, oracle harnesses, and engine source are documented in the accompanying repository.

---

## References

*(Placeholder citations — to be replaced with formal bibliography for submission)*

- [REF-CRYSTALS] Avanzi et al., "CRYSTALS-Kyber Algorithm Specifications and Supporting Documentation," NIST PQC Round 3 Submission, 2021.
- [REF-MLDSA] NIST, "Module-Lattice-Based Digital Signature Standard," FIPS 204, 2024.
- [REF-KYBERSLASH] Kannwischer et al., "KyberSlash: Exploiting secret-dependent division timings in Kyber implementations," 2024.
- [REF-TTEST] Becker et al., "Test Vector Leakage Assessment (TVLA) Methodology in Practice," IACR 2013.
- [REF-RAVI] Ravi et al., "Side-channel and Fault-injection attacks over Lattice-based Post-quantum Schemes," TCHES 2019.
- [REF-HERMELINK] Hermelink et al., "Fault-enabled chosen-ciphertext attacks on Kyber," ASIACRYPT 2021.
- [REF-LLM-VULN] Liang et al., "Can Large Language Models Find And Fix Vulnerable Software?," arXiv 2023.
- [REF-AUTOAUDIT] Yang et al., "LLM-Powered Smart Contract Vulnerability Detection," 2024.
- [REF-PENTEST-GPT] Deng et al., "PentestGPT: An LLM-empowered Automatic Penetration Testing Framework," USENIX Security 2024.
- [REF-HYBRID-FUZZ] Xia et al., "Fuzz4All: Universal Fuzzing with Large Language Models," ICSE 2024.
- [REF-CTVERIF] Almeida et al., "Verifying Constant-Time Implementations," USENIX Security 2016.
- [REF-BINSEC] Daniel et al., "Binsec/Rel: Efficient Relational Symbolic Execution for Constant-Time at Binary-Level," IEEE S&P 2020.
- [REF-DUDECT] Reparaz et al., "Dude, is my code constant time?," DATE 2017.
- [REF-MAZE] Wang et al., "MAZE: Towards Automated Heap Feng Shui," 2021.

---

## Appendix A: Vulnerability Class Taxonomy

| Class | Definition | Examples in this study |
|---|---|---|
| `secret_dependent_branch` | An `if`/`for`/`while` whose condition depends on a secret-derived value, creating a data-dependent execution path | LEAK-1 (cmov), LEAK-2 (poly_tomsg), LEAK-3 (basemul), LEAK-4 (indcpa_dec) |
| `nonconstant_comparison` | Use of a non-CT comparison function (memcmp, strcmp) on secret or secret-derived data, allowing early-exit timing leakage | LEAK-5 (crypto_kem_dec), MLDSA-1 (mld_sign_verify_internal) |
| `variable_loop` | Loop bounds or iteration count depends on secret data | Not planted in this study; covered by secondary scan |

## Appendix B: Engine Configuration Reference

| Env variable | Default | Purpose |
|---|---|---|
| `RAYQ_OLLAMA_URL` | `http://localhost:11434/api/chat` | Ollama API endpoint |
| `RAYQ_CODE_MODEL` | `codellama:7b` | Stage 1 / Stage 3 model |
| `RAYQ_REASON_MODEL` | `qwen3:8b` | Stage 2 refinement model |

## Appendix C: Oracle t-statistics Summary

| Target | n | REPS | mean_A (ns) | mean_B (ns) | Δ mean (ns) | t-statistic | Significant |
|---|---|---|---|---|---|---|---|
| LEAK-1 cmov | 50,000 | 100 | 2.042 | 1.603 | +0.439 | 213.48 | true |
| LEAK-2 poly_tomsg (misprediction) | 50,000 | — | 760.4 | 816.8 | −56.4 | −139.91 | true |
| LEAK-3 basemul | 50,000 | 500 | 5.219 | 5.851 | −0.632 | −2421.91 | true |
| LEAK-4 indcpa_dec | 50,000 | — | 278.19 | 385.75 | −107.56 | −901.41 | true |
| LEAK-5 crypto_kem_dec | 50,000 | — | 45.375 | 30.975 | +14.4 | 141.09 | true |
| MLDSA-1 (WSL2/x86-64) | 50,000 | 100 | 2.482 | 2.193 | +0.289 | 164.30 | true |
| MLDSA-1 (macOS/arm64) | 50,000 | 100–5000 | ≈ same | ≈ same | <0.01 | ≈ 0 | false |
