/* Sieve-accelerated exhaustive search for integer solutions (n,x) of
       V = x^2 (x+6n)^2 + x (36 n^3 - 19)  = perfect square.

   Same mathematics as search_div.c (write x = sigma*e*y^2 with e squarefree,
   e | A = 36n^3-19; then A*e = g*h with h-g = 2*e*y*(x+6n), and y solves the
   cubic sigma*e*y^3 + 6n y = (h-g)/(2e)), but the factorisation of A is obtained
   by a *line sieve* over blocks of n instead of by factoring each A separately:
   for a prime p, p | 36n^3-19 iff n is one of the (at most three) roots of
   36X^3 = 19 (mod p), which are precomputed once in roots.bin.

   The unfactored part of A left after sieving with all primes <= PMAX is used as
   a single opaque factor (it is genuinely prime when it is < PMAX^2).  Solutions
   whose divisor pair needs that part split are therefore missed: the search is
   thorough but, for large n, no longer provably exhaustive.  Every hit that is
   printed is re-verified exactly.

   usage:  ./search_sv <na_lo> <na_hi> <sign> [roots.bin]
*/
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "u128.h"

typedef __int128 i128;
typedef long long ll;
typedef uint32_t u32;

/* ---------- root table ---------- */
static u32 *TP, *TNR, *TR;      /* prime, #roots, roots[3] */
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

/* ---------- 64-bit primality / rho (to split the sieve cofactor) ---------- */
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

/* Montgomery arithmetic mod odd n (64 bit) */
typedef struct { u64 n, ninv, r2; } m64_t;
static void m64_init(m64_t *M, u64 n) {
  M->n = n;
  u64 inv = n;                      /* inv = n^{-1} mod 2^64 by Newton */
  for (int i = 0; i < 6; i++) inv *= 2 - n*inv;
  M->ninv = (u64)0 - inv;           /* -n^{-1} mod 2^64 */
  M->r2 = (u64)(((u128)0 - (u128)n) % n);      /* 2^64 mod n */

}
static inline u64 m64_mul(const m64_t *M, u64 a, u64 b) {
  u128 t = (u128)a*b;
  u64 m = (u64)t * M->ninv;
  u128 u = t + (u128)m * M->n;
  u64 r = (u64)(u >> 64);
  return r >= M->n ? r - M->n : r;
}
/* Brent's cycle finding with batched gcd */
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

/* ---------- cubic solver:  c3 y^3 + c1 y + c0 = 0, real roots ---------- */
static int cubic_roots(long double c3, long double c1, long double c0, long double *out) {
  long double p = c1 / c3, q = c0 / c3;
  long double disc = -4.0L*p*p*p - 27.0L*q*q;
  int cnt = 0;
  if (disc < 0) {
    long double t = q*q/4.0L + p*p*p/27.0L;
    long double sq = sqrtl(t);
    out[cnt++] = cbrtl(-q/2.0L + sq) + cbrtl(-q/2.0L - sq);
  } else {
    long double m = 2.0L*sqrtl(-p/3.0L);
    long double arg = 3.0L*q/(p*m);
    if (arg > 1.0L) arg = 1.0L;
    if (arg < -1.0L) arg = -1.0L;
    long double th = acosl(arg)/3.0L;
    for (int k = 0; k < 3; k++) out[cnt++] = m*cosl(th - 2.0L*3.14159265358979323846L*k/3.0L);
  }
  return cnt;
}

/* ---------- per-n divisor search ---------- */
#define MAXF 20
static u128 fprimes[MAXF]; static int fexp[MAXF]; static int nfac;
static u128 divs[1<<18], cofs[1<<18];
static long long CAP = 2000000;

