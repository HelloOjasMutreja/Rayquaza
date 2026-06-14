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
