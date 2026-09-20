/* scan_curve.c -- ENGINE A : "one elliptic curve per x", deep scan in n.
 *
 *  For a FIXED x the squareness condition
 *        T^2 = D(n) = 36x n^3 + 36x^2 n^2 + 12x^3 n + x^4 - 65x
 *  is a cubic in n (an elliptic curve E_x).  Since D is a cubic polynomial in
 *  n, consecutive values can be produced by third-order finite differences:
 *  three 128-bit additions per candidate, no multiplications at all.  Combined
 *  with the mod-64/63/65/11 square filter this scans ~3*10^8 values of n per
 *  second per core.
 *
 *  This engine is the one that produces the LARGE values of d, because
 *        |d| ~ 3 |n|^{3/2} / |x|^{3/2}
 *  so a small |x| together with a huge |n| gives a huge d whose denominator
 *  divides 2x^2 (i.e. a genuinely non-integer rational for |x| >= 2).
 *
 *  usage: ./scan_curve xmin xmax nmin nmax
 */
#include "common.h"

int main(int argc, char **argv) {
    if (argc < 5) { fprintf(stderr, "usage: %s xmin xmax nmin nmax\n", argv[0]); return 1; }
    init_tables();
    long long xmin = atoll(argv[1]), xmax = atoll(argv[2]);
    long long nmin = atoll(argv[3]), nmax = atoll(argv[4]);

    for (long long x = xmin; x <= xmax; x++) {
        if (x == 0) continue;
        i128 X = x;
        i128 a = 36 * X, b = 36 * X * X, c = 12 * X * X * X, e = X * X * X * X - 65 * X;
        i128 n0 = nmin;
        i128 f0 = ((a * n0 + b) * n0 + c) * n0 + e;
        i128 n1v = n0 + 1, n2v = n0 + 2;
        i128 f1 = ((a * n1v + b) * n1v + c) * n1v + e;
        i128 f2 = ((a * n2v + b) * n2v + c) * n2v + e;
        i128 D = f0, d1 = f1 - f0, d2 = (f2 - f1) - (f1 - f0), d3 = 6 * a;
        for (long long n = nmin; n <= nmax; n++) {
            if (quick_square_filter(D)) {
                i128 T = exact_sqrt_or_neg(D);
                if (T >= 0) report(n, x, T);
            }
            D += d1; d1 += d2; d2 += d3;
        }
    }
    return 0;
}
