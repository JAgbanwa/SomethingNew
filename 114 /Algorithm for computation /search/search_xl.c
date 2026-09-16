/* search_xl.c -- sieve-accelerated search for integer solutions (n,x) of

       V = x^2 (x+6n)^2 + x (36 n^3 - 19)  = perfect square,

   with the *large-x* range included.

   Mathematics (same as search_sv.c).  Write A = 36n^3-19, x = sigma*e*y^2 with
   sigma = +-1, e > 0 squarefree, e | A, y >= 1, s = x+6n.  Then V = y^2 m^2 with

       m^2 - (e y s)^2 = sigma e A,      i.e.   g h = P := sigma e A,
       g = m - e y s,  h = m + e y s,    h - g = 2 e y s,

   so for every factorisation P = g h one solves the cubic

       sigma e y^3 + 6 n y = (h-g)/(2e)

   for an integer y >= 1.

   Difference to search_sv.c
   -------------------------
   search_sv.c held g and h in 128-bit integers, which forced the cut-off
   |x| <= 2^125/|A|.  For n = 10^10 that is |x| <= 1.2*10^6, i.e. only the
   ratio |x|/n <= 1.2*10^-4 was ever examined, although solutions typically
   have |x|/n between 0.1 and 10^3.  Here every quantity is carried twice:

       * exactly modulo 2^128 (wrapping unsigned __int128 arithmetic), and
       * approximately as a double (magnitude only).

   The final test of a candidate is done on the residues mod 2^128, which is
   exact: a wrong candidate would have to agree modulo 2^128.  The doubles are
   used only to locate the candidate (their relative error is ~1e-15, and the
   one place where catastrophic cancellation could occur, |g| ~ |h|, has
   |g|,|h| <= sqrt(|P|) < 2^126, so there both values are exact integers).

   usage:  ./search_xl <lo> <hi> <sign> <K> [roots.bin]
       searches n = sign*[lo,hi]; the x-range is |x| <= min(13 n^2, K*|n|).
*/
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <stdint.h>
#include "fac128.h"

typedef unsigned __int128 u128;
typedef __int128 i128;
typedef unsigned long long u64;
typedef long long ll;
typedef uint32_t u32;

/* ---------- root table ---------- */
static u32 *TP, *TNR, *TR;
static int NPR;

static void load_roots(const char *fn) {
  FILE *f = fopen(fn, "rb");
  if (!f) { fprintf(stderr, "cannot open %s\n", fn); exit(1); }
  fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
  NPR = sz / (5 * 4);
  TP = malloc(NPR * sizeof(u32)); TNR = malloc(NPR * sizeof(u32));
  TR = malloc(3 * NPR * sizeof(u32));
  for (int i = 0; i < NPR; i++) {
    u32 buf[5];
    if (fread(buf, 4, 5, f) != 5) { fprintf(stderr, "short read\n"); exit(1); }
    TP[i] = buf[0]; TNR[i] = buf[1];
    TR[3*i] = buf[2]; TR[3*i+1] = buf[3]; TR[3*i+2] = buf[4];
  }
  fclose(f);
  fprintf(stderr, "loaded %d primes, max %u\n", NPR, TP[NPR-1]);
}

/* ---------- 64-bit primality / rho ---------- */
static u64 mulmod64(u64 a, u64 b, u64 m) { return (u64)((u128)a*b % m); }
static u64 powmod64(u64 a, u64 e, u64 m) { u64 r = 1; a %= m; while (e) { if (e&1) r = mulmod64(r,a,m); a = mulmod64(a,a,m); e >>= 1; } return r; }
static int isprime64(u64 n) {
  if (n < 2) return 0;
  static const u64 sp[12] = {2,3,5,7,11,13,17,19,23,29,31,37};
  for (int i = 0; i < 12; i++) { if (n % sp[i] == 0) return n == sp[i]; }
  u64 d = n-1; int r = 0; while (!(d&1)) { d >>= 1; r++; }
  for (int i = 0; i < 12; i++) {
    u64 x = powmod64(sp[i], d, n);
    if (x == 1 || x == n-1) continue;
    int ok = 0;
    for (int j = 1; j < r; j++) { x = mulmod64(x,x,n); if (x == n-1) { ok = 1; break; } }
    if (!ok) return 0;
  }
  return 1;
}
static u64 gcd64(u64 a, u64 b) { while (b) { u64 t = a % b; a = b; b = t; } return a; }

