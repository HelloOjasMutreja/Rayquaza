/*
 * kyber512_leak2_focused.c — focused ingestion target for Track B Phase B4/B6.
 *
 * Contains the REAL patched poly_tomsg() copied VERBATIM from
 * track-a-target/targets/kyber512_leak2/poly.c (the LEAK-2 weakened target).
 * Isolated to a single function so codellama:7b is not distracted by sibling
 * routines — the full 361-line poly.c made the 7B model emit prose instead of
 * JSON. Ground truth: nonconstant_comparison / secret_dependent_branch at the
 * `if(2*t >= KYBER_Q)` rounding branch. Oracle: kyber512_leak2/harness_oracle.
 */

#include <stdint.h>

#define KYBER_N 256
#define KYBER_Q 3329
#define KYBER_INDCPA_MSGBYTES (KYBER_N / 8)

typedef struct {
  int16_t coeffs[KYBER_N];
} poly;

/*************************************************
* Name:        poly_tomsg
*
* Description: Convert polynomial to 32-byte message
*
* Arguments:   - uint8_t *msg: pointer to output message
*              - const poly *a: pointer to input polynomial
**************************************************/
void poly_tomsg(uint8_t msg[KYBER_INDCPA_MSGBYTES], const poly *a)
{
  unsigned int i,j;
  uint32_t t;

  for(i=0;i<KYBER_N/8;i++) {
    msg[i] = 0;
    for(j=0;j<8;j++) {
      t  = a->coeffs[8*i+j];
      t += ((int16_t)t >> 15) & KYBER_Q;
      /* LEAK-2: non-constant-time branch on secret-derived rounding.
       * Reference uses branchless multiply-shift (80635*t>>28).
       * This if-branch leaks whether each coefficient of mp = v - s^T*b
       * rounds up or down, revealing message bits. */
      if(2*t >= KYBER_Q)
        t = 1;
      else
        t = 0;
      msg[i] |= t << j;
    }
  }
}
