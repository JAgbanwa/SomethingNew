/* rd_worker.c -- every rational d, both charts, complete in x for each n.

   Problem.  Find rational d for which

       36n^3 - 19 = -2 d x^2 ( -(x+6n) + sqrt((x+6n)^2 + (36n^3-19)/x) )        (E)

   holds with n an integer and x an integer (integer chart) or a half-integer
   x = X/2, X odd (half chart).  The square root is only required to be
   RATIONAL (it is what makes d rational); it need not be an integer.

   Reduction (both charts at once, X = 2x a nonzero integer, N = 36n^3 - 19):
       d is rational  <=>  F(X) = X^2 (X+12n)^2 + 8 X N  is a perfect square W^2,
   and then  d = -( W/|X| + X + 12n ) / (2X)  is the unique d for (n, x).
   (Clear the radical: with s = x+6n, R = sqrt(s^2 + N/x), (E) times (R+s) gives
   R + s = -2dx, so d is rational iff R is; R = W/(2|X|).)

   Divisor method (as search/search_xl.c, extended to the half chart).  If a
   prime p divides X to an odd power then p | 8N, so X = sigma e y^2 with
   sigma = +-1, e squarefree, e | 2N.  Then W = y w and
       w^2 - (e y S)^2 = M sigma e N',     S = X + 12n,
   i.e. for every factorisation g h = P of that right-hand side,
       sigma e y^3 + c1 n y = (h - g)/(2e)                                   (C)
   is a cubic for the integer y >= 1.
     integer chart (x = sigma e y^2, s = x+6n):  P = sigma e N,   c1 = 6,  e | N;
     half chart    (X = sigma e y^2, X, y odd):  P = 8 sigma e N, c1 = 12, e | N,
                   and g = 2^a g', h = 2^(3-a) h' with a in {1,2}, g' h' = sigma e N
                   (w, e y S are odd, so g, h are both even and v2(g h) = 3).
   (N is odd and prime to 3, so e is odd in both charts.)

   Bounds used only to prune (proved; see README):
     integer chart |x| (x+6n)^2 <= N^2      =>  |x| <= 6|n| + |N|^(2/3)
     half chart    |X| (X+12n)^2 <= 16 N^2  =>  |X| <= 12|n| + (16 N^2)^(1/3)

   Arithmetic.  Every divisor is carried exactly modulo 2^128 and approximately
   as a double, exactly as in search_xl.c; the doubles locate y, and the
   candidate is accepted only if (C) holds modulo 2^128.  Every printed hit is
   re-verified with exact integers by verify_rd.py, so a wrapped coincidence can
   at worst produce a line that the verifier rejects, never a wrong d.

   Completeness caveats are reported, never hidden:
     OPAQUE n   a cofactor of |N| could not be split within the rho budget; it was
                used as if prime (the n was searched, possibly incompletely);
     SKIP n t   the n has more than --cap divisor combinations and was NOT searched.
   Both lists must be re-run (runner: deferred pass) before a range is called complete.

   usage:  rd_worker --n0 A --n1 B [--chart both|int|half] [--sieve P]
                     [--rho R] [--cap C] [--block K]
           rd_worker --list FILE [same options]
           rd_worker --selftest
   Searches every integer n with A <= n <= B (signed).  Output on stdout:
     HIT int  n x        (x = sigma e y^2, integer chart)
     HIT half n X        (x = X/2, half chart)
     OPAQUE n / SKIP n t
     DONE a b pairs      (every n in [a, b] has been processed; one line per block)
*/
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include "fac128.h"
#include <gmp.h>
#include <ecm.h>

typedef unsigned __int128 u128;
typedef __int128 i128;
typedef unsigned long long u64;
typedef long long ll;
typedef uint32_t u32;

/* ------------------------------------------------------------------ */
/* roots of 36 r^3 = 19 (mod p) for the sieve                          */
/* ------------------------------------------------------------------ */
static u32 *TP, *TNR, *TR;
static int NPR;

