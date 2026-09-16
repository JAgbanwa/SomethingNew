/* facstat.c -- how much of the divisor structure of A = 36n^3-19 does a sieve
   with primes <= 3e7 actually see?  Compares tot = prod(2a+3) computed from the
   full factorisation with the value the sieve sees (all unsieved primes lumped
   into one opaque factor).  Also times the extra factoring work.
   usage: ./facstat <nlo> <count> <sign> <budget>                              */
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "fac128.h"

typedef unsigned __int128 u128;

static int *small;   /* primes up to 3e7 */
static int nsmall;

static void gen_small(int lim) {
  char *c = calloc(lim+1, 1);
  small = malloc(2000000*sizeof(int)); nsmall = 0;
  for (int i = 2; i <= lim; i++) {
    if (!c[i]) { small[nsmall++] = i; for (long j = (long)i*i; j <= lim; j += i) c[j] = 1; }
  }
  free(c);
}

int main(int argc, char **argv) {
  long long nlo = atoll(argv[1]);
  long cnt = atol(argv[2]);
  int sgn = atoi(argv[3]);
  long budget = atol(argv[4]);
  gen_small(30000000);
  fprintf(stderr, "%d small primes\n", nsmall);
  unsigned seed = 987654321u;
  double tot_full = 0, tot_sieve = 0;
  long nopaque = 0, nbig2 = 0;
  clock_t t0 = clock();
  for (long i = 0; i < cnt; i++) {
    long long n = nlo + i*7919;          /* spread out samples */
    u128 na = (u128)n;
    u128 A = (u128)36*na*na*na;
    A = sgn > 0 ? A - 19 : A + 19;
    u128 rem = A;
    double tf = 1, ts = 1;
    for (int j = 0; j < nsmall; j++) {
      u128 p = small[j];
      if (p*p > rem) break;
      if (rem % p == 0) { int e = 0; while (rem % p == 0) { rem /= p; e++; } tf *= (2*e+3); ts *= (2*e+3); }
    }
    if (rem > 1) {
      ts *= 5;                            /* sieve: one opaque factor */
      u128 fp[32]; int fe[32]; int nf = 0; int opq = 0;
      for (int j = 0; j < 32; j++) fe[j] = 0;
      factor128(rem, budget, &seed, fp, fe, &nf, 32, &opq);
      for (int j = 0; j < nf; j++) tf *= (2*fe[j]+3);
      if (opq) nopaque++;
      if (nf >= 2) nbig2++;
    }
    tot_full += tf; tot_sieve += ts;
  }
  double secs = (double)(clock()-t0)/CLOCKS_PER_SEC;
  printf("n~%lld sign=%d: %ld samples, %.2f s (%.3f ms/n), %ld with >=2 large primes, %ld unresolved\n",
         nlo, sgn, cnt, secs, 1000.0*secs/cnt, nbig2, nopaque);
  printf("   combos seen by the sieve = %.1f%% of the full count\n", 100.0*tot_sieve/tot_full);
  return 0;
}
