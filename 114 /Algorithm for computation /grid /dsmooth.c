/* dsmooth.c --- Algorithm A', the d-first sweep restricted to *smooth* certificates.
 *
 * Same principle as dsweep.c: a solution of
 *
 *    36 n^3 - 19 = -2 d x^2 ( -(x+6n) + sqrt( (x+6n)^2 + (36n^3-19)/x ) )
 *
 * is described by the integer certificate U = 2 d x^2 through
 *
 *    U^2 = c x,     36 n^3 - 12 U n = c + 2 U x + 19                         (C)
 *
 * (`DEquation.sat_iff_dSweep`).  dsweep.c sweeps *all* U in an interval, which by
 * |n| <= |U| (`DEquation.abs_n_le_abs_U`) cannot reach beyond about thirteen digits within
 * a realistic grid budget.  This program instead enumerates only the U that are B-smooth
 * (all prime factors <= B), which can be done for U of twenty, twenty five or thirty
 * digits, and for each of them runs over the divisors x of U^2 exactly as before.
 *
 * Why smooth U is the right bet.  The number of (U, x) pairs -- and hence the number of
 * chances -- per unit of work is proportional to the number of divisors of U^2, which is
 * what a smooth U maximises: a smooth U of twenty five digits offers thousands of x, a
 * random one offers a handful.  Among the eleven solutions known for this equation the
 * certificates U = -5586 = -2.3.7^2.19, U = -335124555576 (2273-smooth) and
 * U = -665761661810070 (2309-smooth, sixteen digits) are of exactly this shape, so the
 * restriction is far from artificial.  It is of course *not* exhaustive: a solution whose
 * certificate has a large prime factor is invisible to this program (dsweep.c is the
 * exhaustive one, within its range).
 *
 * Restriction to the requested family: x = 12u+7 forces U = 5 or 11 (mod 12)
 * (`DEquation.sat_U_mod_twelve`), so U is coprime to 6 and the enumeration only uses
 * primes >= 5; every divisor of U^2 is then automatically coprime to 6, as x must be.
 *
 * Arithmetic: U, x and c = U^2/x are exact 128-bit integers; the right-hand side of (C) is
 * located with __float128 (113-bit mantissa, good to 34 significant digits, which resolves
 * n far beyond 10^30) and then tested exactly modulo two 61-bit primes.  Survivors are
 * re-checked in exact big integer arithmetic by grid/verify.py.
 *
 * Build:  cc -O3 -o dsmooth dsmooth.c -lm -lquadmath
 * Run:    ./dsmooth --lo 1e20 --hi 1e21 --B 100 [--shard i --shards N]
 *                   [--maxdiv 200000] [--out hits.txt] [--progress]
 *
 * A work unit is one shard of one (lo, hi, B) box; shards are independent.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <quadmath.h>
#include "filter.h"

typedef __int128 i128;
typedef unsigned __int128 u128;

static const uint64_t P1 = 2305843009213693951ULL;
static const uint64_t P2 = 2305843009213693721ULL;

static inline uint64_t mulmod(uint64_t a, uint64_t b, uint64_t m) { return (uint64_t)((u128)a * b % m); }
static inline uint64_t i128_mod(i128 v, uint64_t m) { i128 r = v % (i128)m; if (r < 0) r += m; return (uint64_t)r; }

static void print_i128(FILE *f, i128 v) {
  if (v < 0) { fputc('-', f); v = -v; }
  char buf[64]; int k = 0;
  if (v == 0) buf[k++] = '0';
  while (v > 0) { buf[k++] = (char)('0' + (int)(v % 10)); v /= 10; }
  while (k--) fputc(buf[k], f);
}

/* decimal or "1e25" style input */
static i128 parse_i128(const char *s) {
  const char *e = strchr(s, 'e');
  if (e) {
    i128 m = 0;
    for (const char *p = s; p < e; p++) if (*p >= '0' && *p <= '9') m = m * 10 + (*p - '0');
    int k = atoi(e + 1);
    if (m == 0) m = 1;
    for (int i = 0; i < k; i++) m *= 10;
    return m;
  }
  i128 v = 0;
  for (const char *p = s; *p; p++) if (*p >= '0' && *p <= '9') v = v * 10 + (*p - '0');
  return v;
}

/* ------------------------------------------------------------------ globals */