static u64 mulm(u64 a, u64 b, u64 m) { return (u64)((u128)a * b % m); }
static u64 powm(u64 a, u64 e, u64 m) { u64 r = 1 % m; a %= m; while (e) { if (e & 1) r = mulm(r, a, m); a = mulm(a, a, m); e >>= 1; } return r; }
static u64 invm(u64 a, u64 p) { return powm(a, p - 2, p); }

/* all cube roots of a (mod prime p), returns count (0..3) */
static int cube_roots(u64 a, u64 p, u64 *out) {
  a %= p;
  if (a == 0) { out[0] = 0; return 1; }
  if (p % 3 == 2) { out[0] = powm(a, (2 * p - 1) / 3, p); return 1; }
  if (powm(a, (p - 1) / 3, p) != 1) return 0;
  u64 t = p - 1; int s = 0;
  while (t % 3 == 0) { t /= 3; s++; }
  u64 z = 2;
  while (powm(z, (p - 1) / 3, p) == 1) z++;
  u64 g = powm(z, t, p);                       /* generator of the 3-Sylow subgroup, order 3^s */
  u64 u = (t % 3 == 1) ? (2 * t + 1) / 3 : (t + 1) / 3;   /* 3u = 1 (mod t) */
  u64 x0 = powm(a, u, p);
  u64 b = mulm(mulm(mulm(x0, x0, p), x0, p), invm(a, p), p); /* x0^3 / a, in the 3-Sylow subgroup */
  u64 target = invm(b, p);                     /* want c with c^3 = target, c in <g> */
  /* Pohlig-Hellman: target = g^j */
  u64 pw3[64]; pw3[0] = 1; for (int i = 1; i <= s; i++) pw3[i] = pw3[i - 1] * 3;
  u64 om = powm(g, pw3[s - 1], p);             /* primitive cube root of unity */
  u64 om2 = mulm(om, om, p);
  u64 j = 0, ginv = invm(g, p);
  for (int i = 0; i < s; i++) {
    u64 h = mulm(target, powm(ginv, j, p), p);
    u64 v = powm(h, pw3[s - 1 - i], p);
    int digit = (v == 1) ? 0 : (v == om ? 1 : (v == om2 ? 2 : -1));
    if (digit < 0) return 0;  /* cannot happen */
    j += (u64)digit * pw3[i];
  }
  if (j % 3) return 0;        /* cannot happen: a is a cube */
  u64 c = powm(g, j / 3, p);
  u64 r = mulm(x0, c, p);
  out[0] = r; out[1] = mulm(r, om, p); out[2] = mulm(r, om2, p);
  return 3;
}

static void build_roots(u32 PMAX) {
  char *comp = calloc(PMAX + 1, 1);
  int cap = 1 << 16; NPR = 0;
  TP = malloc(cap * sizeof(u32)); TNR = malloc(cap * sizeof(u32)); TR = malloc(3 * cap * sizeof(u32));
  for (u64 i = 2; i <= PMAX; i++) {
    if (comp[i]) continue;
    for (u64 k = i * i; k <= PMAX; k += i) comp[k] = 1;
    if (i == 2 || i == 3) continue;            /* never divide 36n^3 - 19 */
    u64 a = mulm(19, invm(36, i), i), r[3];
    int nr = cube_roots(a, i, r);
    if (!nr) continue;
    if (NPR >= cap) {
      cap *= 2;
      TP = realloc(TP, cap * sizeof(u32)); TNR = realloc(TNR, cap * sizeof(u32)); TR = realloc(TR, 3 * cap * sizeof(u32));
    }
    TP[NPR] = (u32)i; TNR[NPR] = nr;
    for (int k = 0; k < 3; k++) TR[3 * NPR + k] = k < nr ? (u32)r[k] : 0;
    for (int k = 0; k < nr; k++)                /* self-check */
      if ((mulm(36, powm(r[k], 3, i), i) + i - 19 % i) % i != 0) { fprintf(stderr, "root error p=%llu\n", (u64)i); exit(2); }
    NPR++;
  }
  free(comp);
}

