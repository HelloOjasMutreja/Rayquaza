# Experiment Log

Append-only. One entry per experiment/run. Never edit past entries.
Format:
## YYYY-MM-DD HH:MM [A/B] <short title>
- What: <what was run>
- Settings: <key parameters>
- Result: <what happened>
- Takeaway: <one-line conclusion / next step>

---

## 2026-06-14 [A] liboqs build + Kyber512 round-trip
- What: Built liboqs from source on WSL2/Ubuntu 24.04; ran minimal C test for Kyber512 keygen -> encaps -> decaps.
- Settings: gcc 13.3, cmake 3.28, OpenSSL 3.0.13, ninja 1.11.1. Flags: BUILD_SHARED_LIBS=ON, OQS_BUILD_ONLY_LIB=ON, OQS_DIST_BUILD=ON, KEM_KYBER=ON, SIG_DILITHIUM=ON.
- Result: All four steps passed (keygen OK, encaps OK, decaps OK, shared secret match OK).
- Takeaway: A0 complete. Toolchain confirmed. Build flags handed to Track B via SYNC.md. Next: A1 — map secret flow in Decaps.

## 2026-06-16 [A] A1 — Kyber512 decapsulation source code analysis
- What: Read all key source files in pqcrystals-kyber_kyber512_ref: kem.c, indcpa.c, poly.c, ntt.c, reduce.c, verify.c.
- Settings: liboqs depth-1 clone, ref implementation (not AVX2). Analysis only — no execution.
- Result: Mapped full decapsulation call chain; established sk layout; identified 5 candidate
  timing leak locations across compiler/branch/microarch categories. All are in pqcrystals
  ref C source. Confirmed: montgomery_reduce and barrett_reduce are branchless; poly_tomsg
  uses safe multiply-shift; verify uses XOR-accumulate; cmov uses asm barrier. Reference is
  CT by inspection but has known real-world failures at compiler and microarch layers.
- Takeaway: A1 complete. LEAK-5 (memcmp/FO compare) is highest-value A3 injection target.
  LEAK-1 (cmov/clangover) is easiest to trigger. Next: A2 — timing harness.
