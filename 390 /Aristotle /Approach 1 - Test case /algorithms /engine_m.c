/* engine_m.c -- ENGINE C : the divisor ("m-parameter") engine.  THE POTENT ONE.
 *
 *  Put  A = x(x+6n),  T = sqrt(A^2 + xK),  K = 36n^3-65,  and let
 *        m = T - A        (an integer, positive or negative).
 *  Then  T^2 = A^2 + xK  <=>  2Am + m^2 = xK  <=>
 *
 *        2m x^2 + (12mn - K) x + m^2 = 0.                       (Q)
 *
 *  KEY POINT: conversely, ANY integer triple (n,x,m) satisfying (Q) gives
 *  D = A^2+xK = (A+m)^2, a perfect square *automatically* -- no square test,
 *  no luck required.  So instead of hunting for squares we solve (Q).
 *
 *  (Q) has an integer root x iff its discriminant
 *        Delta = P^2 - 8 m^3,      P = 12 m n - K,
 *  is a perfect square R^2, i.e. iff
 *
 *        (P - R)(P + R) = 8 m^3.                                (F)
 *
 *  So we turn the problem inside out: pick m, FACTOR 8m^3, and let every
 *  factorisation 8m^3 = u*v with u == v (mod 2) propose
 *        P = (u+v)/2,  R = (v-u)/2.
 *  Each proposal P must then come from an actual n, i.e. n must be an integer
 *  root of the cubic
 *        36 n^3 - 12 m n + (P - 65) = 0,                        (C)
 *  which is decided in O(1) by solving the cubic in long double and checking
 *  the (at most 3) nearby integers exactly.  Finally
 *        x = ( K - 12 m n +- R ) / (4m)
 *  has to be an integer, and then (n,x) IS a solution and
 *        d = ( -A - sgn(x) |A+m| ) / (2 x^2).
 *
 *  Why this is far stronger than brute force: a modest m reaches values of
 *  |x| of size ~ m^2 and beyond (we routinely produce |x| ~ 10^12 and larger),
 *  a region containing ~10^24 (n,x) pairs that no scan could ever enumerate.
 *
 *  usage: ./engine_m mmax [stride off]
 *  output lines: "CAND n=.. x=.. m=.." (verified exactly afterwards in Python)
 */
#include "common.h"

static int *spf;              /* smallest prime factor sieve */
static long long SPFMAX;

static void sieve_spf(long long lim) {
    SPFMAX = lim;
    spf = (int*)malloc(sizeof(int) * (size_t)(lim + 1));
    for (long long i = 0; i <= lim; i++) spf[i] = 0;
    for (long long i = 2; i <= lim; i++) {
        if (!spf[i]) for (long long j = i; j <= lim; j += i) if (!spf[j]) spf[j] = (int)i;
    }
}

/* exact evaluation of the cubic (C) */
static inline i128 cubic_eval(i128 n, i128 m, i128 C) {
    return 36 * n * n * n - 12 * m * n + C;
}

/* collect integer roots of 36n^3 - 12 m n + C = 0 into r[]; returns count */
static int cubic_int_roots(i128 m, i128 C, i128 *r) {
    long double a = 36.0L, b = -12.0L * (long double)m, c = (long double)C;
    long double p = b / a, q = c / a;             /* t^3 + p t + q = 0 */
    long double cand[3]; int nc = 0;
    long double disc = -4.0L * p * p * p - 27.0L * q * q;
    if (disc < 0) {                                /* one real root */
        long double u = -q / 2.0L, w = q * q / 4.0L + p * p * p / 27.0L;
        long double sw = sqrtl(w > 0 ? w : 0);
        long double t1 = cbrtl(u + sw), t2 = cbrtl(u - sw);
        cand[nc++] = t1 + t2;
    } else {                                       /* three real roots */
        long double mm = 2.0L * sqrtl(-p / 3.0L);
        long double arg = 3.0L * q / (p * mm);
        if (arg > 1.0L) arg = 1.0L; if (arg < -1.0L) arg = -1.0L;
        long double th = acosl(arg) / 3.0L;
        for (int k = 0; k < 3; k++)
            cand[nc++] = mm * cosl(th - 2.0L * 3.14159265358979323846L * k / 3.0L);
    }
    int cnt = 0;
    for (int i = 0; i < nc; i++) {
        long double v = cand[i];
        if (!(v > -1e30L && v < 1e30L)) continue;
        i128 base = (i128)llroundl(v > 9.0e18L ? 9.0e18L : (v < -9.0e18L ? -9.0e18L : v));
        for (i128 dn = -2; dn <= 2; dn++) {
            i128 n = base + dn;
            if (n == 0) continue;
            if (cubic_eval(n, m, C) == 0) {
                int dup = 0;
                for (int j = 0; j < cnt; j++) if (r[j] == n) dup = 1;
                if (!dup) r[cnt++] = n;
            }
        }
    }
    return cnt;
}