typedef struct { u64 n, ninv, r2; } m64_t;
static void m64_init(m64_t *M, u64 n) {
  M->n = n;
  u64 inv = n;
  for (int i = 0; i < 6; i++) inv *= 2 - n*inv;
  M->ninv = (u64)0 - inv;
  M->r2 = (u64)(((u128)0 - (u128)n) % n);
}
static inline u64 m64_mul(const m64_t *M, u64 a, u64 b) {
  u128 t = (u128)a*b;
  u64 m = (u64)t * M->ninv;
  u128 u = t + (u128)m * M->n;
  u64 r = (u64)(u >> 64);
  return r >= M->n ? r - M->n : r;
}
static u64 rho64(u64 n) {
  if (!(n & 1)) return 2;
  m64_t M; m64_init(&M, n);
  static unsigned sd = 123456789u;
  for (;;) {
    sd = sd*1103515245u + 12345u;
    u64 c = m64_mul(&M, (u64)(sd % 100000) + 1, M.r2);
    u64 y = m64_mul(&M, (u64)(sd % 9973) + 2, M.r2);
    u64 x, ys = y, q = m64_mul(&M, 1, M.r2), g = 1;
    long r = 1, m = 256;
    do {
      x = y;
      for (long i = 0; i < r; i++) { y = m64_mul(&M, y, y); y += c; if (y >= n) y -= n; }
      long k = 0;
      while (k < r && g == 1) {
        ys = y;
        long lim = (m < r - k) ? m : r - k;
        for (long i = 0; i < lim; i++) {
          y = m64_mul(&M, y, y); y += c; if (y >= n) y -= n;
          u64 diff = x > y ? x - y : y - x;
          if (diff) q = m64_mul(&M, q, diff);
        }
        g = gcd64(q, n);
        k += lim;
      }
      r <<= 1;
    } while (g == 1 && r < (1L<<26));
    if (g == n) {
      g = 1;
      do {
        ys = m64_mul(&M, ys, ys); ys += c; if (ys >= n) ys -= n;
        u64 diff = x > ys ? x - ys : ys - x;
        if (!diff) break;
        g = gcd64(diff, n);
      } while (g == 1);
    }
    if (g != n && g != 1) return g;
  }
}

/* ---------- printing ---------- */
static void pr_i128(i128 v) {
  if (v < 0) { putchar('-'); v = -v; }
  char b[64]; int i = 0;
  if (!v) { putchar('0'); return; }
  while (v) { b[i++] = '0' + (int)(v % 10); v /= 10; }
  while (i) putchar(b[--i]);
}

/* ---------- per-n search ---------- */
#define MAXF 20
#define MAXD (1<<18)
static u128 fprimes[MAXF]; static int fexp[MAXF]; static int nfac;
static u128 dv1[MAXD], cf1[MAXD], dv2[MAXD], cf2[MAXD];
static double dvd1[MAXD], cfd1[MAXD], dvd2[MAXD], cfd2[MAXD];
static long long CAP = 2000000;
/* factor A = 36n^3-19 for a single n by running over the root table (a prime can
   divide A only if it occurs there), then split the cofactor. */
static int factor_single(ll n, u128 Aabs);
static long long KRAT = 10000;
static long RHOBUDGET = 200000;
static unsigned rseed = 1234567u;
static long long NOPAQUE = 0;

/* solve a y^3 + b y = z with a>0,b>0,z>0: unique positive root, double.
   Stable Cardano: with p = b/a, q = z/(2a), D = sqrt(q^2+p^3/27),
   u = cbrt(q+D) and the second root of the pair is -p/(3u).            */