static void process(ll n, ll na, u128 Aabs, int Aneg) {
  long long tot = 1;
  for (int i = 0; i < nfac; i++) tot *= (2*fexp[i] + 3);
  if (tot > CAP) { fprintf(stderr, "skip n=%lld tot=%lld\n", n, tot); return; }
  u128 XMAX = (u128)13*(u128)na*(u128)na + 1000000;
  /* keep e*|A| (and hence every divisor) inside 128 bits */
  u128 XCAP = ((u128)1 << 125) / Aabs;
  if (XMAX > XCAP) XMAX = XCAP;
  for (int mask = 0; mask < (1 << nfac); mask++) {
    u128 e = 1; int okE = 1;
    for (int i = 0; i < nfac; i++) if (mask >> i & 1) {
      if (e > XMAX / fprimes[i]) { okE = 0; break; }
      e *= fprimes[i];
    }
    if (!okE || e > XMAX) continue;
    long double ymax = sqrtl((long double)XMAX/(long double)e);
    long double zmax = ymax*((long double)e*ymax*ymax + 6.0L*(long double)na) + 4.0L;
    u128 Pabs = e * Aabs;
    int nd = 1; divs[0] = 1; cofs[0] = Pabs;
    for (int i = 0; i < nfac; i++) {
      int ex = fexp[i] + ((mask >> i) & 1);
      int cur = nd; u128 pk = 1;
      for (int k = 1; k <= ex; k++) {
        pk *= fprimes[i];
        for (int j = 0; j < cur; j++) {
          if (nd < (1<<18)) { divs[nd] = divs[j]*pk; cofs[nd] = cofs[j]/pk; nd++; }
        }
      }
    }
    long double difmaxl = 2.0L*(long double)e*zmax;
    for (int di = 0; di < nd; di++) {
      u128 dpos = divs[di], cpos = cofs[di];
      for (int so = 0; so < 2; so++) {
        i128 sigma = so ? -1 : 1;
        i128 Psign = (Aneg ? -1 : 1) * sigma;
        for (int sg = 0; sg < 2; sg++) {
          i128 g = sg ? -(i128)dpos : (i128)dpos;
          i128 h = (i128)cpos * ((sg ? -1 : 1) * Psign);
          i128 dif = h - g;
          long double difl = (long double)dif;
          if (difl > difmaxl || difl < -difmaxl) continue;
          if (dif & 1) continue;
          if (e > 1 && (dif % (i128)e)) continue;
          i128 z = dif/(2*(i128)e);
          long double roots[3];
          int nr = cubic_roots((long double)(sigma*(i128)e), (long double)(6*(i128)n),
                               (long double)(-z), roots);
          for (int ri = 0; ri < nr; ri++) {
            long double rv = roots[ri];
            if (!(rv > 0.5L) || rv > ymax + 2.0L) continue;
            i128 y0 = (i128)(rv + 0.5L);
            for (int dd = -1; dd <= 1; dd++) {
              i128 y = y0 + dd;
              if (y < 1) continue;
              if ((long double)y > ymax) continue;
              if (sigma*(i128)e*y*y*y + 6*(i128)n*y - z == 0) {
                i128 x = sigma*(i128)e*y*y;
                printf("SOL n=%lld x=", n); pr_i128(x);
                printf(" e="); pr_i128((i128)e);
                printf(" y="); pr_i128(y);
                printf(" g="); pr_i128(g);
                printf("\n"); fflush(stdout);
              }
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

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "usage: %s lo hi sign [roots.bin]\n", argv[0]); return 1; }
  ll NLO = atoll(argv[1]), NHI = atoll(argv[2]);
  int SGN = atoi(argv[3]);
  load_roots(argc > 4 ? argv[4] : "roots3e7.bin");
  u128 PMAX2 = (u128)TP[NPR-1]*(u128)TP[NPR-1];

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
          if (rem_[i] % p) continue;             /* safety */
          int ex = 0;
          do { rem_[i] /= p; ex++; } while (rem_[i] % p == 0);
          unsigned char c = fc_[i];
          if (c < MAXF) { fp_[i][c] = p; fe_[i][c] = ex; fc_[i] = c + 1; }
          else fc_[i] = MAXF + 1;                 /* overflow marker */
        }
      }
    }
    for (ll i = 0; i < len; i++) {
      ll na = base + i, n = SGN > 0 ? na : -na;
      if (fc_[i] > MAXF) { fprintf(stderr, "overflow n=%lld\n", n); continue; }
      nfac = 0;
      for (int c = 0; c < fc_[i]; c++) { fprimes[nfac] = fp_[i][c]; fexp[nfac] = fe_[i][c]; nfac++; }
      if (rem_[i] > 1) {
        u128 C = rem_[i];
        u128 two64 = (u128)1 << 62;   /* 64-bit Montgomery REDC needs n < 2^62 */
        long long totsm = 1;
        for (int c2 = 0; c2 < nfac; c2++) totsm *= (2*fexp[c2] + 3);
        if (C < two64 && totsm >= 25 && !isprime64((u64)C)) {
          u64 f = rho64((u64)C), h = (u64)C / f;
          if (nfac + 2 > MAXF) { fprintf(stderr, "overflow n=%lld\n", n); continue; }
          if (f == h) { fprimes[nfac] = f; fexp[nfac] = 2; nfac++; }
          else { fprimes[nfac] = f; fexp[nfac] = 1; nfac++; fprimes[nfac] = h; fexp[nfac] = 1; nfac++; }
        } else {
          if (nfac >= MAXF) { fprintf(stderr, "overflow n=%lld\n", n); continue; }
          fprimes[nfac] = C; fexp[nfac] = 1; nfac++;   /* prime, or opaque composite */
        }
      }
      u128 na2 = (u128)na, Aabs = (u128)36*na2*na2*na2;
      Aabs = SGN > 0 ? Aabs - 19 : Aabs + 19;
      process(n, na, Aabs, SGN > 0 ? 0 : 1);
    }
    fprintf(stderr, "n=%lld\n", SGN > 0 ? base + len - 1 : -(base + len - 1));
    fflush(stderr);
  }
  (void)PMAX2;
  return 0;
}
