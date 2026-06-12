# Project Charter

## Research Question
Does LLM-augmented adversarial guidance provide statistically significant uplift to an 
attacker probing post-quantum cryptography implementations, compared to classical fuzzing 
and manual analysis?

## Hypotheses
- H1: LLM-guided fuzzing finds implementation weaknesses faster than unguided fuzzing.
- H2: LLM-guided analysis achieves broader attack-surface coverage than classical tools.
- H3: Prompt strategies transfer across schemes (Kyber to Dilithium).
- H4: LLM + quantum-inspired heuristics outperform either alone (stretch goal).

## Scope
In scope: Kyber and Dilithium reference implementations (liboqs), timing side-channels, 
LLM-guided test-vector generation, AFL++ baseline comparison.
Out of scope: hardware/power side-channels (possible extension), breaking the underlying 
math, attacks on production systems.

## Targets (deliverables)
1. LLM-guided attack harness
2. Benchmark comparison: LLM-guided vs AFL++ vs manual
3. Vulnerability taxonomy for lattice PQC
4. Technical report (classified) + research paper draft
5. Documented, reusable codebase

## Timeline
8 weeks, two interns, extensible beyond the internship. See track plans for phase detail.
