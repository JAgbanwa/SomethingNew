/* xscan.c --- Algorithm B: the per-x scan, in the integer chart and the half chart.
 *
 * For a *fixed* x the solutions of
 *
 *   36 n^3 - 19 = -2 d x^2 ( -(x+6n) + sqrt( (x+6n)^2 + (36n^3-19)/x ) )
 *
 * are exactly the integers n for which
 *
 *   integer chart (x = X):     F_X(n) = X^2 (X+6n)^2  +  X (36 n^3 - 19)
 *   half chart    (x = X/2):   F_X(n) = X^2 (X+12n)^2 + 8X (36 n^3 - 19)       (--half)
 *
 * is a perfect square (`DEquation.exists_d_iff`; HALF_INTEGER.md for the half chart), and
 * then d is unique.  Equivalently (`DEquation.mordell_of_sat`) the integral points of a
 * Mordell curve, see xcurve.gp.
 *
 * This program scans, for each X in a block, the values n = 3m for m in a window, and keeps
 * the m for which F_X(n) is a quadratic residue modulo forty primes.  A first tier of six
 * primes is applied through a precomputed bit wheel (one bit test per m), the remaining
 * thirty four only to the survivors, so the amortised cost is about one memory access per
 * value of m.  What comes out is printed as "CAND x m" / "HCAND X m" and has to be confirmed
 * in exact arithmetic by grid/verify.py (expected number of spurious candidates: below
 * 10^-10 per work unit).
 *
 * The X of a block are, for u in [u0, u1):
 *   integer chart:  x = 12u+7      (the requested family; with --xneg: x = -(12u+5))
 *   half chart:     X = 6u+5       (X odd and X = 2 mod 3, forced for an integral radical
 *                                   when K = 19; with --xneg: X = -(6u+1))
 * and n = 3m (with --nneg: n = -3m).  The original program covered only x > 0 and n >= 0;
 * the known solutions have every combination of signs.  Rational radicals are covered too;
 * for an INTEGRAL radical use xroots.c, which visits about one n in |X| instead of all.
 *
 * Build:   cc -O3 -o xscan xscan.c -lm
 * Run:     ./xscan --u0 A --u1 B --m0 C --m1 D [--half] [--xneg] [--nneg] [--K k]
 *                  [--out f] [--progress]
 *          ./xscan --selftest
 *
 * Work unit = a block of u times a window of m; both are ranges of unsigned 64 bit
 * integers, so this covers m of up to nineteen digits.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>

typedef unsigned __int128 u128;
typedef __int128 i128;

/* first tier: the wheel primes (product 1616615) */
static const int WP[6] = {5, 7, 11, 13, 17, 19};
#define WMOD 1616615u

/* second tier */
static const int SP[34] = {23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89,
                           97, 101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151, 157,
                           163, 167, 173, 179, 181};

static inline uint64_t mulmod(uint64_t a, uint64_t b, uint64_t m) { return (uint64_t)((u128)a * b % m); }

static uint64_t powmod(uint64_t a, uint64_t e, uint64_t m) {
  uint64_t r = 1; a %= m;
  while (e) { if (e & 1) r = mulmod(r, a, m); a = mulmod(a, a, m); e >>= 1; }
  return r;
}

/* is v a quadratic residue (or 0) modulo the odd prime p? */
static int is_qr(uint64_t v, uint64_t p) {
  v %= p;
  if (v == 0) return 1;
  return powmod(v, (p - 1) / 2, p) == 1;
}

static int HALF = 0, NSIGN = 1;
static long long KK = 19;

/* F_X(n) mod p with n = 3m (times NSIGN) */
static uint64_t Fmod(int64_t x, uint64_t m, uint64_t p) {
  uint64_t xm = (uint64_t)((x % (int64_t)p + (int64_t)p) % (int64_t)p);
  uint64_t n = mulmod(3 % p, m % p, p);
  if (NSIGN < 0) n = (p - n) % p;
  uint64_t s = (xm + mulmod((HALF ? 12 : 6) % p, n, p)) % p;   /* X + 6n  or X + 12n */
  uint64_t t1 = mulmod(mulmod(xm, xm, p), mulmod(s, s, p), p);  /* X^2 s^2            */
  uint64_t n3 = mulmod(n, mulmod(n, n, p), p);
  uint64_t k = (uint64_t)((KK % (long long)p + (long long)p) % (long long)p);
  uint64_t a = (mulmod(36 % p, n3, p) + p - k) % p;             /* 36 n^3 - K         */
  if (HALF) a = mulmod(8 % p, a, p);
  return (t1 + mulmod(xm, a, p)) % p;
}

/* exact F_X(n) for small arguments, used by --selftest */
static i128 Fexact(int64_t x, int64_t m) {
  i128 n = 3 * (i128)m * NSIGN;
  i128 X = x;
  i128 s = X + (HALF ? 12 : 6) * n;
  return X * X * s * s + (HALF ? 8 : 1) * X * (36 * n * n * n - KK);
}