/* ------------------------------------------------------------------ */
/* per-n search                                                        */
/* ------------------------------------------------------------------ */
#define MAXF 24
#define MAXD (1 << 20)
static u128 fprimes[MAXF]; static int fexp[MAXF]; static int nfac;
static u128 *dv1, *cf1, *dv2, *cf2;
static double *dvd1, *cfd1, *dvd2, *cfd2;
static long long CAP = 4000000;
static long RHOBUDGET = 0;   /* extra rho after ECM failure (normally unused) */
static unsigned rseed = 1234567u;
static int DO_INT = 1, DO_HALF = 1;
static long long PAIRS = 0, HITS = 0;

static void pr_i128(i128 v) {
  char b[64]; int i = 0;
  if (v < 0) { putchar('-'); v = -v; }
  if (!v) { putchar('0'); return; }
  while (v) { b[i++] = '0' + (int)(v % 10); v /= 10; }
  while (i) putchar(b[--i]);
}

/* unique positive root of a y^3 + b y = z (a, b, z > 0) */
static inline double mono_root(double a, double b, double z) {
  double p = b / a, q = z / (2.0 * a);
  double D = sqrt(q * q + p * p * p / 27.0);
  double u = cbrt(q + D);
  double y = u - p / (3.0 * u);
  for (int it = 0; it < 2; it++) { double f = (a * y * y + b) * y - z, fp = 3.0 * a * y * y + b; y -= f / fp; }
  return y;
}

/* real roots of c3 y^3 + c1 y + c0 = 0 */
static int cubic_roots(double c3, double c1, double c0, double *out) {
  double p = c1 / c3, q = c0 / c3;
  double disc = -4.0 * p * p * p - 27.0 * q * q;
  int cnt = 0;
  if (disc < 0) {
    double t = q * q / 4.0 + p * p * p / 27.0, sq = sqrt(t);
    out[cnt++] = cbrt(-q / 2.0 + sq) + cbrt(-q / 2.0 - sq);
  } else {
    double m = 2.0 * sqrt(-p / 3.0), arg = 3.0 * q / (p * m);
    if (arg > 1.0) arg = 1.0;
    if (arg < -1.0) arg = -1.0;
    double th = acos(arg) / 3.0;
    for (int k = 0; k < 3; k++) out[cnt++] = m * cos(th - 2.0 * 3.14159265358979323846 * k / 3.0);
  }
  for (int k = 0; k < cnt; k++) {
    double y = out[k];
    for (int it = 0; it < 3; it++) { double f = ((c3 * y) * y + c1) * y + c0, fp = 3.0 * c3 * y * y + c1; if (fp != 0.0) y -= f / fp; }
    out[k] = y;
  }
  return cnt;
}

/* accept y iff 2e(sigma e y^3 + c1 n y) == dif (mod 2^128) and the magnitudes agree */
static inline void try_y(ll n, int half, int sigma, u128 e128, double ed, i128 y,
                         u128 dif128, double difd, double xmaxd) {
  if (y < 1) return;
  if (half && !(y & 1)) return;              /* X odd needs y odd (e is odd) */
  double yd = (double)y;
  if (ed * yd * yd > xmaxd) return;
  u128 yy = (u128)y;
  u128 se = sigma > 0 ? e128 : (u128)0 - e128;
  u128 c1n = (u128)((i128)(half ? 12 : 6) * (i128)n);
  u128 lhs = (u128)2 * e128 * (se * yy * yy * yy + c1n * yy);
  if (lhs != dif128) return;
  double lhsd = 2.0 * ed * ((sigma > 0 ? ed : -ed) * yd * yd * yd + (half ? 12.0 : 6.0) * (double)n * yd);
  double sc = fabs(difd) + fabs(lhsd) + 1.0;
  if (fabs(lhsd - difd) > 1e-6 * sc) return;
  i128 X = (i128)(se * yy * yy);
  printf("HIT %s %lld ", half ? "half" : "int", n);
  pr_i128(X);
  putchar('\n');
  fflush(stdout);
  HITS++;
}

