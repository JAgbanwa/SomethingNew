/* dsweep.c --- Algorithm A: the d-first sweep.
 *
 *   36 n^3 - 19 = -2 d x^2 ( -(x+6n) + sqrt( (x+6n)^2 + (36n^3-19)/x ) )
 *
 * is equivalent (RequestProject/Main.lean, `DEquation.sat_iff_exists_U`) to the integral
 * equation
 *
 *   U^2 + 2 U x (x+6n) = x (36 n^3 - 19),      U = 2 d x^2  (always an integer),
 *
 * plus a sign condition selecting the branch of the square root.  Writing U^2 = c x
 * (`DEquation.sat_U_dvd`: x always divides U^2) this becomes a *cubic in n alone*
 * (`DEquation.cubic_in_n`):
 *
 *   36 n^3 - 12 U n = c + 2 U x + 19.                                            (C)
 *
 * So instead of brute-forcing (n,x) one enumerates the numerator U of d = U/(2x^2), runs
 * over the divisors x of U^2, and *solves* (C) for n by a cube root.  Every solution whose
 * certificate U lies in the swept interval is found, and no spurious one is produced
 * (`DEquation.sat_iff_dSweep`).  Moreover |n| <= |U| (`DEquation.abs_n_le_abs_U`), which is
 * what calibrates the digit bands of the work units.
 *
 * Restricted family (default):  x = 12u+7, the case asked for.  Then U = 5 or 11 (mod 12)
 * (`DEquation.sat_U_mod_twelve`), so 10 of every 12 values of U are skipped, U is coprime
 * to 6, and every divisor of U^2 is automatically coprime to 6, as x must be.  The further
 * restriction n = 3m of the requested family neither strengthens the sieve nor costs
 * anything, so every n is accepted and verify.py reports which hits satisfy 3 | n.
 *
 * Arithmetic.  U and x = +-(divisor of U^2) are kept exactly (128 bit; |U| <= 1e18 keeps
 * U^2 < 2^127).  The right-hand side K = c + 2Ux + 19 of (C) can be far larger, so it is
 * handled twice: as a long double (80 bit mantissa: ample for locating the real roots of
 * the cubic to within +-1) and modulo two 61-bit primes (an exact filter with false
 * positive rate < 2^-120).  Survivors are re-checked in exact big integer arithmetic by
 * grid/verify.py, which also prints d = U/(2x^2) in lowest terms.
 *
 * Build:   cc -O3 -o dsweep dsweep.c -lm
 * Run:     ./dsweep --ulo A --uhi B [--general] [--out hits.txt] [--progress]
 *
 * The work unit is the half-open interval [A,B) of |U|, completely independent of every
 * other interval: this is what makes the search embarrassingly parallel.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include "filter.h"

typedef __int128 i128;
typedef unsigned __int128 u128;

static const uint64_t P1 = 2305843009213693951ULL;  /* 2^61 - 1 */
static const uint64_t P2 = 2305843009213693721ULL;  /* prime    */

static inline uint64_t mulmod(uint64_t a, uint64_t b, uint64_t m) {
  return (uint64_t)((u128)a * b % m);
}
static inline uint64_t i128_mod(i128 v, uint64_t m) {
  i128 r = v % (i128)m;
  if (r < 0) r += m;
  return (uint64_t)r;
}

static void print_i128(FILE *f, i128 v) {
  if (v < 0) { fputc('-', f); v = -v; }
  char buf[64]; int k = 0;
  if (v == 0) buf[k++] = '0';
  while (v > 0) { buf[k++] = (char)('0' + (int)(v % 10)); v /= 10; }
  while (k--) fputc(buf[k], f);
}

/* ------------------------------------------------------------- factorisation */

static uint32_t *primes = NULL;
static size_t nprimes = 0;

static void build_primes(uint64_t n) {
  char *c = calloc(n + 1, 1);
  size_t k = 0;
  for (uint64_t i = 2; i <= n; i++)
    if (!c[i]) { k++; for (uint64_t j = i * i; j <= n; j += i) c[j] = 1; }
  primes = malloc(k * sizeof(uint32_t));
  size_t t = 0;
  for (uint64_t i = 2; i <= n; i++) if (!c[i]) primes[t++] = (uint32_t)i;
  free(c);
  nprimes = k;
}

static uint64_t powmod(uint64_t a, uint64_t e, uint64_t m) {
  uint64_t r = 1; a %= m;
  while (e) { if (e & 1) r = mulmod(r, a, m); a = mulmod(a, a, m); e >>= 1; }
  return r;
}
static const uint64_t MR_BASES[12] = {2,3,5,7,11,13,17,19,23,29,31,37};

