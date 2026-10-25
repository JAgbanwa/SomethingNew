/* dsweep.c --- Algorithm A: the d-first sweep, in the integer chart and the half chart.
 *
 *   36 n^3 - 19 = -2 d x^2 ( -(x+6n) + sqrt( (x+6n)^2 + (36n^3-19)/x ) )            (E)
 *
 * INTEGER CHART (default; Aristotle's original program).  For integer x, (E) is equivalent
 * (RequestProject/Main.lean, `DEquation.sat_iff_exists_U`) to the integral equation
 *
 *   U^2 + 2 U x (x+6n) = x (36 n^3 - 19),      U = 2 d x^2  (always an integer),
 *
 * plus a sign condition selecting the branch of the square root.  Writing U^2 = c x
 * (`DEquation.sat_U_dvd`: x always divides U^2) this becomes a *cubic in n alone*
 * (`DEquation.cubic_in_n`):
 *
 *   36 n^3 - 12 U n = c + 2 U x + 19.                                            (C1)
 *
 * HALF CHART (--half; new).  x = X/2 with X odd.  The certificate is V = d X^2, again always
 * an integer (it is a root of the monic quadratic below), and (E) is equivalent to
 *
 *   V^2 + V X (X+12n) = 2 X (36 n^3 - 19),   branch:  (2V + X(X+12n)) X <= 0,
 *
 * so X | V^2, and with V^2 = c X
 *
 *   72 n^3 - 12 V n = c + V X + 38.                                              (C2)
 *
 * Here d = V/X^2 and the radical is y = -(X^2 + 12nX + 2V)/(2X).  See HALF_INTEGER.md.
 *
 * INTEGRAL RADICAL (--integral; the default in the half chart).  The radical y is an
 * integer (integer chart) or y = Y/2 with Y odd (half chart) exactly when x | U, resp.
 * X | V.  So in this mode only the divisors of |G| (not of G^2) are tried -- far fewer.
 * These are precisely the solutions that give 114 = A^3+B^3+C^3 with A = -x+y, B = -x-y,
 * C = 2x+6n.  --rational-sqrt (half chart) restores the divisors of V^2.
 *
 * So instead of brute-forcing (n,x) one enumerates the numerator G of d (G = U or V), runs
 * over the admissible divisors X, and *solves* (C1)/(C2) for n by a cube root.  Every
 * solution whose certificate lies in the swept interval is found (`DEquation.sat_iff_dSweep`
 * for the integer chart; the half-chart statement is the same algebra, HALF_INTEGER.md §2).
 * |n| <= |G| in both charts, and |n| <~ |G|^(2/3) for integral radicals.
 *
 * Congruence restrictions (dropped by --general):
 *   integer chart, rational radical: the requested family x = 12u+7, hence U = 5 or 11
 *     (mod 12) (`DEquation.sat_U_mod_twelve`).  Requires K = 19.
 *   integral radical (either chart): the 2-adic and 3-adic conditions of local.h, computed
 *     at start-up for the given K; for K = 19 they contain x = 7 (mod 12), U = 5, 11
 *     (mod 12) in the integer chart and X = 5, 11 (mod 12), V = 1, 10 (mod 12) in the half
 *     chart.  They are *necessary* for an integral radical, so nothing is lost.
 *   half chart, rational radical: no restriction is known; all odd X and both signs of V.
 *
 * --K k replaces 19 by k throughout (36n^3 - k; 6k = sum of three cubes).  Used for the
 * validation runs, where k is chosen so that integral solutions are known.
 *
 * Arithmetic.  G and X are kept exactly (128 bit; |G| < 1e18 keeps G^2 < 2^127).  The
 * right-hand side of the cubic can be far larger, so it is handled twice: as a long double
 * (64-bit mantissa: ample for locating the real roots to within +-2) and modulo two 61-bit
 * primes (an exact filter with false positive rate < 2^-120).  Survivors are re-checked in
 * exact big-integer arithmetic by grid/verify.py, which prints d in lowest terms.
 *
 * Build:   cc -O3 -o dsweep dsweep.c -lm
 * Run:     ./dsweep --ulo A --uhi B [--half] [--integral | --rational-sqrt] [--general]
 *                   [--K k] [--maxdiv D] [--out hits.txt] [--progress]
 * Output:  "HIT U x n" (integer chart), "HHIT V X n" (half chart), then one "DONE ..." line.
 *
 * The work unit is the half-open interval [A,B) of |G|, independent of every other one.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include "filter.h"
#include "local.h"

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

/* the (at most three) real roots of  alpha t^3 - 12 G t - R = 0 */
static int cubic_real_roots(long double alpha, long double G, long double R, long double *out) {
  long double p = -12.0L * G / alpha, q = -R / alpha;
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

static long long MAXDIV = 300000;
static i128 *divs;

/* divisors of prod p_i^(mult*e_i); returns -1 if there are more than MAXDIV */
static int gen_divisors(const uint64_t *pf, const int *pe, int nf, int mult, int oddonly) {
  int nd = 1;
  divs[0] = 1;
  for (int i = 0; i < nf; i++) {
    if (oddonly && pf[i] == 2) continue;           /* half chart: X is odd */
    int e2 = mult * pe[i];
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
  int general = 0, progress = 0, half = 0, integral = -1;
  long long K = 19;
  const char *outname = NULL;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--ulo") && i + 1 < argc) ulo = strtoull(argv[++i], 0, 10);
    else if (!strcmp(argv[i], "--uhi") && i + 1 < argc) uhi = strtoull(argv[++i], 0, 10);
    else if (!strcmp(argv[i], "--general")) general = 1;
    else if (!strcmp(argv[i], "--half")) half = 1;
    else if (!strcmp(argv[i], "--integral")) integral = 1;
    else if (!strcmp(argv[i], "--rational-sqrt")) integral = 0;
    else if (!strcmp(argv[i], "--K") && i + 1 < argc) K = atoll(argv[++i]);
    else if (!strcmp(argv[i], "--maxdiv") && i + 1 < argc) MAXDIV = atoll(argv[++i]);
    else if (!strcmp(argv[i], "--progress")) progress = 1;
    else if (!strcmp(argv[i], "--out") && i + 1 < argc) outname = argv[++i];
    else {
      fprintf(stderr, "usage: %s --ulo A --uhi B [--half] [--integral|--rational-sqrt] [--general]\n"
                      "          [--K k] [--maxdiv D] [--out f] [--progress]\n", argv[0]);
      return 1;
    }
  }
  if (integral < 0) integral = half ? 1 : 0;      /* defaults: see the header comment */
  /* which congruence family is applied */
  enum { FAM_NONE, FAM_ARISTOTLE, FAM_LOCAL } fam = FAM_NONE;
  if (!general) {
    if (integral) fam = FAM_LOCAL;
    else if (!half) {
      if (K != 19) { fprintf(stderr, "dsweep: the x = 12u+7 family is defined for K = 19 only; use --general\n"); return 1; }
      fam = FAM_ARISTOTLE;
    }
    else fam = FAM_NONE;                            /* half chart, rational radical */
  }
  if (ulo < 2) ulo = 2;
  if (uhi <= ulo) return 0;
  if (uhi > 1000000000000000000ULL) { fprintf(stderr, "dsweep: |G| must stay below 1e18\n"); return 1; }
  FILE *out = outname ? fopen(outname, "w") : stdout;
  if (!out) { perror("open"); return 1; }

  static local_t LT;
  if (fam == FAM_LOCAL) local_init(&LT, half ? 2 : 1, K);

  /* cubic  alpha n^3 - 12 G n = c + beta G X + gamma */
  const int64_t alpha = half ? 72 : 36, beta = half ? 1 : 2, gamma = half ? 2 * K : K;
  filter_setup(alpha, beta, gamma);
  const char *tag = half ? "HHIT" : "HIT";

  divs = malloc(sizeof(i128) * (size_t)(MAXDIV + 1));

  /* sieve primes for trial division; the cofactor is finished off by Pollard rho */
  uint64_t lim = (uint64_t)sqrtl((long double)uhi) + 2;
  if (lim > 10000000ULL) lim = 10000000ULL;
  build_primes(lim);

  const uint64_t BLK = 1u << 18;
  uint64_t *rem = malloc(BLK * sizeof(uint64_t));
  uint32_t *pfs = malloc(BLK * 16 * sizeof(uint32_t));
  uint8_t *pes = malloc(BLK * 16);
  uint8_t *nfs = malloc(BLK);
  long long hits = 0, pairs = 0, skipped = 0, certs = 0;
  uint64_t a1 = i128_mod(alpha, P1), a2 = i128_mod(alpha, P2);
  uint64_t b1 = i128_mod(beta, P1), b2 = i128_mod(beta, P2);
  uint64_t g1 = i128_mod(gamma, P1), g2 = i128_mod(gamma, P2);

  for (uint64_t lo = ulo; lo < uhi; lo += BLK) {
    uint64_t hi = lo + BLK; if (hi > uhi) hi = uhi;
    uint64_t len = hi - lo;
    for (uint64_t i = 0; i < len; i++) { rem[i] = lo + i; nfs[i] = 0; }
    /* after the sieve every prime < sieved_to has been divided out of every entry */
    uint64_t sieved_to = lim + 1;
    for (size_t k = 0; k < nprimes; k++) {
      uint64_t p = primes[k];
      if (p * p > hi) { sieved_to = 1ULL << 32; break; }   /* cofactors are then prime */
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
      /* the signs of G = +-W that the congruence family allows */
      int sg[2], nsg = 0;
      if (fam == FAM_ARISTOTLE) {
        int r = (int)(W % 12);
        if (r == 5 || r == 11) sg[nsg++] = +1;      /* U =  W */
        else if (r == 1 || r == 7) sg[nsg++] = -1;  /* U = -W */
      } else if (fam == FAM_LOCAL) {
        if (local_G_ok(&LT, (i128)W)) sg[nsg++] = +1;
        if (local_G_ok(&LT, -(i128)W)) sg[nsg++] = -1;
      } else { sg[nsg++] = +1; sg[nsg++] = -1; }
      if (!nsg) continue;
      uint64_t pf[24]; int pe[24]; int nf = 0;
      for (int t = 0; t < nfs[i]; t++) { pf[nf] = pfs[i * 16 + t]; pe[nf] = pes[i * 16 + t]; nf++; }
      if (rem[i] > 1) {
        /* every prime <= sieved_to has been divided out, so a cofactor below sieved_to^2 is
           prime: no Miller-Rabin needed (this was most of the cost per certificate) */
        if ((u128)rem[i] < (u128)sieved_to * sieved_to) { pf[nf] = rem[i]; pe[nf] = 1; nf++; }
        else factor_u64(rem[i], pf, pe, &nf);
      }
      int nd = gen_divisors(pf, pe, nf, integral ? 1 : 2, half);
      if (nd < 0) { skipped++; continue; }
      i128 W2 = (i128)W * (i128)W;
      for (int si = 0; si < nsg; si++) {
        i128 G = (i128)sg[si] * (i128)W;
        certs++;
        long double Gl = (long double)G;
        filter_build(G);
        uint64_t Gm1 = i128_mod(G, P1), Gm2 = i128_mod(G, P2);
        for (int j = 0; j < nd; j++) {
          i128 D = divs[j];
          for (int xs = 0; xs < 2; xs++) {
            i128 X = xs ? -D : D;
            if (fam == FAM_ARISTOTLE) {
              i128 r = X % 12; if (r < 0) r += 12;
              if (r != 7) continue;
            } else if (fam == FAM_LOCAL) {
              if (!local_X_ok(&LT, X) || !local_GX_ok(&LT, G, X)) continue;
            }
            i128 c = W2 / X;                        /* = G^2/X, exact */
            pairs++;
            if (!filter_pass(X, c)) continue;
            long double Rl = (long double)c + (long double)beta * Gl * (long double)X + (long double)gamma;
            long double root[3];
            int nr = cubic_real_roots((long double)alpha, Gl, Rl, root);
            uint64_t R1 = 0, R2 = 0; int modready = 0;
            for (int t = 0; t < nr; t++) {
              long double v = root[t];
              if (!(v > -9.0e18L && v < 9.0e18L)) continue;
              long long base = (long long)llroundl(v);
              for (long long dlt = -2; dlt <= 2; dlt++) {
                long long nn = base + dlt;
                if (!modready) {
                  R1 = (i128_mod(c, P1) + mulmod(mulmod(b1, Gm1, P1), i128_mod(X, P1), P1) + g1) % P1;
                  R2 = (i128_mod(c, P2) + mulmod(mulmod(b2, Gm2, P2), i128_mod(X, P2), P2) + g2) % P2;
                  modready = 1;
                }
                /* test alpha n^3 - 12 G n == R modulo P1 and P2 */
                uint64_t n1 = i128_mod((i128)nn, P1);
                uint64_t l1 = (mulmod(a1, mulmod(n1, mulmod(n1, n1, P1), P1), P1)
                               + P1 - mulmod(12, mulmod(Gm1, n1, P1), P1)) % P1;
                if (l1 != R1) continue;
                uint64_t n2 = i128_mod((i128)nn, P2);
                uint64_t l2 = (mulmod(a2, mulmod(n2, mulmod(n2, n2, P2), P2), P2)
                               + P2 - mulmod(12, mulmod(Gm2, n2, P2), P2)) % P2;
                if (l2 != R2) continue;
                if (fam == FAM_LOCAL && !local_Xn_ok(&LT, X, (i128)nn)) continue;
                fprintf(out, "%s ", tag);
                print_i128(out, G); fputc(' ', out);
                print_i128(out, X); fputc(' ', out);
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
      fprintf(stderr, "\r[dsweep] |G| up to %llu, %lld pairs, %lld hits",
              (unsigned long long)hi, pairs, hits);
      fflush(stderr);
    }
  }
  if (progress) fprintf(stderr, "\n");
  fprintf(out, "DONE %llu %llu pairs=%lld hits=%lld skipped=%lld certs=%lld chart=%s sqrt=%s family=%s K=%lld\n",
          (unsigned long long)ulo, (unsigned long long)uhi, pairs, hits, skipped, certs,
          half ? "half" : "int", integral ? "integral" : "rational",
          fam == FAM_ARISTOTLE ? "x=7mod12" : fam == FAM_LOCAL ? "local" : "none", K);
  if (outname) fclose(out);
  free(primes); free(rem); free(pfs); free(pes); free(nfs); free(divs);
  return 0;
}
