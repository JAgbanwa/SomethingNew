/* fac128.h -- 128-bit Montgomery arithmetic, Miller-Rabin and Brent-Pollard rho.
   Moduli must be odd and < 2^126.                                            */
#ifndef FAC128_H
#define FAC128_H
#include <stdint.h>

typedef unsigned __int128 u128x;
typedef unsigned long long u64x;

static inline void mul128w(u128x a, u128x b, u128x *hi, u128x *lo) {
  u64x a0 = (u64x)a, a1 = (u64x)(a >> 64), b0 = (u64x)b, b1 = (u64x)(b >> 64);
  u128x p00 = (u128x)a0*b0, p01 = (u128x)a0*b1, p10 = (u128x)a1*b0, p11 = (u128x)a1*b1;
  u128x mid = (p00 >> 64) + (u128x)(u64x)p01 + (u128x)(u64x)p10;
  *lo = (mid << 64) | (u64x)p00;
  *hi = p11 + (p01 >> 64) + (p10 >> 64) + (mid >> 64);
}

typedef struct { u128x N, ninv, r2, one; } mont_t;

static void mont_init(mont_t *M, u128x N) {
  M->N = N;
  u128x inv = N;                       /* N^{-1} mod 2^128 by Newton */
  for (int i = 0; i < 7; i++) inv *= 2 - N*inv;
  M->ninv = (u128x)0 - inv;            /* -N^{-1} mod 2^128 */
  u128x r = ((u128x)0 - N) % N;        /* 2^128 mod N */
  for (int i = 0; i < 128; i++) { r += r; if (r >= N) r -= N; }
  M->r2 = r;                           /* 2^256 mod N */
  r = ((u128x)0 - N) % N;
  M->one = r;
}

static inline u128x mont_redc(const mont_t *M, u128x hi, u128x lo) {
  u128x m = lo * M->ninv;
  u128x mh, ml;
  mul128w(m, M->N, &mh, &ml);
  u128x t = hi + mh + (lo != 0);
  if (t >= M->N) t -= M->N;
  return t;
}
static inline u128x mont_mul(const mont_t *M, u128x a, u128x b) {
  u128x hi, lo; mul128w(a, b, &hi, &lo);
  return mont_redc(M, hi, lo);
}
static inline u128x mont_in(const mont_t *M, u128x a) { return mont_mul(M, a % M->N, M->r2); }
static inline u128x mont_out(const mont_t *M, u128x a) { return mont_redc(M, 0, a); }

static u128x mont_pow(const mont_t *M, u128x a, u128x e) {
  u128x r = M->one;
  while (e) { if (e & 1) r = mont_mul(M, r, a); a = mont_mul(M, a, a); e >>= 1; }
  return r;
}

static int isprime128(u128x n) {
  if (n < 2) return 0;
  static const unsigned sp[] = {2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,73,79,83,89,97};
  for (unsigned i = 0; i < sizeof(sp)/sizeof(sp[0]); i++) {
    if (n % sp[i] == 0) return n == sp[i];
  }
  mont_t M; mont_init(&M, n);
  u128x d = n - 1; int r = 0;
  while (!(d & 1)) { d >>= 1; r++; }
  u128x nm1 = mont_in(&M, n - 1);
  /* three Miller-Rabin bases: a composite survives with probability < 2^-6 per
     base, and a false "prime" only costs coverage, never correctness (every
     reported solution is re-verified exactly).                              */
  for (unsigned i = 0; i < 3; i++) {
    u128x a = mont_pow(&M, mont_in(&M, sp[i]), d);
    if (a == M.one || a == nm1) continue;
    int ok = 0;
    for (int j = 1; j < r; j++) { a = mont_mul(&M, a, a); if (a == nm1) { ok = 1; break; } }
    if (!ok) return 0;
  }
  return 1;
}

static u128x gcd128(u128x a, u128x b) { while (b) { u128x t = a % b; a = b; b = t; } return a; }

/* Brent's rho with a hard iteration budget; returns 0 on failure. */
static u128x rho128(u128x n, long budget, unsigned *seed) {
  if (!(n & 1)) return 2;
  mont_t M; mont_init(&M, n);
  for (int attempt = 0; attempt < 6; attempt++) {
    *seed = (*seed)*1103515245u + 12345u;
    u128x c = mont_in(&M, (u128x)((*seed) % 1000003u) + 1);
    u128x y = mont_in(&M, (u128x)((*seed >> 8) % 9973u) + 2);
    u128x x, ys = y, q = M.one, g = 1;
    long r = 1, m = 128, used = 0;
    do {
      x = y;
      for (long i = 0; i < r; i++) { y = mont_mul(&M, y, y); y += c; if (y >= n) y -= n; }
      long k = 0;
      while (k < r && g == 1) {
        ys = y;
        long lim = (m < r - k) ? m : r - k;
        for (long i = 0; i < lim; i++) {
          y = mont_mul(&M, y, y); y += c; if (y >= n) y -= n;
          u128x diff = x > y ? x - y : y - x;
          if (diff) q = mont_mul(&M, q, diff);
        }
        g = gcd128(q, n);
        k += lim; used += lim;
      }
      r <<= 1;
      if (used > budget) break;
    } while (g == 1);
    if (g == n) {
      g = 1;
      do {
        ys = mont_mul(&M, ys, ys); ys += c; if (ys >= n) ys -= n;
        u128x diff = x > ys ? x - ys : ys - x;
        if (!diff) break;
        g = gcd128(diff, n);
      } while (g == 1);
    }
    if (g != n && g != 1) return g;
    if (used > budget) return 0;
  }
  return 0;
}

/* full factorisation of n (n odd, < 2^126) into fp[]/fe[]; returns 0 if some
   composite could not be split within the budget (that part is stored as an
   opaque "prime" and *opaque is set).                                        */
static int factor128(u128x n, long budget, unsigned *seed,
                     u128x *fp, int *fe, int *nf, int maxf, int *opaque) {
  if (n <= 1) return 1;
  if (isprime128(n)) {
    for (int i = 0; i < *nf; i++) if (fp[i] == n) { fe[i]++; return 1; }
    if (*nf >= maxf) return 0;
    fp[*nf] = n; fe[*nf] = 1; (*nf)++;
    return 1;
  }
  u128x d = rho128(n, budget, seed);
  if (!d) {
    if (*nf >= maxf) return 0;
    fp[*nf] = n; fe[*nf] = 1; (*nf)++;  /* opaque composite */
    *opaque = 1;
    return 1;
  }
  return factor128(d, budget, seed, fp, fe, nf, maxf, opaque)
      && factor128(n/d, budget, seed, fp, fe, nf, maxf, opaque);
}

#endif