static void solve_pair(ll n, int half, int sigma, u128 e, double ed, double ymaxd, double xmaxd,
                       u128 g128, u128 h128, double gd, double hd, double difmaxd) {
  double difd = hd - gd;
  if (difd > difmaxd || difd < -difmaxd) return;
  PAIRS++;
  u128 dif128 = h128 - g128;
  if (fabs(gd) < 4.2e37 && fabs(hd) < 4.2e37) difd = (double)(i128)dif128;  /* exact there */
  double zd = difd / (2.0 * ed);
  double a = sigma > 0 ? ed : -ed, b = (half ? 12.0 : 6.0) * (double)n;
  if (b == 0.0 || (a > 0) == (b > 0)) {
    if ((zd > 0) != (a > 0)) return;
    double y = (b == 0.0) ? cbrt(fabs(zd) / fabs(a)) : mono_root(fabs(a), fabs(b), fabs(zd));
    if (b == 0.0) { double f = fabs(a) * y * y * y - fabs(zd); y -= f / (3.0 * fabs(a) * y * y + 1e-300); }
    if (y < -2.0 || y > ymaxd + 3.0) return;
    i128 y0 = (i128)(y + 0.5);
    for (int dy = -2; dy <= 2; dy++) try_y(n, half, sigma, e, ed, y0 + dy, dif128, difd, xmaxd);
  } else {
    double rts[3];
    int nr = cubic_roots(a, b, -zd, rts);
    for (int ri = 0; ri < nr; ri++) {
      double y = rts[ri];
      if (y < -2.0 || y > ymaxd + 3.0) continue;
      i128 y0 = (i128)(y + 0.5);
      for (int dy = -2; dy <= 2; dy++) try_y(n, half, sigma, e, ed, y0 + dy, dif128, difd, xmaxd);
    }
  }
}