static inline double mono_root(double a, double b, double z) {
  double p = b/a, q = z/(2.0*a);
  double D = sqrt(q*q + p*p*p/27.0);
  double u = cbrt(q + D);
  double y = u - p/(3.0*u);
  /* one Newton polish */
  double f = (a*y*y + b)*y - z, fp = 3.0*a*y*y + b;
  y -= f/fp;
  return y;
}

/* general cubic c3 y^3 + c1 y - z = 0, real roots (doubles) */
static int cubic_roots(double c3, double c1, double c0, double *out) {
  double p = c1 / c3, q = c0 / c3;
  double disc = -4.0*p*p*p - 27.0*q*q;
  int cnt = 0;
  if (disc < 0) {
    double t = q*q/4.0 + p*p*p/27.0;
    double sq = sqrt(t);
    out[cnt++] = cbrt(-q/2.0 + sq) + cbrt(-q/2.0 - sq);
  } else {
    double m = 2.0*sqrt(-p/3.0);
    double arg = 3.0*q/(p*m);
    if (arg > 1.0) arg = 1.0;
    if (arg < -1.0) arg = -1.0;
    double th = acos(arg)/3.0;
    for (int k = 0; k < 3; k++) out[cnt++] = m*cos(th - 2.0*3.14159265358979323846*k/3.0);
  }
  /* Newton polish (twice) on the original cubic c3 y^3 + c1 y + c0 */
  for (int k = 0; k < cnt; k++) {
    double y = out[k];
    for (int it = 0; it < 2; it++) {
      double f = ((c3*y)*y + c1)*y + c0, fp = 3.0*c3*y*y + c1;
      if (fp != 0.0) y -= f/fp;
    }
    out[k] = y;
  }
  return cnt;
}

static long long SOLCNT = 0;
long long DBG_OK = 0, DBG_BAD = 0;

/* exact check (mod 2^128) that 2 e (sigma e y^3 + 6 n y) == dif, and report */
static inline void try_y(ll n, i128 sgn_e /* sigma*e as i128 (may wrap) */,
                         u128 e128, double ed, int sigma, i128 y,
                         u128 dif128, double difd, double xmaxd) {
  if (y < 1) return;
  double yd = (double)y;
  if (ed*yd*yd > xmaxd) return;
  u128 yy = (u128)(i128)y;
  u128 cube = yy*yy*yy;
  u128 val = (u128)sgn_e*cube + (u128)(6*(i128)n) * yy;   /* sigma e y^3 + 6 n y */
  u128 lhs = (u128)2 * e128 * val;
#ifdef DEBUG_RESID
  {
    /* consistency check: the residual lhs-dif must have the magnitude predicted
       by the derivative, not look like a random 128-bit number */
    i128 r = (i128)(lhs - dif128);
    double rd = (double)(r < 0 ? -r : r);
    double pred = 2.0*ed*(3.0*ed*yd*yd + 6.0*fabs((double)n)) + 1.0;
    extern long long DBG_OK, DBG_BAD;
    if (pred < 1e35) { if (rd <= 1000.0*pred) DBG_OK++; else DBG_BAD++; }
  }
#endif
  if (lhs != dif128) return;
  /* magnitude sanity (guards against a wrapped coincidence) */
  double lhsd = 2.0*ed*((sigma>0?ed:-ed)*yd*yd*yd + 6.0*(double)n*yd);
  double sc = fabs(difd) + fabs(lhsd) + 1.0;
  if (fabs(lhsd - difd) > 1e-6*sc) return;
  i128 x = (i128)((u128)(i128)(sigma>0?1:-1) * e128 * yy * yy);
  printf("SOL n=%lld x=", n); pr_i128(x);
  printf(" e="); pr_i128((i128)e128);
  printf(" y="); pr_i128(y);
  printf(" sigma=%d\n", sigma);
  fflush(stdout);
  SOLCNT++;
}

