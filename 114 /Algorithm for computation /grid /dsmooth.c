/* dsmooth.c --- Algorithm A', the d-first sweep restricted to *smooth* certificates.
 *
 * Same principle as dsweep.c: a solution of
 *
 *    36 n^3 - 19 = -2 d x^2 ( -(x+6n) + sqrt( (x+6n)^2 + (36n^3-19)/x ) )
 *
 * is described by an integer certificate G of d through
 *
 *    integer chart (x = X):     G = U = 2dx^2,  G^2 = c X,  36 n^3 - 12 G n = c + 2 G X + 19
 *    half chart    (x = X/2):   G = V = dX^2,   G^2 = c X,  72 n^3 - 12 G n = c +   G X + 38
 *
 * (`DEquation.sat_iff_dSweep` for the integer chart; HALF_INTEGER.md for the half chart).
 * dsweep.c sweeps *all* G in an interval, which by |n| <= |G| cannot reach beyond about
 * thirteen digits within a realistic grid budget.  This program instead enumerates only the
 * G that are B-smooth (all prime factors <= B), which can be done for G of twenty, twenty
 * five or thirty digits, and for each of them runs over the divisors X of G^2 exactly as
 * before -- or, with an INTEGRAL radical (--integral; the default in the half chart), over
 * the divisors of G only: y is an integer (resp. y = Y/2, Y odd) iff X | G.  Those are the
 * solutions that give 114 = A^3+B^3+C^3 (A = -x+y, B = -x-y, C = 2x+6n).
 *
 * Why smooth G.  The number of (G, X) pairs -- and hence the number of chances -- per unit
 * of work is proportional to the number of divisors, which is what a smooth G maximises.
 * Among the eleven solutions known for this equation (integer chart, rational radical) the
 * certificates U = -5586 = -2.3.7^2.19, U = -335124555576 (2273-smooth) and
 * U = -665761661810070 (2309-smooth) are of exactly this shape.  It is of course *not*
 * exhaustive: a solution whose certificate has a large prime factor is invisible here.
 *
 * Congruence restrictions (dropped by --general, alias --test):
 *   integer chart, rational radical: the requested family x = 12u+7, hence U = 5, 11
 *     (mod 12) (`DEquation.sat_U_mod_twelve`): U is coprime to 6 and only primes >= 5 are
 *     used.  Requires K = 19.
 *   integral radical: the 2-adic / 3-adic conditions of local.h for the given K; the prime
 *     2 (resp. 3) is left out of the enumeration when no admissible G is even (resp. a
 *     multiple of 3).
 *   half chart, rational radical: none.
 *
 * Arithmetic: G, X and c = G^2/X are exact 128-bit integers; the right-hand side of the
 * cubic is located with __float128 (113-bit mantissa) and then tested exactly modulo two
 * 61-bit primes.  Survivors are re-checked in exact arithmetic by grid/verify.py.
 *
 * Build:  cc -O3 -o dsmooth dsmooth.c -lm -lquadmath
 * Run:    ./dsmooth --lo 1e20 --hi 1e21 --B 100 [--shard i --shards N] [--half]
 *                   [--integral | --rational-sqrt] [--general] [--K k]
 *                   [--maxdiv 200000] [--out hits.txt] [--progress]
 * Output: "HIT U x n" / "HHIT V X n" lines and one "DONE ..." line.
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
#include "local.h"

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

/* decimal or "1e25" / "3e20" style input */
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
static int NPR;                       /* primes used in the enumeration */
static uint64_t *PR;                  /* all of them (the original code silently kept only
                                         the first 512 primes, i.e. B <= 3671)          */
static int STK_I[128], STK_E[128];    /* (prime index, exponent) of the current G        */
static int DEPTH = 0;
static long long MAXDIV = 200000;
static long long shard = 0, shards = 1, counter = 0;
static int GENERAL = 0, HALF = 0, INTEGRAL = -1;
static long long KK = 19;
enum { FAM_NONE, FAM_ARISTOTLE, FAM_LOCAL };
static int FAM = FAM_NONE;
static local_t LT;
static int ALPHA = 36, BETA = 2;
static long long GAMMA = 19;
static long long cntU = 0, cntPairs = 0, cntSolved = 0, cntHits = 0, cntSkip = 0;
static FILE *OUT;
static const i128 XMAX = ((i128)1 << 126);   /* keep X and c inside 128 bits */

/* -------------------------------------------------------- the cubic solver */

