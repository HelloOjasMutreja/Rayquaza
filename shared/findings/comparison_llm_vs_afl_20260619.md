# LLM adversary loop vs AFL++ baseline

Clean baseline corpus paths: **2** | crashes: **0**

| Target | Truth | AFL paths | AFL crashes | Distinguishes clean? | LLM located? | LLM confirmed (this vector) | LLM t |
|---|---|---|---|---|---|---|---|
| leak2 | poly_tomsg | 20 | 0 | yes | yes | no | -0.17 |
| leak4 | indcpa_dec | 18 | 0 | yes | yes | yes | -901.41 |
| leak5 | crypto_kem_dec | 2 | 0 | no | yes | yes | 141.09 |

Notes:
- AFL++ crashes = 0 by construction: a non-constant-time branch/compare is not a
  memory-safety bug, so coverage fuzzing cannot *detect* a timing leak at all.
- 'Distinguishes clean?' = does the weakened target's corpus differ from the clean
  baseline. Branch leaks add reachable edges (corpus differs); the memcmp leak rides
  the same path (corpus identical) — coverage is blind to it even structurally.
- 'LLM located' = named the correct category + location. 'LLM confirmed' = the oracle
  returned significant under the loop's chosen test vector (a stricter, vector-dependent
  bar — e.g. leak2 is located correctly but its recorded vector hit the predictable
  branch direction, which is not significant; the misprediction vector gives t=-139.91).