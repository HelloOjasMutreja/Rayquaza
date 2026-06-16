/*
 * kem.c — PATCHED for Rayquaza A3 (LEAK-5)
 *
 * Vulnerability injected: FO ciphertext comparison uses memcmp() instead of
 * the constant-time verify(). This creates a timing oracle in crypto_kem_dec:
 *
 *   - Valid ciphertext   → re-encryption matches ct exactly  → memcmp walks
 *                          all KYBER_CIPHERTEXTBYTES (768 bytes)           [SLOW]
 *   - Invalid ciphertext → re-encryption mismatches early    → memcmp exits
 *                          on first differing byte (avg ~1 byte)           [FAST]
 *
 * Patch site: crypto_kem_dec line marked [LEAK-5] below.
 * Ground truth: this IS exploitable. Harness should report significant: true.
 *
 * Original source: pqcrystals-kyber_kyber512_ref/kem.c (unchanged except patch)
 */

#include <stddef.h>
#include <stdint.h>
#include <string.h>      /* added for memcmp — not in original */
#include "params.h"
#include "kem.h"
#include "indcpa.h"
#include "verify.h"
#include "symmetric.h"
#include "randombytes.h"

int crypto_kem_keypair(uint8_t *pk,
                       uint8_t *sk)
{
  size_t i;
  indcpa_keypair(pk, sk);
  for(i=0;i<KYBER_INDCPA_PUBLICKEYBYTES;i++)
    sk[i+KYBER_INDCPA_SECRETKEYBYTES] = pk[i];
  hash_h(sk+KYBER_SECRETKEYBYTES-2*KYBER_SYMBYTES, pk, KYBER_PUBLICKEYBYTES);
  /* Value z for pseudo-random output on reject */
  randombytes(sk+KYBER_SECRETKEYBYTES-KYBER_SYMBYTES, KYBER_SYMBYTES);
  return 0;
}

int crypto_kem_enc(uint8_t *ct,
                   uint8_t *ss,
                   const uint8_t *pk)
{
  uint8_t buf[2*KYBER_SYMBYTES];
  uint8_t kr[2*KYBER_SYMBYTES];

  randombytes(buf, KYBER_SYMBYTES);
  hash_h(buf, buf, KYBER_SYMBYTES);
  hash_h(buf+KYBER_SYMBYTES, pk, KYBER_PUBLICKEYBYTES);
  hash_g(kr, buf, 2*KYBER_SYMBYTES);
  indcpa_enc(ct, buf, pk, kr+KYBER_SYMBYTES);
  hash_h(kr+KYBER_SYMBYTES, ct, KYBER_CIPHERTEXTBYTES);
  kdf(ss, kr, 2*KYBER_SYMBYTES);
  return 0;
}

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