/* Nabs = |36n^3 - 19|, factored in fprimes/fexp (all odd primes) */
static void process(ll n, u128 Nabs, int Nneg) {
  long long tot = 1;
  for (int i = 0; i < nfac; i++) tot *= (2 * fexp[i] + 3);
  if (DO_INT && DO_HALF) tot *= 3;
  else if (DO_HALF) tot *= 2;
  if (tot > CAP) { printf("SKIP %lld %lld\n", n, tot); fflush(stdout); return; }
  double nad = fabs((double)n), Nd = (double)Nabs;

  for (int half = 0; half <= 1; half++) {
    if (half ? !DO_HALF : !DO_INT) continue;
    double xmaxd = half ? 12.0 * nad + cbrt(16.0 * Nd * Nd) : 6.0 * nad + cbrt(Nd * Nd);
    xmaxd = xmaxd * (1.0 + 1e-9) + 16.0;
    double c1 = half ? 12.0 : 6.0;
    for (int mask = 0; mask < (1 << nfac); mask++) {
      u128 e = 1; double ed = 1.0; int ok = 1;
      for (int i = 0; i < nfac; i++) if (mask >> i & 1) {
        ed *= (double)fprimes[i];
        if (ed > xmaxd) { ok = 0; break; }
        e *= fprimes[i];
      }
      if (!ok) continue;
      double ymaxd = sqrt(xmaxd / ed);
      double zmaxd = ymaxd * (xmaxd + c1 * nad) + 4.0;
      double difmaxd = 2.0 * ed * zmaxd * 1.000001 + 16.0;

      /* divisors (dv, cf) of e*Nabs with dv*cf = e*Nabs; exact mod 2^128 + doubles */
      int nd = 1, overflow = 0;
      u128 *dv = dv1, *cf = cf1, *dvo = dv2, *cfo = cf2;
      double *dvd = dvd1, *cfd = cfd1, *dvdo = dvd2, *cfdo = cfd2;
      dv[0] = 1; cf[0] = 1; dvd[0] = 1.0; cfd[0] = 1.0;
      for (int i = 0; i < nfac && !overflow; i++) {
        int ex = fexp[i] + ((mask >> i) & 1);
        u128 p = fprimes[i]; double pd = (double)p;
        u128 pw[130]; double pwd[130];
        pw[0] = 1; pwd[0] = 1.0;
        for (int k = 1; k <= ex; k++) { pw[k] = pw[k - 1] * p; pwd[k] = pwd[k - 1] * pd; }
        int nn = 0;
        for (int j = 0; j < nd && !overflow; j++)
          for (int k = 0; k <= ex; k++) {
            if (nn >= MAXD) { overflow = 1; break; }
            dvo[nn] = dv[j] * pw[k];      dvdo[nn] = dvd[j] * pwd[k];
            cfo[nn] = cf[j] * pw[ex - k]; cfdo[nn] = cfd[j] * pwd[ex - k];
            nn++;
          }
        nd = nn;
        u128 *t1 = dv; dv = dvo; dvo = t1;  u128 *t2 = cf; cf = cfo; cfo = t2;
        double *t3 = dvd; dvd = dvdo; dvdo = t3;  double *t4 = cfd; cfd = cfdo; cfdo = t4;
      }
      if (overflow) { printf("SKIP %lld divisors\n", n); fflush(stdout); return; }

      for (int di = 0; di < nd; di++) {
        double dd = dvd[di], cd = cfd[di];
        /* (g,h) and (-h,-g) give the same y: keep the half with |odd part of g| <= |odd part of h| */
        if (dd > cd * (1.0 + 1e-12)) continue;
        u128 d128 = dv[di], c128 = cf[di];
        for (int so = 0; so < 2; so++) {
          int sigma = so ? -1 : 1;
          int Psign = (Nneg ? -1 : 1) * sigma;           /* sign of sigma e N */
          for (int sg = 0; sg < 2; sg++) {
            int gs = sg ? -1 : 1, hs = gs * Psign;        /* g' = gs*d, h' = hs*c, g'h' = sigma e N */
            u128 gp = gs > 0 ? d128 : (u128)0 - d128;
            u128 hp = hs > 0 ? c128 : (u128)0 - c128;
            double gpd = gs * dd, hpd = hs * cd;
            if (!half) {
              solve_pair(n, 0, sigma, e, ed, ymaxd, xmaxd, gp, hp, gpd, hpd, difmaxd);
            } else {
              /* g = 2 g', h = 4 h'   and   g = 4 g', h = 2 h' */
              solve_pair(n, 1, sigma, e, ed, ymaxd, xmaxd, gp * 2, hp * 4, gpd * 2, hpd * 4, difmaxd);
              solve_pair(n, 1, sigma, e, ed, ymaxd, xmaxd, gp * 4, hp * 2, gpd * 4, hpd * 2, difmaxd);
            }
          }
        }
      }
    }
  }
}

/* ------------------------------------------------------------------ */
/* factoring                                                           */
/* ------------------------------------------------------------------ */
static long long NOPAQUE = 0;

static u128 absN(ll n, int *neg) {
  u128 na = (u128)(n < 0 ? -(i128)n : (i128)n);
  u128 v = (u128)36 * na * na * na;
  if (n >= 0) { if (v >= 19) { *neg = 0; return v - 19; } *neg = 1; return 19 - v; }
  *neg = 1; return v + 19;
}

/* ---- complete factorisation of the sieve cofactor (all its primes exceed the sieve
   bound P): C < P^2 => prime; else Miller-Rabin, a short Brent-rho, then GMP-ECM with
   growing B1.  Only if ECM also fails (never observed) is the part kept opaque. ---- */