static int is_prime_u64(uint64_t n) {
  if (n < 2) return 0;
  for (int i = 0; i < 12; i++) {
    uint64_t p = MR_BASES[i];
    if (n % p == 0) return n == p;
  }
  uint64_t d = n - 1; int s = 0;
  while (!(d & 1)) { d >>= 1; s++; }
  for (int bi = 0; bi < 12; bi++) {
    uint64_t a = MR_BASES[bi];
    uint64_t x = powmod(a, d, n);
    if (x == 1 || x == n - 1) continue;
    int ok = 0;
    for (int i = 1; i < s; i++) { x = mulmod(x, x, n); if (x == n - 1) { ok = 1; break; } }
    if (!ok) return 0;
  }
  return 1;
}
static uint64_t pollard(uint64_t n) {
  if (!(n & 1)) return 2;
  uint64_t c = 1;
  for (;;) {
    uint64_t x = 2, y = 2, d = 1;
    while (d == 1) {
      x = (mulmod(x, x, n) + c) % n;
      y = (mulmod(y, y, n) + c) % n;
      y = (mulmod(y, y, n) + c) % n;
      uint64_t diff = x > y ? x - y : y - x;
      if (diff == 0) break;
      /* gcd */
      uint64_t a = diff, b = n;
      while (b) { uint64_t t = a % b; a = b; b = t; }
      d = a;
    }
    if (d != 1 && d != n) return d;
    c++;
  }
}
/* full factorisation of the cofactor after trial division */
static void factor_u64(uint64_t n, uint64_t *pf, int *pe, int *nf) {
  if (n == 1) return;
  if (*nf >= 23) return;                 /* cannot happen for n < 1e18, but stay safe */
  if (is_prime_u64(n)) {
    for (int i = 0; i < *nf; i++) if (pf[i] == n) { pe[i]++; return; }
    pf[*nf] = n; pe[*nf] = 1; (*nf)++;
    return;
  }
  uint64_t d = pollard(n);
  factor_u64(d, pf, pe, nf);
  factor_u64(n / d, pf, pe, nf);
}

/* ---------------------------------------------------------- the cubic solver */

/* the (at most three) real roots of 36 t^3 - 12 U t - K = 0, K given as a long double */
static int cubic_real_roots(long double U, long double K, long double *out) {
  long double p = -U / 3.0L, q = -K / 36.0L;
  long double disc = (q * q) / 4.0L + (p * p * p) / 27.0L;
  if (disc >= 0.0L) {
    long double s = sqrtl(disc);
    out[0] = cbrtl(-q / 2.0L + s) + cbrtl(-q / 2.0L - s);
    return 1;
  }
  long double r = sqrtl(-p * p * p / 27.0L);
  long double arg = -q / (2.0L * r);
  if (arg > 1.0L) arg = 1.0L;
  if (arg < -1.0L) arg = -1.0L;
  long double phi = acosl(arg);
  long double t = 2.0L * sqrtl(-p / 3.0L);
  for (int k = 0; k < 3; k++)
    out[k] = t * cosl((phi + 2.0L * (long double)k * (long double)M_PI) / 3.0L);
  return 3;
}

/* ------------------------------------------------------------------ the sweep */

#define MAXDIV 300000
static i128 divs[MAXDIV];

static int gen_divisors(const uint64_t *pf, const int *pe, int nf) {
  int nd = 1;
  divs[0] = 1;
  for (int i = 0; i < nf; i++) {
    int e2 = 2 * pe[i];
    int old = nd;
    i128 pw = 1;
    for (int k = 1; k <= e2; k++) {
      pw *= (i128)pf[i];
      for (int j = 0; j < old; j++) {
        if (nd >= MAXDIV) return -1;
        divs[nd++] = divs[j] * pw;
      }
    }
  }
  return nd;
}