static void process(ll n, ll na, u128 Aabs, int Aneg) {
  long long tot = 1;
  for (int i = 0; i < nfac; i++) tot *= (2*fexp[i] + 3);
  if (tot > CAP) { fprintf(stderr, "skip n=%lld tot=%lld\n", n, tot); return; }
  u128 XMAX = (u128)13*(u128)na*(u128)na + 1000000;
  u128 XK = (u128)KRAT*(u128)na;
  if (XK < XMAX) XMAX = XK;
  double XMAXd = (double)XMAX;
  double nad = (double)na;
  double Ad = (double)Aabs;

  for (int mask = 0; mask < (1 << nfac); mask++) {
    u128 e = 1; int okE = 1;
    for (int i = 0; i < nfac; i++) if (mask >> i & 1) {
      if (e > XMAX / fprimes[i]) { okE = 0; break; }
      e *= fprimes[i];
    }
    if (!okE || e > XMAX) continue;
    double ed = (double)e;
    double ymaxd = sqrt(XMAXd/ed);
    double zmaxd = ymaxd*(XMAXd + 6.0*nad) + 4.0;
    double difmaxd = 2.0*ed*zmaxd;
    double Pd = ed*Ad;                        /* |P| = e|A| */

    /* generate all divisor pairs (d, c) with d*c = e|A| */
    int nd = 1;
    u128 *dv = dv1, *cf = cf1, *dvo = dv2, *cfo = cf2;
    double *dvd = dvd1, *cfd = cfd1, *dvdo = dvd2, *cfdo = cfd2;
    dv[0] = 1; cf[0] = 1; dvd[0] = 1.0; cfd[0] = 1.0;
    int overflow = 0;
    for (int i = 0; i < nfac && !overflow; i++) {
      int ex = fexp[i] + ((mask >> i) & 1);
      u128 p = fprimes[i]; double pd = (double)p;
      u128 pw[64]; double pwd[64];
      pw[0] = 1; pwd[0] = 1.0;
      for (int k = 1; k <= ex; k++) { pw[k] = pw[k-1]*p; pwd[k] = pwd[k-1]*pd; }
      int nn = 0;
      for (int j = 0; j < nd; j++) {
        for (int k = 0; k <= ex; k++) {
          if (nn >= MAXD) { overflow = 1; break; }
          dvo[nn] = dv[j]*pw[k];      dvdo[nn] = dvd[j]*pwd[k];
          cfo[nn] = cf[j]*pw[ex-k];   cfdo[nn] = cfd[j]*pwd[ex-k];
          nn++;
        }
        if (overflow) break;
      }
      nd = nn;
      u128 *t1 = dv; dv = dvo; dvo = t1;
      u128 *t2 = cf; cf = cfo; cfo = t2;
      double *t3 = dvd; dvd = dvdo; dvdo = t3;
      double *t4 = cfd; cfd = cfdo; cfdo = t4;
    }
    if (overflow) { fprintf(stderr, "divoverflow n=%lld\n", n); continue; }
    (void)Pd;

    for (int di = 0; di < nd; di++) {
      double dd = dvd[di], cd = cfd[di];
      /* (d, c) and (c, d) give the same four (sigma, difference) pairs, so only
         the half with d <= c is processed; the tolerance keeps both entries when
         the two are equal to within the accuracy of the double magnitudes. */
      if (dd > cd*(1.0 + 1e-12)) continue;
      u128 d128 = dv[di], c128 = cf[di];
      /* four combinations: sigma = +-1 and sign of g */
      for (int so = 0; so < 2; so++) {
        int sigma = so ? -1 : 1;
        int Psign = (Aneg ? -1 : 1) * sigma;          /* sign of P */
        for (int sg = 0; sg < 2; sg++) {
          /* g = +-d, h = P/g */
          double gd = sg ? -dd : dd;
          double hd = (sg ? -Psign : Psign) * cd;
          double difd = hd - gd;
          if (difd > difmaxd || difd < -difmaxd) continue;
          u128 g128 = sg ? (u128)0 - d128 : d128;
          u128 h128 = ((sg ? -Psign : Psign) > 0) ? c128 : (u128)0 - c128;
          u128 dif128 = h128 - g128;
          /* if both |g| and |h| are below 2^126 the residues are exact */
          if (dd < 6.0e37 && cd < 6.0e37) difd = (double)(i128)dif128;
          double zd = difd/(2.0*ed);
          i128 sgn_e = sigma > 0 ? (i128)e : -(i128)e;
          double a = sigma > 0 ? ed : -ed;
          double b = 6.0*(double)n;
          if ((a > 0) == (b > 0)) {
            /* monotone: root exists with the sign of z */
            if ((zd > 0) != (a > 0)) continue;
            double y = mono_root(fabs(a), fabs(b), fabs(zd));
            if (y > ymaxd + 2.0 || y < 0.0) continue;
            i128 y0 = (i128)(y + 0.5);
            for (int dy = -1; dy <= 1; dy++)
              try_y(n, sgn_e, e, ed, sigma, y0 + dy, dif128, difd, XMAXd);
          } else {
            double rts[3];
            int nr = cubic_roots(a, b, -zd, rts);
            for (int ri = 0; ri < nr; ri++) {
              double y = rts[ri];
              if (y < 0.0 || y > ymaxd + 2.0) continue;
              i128 y0 = (i128)(y + 0.5);
              for (int dy = -1; dy <= 1; dy++)
                try_y(n, sgn_e, e, ed, sigma, y0 + dy, dif128, difd, XMAXd);
            }
          }
        }
      }
    }
  }
}

