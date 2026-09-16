/* search_u2.c -- search for integer solutions (n,x) of
       V = x^2 (x+6n)^2 + x (36 n^3 - 19)  = perfect square
   by enumerating the parameter U = 2 d x^2 = t - x(x+6n).

   Mathematics.  With A = 36n^3-19, s = x+6n, t^2 = x^2 s^2 + xA and U = t - xs,

       U^2 + 2 U x s = x A ,                                        (1)

   so x | U^2 and, solving (1) for A,

       36 n^3 - 12 U n - 19 - 2 U x - U^2/x = 0 .                   (2)

   Hence for every integer U and every (signed) divisor x of U^2, (2) is a cubic
   in n whose integer roots give all solutions with that U -- *for every n, of
   any size*.  This complements the search over n (search_xl.c): a solution is
   reached here as soon as one of its two roots U, U' = -U-2xs is small, which
   happens exactly when |x| is large compared with n (U ~ 18n^3/x for |x| >> n).

   usage: ./search_u2 <Ulo> <Uhi> [block]                                      */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <stdint.h>

typedef unsigned __int128 u128;
typedef __int128 i128;
typedef unsigned long long u64;
typedef long long ll;

/* ---------- small primes ---------- */
static int *sp; static int nsp;
static void gen_primes(int lim) {
  char *c = calloc(lim+1, 1);
  sp = malloc((lim/10+1000)*sizeof(int)); nsp = 0;
  for (int i = 2; i <= lim; i++)
    if (!c[i]) { sp[nsp++] = i; for (long j = (long)i*i; j <= lim; j += i) c[j] = 1; }
  free(c);
}

