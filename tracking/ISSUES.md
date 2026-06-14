# Issues & Open Questions

GitHub-issue style, in-repo so agents can see them. Tag [A]/[B]. 
Format: [STATUS] date [track] description.
STATUS = OPEN / IN-PROGRESS / RESOLVED.

- [RESOLVED] 2026-06-14 [A] Confirm liboqs build flags to share with Track B. → Logged in SYNC.md.
- [OPEN] 2026-06-14 [B] [B-001] AFL++ harness (track-b-engine/fuzzing/harness.c) uses a STUB OQS_KEM_decaps returning 0. Replace with real liboqs. NOTE: this is NOT blocked on Track A — A0 build flags are already delivered (see SYNC.md); link -loqs -lssl -lcrypto -lpthread against ~/liboqs-install. Status: OPEN (Track B internal work).
- [OPEN] 2026-06-14 [B] [B-002] Stage 3 vector generation: codellama:7b produces C that is structurally close but does NOT compile (untyped global arrays `class_A = {...}`, undeclared start/end/secret_key/table, missing <math.h> for fabs/sqrt, prints significant as %d not true/false). The B3 loop mechanics are verified end-to-end with mock feedback regardless; vector quality is the target of Phase B4 prompt iteration. Candidate fixes: tighten stage3_vector.txt with a full worked example, deepen the looks_like_c() validation to attempt a real gcc compile + auto-retry on failure. Status: OPEN.
