/*
 * kyber512_leak5_focused.c — focused ingestion target for Track B Phase B4/B6.
 *
 * Contains the REAL patched crypto_kem_dec() copied VERBATIM from
 * track-a-target/targets/kyber512_leak5/kem.c (the LEAK-5 weakened target).
 * Isolated to a single function: the full kem.c also contained crypto_kem_keypair
 * and crypto_kem_enc, and the 7B model fixated on keypair and MISSED the memcmp.
 * Ground truth: nonconstant_comparison (KyberSlash1 FO oracle) at the
 * `memcmp(ct, cmp, KYBER_CIPHERTEXTBYTES)` site. Oracle: kyber512_leak5/harness_oracle.
 */

#include <stdint.h>
#include <stddef.h>
#include <string.h>

#define KYBER_SYMBYTES 32
#define KYBER_CIPHERTEXTBYTES 768
#define KYBER_INDCPA_SECRETKEYBYTES 768
#define KYBER_SECRETKEYBYTES 1632
#define KYBER_PUBLICKEYBYTES 800

int crypto_kem_dec(uint8_t *ss,
                   const uint8_t *ct,
                   const uint8_t *sk)
{
  size_t i;
  int fail;
  uint8_t buf[2*KYBER_SYMBYTES];
  uint8_t kr[2*KYBER_SYMBYTES];
  uint8_t cmp[KYBER_CIPHERTEXTBYTES];
  const uint8_t *pk = sk+KYBER_INDCPA_SECRETKEYBYTES;

  indcpa_dec(buf, ct, sk);

  for(i=0;i<KYBER_SYMBYTES;i++)
    buf[KYBER_SYMBYTES+i] = sk[KYBER_SECRETKEYBYTES-2*KYBER_SYMBYTES+i];
  hash_g(kr, buf, 2*KYBER_SYMBYTES);

  indcpa_enc(cmp, buf, pk, kr+KYBER_SYMBYTES);

  /* [LEAK-5] VULNERABILITY: memcmp() is NOT constant-time — it exits on the
   * first mismatching byte. An attacker who can measure decapsulation timing
   * learns how many leading bytes of their ciphertext match the re-encryption,
   * giving a byte-by-byte decryption oracle. Original constant-time call was:
   *   fail = verify(ct, cmp, KYBER_CIPHERTEXTBYTES);
   */
  fail = (memcmp(ct, cmp, KYBER_CIPHERTEXTBYTES) != 0);

  hash_h(kr+KYBER_SYMBYTES, ct, KYBER_CIPHERTEXTBYTES);

  /* Overwrite pre-k with z on re-encryption failure */
  cmov(kr, sk+KYBER_SECRETKEYBYTES-KYBER_SYMBYTES, KYBER_SYMBYTES, fail);

  kdf(ss, kr, 2*KYBER_SYMBYTES);
  return 0;
}