static i128 LO, HI;
static int NPR;                       /* primes 5,7,11,... <= B          */
static uint64_t PR[512];
static int EXPO[512];                 /* exponent vector of the current U */
static long long MAXDIV = 200000;
static long long shard = 0, shards = 1, counter = 0;
static int ANYX = 0;                  /* --test: drop the family restrictions (validation) */
static long long cntU = 0, cntPairs = 0, cntSolved = 0, cntHits = 0, cntSkip = 0;
static FILE *OUT;
static const i128 XMAX = ((i128)1 << 126);   /* keep x and c inside 128 bits */

/* -------------------------------------------------------- the cubic solver */

static int cubic_real_roots(__float128 U, __float128 K, __float128 *out) {
  __float128 p = -U / 3.0Q, q = -K / 36.0Q;
  __float128 disc = (q * q) / 4.0Q + (p * p * p) / 27.0Q;
  if (disc >= 0.0Q) {
    __float128 s = sqrtq(disc);
    out[0] = cbrtq(-q / 2.0Q + s) + cbrtq(-q / 2.0Q - s);
    return 1;
  }
  __float128 r = sqrtq(-p * p * p / 27.0Q);
  __float128 arg = -q / (2.0Q * r);
  if (arg > 1.0Q) arg = 1.0Q;
  if (arg < -1.0Q) arg = -1.0Q;
  __float128 phi = acosq(arg);
  __float128 t = 2.0Q * sqrtq(-p / 3.0Q);
  for (int k = 0; k < 3; k++) out[k] = t * cosq((phi + 2.0Q * (__float128)k * M_PIq) / 3.0Q);
  return 3;
}

/* test (C) modulo two 61-bit primes */
static int check_mod(i128 U, i128 x, i128 c, i128 n) {
  uint64_t u1 = i128_mod(U, P1), n1 = i128_mod(n, P1);
  uint64_t K1 = (i128_mod(c, P1) + mulmod(2 * u1 % P1, i128_mod(x, P1), P1) + 19) % P1;
  uint64_t l1 = (mulmod(36, mulmod(n1, mulmod(n1, n1, P1), P1), P1) + P1
                 - mulmod(12, mulmod(u1, n1, P1), P1)) % P1;
  if (l1 != K1) return 0;
  uint64_t u2 = i128_mod(U, P2), n2 = i128_mod(n, P2);
  uint64_t K2 = (i128_mod(c, P2) + mulmod(2 * u2 % P2, i128_mod(x, P2), P2) + 19) % P2;
  uint64_t l2 = (mulmod(36, mulmod(n2, mulmod(n2, n2, P2), P2), P2) + P2
                 - mulmod(12, mulmod(u2, n2, P2), P2)) % P2;
  return l2 == K2;
}

static void try_pair(i128 U, i128 x, i128 c) {
  cntPairs++;
  if (!filter_pass(x, c)) return;
  cntSolved++;
  __float128 Kq = (__float128)c + 2.0Q * (__float128)U * (__float128)x + 19.0Q;
  __float128 root[3];
  int nr = cubic_real_roots((__float128)U, Kq, root);
  for (int t = 0; t < nr; t++) {
    __float128 v = root[t];
    if (!(v > -1.0e37Q && v < 1.0e37Q)) continue;
    i128 base = (i128)v;
    for (int dlt = -3; dlt <= 3; dlt++) {
      i128 n = base + dlt;
      if (!check_mod(U, x, c, n)) continue;
      fprintf(OUT, "HIT ");
      print_i128(OUT, U); fputc(' ', OUT);
      print_i128(OUT, x); fputc(' ', OUT);
      print_i128(OUT, n); fputc('\n', OUT);
      fflush(OUT);
      cntHits++;
    }
  }
}

/* run over the divisor pairs (x0, c0) of U^2 with x0 * c0 = U^2, building both factors
   multiplicatively so that U^2 itself is never formed (it need not fit in 128 bits) */
static long long ndiv;
static void divrec(int idx, i128 x0, i128 c0, i128 U, int nf, const int *pf, const int *ex) {
  if (ndiv > MAXDIV) return;
  if (x0 > XMAX || c0 > XMAX) return;
  if (idx == nf) {
    ndiv++;
    if (ANYX) { try_pair(U, x0, c0); try_pair(U, -x0, -c0); return; }
    /* x must be 7 (mod 12); only one of the two signs can qualify */
    i128 r = x0 % 12;
    if (r == 7) try_pair(U, x0, c0);
    else if (r == 5) try_pair(U, -x0, -c0);
    return;
  }
  int e2 = 2 * ex[idx];
  uint64_t p = PR[pf[idx]];
  /* powers p^0 .. p^e2, marked -1 when they no longer fit */
  i128 pw[256];
  int top = e2 < 255 ? e2 : 255;
  pw[0] = 1;
  for (int k = 1; k <= top; k++)
    pw[k] = (pw[k - 1] > 0 && pw[k - 1] <= XMAX / (i128)p) ? pw[k - 1] * (i128)p : -1;
  for (int k = 0; k <= top; k++) {
    i128 a = pw[k], b = pw[top - k];
    if (a < 0) break;                       /* x factor already too large */
    if (b < 0) continue;                    /* c factor too large: try a larger k */
    if (x0 > XMAX / a || c0 > XMAX / b) continue;
    divrec(idx + 1, x0 * a, c0 * b, U, nf, pf, ex);
  }
}

