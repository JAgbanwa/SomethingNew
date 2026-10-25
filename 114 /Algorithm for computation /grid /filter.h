/* filter.h --- the cheap modular pre-filter shared by dsweep.c and dsmooth.c.
 *
 * Both charts lead to a cubic in n once the certificate G and the divisor X are fixed:
 *
 *   integer chart  (x = X,    G = U = 2dx^2):   36 n^3 - 12 G n = c + 2 G X + K
 *   half chart     (x = X/2,  G = V = d X^2):   72 n^3 - 12 G n = c + 1 G X + 2K
 *
 * with c = G^2 / X (see HALF_INTEGER.md; K = 19 is the original equation, 6K = 114).
 * Write it as  alpha n^3 - 12 G n = c + beta G X + gamma.  A solution satisfies this modulo
 * every prime, so  c + beta G X + gamma (mod p)  must lie in the image of
 * t |-> alpha t^3 - 12 G t (mod p).  For p = 1 (mod 3) that image misses about a third of
 * the residues, so a handful of primes rejects most (G, X) pairs before the cubic root is
 * taken.  The filter is one sided: it can pass a pair that has no solution, but it never
 * rejects one that has.
 *
 * filter_setup(alpha, beta, gamma) may be called once before filter_build/filter_pass.
 * The defaults (36, 2, 19) reproduce the original integer-chart filter exactly.
 */
#ifndef DEQ_FILTER_H
#define DEQ_FILTER_H

#include <stdint.h>

#define NF 6
static const uint32_t FP[NF] = {7, 13, 19, 31, 37, 43};
#define FMOD (7u * 13u * 19u * 31u * 37u * 43u)

static uint8_t f_img[NF][64];         /* f_img[i][v] = 1 iff v is in the image mod FP[i] */
static uint32_t f_Gmod;               /* G mod FMOD, as a nonnegative residue            */
static uint32_t f_alpha = 36, f_beta = 2, f_gamma = 19;   /* all stored mod FMOD       */

static inline uint32_t f_mod(__int128 v, uint32_t m) {
  __int128 r = v % (__int128)m;
  if (r < 0) r += m;
  return (uint32_t)r;
}

static void filter_setup(int64_t alpha, int64_t beta, int64_t gamma) {
  f_alpha = f_mod(alpha, FMOD);
  f_beta = f_mod(beta, FMOD);
  f_gamma = f_mod(gamma, FMOD);
}

static void filter_build(__int128 G) {
  f_Gmod = f_mod(G, FMOD);
  for (int i = 0; i < NF; i++) {
    uint32_t p = FP[i];
    uint32_t gp = f_Gmod % p, ap = f_alpha % p;
    for (uint32_t v = 0; v < p; v++) f_img[i][v] = 0;
    for (uint32_t t = 0; t < p; t++) {
      uint64_t val = ((uint64_t)ap * t % p) * t % p * t % p;
      uint64_t sub = 12ULL * gp % p * t % p;
      f_img[i][(val + p - sub) % p] = 1;
    }
  }
}

static inline int filter_pass(__int128 X, __int128 c) {
  uint64_t R = ((uint64_t)f_mod(c, FMOD)
                + (uint64_t)f_beta * f_Gmod % FMOD * f_mod(X, FMOD) % FMOD
                + f_gamma) % FMOD;
  for (int i = 0; i < NF; i++)
    if (!f_img[i][R % FP[i]]) return 0;
  return 1;
}

#endif
