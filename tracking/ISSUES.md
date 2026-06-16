# Issues & Open Questions

GitHub-issue style, in-repo so agents can see them. Tag [A]/[B]. 
Format: [STATUS] date [track] description.
STATUS = OPEN / IN-PROGRESS / RESOLVED.

- [RESOLVED] 2026-06-14 [A] Confirm liboqs build flags to share with Track B. → Logged in SYNC.md.
- [OPEN] 2026-06-14 [B] [B-001] AFL++ harness (track-b-engine/fuzzing/harness.c) uses a STUB OQS_KEM_decaps returning 0. Replace with real liboqs. NOTE: this is NOT blocked on Track A — A0 build flags are already delivered (see SYNC.md); link -loqs -lssl -lcrypto -lpthread against ~/liboqs-install. Status: OPEN (Track B internal work).
- [DEFERRED] 2026-06-14→2026-06-16 [B] [B-002] Stage 3 vector generation: codellama:7b produces C that is structurally close but does NOT compile. DEFERRED for B4: generated C vectors are documentation artifacts only; real timing measurement runs through Track A's harness_oracle, not by compiling/running these vectors. What matters for B4 is whether the LLM hypothesis correctly identifies the vulnerability the oracle confirms. Revisit vector-compile quality (worked example in stage3_vector.txt + gcc-compile-and-retry in the loop) if/when vectors need to be directly executable. Not blocking B4.
- [OPEN] 2026-06-16 [B] [B-003] B4 real-oracle runs blocked: the targets assumed for B4 (track-a-target/targets/kyber512_leak5/kem.c, kyber512_leak2/poly.c) and the harness_oracle binary are absent — targets/ holds only .gitkeep, and A2/A3 are still PENDING in SYNC.md. No real loop run or oracle measurement was performed; no rediscovery/t-stat results were produced or logged as fact. Unblock: Track A commits A2 (harness_oracle) + A3 (weakened targets). Status: OPEN (cross-track, blocked on A).
