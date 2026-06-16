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
- IND-CPA: Indistinguishability under Chosen Plaintext Attack; weaker security notion that Kyber's inner layer (indcpa) achieves.
- IND-CCA2: Indistinguishability under Adaptive Chosen Ciphertext Attack; what the full Kyber KEM achieves via the FO transform.
- Implicit rejection: FO transform mechanism where invalid ciphertexts produce a deterministic pseudorandom output (using secret z) rather than an explicit error; hides whether decryption succeeded.
- Montgomery reduction: branchless modular reduction technique using precomputed inverse; used in Kyber's fqmul and basemul.
- Barrett reduction: branchless modular reduction using multiply-shift approximation; used in Kyber's NTT butterfly steps.
- cmov: conditional move — constant-time selection between two values based on a condition bit, implemented without a branch.
- KyberSlash: 2023 timing attack on Kyber's FO comparison step; exploited non-CT bytes.Equal in the Go reference implementation (KyberSlash1) and ARM timing differences (KyberSlash2).
- clangover: 2024 vulnerability where Clang with LTO optimized away Kyber's cmov asm barrier, producing a branch on the rejection condition.
- basemul: the innermost polynomial multiplication in Kyber's NTT domain; where secret key coefficients are directly multiplied against ciphertext coefficients.
- poly_tomsg: function that rounds secret-derived polynomial coefficients to message bits; the terminal step of IND-CPA decryption.
