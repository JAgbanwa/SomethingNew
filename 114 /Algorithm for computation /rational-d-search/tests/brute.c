/* brute.c -- independent reference: for every n in [n0,n1] and EVERY nonzero
   integer X with |X| <= 12|n| + (16 N^2)^(1/3) + 16 (which contains both charts'
   proven bounds), test whether F = X^2 (X+12n)^2 + 8 X N is a perfect square,
   N = 36n^3 - 19.  Prints "HIT int n x" (X even, x = X/2) or "HIT half n X".
   Exact 128-bit arithmetic; |n| <= 2000.                                    */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
typedef __int128 i128;
static int issq(i128 v, i128 *r) {
  if (v < 0) return 0;
  long double s = sqrtl((long double)v);
  i128 t = (i128)s;
  while (t * t > v) t--;
  while ((t + 1) * (t + 1) <= v) t++;
  *r = t; return t * t == v;
}
int main(int argc, char **argv) {
  long long n0 = atoll(argv[1]), n1 = atoll(argv[2]);
  static unsigned char q64[64], q63[63], q65[65], q11[11];
  for (int i = 0; i < 64; i++) q64[i * i % 64] = 1;
  for (int i = 0; i < 63; i++) q63[i * i % 63] = 1;
  for (int i = 0; i < 65; i++) q65[i * i % 65] = 1;
  for (int i = 0; i < 11; i++) q11[i * i % 11] = 1;
  for (long long n = n0; n <= n1; n++) {
    i128 N = (i128)36 * n * n * n - 19;
    double Nd = fabs((double)N);
    long long XM = (long long)(12.0 * fabs((double)n) + cbrt(16.0 * Nd * Nd) + 16.0);
    for (long long X = -XM; X <= XM; X++) {
      if (!X) continue;
      i128 S = X + 12 * (i128)n;
      i128 F = (i128)X * X * S * S + 8 * (i128)X * N;
      if (F < 0) continue;
      if (!q64[(int)(F % 64)] || !q63[(int)(F % 63)] || !q65[(int)(F % 65)] || !q11[(int)(F % 11)]) continue;
      i128 r;
      if (!issq(F, &r)) continue;
      if (X % 2 == 0) printf("HIT int %lld %lld\n", n, X / 2);
      else printf("HIT half %lld %lld\n", n, X);
    }
  }
  return 0;
}
