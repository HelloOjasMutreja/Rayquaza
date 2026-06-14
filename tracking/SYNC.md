# Sync & Handoffs

Cross-track coordination board. Log here when one track delivers something the other needs, 
or needs something from the other. This is how the two halves stay coupled.

## Track A -> Track B (deliverables B depends on)
- [DELIVERED] 2026-06-14 A0: liboqs build flags (for B2 fuzzing baseline).
  liboqs commit: depth-1 clone of open-quantum-safe/liboqs main.
  cmake -G Ninja .. \
    -DCMAKE_INSTALL_PREFIX="$HOME/liboqs-install" \
    -DBUILD_SHARED_LIBS=ON \
    -DOQS_BUILD_ONLY_LIB=ON \
    -DOQS_DIST_BUILD=ON \
    -DOQS_ENABLE_KEM_KYBER=ON \
    -DOQS_ENABLE_SIG_DILITHIUM=ON
  Installs to ~/liboqs-install/{include,lib}. Link with -loqs -lssl -lcrypto -lpthread.
  Tested on Ubuntu 24.04, gcc 13.3, cmake 3.28, OpenSSL 3.0.13.
- [PENDING] A2: timing harness + input/output format (needed for B3 engine loop).
- [PENDING] A3: weakened Kyber targets + ground truth (needed for B3 testing).
- [PENDING] A5: Dilithium target (needed for B5).

## Track B -> Track A (deliverables A depends on)
- [PENDING] B3: test-vector format spec (so A harness can consume them).

## Open coordination questions
(none yet)