static double SIEVE_P = 0;
static long ECM_MAXCURVES = 3000;
static long long NECM = 0;
static long RHO1 = 20000;
static double B2MULT = 0;   /* 0: GMP-ECM default B2; else B2 = B2MULT * B1 */
static double ECMB1 = 2000;

static u128 mpz_to_u128(const mpz_t z) {
  u128 lo = mpz_getlimbn(z, 0), hi = mpz_size(z) > 1 ? mpz_getlimbn(z, 1) : 0;
  return (hi << 64) | lo;
}
static void u128_to_mpz(mpz_t z, u128 v) {
  mpz_set_ui(z, (unsigned long)(v >> 64)); mpz_mul_2exp(z, z, 64); mpz_add_ui(z, z, (unsigned long)(u64)v);
}

static u128 ecm_split(u128 C) {
  mpz_t n, f; mpz_init(n); mpz_init(f); u128_to_mpz(n, C);
  u128 res = 0;
  for (long k = 0; k < ECM_MAXCURVES && !res; k++) {
    double B1 = k < 40 ? ECMB1 : k < 200 ? 5.5 * ECMB1 : k < 800 ? 25 * ECMB1 : 125 * ECMB1;
    ecm_params q; ecm_init(q);
    mpz_set_ui(q->sigma, 0);   /* random curve */
    if (B2MULT > 0) mpz_set_d(q->B2, B2MULT * B1);
    NECM++;
    int r = ecm_factor(f, n, B1, q);
    ecm_clear(q);
    if (r > 0 && mpz_cmp_ui(f, 1) > 0 && mpz_cmp(f, n) < 0) res = mpz_to_u128(f);
  }
  mpz_clear(n); mpz_clear(f);
  return res;
}

static int add_prime(u128 p, int e) {
  for (int i = 0; i < nfac; i++) if (fprimes[i] == p) { fexp[i] += e; return 1; }
  if (nfac >= MAXF) return 0;
  fprimes[nfac] = p; fexp[nfac] = e; nfac++;
  return 1;
}

/* returns 0 on failure (too many factors); *opq set if a part stayed unsplit */
static int factor_rec(u128 C, int *opq) {
  if (C <= 1) return 1;
  if ((double)C < SIEVE_P * SIEVE_P || isprime128(C)) return add_prime(C, 1);
  u128 d = RHO1 > 0 ? rho128(C, RHO1, &rseed) : 0;
  if (!d) d = ecm_split(C);
  if (!d && RHOBUDGET > 0) d = rho128(C, RHOBUDGET, &rseed);
  if (!d) { *opq = 1; return add_prime(C, 1); }
  return factor_rec(d, opq) && factor_rec(C / d, opq);
}

static int split_cofactor(ll n, u128 C) {
  int opq = 0;
  if (!factor_rec(C, &opq)) return 0;
  if (opq) { NOPAQUE++; printf("OPAQUE %lld\n", n); fflush(stdout); }
  return 1;
}

static void factor_and_process_single(ll n) {
  int neg; u128 Nabs = absN(n, &neg), rem = Nabs;
  nfac = 0;
  ll na = n < 0 ? -n : n;
  for (int j = 0; j < NPR; j++) {
    u32 p = TP[j], r = (u32)(na % p);
    int hit = 0;
    for (u32 k = 0; k < TNR[j]; k++) {
      u32 t = n >= 0 ? TR[3 * j + k] : (TR[3 * j + k] ? p - TR[3 * j + k] : 0);
      if (r == t) { hit = 1; break; }
    }
    if (!hit || rem % p) continue;
    int ex = 0; do { rem /= p; ex++; } while (rem % p == 0);
    if (nfac >= MAXF) { printf("SKIP %lld factors\n", n); return; }
    fprimes[nfac] = p; fexp[nfac] = ex; nfac++;
  }
  if (!split_cofactor(n, rem)) { printf("SKIP %lld factors\n", n); return; }
  process(n, Nabs, neg);
}