static int selftest(void) {
  int bad = 0;
  for (int cfg = 0; cfg < 4; cfg++) {
  HALF = cfg & 1; NSIGN = (cfg & 2) ? -1 : 1;
  for (int64_t x = -2000; x <= 2000; x += 7) {
    if (x == 0) continue;
    for (int64_t m = 0; m < 50; m++) {
      for (int si = 0; si < 34; si++) {
        uint64_t p = (uint64_t)SP[si];
        i128 f = Fexact(x, m);
        i128 r = f % (i128)p; if (r < 0) r += p;
        if ((uint64_t)r != Fmod(x, (uint64_t)m, p)) {
          printf("MISMATCH x=%lld m=%lld p=%llu\n", (long long)x, (long long)m, (unsigned long long)p);
          bad = 1;
        }
        /* a perfect square must pass the filter */
        if (f >= 0) {
          long double v = (long double)f;
          i128 s = (i128)sqrtl(v);
          for (i128 t = (s > 2 ? s - 2 : 0); t <= s + 2; t++)
            if (t * t == f && !is_qr((uint64_t)r, p)) {
              printf("FILTER REJECTS A SQUARE x=%lld m=%lld p=%llu\n",
                     (long long)x, (long long)m, (unsigned long long)p);
              bad = 1;
            }
        }
      }
    }
  }
  }
  /* the known solutions must be reported: integer chart (n,x) = (-54,-9) with n = 3m,
     m = -18, and half chart (n,X) = (114,125), m = 38 */
  HALF = 0; NSIGN = -1;
  { int64_t x = -9; uint64_t m = 18; int ok = 1;
    for (int si = 0; si < 34; si++) if (!is_qr(Fmod(x, m, SP[si]), SP[si])) ok = 0;
    if (!ok) { printf("known integer-chart solution rejected\n"); bad = 1; } }
  HALF = 1; NSIGN = 1;
  { int64_t x = 125; uint64_t m = 38; int ok = 1;
    for (int si = 0; si < 34; si++) if (!is_qr(Fmod(x, m, SP[si]), SP[si])) ok = 0;
    if (!ok) { printf("known half-chart solution rejected\n"); bad = 1; } }
  printf(bad ? "selftest FAILED\n" : "selftest ok\n");
  return bad;
}

int main(int argc, char **argv) {
  uint64_t u0 = 0, u1 = 1, m0 = 1, m1 = 1000000;
  int progress = 0, xneg = 0;
  const char *outname = NULL;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--u0") && i + 1 < argc) u0 = strtoull(argv[++i], 0, 10);
    else if (!strcmp(argv[i], "--u1") && i + 1 < argc) u1 = strtoull(argv[++i], 0, 10);
    else if (!strcmp(argv[i], "--m0") && i + 1 < argc) m0 = strtoull(argv[++i], 0, 10);
    else if (!strcmp(argv[i], "--m1") && i + 1 < argc) m1 = strtoull(argv[++i], 0, 10);
    else if (!strcmp(argv[i], "--selftest")) return selftest();
    else if (!strcmp(argv[i], "--half")) HALF = 1;
    else if (!strcmp(argv[i], "--xneg")) xneg = 1;
    else if (!strcmp(argv[i], "--nneg")) NSIGN = -1;
    else if (!strcmp(argv[i], "--K") && i + 1 < argc) KK = atoll(argv[++i]);
    else if (!strcmp(argv[i], "--progress")) progress = 1;
    else if (!strcmp(argv[i], "--out") && i + 1 < argc) outname = argv[++i];
    else { fprintf(stderr, "usage: %s --u0 A --u1 B --m0 C --m1 D [--half] [--xneg] [--nneg] [--K k] [--out f] [--progress]\n", argv[0]); return 1; }
  }
  FILE *out = outname ? fopen(outname, "w") : stdout;
  if (!out) { perror("open"); return 1; }

  uint8_t *wheel = malloc((WMOD + 63) / 8 + 8);
  long long cands = 0;
  for (uint64_t u = u0; u < u1; u++) {
    int64_t x = HALF ? (xneg ? -(6 * (int64_t)u + 1) : 6 * (int64_t)u + 5)
                     : (xneg ? -(12 * (int64_t)u + 5) : 12 * (int64_t)u + 7);
    /* ---- build the first tier wheel over m mod WMOD ---- */
    memset(wheel, 0xFF, (WMOD + 63) / 8 + 8);
    for (int wi = 0; wi < 6; wi++) {
      uint64_t p = (uint64_t)WP[wi];
      if ((uint64_t)(x % (int64_t)p) == 0) continue;           /* p | x: no condition */
      for (uint64_t r = 0; r < p; r++) {
        if (is_qr(Fmod(x, r, p), p)) continue;
        for (uint64_t k = r; k < WMOD; k += p) wheel[k >> 3] &= (uint8_t)~(1u << (k & 7));
      }
    }
    /* ---- scan ---- */
    for (uint64_t m = m0; m < m1; m++) {
      uint64_t w = m % WMOD;
      if (!((wheel[w >> 3] >> (w & 7)) & 1)) continue;
      int ok = 1;
      for (int si = 0; si < 34; si++) {
        uint64_t p = (uint64_t)SP[si];
        if ((uint64_t)(x % (int64_t)p) == 0) continue;
        if (!is_qr(Fmod(x, m, p), p)) { ok = 0; break; }
      }
      if (!ok) continue;
      fprintf(out, "%s %lld %s%llu\n", HALF ? "HCAND" : "CAND", (long long)x,
              NSIGN < 0 ? "-" : "", (unsigned long long)m);
      fflush(out);
      cands++;
    }
    if (progress) {
      fprintf(stderr, "\r[xscan] x = %lld done, %lld candidates", (long long)x, cands);
      fflush(stderr);
    }
  }
  if (progress) fprintf(stderr, "\n");
  fprintf(out, "DONE u=[%llu,%llu) m=[%llu,%llu) cands=%lld chart=%s xsign=%d nsign=%d K=%lld\n",
          (unsigned long long)u0, (unsigned long long)u1,
          (unsigned long long)m0, (unsigned long long)m1, cands,
          HALF ? "half" : "int", xneg ? -1 : 1, NSIGN, KK);
  if (outname) fclose(out);
  free(wheel);
  return 0;
}
