# Issues & Open Questions

GitHub-issue style, in-repo so agents can see them. Tag [A]/[B]. 
Format: [STATUS] date [track] description.
STATUS = OPEN / IN-PROGRESS / RESOLVED.

- [RESOLVED] 2026-06-14 [A] Confirm liboqs build flags to share with Track B. → Logged in SYNC.md.
- [OPEN] 2026-06-14 [B] [B-001] AFL++ harness (track-b-engine/fuzzing/harness.c) uses a STUB OQS_KEM_decaps returning 0. Replace with real liboqs. NOTE: this is NOT blocked on Track A — A0 build flags are already delivered (see SYNC.md); link -loqs -lssl -lcrypto -lpthread against ~/liboqs-install. Status: OPEN (Track B internal work).
