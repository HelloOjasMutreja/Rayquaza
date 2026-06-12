# System Architecture

## Components
1. Target Library (Track A): liboqs Kyber/Dilithium, clean + weakened variants.
2. Timing Harness (Track A): high-resolution measurement of decapsulation/signing timing.
3. LLM Adversary Engine (Track B): ingests source, generates hypotheses, produces test 
   vectors, refines on feedback.
4. Test Vector Generator (Track B): converts LLM strategies into executable inputs.
5. Fuzzing Baseline (Track B): AFL++ with ASAN as the classical control.
6. Analysis (Shared): statistical comparison of attack paths and coverage.

## Data Flow
LLM Engine -> test vectors -> Timing Harness -> timing data -> LLM Engine (feedback loop).
Both attack paths (LLM-guided, AFL++) run against the same instrumented targets for fair 
comparison. Ground truth lives in shared/benchmark/.

## Integration Contract
Track A exposes: an instrumented target binary/library + a documented input/output format 
for feeding test vectors and receiving timing measurements. Defined in shared/schemas/.