static void process_signed(i128 U, i128 W);

static void process(i128 W) {
  if (ANYX) { process_signed(W, W); process_signed(-W, W); return; }
  /* sign of U forced by U = 5, 11 (mod 12) */
  int r = (int)(W % 12);
  i128 U;
  if (r == 5 || r == 11) U = W;
  else if (r == 1 || r == 7) U = -W;
  else return;
  process_signed(U, W);
}

static void process_signed(i128 U, i128 W) {
  (void)W;
  if (shards > 1 && (counter++ % shards) != shard) return;
  cntU++;
  int pf[512], ex[512], nf = 0;
  for (int i = 0; i < NPR; i++) if (EXPO[i]) { pf[nf] = i; ex[nf] = EXPO[i]; nf++; }
  filter_build(U);
  ndiv = 0;
  divrec(0, 1, 1, U, nf, pf, ex);
  if (ndiv > MAXDIV) cntSkip++;
}

/* depth first enumeration of the B-smooth numbers in [LO, HI) */
static void gen(int idx, i128 v) {
  if (v >= LO) process(v);
  for (int i = idx; i < NPR; i++) {
    uint64_t p = PR[i];
    if (v > HI / (i128)p) continue;
    i128 w = v;
    int e = 0;
    while (w <= HI / (i128)p) {
      w *= (i128)p;
      e++;
      EXPO[i] = e;
      if (w < HI) gen(i + 1, w);
    }
    EXPO[i] = 0;
  }
}

int main(int argc, char **argv) {
  LO = parse_i128("1000000000000000000");   /* 1e18 */
  HI = parse_i128("2000000000000000000");
  uint64_t B = 100;
  int progress = 0;
  const char *outname = NULL;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--lo") && i + 1 < argc) LO = parse_i128(argv[++i]);
    else if (!strcmp(argv[i], "--hi") && i + 1 < argc) HI = parse_i128(argv[++i]);
    else if (!strcmp(argv[i], "--B") && i + 1 < argc) B = strtoull(argv[++i], 0, 10);
    else if (!strcmp(argv[i], "--shard") && i + 1 < argc) shard = atoll(argv[++i]);
    else if (!strcmp(argv[i], "--shards") && i + 1 < argc) shards = atoll(argv[++i]);
    else if (!strcmp(argv[i], "--maxdiv") && i + 1 < argc) MAXDIV = atoll(argv[++i]);
    else if (!strcmp(argv[i], "--test")) ANYX = 1;
    else if (!strcmp(argv[i], "--progress")) progress = 1;
    else if (!strcmp(argv[i], "--out") && i + 1 < argc) outname = argv[++i];
    else { fprintf(stderr, "usage: %s --lo L --hi H --B b [--shard i --shards N] [--maxdiv D] [--out f]\n", argv[0]); return 1; }
  }
  OUT = outname ? fopen(outname, "w") : stdout;
  if (!OUT) { perror("open"); return 1; }

  /* primes 5 <= p <= B (U is coprime to 6) */
  NPR = 0;
  for (uint64_t p = ANYX ? 2 : 5; p <= B && NPR < 512; p++) {
    int isp = 1;
    for (uint64_t q = 2; q * q <= p; q++) if (p % q == 0) { isp = 0; break; }
    if (isp) PR[NPR++] = p;
  }
  memset(EXPO, 0, sizeof(EXPO));
  gen(0, 1);

  fprintf(OUT, "DONE lo=");
  print_i128(OUT, LO); fprintf(OUT, " hi="); print_i128(OUT, HI);
  fprintf(OUT, " B=%llu shard=%lld/%lld U=%lld pairs=%lld solved=%lld hits=%lld skipped=%lld\n",
          (unsigned long long)B, shard, shards, cntU, cntPairs, cntSolved, cntHits, cntSkip);
  if (progress) fprintf(stderr, "U=%lld pairs=%lld hits=%lld\n", cntU, cntPairs, cntHits);
  if (outname) fclose(OUT);
  return 0;
}