/* ---------- main: block sieve ---------- */
#define BLK (1<<22)
static u128 rem_[BLK];
static u32  fp_[BLK][MAXF];
static unsigned char fe_[BLK][MAXF];
static unsigned char fc_[BLK];

/* ---------- list mode ---------- */
static int factor_single(ll n, u128 Aabs) {
  u128 rem = Aabs;
  nfac = 0;
  ll na = n < 0 ? -n : n;
  for (int j = 0; j < NPR; j++) {
    u32 p = TP[j];
    u32 r = (u32)(na % p);
    int hit = 0;
    for (u32 k = 0; k < TNR[j]; k++) {
      u32 target = n > 0 ? TR[3*j+k] : (TR[3*j+k] ? p - TR[3*j+k] : 0);
      if (r == target) { hit = 1; break; }
    }
    if (!hit) continue;
    if (rem % p) continue;
    int ex = 0;
    do { rem /= p; ex++; } while (rem % p == 0);
    if (nfac >= MAXF) return 0;
    fprimes[nfac] = p; fexp[nfac] = ex; nfac++;
  }
  if (rem > 1) {
    int opq = 0, nl = 0;
    u128 lp[MAXF]; int le[MAXF];
    for (int c = 0; c < MAXF; c++) le[c] = 0;
    if (!factor128(rem, RHOBUDGET, &rseed, lp, le, &nl, MAXF - nfac, &opq)) return 0;
    if (opq) NOPAQUE++;
    for (int c = 0; c < nl; c++) {
      if (nfac >= MAXF) return 0;
      fprimes[nfac] = lp[c]; fexp[nfac] = le[c]; nfac++;
    }
  }
  return 1;
}

static int run_list(const char *fn) {
  FILE *f = fopen(fn, "r");
  if (!f) { fprintf(stderr, "cannot open %s\n", fn); return 1; }
  ll n; long cnt = 0;
  while (fscanf(f, "%lld", &n) == 1) {
    if (n == 0) continue;
    ll na = n < 0 ? -n : n;
    u128 na2 = (u128)na, Aabs = (u128)36*na2*na2*na2;
    Aabs = n > 0 ? Aabs - 19 : Aabs + 19;
    if (!factor_single(n, Aabs)) { fprintf(stderr, "factor fail n=%lld\n", n); continue; }
    process(n, na, Aabs, n > 0 ? 0 : 1);
    if (++cnt % 100 == 0) { fprintf(stderr, "list %ld done (n=%lld)\n", cnt, n); fflush(stderr); }
  }
  fclose(f);
  fprintf(stderr, "list finished: %ld values, %lld hits\n", cnt, SOLCNT);
  return 0;
}

