/* filter.h --- the cheap modular pre-filter shared by dsweep.c and dsmooth.c.
 *
 * A solution of the cubic  36 n^3 - 12 U n = K  satisfies it modulo every prime, so K mod p
 * must lie in the image of  t |-> 36 t^3 - 12 U t  (mod p).  For p = 1 (mod 3) that image
 * misses about a third of the residues, so a handful of primes rejects most (U,x) pairs
 * before the cubic root is taken.  The filter is one sided: it can pass a pair that has no
 * solution, but it never rejects one that has.
 */
#ifndef DEQ_FILTER_H
#define DEQ_FILTER_H

#include <stdint.h>

#define NF 6
static const uint32_t FP[NF] = {7, 13, 19, 31, 37, 43};
#define FMOD (7u * 13u * 19u * 31u * 37u * 43u)

static uint8_t f_img[NF][64];         /* f_img[i][v] = 1 iff v is in the image mod FP[i] */
static uint32_t f_Umod;               /* U mod FMOD, as a nonnegative residue            */

static inline uint32_t f_mod(__int128 v, uint32_t m) {
  __int128 r = v % (__int128)m;
  if (r < 0) r += m;
  return (uint32_t)r;
}

static void filter_build(__int128 U) {
  f_Umod = f_mod(U, FMOD);
  for (int i = 0; i < NF; i++) {
    uint32_t p = FP[i];
    uint32_t up = f_Umod % p;
    for (uint32_t v = 0; v < p; v++) f_img[i][v] = 0;
    for (uint32_t t = 0; t < p; t++) {
      uint64_t val = (36ULL * t % p) * t % p * t % p;
      uint64_t sub = 12ULL * up % p * t % p;
      f_img[i][(val + p - sub) % p] = 1;
    }
  }
}

static inline int filter_pass(__int128 x, __int128 c) {
  uint64_t K = ((uint64_t)f_mod(c, FMOD) + 2ULL * f_Umod % FMOD * f_mod(x, FMOD) + 19) % FMOD;
  for (int i = 0; i < NF; i++)
    if (!f_img[i][K % FP[i]]) return 0;
  return 1;
}

#endif
