# Glossary

(Shared vocabulary for both tracks. Add terms as the project grows.)

- KEM: Key Encapsulation Mechanism. Kyber is a KEM.
- Kyber / ML-KEM: NIST-standardized lattice-based KEM (FIPS 203).
- Dilithium / ML-DSA: NIST-standardized lattice-based signature scheme (FIPS 204).
- Module-LWE: the hard problem underlying Kyber and Dilithium security.
- NTT: Number Theoretic Transform; Kyber's polynomial multiplication primitive.
- FO Transform: Fujisaki-Okamoto; gives Kyber its CCA security via a re-encryption check.
- Constant-time: code whose execution time does not depend on secret values.
- Timing side-channel: leakage of secret info through execution-time variation.
- Side-channel oracle: an interface that leaks secret-dependent info to an attacker.
- ASAN: AddressSanitizer; detects memory errors.
- AFL++: coverage-guided fuzzer used as our classical baseline.