#define MAXDIV 500000
static i128 divs[MAXDIV];

static void handle(i128 m, i128 P, i128 R) {
    i128 C = P - 65;
    i128 roots[8];
    int cnt = cubic_int_roots(m, C, roots);
    for (int i = 0; i < cnt; i++) {
        i128 n = roots[i];
        i128 K = 36 * n * n * n - 65;
        i128 den = 4 * m;
        for (int sr = 0; sr < 2; sr++) {            /* both roots: +R and -R */
            i128 num = K - 12 * m * n + (sr ? -R : R);
            if (num % den) continue;
            i128 x = num / den;
            if (x == 0) continue;
            /* exact check of (Q):  2m x^2 + (12mn-K)x + m^2 = 0  */
            i128 lhs = 2 * m * x * x + (12 * m * n - K) * x + m * m;
            if (lhs != 0) continue;
            char b1[64], b2[64], b3[64];
            print_i128(b1, n); print_i128(b2, x); print_i128(b3, m);
            printf("CAND n=%s x=%s m=%s\n", b1, b2, b3);
            fflush(stdout);
        }
    }
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s mmax [stride off]\n", argv[0]); return 1; }
    long long mmax = atoll(argv[1]);
    long long stride = (argc > 2) ? atoll(argv[2]) : 1;
    long long off = (argc > 3) ? atoll(argv[3]) : 0;
    init_tables();
    sieve_spf(mmax);

    for (long long am = 1 + off; am <= mmax; am += stride) {
        /* factor 8*am^3 */
        int pr[32], ex[32], np = 0;
        long long t = am;
        while (t > 1) { int p = spf[t], e = 0; while (t % p == 0) { t /= p; e++; } pr[np] = p; ex[np] = 3 * e; np++; }
        /* multiply in the 2^3 */
        int found2 = 0;
        for (int i = 0; i < np; i++) if (pr[i] == 2) { ex[i] += 3; found2 = 1; }
        if (!found2) { pr[np] = 2; ex[np] = 3; np++; }
        /* generate divisors of 8 am^3 */
        int nd = 1; divs[0] = 1;
        for (int i = 0; i < np; i++) {
            int cur = nd;
            i128 pw = 1;
            for (int e = 1; e <= ex[i]; e++) {
                pw *= pr[i];
                for (int j = 0; j < cur; j++) {
                    if (nd >= MAXDIV) { nd = MAXDIV; break; }
                    divs[nd++] = divs[j] * pw;
                }
            }
        }
        i128 Nabs = 8 * (i128)am * (i128)am * (i128)am;
        for (int smm = 0; smm < 2; smm++) {
            i128 m = smm ? -(i128)am : (i128)am;
            i128 N = smm ? -Nabs : Nabs;           /* N = 8 m^3 */
            for (int i = 0; i < nd; i++) {
                i128 u = divs[i], v = N / u;
                if (((u + v) & 1) != 0) continue;
                i128 P = (u + v) / 2, R = (v - u) / 2;
                handle(m, P, R);
                handle(m, -P, R);
            }
        }
    }
    return 0;
}
