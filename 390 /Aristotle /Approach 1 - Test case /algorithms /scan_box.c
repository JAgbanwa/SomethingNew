/* scan_box.c -- ENGINE B : box scan over (n,x) by 4th-order finite differences.
 *
 *  For a FIXED n the squareness condition is the quartic
 *        T^2 = D(x) = x^4 + 12 n x^3 + 36 n^2 x^2 + (36n^3-65) x .
 *  Stepping x by 1 costs four 128-bit additions (the 4th difference of a
 *  quartic is the constant 24), so the inner loop has NO multiplications and
 *  NO divisions apart from the cheap residue filter.  Throughput is roughly
 *  3-4 * 10^8 (n,x) pairs per second per core.
 *
 *  usage: ./scan_box nmin nmax xmax            (scans |x| <= xmax, x != 0)
 *     or  ./scan_box nmin nmax xmax stride off (for splitting over cores:
 *                                               takes n = nmin+off, +stride,...)
 */
#include "common.h"

static void scan_n(long long n, long long xmax) {
    i128 N = n;
    i128 K = 36 * N * N * N - 65;
    /* positive x, then negative x */
    for (int sgn = 0; sgn < 2; sgn++) {
        long long step = sgn ? -1 : 1;
        i128 x0 = step;                     /* first x: +1 or -1 */
        i128 c3 = 12 * N, c2 = 36 * N * N;
        /* f(x) = x^4 + c3 x^3 + c2 x^2 + K x, sampled at x0, x0+step, ... */
        i128 f[5];
        for (int i = 0; i < 5; i++) {
            i128 xx = x0 + (i128)i * step;
            f[i] = (((xx + c3) * xx + c2) * xx + K) * xx;
        }
        i128 D = f[0];
        i128 d1 = f[1] - f[0];
        i128 d2 = f[2] - 2 * f[1] + f[0];
        i128 d3 = f[3] - 3 * f[2] + 3 * f[1] - f[0];
        i128 d4 = f[4] - 4 * f[3] + 6 * f[2] - 4 * f[1] + f[0];
        for (long long k = 0; k < xmax; k++) {
            if (quick_square_filter(D)) {
                i128 T = exact_sqrt_or_neg(D);
                if (T >= 0) report(N, x0 + (i128)k * step, T);
            }
            D += d1; d1 += d2; d2 += d3; d3 += d4;
        }
    }
}

int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "usage: %s nmin nmax xmax [stride off]\n", argv[0]); return 1; }
    init_tables();
    long long nmin = atoll(argv[1]), nmax = atoll(argv[2]), xmax = atoll(argv[3]);
    long long stride = (argc > 4) ? atoll(argv[4]) : 1;
    long long off = (argc > 5) ? atoll(argv[5]) : 0;
    for (long long n = nmin + off; n <= nmax; n += stride) scan_n(n, xmax);
    return 0;
}