static int cubic_real_roots(__float128 alpha, __float128 G, __float128 R, __float128 *out) {
  __float128 p = -12.0Q * G / alpha, q = -R / alpha;
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

/* test  alpha n^3 - 12 G n = c + beta G X + gamma  modulo two 61-bit primes */
static int check_mod1(uint64_t P, i128 G, i128 X, i128 c, i128 n) {
  uint64_t g = i128_mod(G, P), nn = i128_mod(n, P);
  uint64_t R = (i128_mod(c, P) + mulmod(mulmod((uint64_t)BETA, g, P), i128_mod(X, P), P)
                + i128_mod(GAMMA, P)) % P;
  uint64_t l = (mulmod((uint64_t)ALPHA, mulmod(nn, mulmod(nn, nn, P), P), P) + P
                - mulmod(12, mulmod(g, nn, P), P)) % P;
  return l == R;
}

static void try_pair(i128 G, i128 X, i128 c) {
  cntPairs++;
  if (!filter_pass(X, c)) return;
  cntSolved++;
  __float128 Rq = (__float128)c + (__float128)BETA * (__float128)G * (__float128)X + (__float128)GAMMA;
  __float128 root[3];
  int nr = cubic_real_roots((__float128)ALPHA, (__float128)G, Rq, root);
  for (int t = 0; t < nr; t++) {
    __float128 v = root[t];
    if (!(v > -1.0e37Q && v < 1.0e37Q)) continue;
    i128 base = (i128)v;
    for (int dlt = -3; dlt <= 3; dlt++) {
      i128 n = base + dlt;
      if (!check_mod1(P1, G, X, c, n) || !check_mod1(P2, G, X, c, n)) continue;
      if (FAM == FAM_LOCAL && !local_Xn_ok(&LT, X, n)) continue;
      fprintf(OUT, HALF ? "HHIT " : "HIT ");
      print_i128(OUT, G); fputc(' ', OUT);
      print_i128(OUT, X); fputc(' ', OUT);
      print_i128(OUT, n); fputc('\n', OUT);
      fflush(OUT);
      cntHits++;
    }
  }
}

/* run over the divisor pairs (x0, c0) with x0 * c0 = G^2 and x0 | G^2 (rational radical)
   or x0 | G (integral radical), building both factors multiplicatively so that G^2 itself
   is never formed (it need not fit in 128 bits) */
static long long ndiv;
static void leaf(i128 G, i128 x0, i128 c0) {
  if (FAM == FAM_ARISTOTLE) {
    /* x must be 7 (mod 12); only one of the two signs can qualify */
    i128 r = x0 % 12;
    if (r == 7) try_pair(G, x0, c0);
    else if (r == 5) try_pair(G, -x0, -c0);
    return;
  }
  for (int s = 0; s < 2; s++) {
    i128 X = s ? -x0 : x0, c = s ? -c0 : c0;
    if (FAM == FAM_LOCAL && (!local_X_ok(&LT, X) || !local_GX_ok(&LT, G, X))) continue;
    try_pair(G, X, c);
  }
}

static void divrec(int idx, i128 x0, i128 c0, i128 G, int nf, const int *pf, const int *ex) {
  if (ndiv > MAXDIV) return;
  if (x0 > XMAX || c0 > XMAX) return;
  if (idx == nf) { ndiv++; leaf(G, x0, c0); return; }
  int e2 = 2 * ex[idx];
  uint64_t p = PR[pf[idx]];
  int kmax = INTEGRAL ? ex[idx] : e2;                  /* exponent of p in X */
  if (HALF && p == 2) kmax = 0;                        /* half chart: X is odd */
  /* powers p^0 .. p^e2, marked -1 when they no longer fit */
  i128 pw[256];
  int top = e2 < 255 ? e2 : 255;
  pw[0] = 1;
  for (int k = 1; k <= top; k++)
    pw[k] = (pw[k - 1] > 0 && pw[k - 1] <= XMAX / (i128)p) ? pw[k - 1] * (i128)p : -1;
  for (int k = 0; k <= kmax && k <= top; k++) {
    i128 a = pw[k], b = pw[top - k];
    if (a < 0) break;                       /* x factor already too large */
    if (b < 0) continue;                    /* c factor too large: try a larger k */
    if (x0 > XMAX / a || c0 > XMAX / b) continue;
    divrec(idx + 1, x0 * a, c0 * b, G, nf, pf, ex);
  }
}

static void process_signed(i128 G);

static void process(i128 W) {
  if (FAM == FAM_ARISTOTLE) {
    /* sign of U forced by U = 5, 11 (mod 12) */
    int r = (int)(W % 12);
    if (r == 5 || r == 11) process_signed(W);
    else if (r == 1 || r == 7) process_signed(-W);
    return;
  }
  if (FAM == FAM_LOCAL) {
    if (local_G_ok(&LT, W)) process_signed(W);
    if (local_G_ok(&LT, -W)) process_signed(-W);
    return;
  }
  process_signed(W);
  process_signed(-W);
}

static void process_signed(i128 G) {
  if (shards > 1 && (counter++ % shards) != shard) return;
  cntU++;
  int pf[128], ex[128], nf = DEPTH;
  for (int i = 0; i < DEPTH; i++) { pf[i] = STK_I[i]; ex[i] = STK_E[i]; }
  filter_build(G);
  ndiv = 0;
  divrec(0, 1, 1, G, nf, pf, ex);
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
    STK_I[DEPTH] = i;
    DEPTH++;
    while (w <= HI / (i128)p) {
      w *= (i128)p;
      e++;
      STK_E[DEPTH - 1] = e;
      if (w < HI) gen(i + 1, w);
    }
    DEPTH--;
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
    else if (!strcmp(argv[i], "--test") || !strcmp(argv[i], "--general")) GENERAL = 1;
    else if (!strcmp(argv[i], "--half")) HALF = 1;
    else if (!strcmp(argv[i], "--integral")) INTEGRAL = 1;
    else if (!strcmp(argv[i], "--rational-sqrt")) INTEGRAL = 0;
    else if (!strcmp(argv[i], "--K") && i + 1 < argc) KK = atoll(argv[++i]);
    else if (!strcmp(argv[i], "--progress")) progress = 1;
    else if (!strcmp(argv[i], "--out") && i + 1 < argc) outname = argv[++i];
    else {
      fprintf(stderr, "usage: %s --lo L --hi H --B b [--shard i --shards N] [--half]\n"
                      "          [--integral|--rational-sqrt] [--general] [--K k] [--maxdiv D] [--out f]\n", argv[0]);
      return 1;
    }
  }
  if (INTEGRAL < 0) INTEGRAL = HALF ? 1 : 0;
  if (!GENERAL) {
    if (INTEGRAL) FAM = FAM_LOCAL;
    else if (!HALF) {
      if (KK != 19) { fprintf(stderr, "dsmooth: the x = 12u+7 family is defined for K = 19 only; use --general\n"); return 1; }
      FAM = FAM_ARISTOTLE;
    }
  }
  if (FAM == FAM_LOCAL) local_init(&LT, HALF ? 2 : 1, KK);
  ALPHA = HALF ? 72 : 36; BETA = HALF ? 1 : 2; GAMMA = HALF ? 2 * KK : KK;
  filter_setup(ALPHA, BETA, GAMMA);
  OUT = outname ? fopen(outname, "w") : stdout;
  if (!OUT) { perror("open"); return 1; }

  /* the primes p <= B that an admissible G can contain */
  int use2 = 1, use3 = 1;
  if (FAM == FAM_ARISTOTLE) use2 = use3 = 0;          /* U coprime to 6 */
  if (FAM == FAM_LOCAL) {
    use2 = use3 = 0;
    for (int r = 0; r < LOC2; r += 2) if (LT.G2[r]) use2 = 1;
    for (int r = 0; r < LOC3; r += 3) if (LT.G3[r]) use3 = 1;
  }
  NPR = 0;
  {
    char *comp = calloc(B + 1, 1);
    PR = malloc(sizeof(uint64_t) * (B / 2 + 2));
    for (uint64_t p = 2; p <= B; p++) {
      if (comp[p]) continue;
      for (uint64_t q = p * p; q <= B; q += p) comp[q] = 1;
      if ((p == 2 && !use2) || (p == 3 && !use3)) continue;
      PR[NPR++] = p;
    }
    free(comp);
  }
  gen(0, 1);

  fprintf(OUT, "DONE lo=");
  print_i128(OUT, LO); fprintf(OUT, " hi="); print_i128(OUT, HI);
  fprintf(OUT, " B=%llu shard=%lld/%lld U=%lld pairs=%lld solved=%lld hits=%lld skipped=%lld"
          " chart=%s sqrt=%s family=%s K=%lld\n",
          (unsigned long long)B, shard, shards, cntU, cntPairs, cntSolved, cntHits, cntSkip,
          HALF ? "half" : "int", INTEGRAL ? "integral" : "rational",
          FAM == FAM_ARISTOTLE ? "x=7mod12" : FAM == FAM_LOCAL ? "local" : "none", KK);
  if (progress) fprintf(stderr, "U=%lld pairs=%lld hits=%lld\n", cntU, cntPairs, cntHits);
  if (outname) fclose(OUT);
  return 0;
}