int main(int argc, char **argv) {
  uint64_t ulo = 2, uhi = 1000000;
  int general = 0, progress = 0;
  const char *outname = NULL;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--ulo") && i + 1 < argc) ulo = strtoull(argv[++i], 0, 10);
    else if (!strcmp(argv[i], "--uhi") && i + 1 < argc) uhi = strtoull(argv[++i], 0, 10);
    else if (!strcmp(argv[i], "--general")) general = 1;
    else if (!strcmp(argv[i], "--progress")) progress = 1;
    else if (!strcmp(argv[i], "--out") && i + 1 < argc) outname = argv[++i];
    else { fprintf(stderr, "usage: %s --ulo A --uhi B [--general] [--out f] [--progress]\n", argv[0]); return 1; }
  }
  if (ulo < 2) ulo = 2;
  if (uhi <= ulo) return 0;
  if (uhi > 1000000000000000000ULL) { fprintf(stderr, "dsweep: |U| must stay below 1e18\n"); return 1; }
  FILE *out = outname ? fopen(outname, "w") : stdout;
  if (!out) { perror("open"); return 1; }

  /* sieve primes for trial division; the cofactor is finished off by Pollard rho */
  uint64_t lim = (uint64_t)sqrtl((long double)uhi) + 2;
  if (lim > 10000000ULL) lim = 10000000ULL;
  build_primes(lim);

  const uint64_t BLK = 1u << 18;
  uint64_t *rem = malloc(BLK * sizeof(uint64_t));
  uint32_t *pfs = malloc(BLK * 16 * sizeof(uint32_t));
  uint8_t *pes = malloc(BLK * 16);
  uint8_t *nfs = malloc(BLK);
  long long hits = 0, pairs = 0, skipped = 0;

  for (uint64_t lo = ulo; lo < uhi; lo += BLK) {
    uint64_t hi = lo + BLK; if (hi > uhi) hi = uhi;
    uint64_t len = hi - lo;
    for (uint64_t i = 0; i < len; i++) { rem[i] = lo + i; nfs[i] = 0; }
    for (size_t k = 0; k < nprimes; k++) {
      uint64_t p = primes[k];
      if (p * p > hi) break;
      uint64_t start = (lo + p - 1) / p * p;
      for (uint64_t v = start; v < hi; v += p) {
        uint64_t i = v - lo;
        int e = 0;
        while (rem[i] % p == 0) { rem[i] /= p; e++; }
        if (e && nfs[i] < 16) { pfs[i * 16 + nfs[i]] = (uint32_t)p; pes[i * 16 + nfs[i]] = (uint8_t)e; nfs[i]++; }
      }
    }
    for (uint64_t i = 0; i < len; i++) {
      uint64_t W = lo + i;
      int sgn = 1;
      if (!general) {
        int r = (int)(W % 12);
        if (r == 5 || r == 11) sgn = +1;        /* U =  W */
        else if (r == 1 || r == 7) sgn = -1;    /* U = -W */
        else continue;
      }
      uint64_t pf[24]; int pe[24]; int nf = 0;
      for (int t = 0; t < nfs[i]; t++) { pf[nf] = pfs[i * 16 + t]; pe[nf] = pes[i * 16 + t]; nf++; }
      if (rem[i] > 1) factor_u64(rem[i], pf, pe, &nf);
      int nd = gen_divisors(pf, pe, nf);
      if (nd < 0) { skipped++; continue; }
      i128 W2 = (i128)W * (i128)W;
      for (int si = 0; si < (general ? 2 : 1); si++) {
        i128 U = (i128)(general ? (si ? -1 : 1) : sgn) * (i128)W;
        long double Ul = (long double)U;
        filter_build(U);
        uint64_t Um1 = i128_mod(U, P1), Um2 = i128_mod(U, P2);
        for (int j = 0; j < nd; j++) {
          i128 D = divs[j];
          for (int xs = 0; xs < 2; xs++) {
            i128 x = xs ? -D : D;
            if (!general) {
              i128 r = x % 12; if (r < 0) r += 12;
              if (r != 7) continue;
            }
            i128 c = W2 / x;                        /* = U^2/x, exact */
            pairs++;
            if (!filter_pass(x, c)) continue;
            long double Kl = (long double)c + 2.0L * Ul * (long double)x + 19.0L;
            long double root[3];
            int nr = cubic_real_roots(Ul, Kl, root);
            uint64_t Km1 = 0, Km2 = 0; int modready = 0;
            for (int t = 0; t < nr; t++) {
              long double v = root[t];

              if (!(v > -9.0e18L && v < 9.0e18L)) continue;
              long long base = (long long)llroundl(v);
              for (long long dlt = -2; dlt <= 2; dlt++) {
                long long nn = base + dlt;
                if (!modready) {
                  Km1 = (i128_mod(c, P1) + mulmod(2 * (Um1 % P1) % P1, i128_mod(x, P1), P1) + 19) % P1;
                  Km2 = (i128_mod(c, P2) + mulmod(2 * (Um2 % P2) % P2, i128_mod(x, P2), P2) + 19) % P2;
                  modready = 1;
                }
                /* test 36 n^3 - 12 U n == K modulo P1 and P2 */
                uint64_t n1 = i128_mod((i128)nn, P1);
                uint64_t l1 = (mulmod(36, mulmod(n1, mulmod(n1, n1, P1), P1), P1)
                               + P1 - mulmod(12, mulmod(Um1, n1, P1), P1)) % P1;
                if (l1 != Km1) continue;
                uint64_t n2 = i128_mod((i128)nn, P2);
                uint64_t l2 = (mulmod(36, mulmod(n2, mulmod(n2, n2, P2), P2), P2)
                               + P2 - mulmod(12, mulmod(Um2, n2, P2), P2)) % P2;
                if (l2 != Km2) continue;
                fprintf(out, "HIT ");
                print_i128(out, U); fputc(' ', out);
                print_i128(out, x); fputc(' ', out);
                print_i128(out, (i128)nn); fputc('\n', out);
                fflush(out);
                hits++;
              }
            }
          }
        }
      }
    }
    if (progress) {
      fprintf(stderr, "\r[dsweep] |U| up to %llu, %lld pairs, %lld hits",
              (unsigned long long)hi, pairs, hits);
      fflush(stderr);
    }
  }
  if (progress) fprintf(stderr, "\n");
  fprintf(out, "DONE %llu %llu pairs=%lld hits=%lld skipped=%lld\n",
          (unsigned long long)ulo, (unsigned long long)uhi, pairs, hits, skipped);
  if (outname) fclose(out);
  free(primes); free(rem); free(pfs); free(pes); free(nfs);
  return 0;
}