/* ---------- 64-bit primality / rho for the block leftovers ---------- */
static u64 mulmod64(u64 a, u64 b, u64 m) { return (u64)((u128)a*b % m); }
static u64 powmod64(u64 a, u64 e, u64 m) { u64 r = 1; a %= m; while (e) { if (e&1) r = mulmod64(r,a,m); a = mulmod64(a,a,m); e >>= 1; } return r; }
static int isprime64(u64 n) {
  if (n < 2) return 0;
  static const u64 s[12] = {2,3,5,7,11,13,17,19,23,29,31,37};
  for (int i = 0; i < 12; i++) if (n % s[i] == 0) return n == s[i];
  u64 d = n-1; int r = 0; while (!(d&1)) { d >>= 1; r++; }
  for (int i = 0; i < 12; i++) {
    u64 x = powmod64(s[i], d, n);
    if (x == 1 || x == n-1) continue;
    int ok = 0;
    for (int j = 1; j < r; j++) { x = mulmod64(x,x,n); if (x == n-1) { ok = 1; break; } }
    if (!ok) return 0;
  }
  return 1;
}
static u64 gcd64(u64 a, u64 b) { while (b) { u64 t = a % b; a = b; b = t; } return a; }
static u64 rho64(u64 n) {
  if (!(n&1)) return 2;
  static unsigned sd = 24681357u;
  for (;;) {
    sd = sd*1103515245u + 12345u;
    u64 c = sd % 1000 + 1, x = sd % 997 + 2, y = x, d = 1;
    do {
      x = (mulmod64(x,x,n)+c) % n;
      y = (mulmod64(y,y,n)+c) % n; y = (mulmod64(y,y,n)+c) % n;
      u64 diff = x > y ? x-y : y-x;
      if (!diff) { d = n; break; }
      d = gcd64(diff, n);
    } while (d == 1);
    if (d != n) return d;
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

/* ---------- cubic 36 n^3 - 12 U n - C = 0 ---------- */
static int cubic_roots(double c3, double c1, double c0, double *out) {
  double p = c1/c3, q = c0/c3;
  double disc = -4.0*p*p*p - 27.0*q*q;
  int cnt = 0;
  if (disc < 0) {
    double t = q*q/4.0 + p*p*p/27.0;
    double sq = sqrt(t);
    double a = -q/2.0 + sq, b = -q/2.0 - sq;
    out[cnt++] = cbrt(a) + cbrt(b);
  } else {
    double m = 2.0*sqrt(-p/3.0);
    double arg = 3.0*q/(p*m);
    if (arg > 1.0) arg = 1.0;
    if (arg < -1.0) arg = -1.0;
    double th = acos(arg)/3.0;
    for (int k = 0; k < 3; k++) out[cnt++] = m*cos(th - 2.0*3.14159265358979323846*k/3.0);
  }
  for (int k = 0; k < cnt; k++) {
    double y = out[k];
    for (int it = 0; it < 3; it++) {
      double f = ((c3*y)*y + c1)*y + c0, fp = 3.0*c3*y*y + c1;
      if (fp != 0.0) y -= f/fp;
    }
    out[k] = y;
  }
  return cnt;
}

#define MAXD (1<<17)
static i128 divs[MAXD];
static long long SOLCNT = 0;

static void report(ll n, i128 x, ll U) {
  printf("SOL n=%lld x=", n); pr_i128(x);
  printf(" U=%lld\n", U); fflush(stdout);
  SOLCNT++;
}

int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "usage: %s Ulo Uhi [block]\n", argv[0]); return 1; }
  ll ULO = atoll(argv[1]), UHI = atoll(argv[2]);
  long BLK = argc > 3 ? atol(argv[3]) : 1000000;
  int PLIM = (int)(sqrt((double)UHI) + 2);
  if (PLIM < 100) PLIM = 100;
  gen_primes(PLIM);
  fprintf(stderr, "%d primes up to %d\n", nsp, PLIM);

  u64 *rem = malloc(BLK*sizeof(u64));
  unsigned *fp = malloc(BLK*16*sizeof(unsigned));
  unsigned char *fe = malloc(BLK*16);
  unsigned char *fc = malloc(BLK);

  for (ll base = ULO; base <= UHI; base += BLK) {
    long len = (UHI - base + 1 < BLK) ? (long)(UHI - base + 1) : BLK;
    for (long i = 0; i < len; i++) { rem[i] = (u64)(base + i); fc[i] = 0; }
    for (int j = 0; j < nsp; j++) {
      u64 p = sp[j];
      if (p > (u64)(base + len - 1)) break;
      ll start = (ll)((p - (u64)base % p) % p);
      for (long i = start; i < len; i += p) {
        if (rem[i] % p) continue;
        int e = 0;
        do { rem[i] /= p; e++; } while (rem[i] % p == 0);
        unsigned char c = fc[i];
        if (c < 16) { fp[i*16+c] = (unsigned)p; fe[i*16+c] = e; fc[i] = c+1; }
      }
    }
    for (long i = 0; i < len; i++) {
      ll Uabs = base + i;
      if (Uabs < 1) continue;
      /* assemble the complete factorisation of |U| */
      u64 pp[20]; int ee[20]; int nf = 0;
      for (int c = 0; c < fc[i]; c++) { pp[nf] = fp[i*16+c]; ee[nf] = fe[i*16+c]; nf++; }
      u64 left = rem[i];
      if (left > 1) {
        if (isprime64(left)) { pp[nf] = left; ee[nf] = 1; nf++; }
        else {
          u64 f = rho64(left), g = left/f;
          if (f == g) { pp[nf] = f; ee[nf] = 2; nf++; }
          else { pp[nf] = f; ee[nf] = 1; nf++; pp[nf] = g; ee[nf] = 1; nf++; }
        }
      }
      /* all divisors of U^2 */
      int nd = 1; divs[0] = 1; int ok = 1;
      for (int j = 0; j < nf && ok; j++) {
        int e2 = 2*ee[j];
        int cur = nd; i128 pk = 1;
        for (int k = 1; k <= e2 && ok; k++) {
          pk *= (i128)pp[j];
          for (int t = 0; t < cur; t++) {
            if (nd >= MAXD) { ok = 0; break; }
            divs[nd++] = divs[t]*pk;
          }
        }
      }
      if (!ok) { fprintf(stderr, "too many divisors U=%lld\n", Uabs); continue; }

      i128 U2 = (i128)Uabs*(i128)Uabs;
      for (int di = 0; di < nd; di++) {
        i128 xa = divs[di];
        i128 comp = U2/xa;                   /* U^2/|x| */
        for (int su = 0; su < 2; su++) {
          i128 U = su ? -(i128)Uabs : (i128)Uabs;
          for (int sx = 0; sx < 2; sx++) {
            i128 x = sx ? -xa : xa;
            i128 C = 19 + 2*U*x + (sx ? -comp : comp);
            double roots[3];
            int nr = cubic_roots(36.0, -12.0*(double)U, -(double)C, roots);
            for (int r = 0; r < nr; r++) {
              double rv = roots[r];
              if (!(rv > -5e15 && rv < 5e15)) continue;
              i128 n0 = (i128)(rv >= 0 ? rv + 0.5 : rv - 0.5);
              for (int dn = -1; dn <= 1; dn++) {
                i128 n = n0 + dn;
                if (36*n*n*n - 12*U*n - C == 0) report((ll)n, x, (ll)U);
              }
            }
          }
        }
      }
    }
    fprintf(stderr, "U=%lld\n", base + len - 1); fflush(stderr);
  }
  fprintf(stderr, "done, %lld hits\n", SOLCNT);
  return 0;
}