/* u128 divided by a 32-bit p with 64-bit hardware divisions (no __umodti3 libcall) */
static inline u128 divmod32(u128 v, u32 p, u32 *rem) {
  u64 hi = (u64)(v >> 64), lo = (u64)v;
  u64 qh = hi / p, r = hi % p;
  u64 t = (r << 32) | (lo >> 32);      u64 q1 = t / p; r = t % p;
  t = (r << 32) | (lo & 0xffffffffu);  u64 q0 = t / p; r = t % p;
  *rem = (u32)r;
  return ((u128)qh << 64) | ((u128)q1 << 32) | q0;
}

/* block sieve over |n| in [lo, hi] with sign sgn */
static ll BLK = 1 << 18;
static u128 *rem_;
static u32 (*fp_)[MAXF];
static unsigned char (*fe_)[MAXF];
static unsigned char *fc_;

static void sieve_range(ll lo, ll hi, int sgn) {
  for (ll base = lo; base <= hi; base += BLK) {
    ll len = hi - base + 1; if (len > BLK) len = BLK;
    long long p0 = PAIRS;
    for (ll i = 0; i < len; i++) {
      int neg; ll n = sgn > 0 ? base + i : -(base + i);
      rem_[i] = absN(n, &neg); fc_[i] = 0;
    }
    for (int j = 0; j < NPR; j++) {
      u32 p = TP[j];
      for (u32 k = 0; k < TNR[j]; k++) {
        u32 r = TR[3 * j + k];
        u32 t = sgn > 0 ? r : (r ? p - r : 0);
        ll start = ((ll)t - base) % (ll)p; if (start < 0) start += p;
        for (ll i = start; i < len; i += p) {
          u32 rr; u128 q = divmod32(rem_[i], p, &rr);
          if (rr) continue;                /* cannot happen (p | N here); kept for safety */
          int ex = 0;
          do { rem_[i] = q; ex++; q = divmod32(rem_[i], p, &rr); } while (rr == 0);
          unsigned char c = fc_[i];
          if (c < MAXF) { fp_[i][c] = p; fe_[i][c] = ex; fc_[i] = c + 1; } else fc_[i] = MAXF + 1;
        }
      }
    }
    for (ll i = 0; i < len; i++) {
      ll n = sgn > 0 ? base + i : -(base + i);
      if (fc_[i] > MAXF) { printf("SKIP %lld factors\n", n); continue; }
      nfac = 0;
      for (int c = 0; c < fc_[i]; c++) { fprimes[nfac] = fp_[i][c]; fexp[nfac] = fe_[i][c]; nfac++; }
      if (!split_cofactor(n, rem_[i])) { printf("SKIP %lld factors\n", n); continue; }
      int neg; u128 Nabs = absN(n, &neg);
      process(n, Nabs, neg);
    }
    ll a = sgn > 0 ? base : -(base + len - 1), b = sgn > 0 ? base + len - 1 : -base;
    printf("DONE %lld %lld %lld\n", a, b, PAIRS - p0);
    fflush(stdout);
  }
}

static int selftest(void) {
  /* cube roots against brute force for all primes < 3000 */
  for (u32 j = 0; j < (u32)NPR && TP[j] < 3000; j++) {
    u32 p = TP[j]; int cnt = 0;
    for (u32 r = 0; r < p; r++) if ((36ull * r % p * r % p * r + p * 20 - 19) % p == 0) cnt++;
    if (cnt != (int)TNR[j]) { fprintf(stderr, "selftest: p=%u roots %u vs %d\n", p, TNR[j], cnt); return 1; }
  }
  fprintf(stderr, "selftest: cube roots OK\n");
  return 0;
}