int main(int argc, char **argv) {
  if (argc >= 3 && !strcmp(argv[1], "-f")) {
    /* usage: search_xl -f <file> <K> <roots.bin> <rhobudget> <cap> */
    KRAT = argc > 3 ? atoll(argv[3]) : 10000;
    load_roots(argc > 4 ? argv[4] : "roots3e7.bin");
    if (argc > 5) RHOBUDGET = atol(argv[5]);
    if (argc > 6) CAP = atoll(argv[6]);
    return run_list(argv[2]);
  }
  if (argc < 5) { fprintf(stderr, "usage: %s lo hi sign K [roots.bin] [rhobudget]\n       %s -f <nfile> <K> [roots.bin] [rhobudget] [cap]\n", argv[0], argv[0]); return 1; }
  ll NLO = atoll(argv[1]), NHI = atoll(argv[2]);
  int SGN = atoi(argv[3]);
  KRAT = atoll(argv[4]);
  if (argc > 6) RHOBUDGET = atol(argv[6]);
  load_roots(argc > 5 ? argv[5] : "roots3e7.bin");

  for (ll base = NLO; base <= NHI; base += BLK) {
    ll len = NHI - base + 1; if (len > BLK) len = BLK;
    for (ll i = 0; i < len; i++) {
      u128 na = (u128)(base + i);
      u128 v = (u128)36*na*na*na;
      rem_[i] = SGN > 0 ? v - 19 : v + 19;
      fc_[i] = 0;
    }
    for (int j = 0; j < NPR; j++) {
      u32 p = TP[j];
      for (u32 k = 0; k < TNR[j]; k++) {
        u32 r = TR[3*j+k];
        u32 target = SGN > 0 ? r : (r ? p - r : 0);
        ll start = ((ll)target - base) % (ll)p;
        if (start < 0) start += p;
        for (ll i = start; i < len; i += p) {
          if (rem_[i] % p) continue;
          int ex = 0;
          do { rem_[i] /= p; ex++; } while (rem_[i] % p == 0);
          unsigned char c = fc_[i];
          if (c < MAXF) { fp_[i][c] = p; fe_[i][c] = ex; fc_[i] = c + 1; }
          else fc_[i] = MAXF + 1;
        }
      }
    }
    for (ll i = 0; i < len; i++) {
      ll na = base + i, n = SGN > 0 ? na : -na;
      if (fc_[i] > MAXF) { fprintf(stderr, "overflow n=%lld\n", n); continue; }
      nfac = 0;
      for (int c = 0; c < fc_[i]; c++) { fprimes[nfac] = fp_[i][c]; fexp[nfac] = fe_[i][c]; nfac++; }
      if (rem_[i] > 1) {
        /* split the unsieved cofactor completely (128-bit rho, bounded work) */
        u128 C = rem_[i];
        int nf0 = nfac, opq = 0;
        u128 lp[MAXF]; int le[MAXF]; int nl = 0;
        for (int c2 = 0; c2 < MAXF; c2++) le[c2] = 0;
        if (!factor128(C, RHOBUDGET, &rseed, lp, le, &nl, MAXF - nf0, &opq)) {
          fprintf(stderr, "facfail n=%lld\n", n); continue;
        }
        if (opq) NOPAQUE++;
        for (int c2 = 0; c2 < nl; c2++) {
          if (nfac >= MAXF) { fprintf(stderr, "overflow n=%lld\n", n); nfac = -1; break; }
          fprimes[nfac] = lp[c2]; fexp[nfac] = le[c2]; nfac++;
        }
        if (nfac < 0) continue;
      }
      u128 na2 = (u128)na, Aabs = (u128)36*na2*na2*na2;
      Aabs = SGN > 0 ? Aabs - 19 : Aabs + 19;
      process(n, na, Aabs, SGN > 0 ? 0 : 1);
    }
    fprintf(stderr, "n=%lld\n", SGN > 0 ? base + len - 1 : -(base + len - 1));
    fflush(stderr);
  }
  fprintf(stderr, "done, %lld hits, %lld opaque cofactors\n", SOLCNT, NOPAQUE);
#ifdef DEBUG_RESID
  fprintf(stderr, "resid ok=%lld bad=%lld\n", DBG_OK, DBG_BAD);
#endif
  return 0;
}