int main(int argc, char **argv) {
  ll n0 = 0, n1 = -1; const char *list = NULL; u32 PMAX = 1u << 24; int st = 0;
  for (int i = 1; i < argc; i++) {
    const char *a = argv[i]; const char *v = i + 1 < argc ? argv[i + 1] : NULL;
    if (!strcmp(a, "--n0") && v) { n0 = atoll(v); i++; }
    else if (!strcmp(a, "--n1") && v) { n1 = atoll(v); i++; }
    else if (!strcmp(a, "--list") && v) { list = v; i++; }
    else if (!strcmp(a, "--sieve") && v) { PMAX = (u32)atoll(v); i++; }
    else if (!strcmp(a, "--rho") && v) { RHOBUDGET = atol(v); i++; }
    else if (!strcmp(a, "--rho1") && v) { RHO1 = atol(v); i++; }
    else if (!strcmp(a, "--b2mult") && v) { B2MULT = atof(v); i++; }
    else if (!strcmp(a, "--ecm-b1") && v) { ECMB1 = atof(v); i++; }
    else if (!strcmp(a, "--cap") && v) { CAP = atoll(v); i++; }
    else if (!strcmp(a, "--block") && v) { BLK = atoll(v); i++; }
    else if (!strcmp(a, "--chart") && v) {
      DO_INT = !strcmp(v, "both") || !strcmp(v, "int");
      DO_HALF = !strcmp(v, "both") || !strcmp(v, "half");
      if (!DO_INT && !DO_HALF) { fprintf(stderr, "bad --chart\n"); return 1; }
      i++;
    }
    else if (!strcmp(a, "--selftest")) st = 1;
    else { fprintf(stderr, "usage: %s --n0 A --n1 B [--chart both|int|half] [--sieve P] [--rho R] [--cap C] [--block K]\n"
                           "       %s --list FILE [options]   |   %s --selftest\n", argv[0], argv[0], argv[0]); return 1; }
  }
  if (n0 < -(1LL << 40) || n1 > (1LL << 40)) { fprintf(stderr, "|n| must be < 2^40 (36n^3 < 2^126)\n"); return 1; }
  if (PMAX < 1000) PMAX = 1000;
  build_roots(PMAX);
  SIEVE_P = (double)PMAX;
  if (st) return selftest();
  dv1 = malloc(MAXD * sizeof(u128)); cf1 = malloc(MAXD * sizeof(u128));
  dv2 = malloc(MAXD * sizeof(u128)); cf2 = malloc(MAXD * sizeof(u128));
  dvd1 = malloc(MAXD * sizeof(double)); cfd1 = malloc(MAXD * sizeof(double));
  dvd2 = malloc(MAXD * sizeof(double)); cfd2 = malloc(MAXD * sizeof(double));
  if (list) {
    FILE *f = fopen(list, "r");
    if (!f) { fprintf(stderr, "cannot open %s\n", list); return 1; }
    ll n;
    while (fscanf(f, "%lld", &n) == 1) {
      long long p0 = PAIRS;
      factor_and_process_single(n);
      printf("DONE %lld %lld %lld\n", n, n, PAIRS - p0); fflush(stdout);
    }
    fclose(f);
  } else {
    rem_ = malloc(BLK * sizeof(u128)); fc_ = malloc(BLK);
    fp_ = malloc(BLK * sizeof(*fp_)); fe_ = malloc(BLK * sizeof(*fe_));
    /* negative part from the side nearest 0 outward, then the non-negative part */
    if (n0 < 0) { ll hi = -n0, lo = n1 < 0 ? -n1 : 1; sieve_range(lo, hi, -1); }
    if (n1 >= 0) { ll lo = n0 > 0 ? n0 : 0; sieve_range(lo, n1, +1); }
  }
  fprintf(stderr, "finished: hits=%lld pairs=%lld opaque=%lld ecm_curves=%lld\n", HITS, PAIRS, NOPAQUE, NECM);
  return 0;
}
