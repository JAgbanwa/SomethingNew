/* engine_sqfree.c -- ENGINE E : the squarefree-kernel congruence sieve.
 *                    THE FASTEST ENGINE FOR LARGE |d|.
 *
 *  THEOREM (proved in RequestProject/DSearch.lean, `sqfreePart_dvd_K`):
 *  write  m = T - x(x+6n)  as before; from  T^2 = x^2(x+6n)^2 + xK  one gets
 *        m^2 = x * ( K - 2(x+6n) m ),      so       x | m^2 .
 *  Writing  x = s t^2  with s SQUAREFREE gives  s t | m,  m = s t r,  and
 *        K = 2 (x+6n) m + m^2 / x = s ( 2 t r (x+6n) + r^2 ) ,
 *  hence the NECESSARY CONDITION
 *
 *        s | 36 n^3 - 65          (s = squarefree kernel of x).
 *
 *  Two immediate consequences, because 36n^3-65 is always odd and always
 *  = 1 (mod 3):
 *        * s is odd and 3 does not divide s, i.e. v_2(x) and v_3(x) are EVEN;
 *          in particular x = +-2, +-3, +-6, +-8, +-12, ... are impossible.
 *        * for every other x, n is confined to the roots of the cubic
 *          congruence 36 n^3 = 65 (mod s) -- typically ONE residue class
 *          modulo s out of s.
 *
 *  So instead of testing all n we test only ~1/s of them: the speed-up over a
 *  plain (n,x) scan is a factor of s, i.e. up to |x| itself.  Covering
 *  |x| <= 10^6 and |n| <= 10^8 (2*10^14 pairs!) costs only ~3*10^11 tests.
 *  This is the engine that can reach the regime |n| >> |x| where
 *        |d| ~ 3 |n|^{3/2} / |x|^{3/2}
 *  is large, with denominator dividing 2x^2 (so a genuinely big non-integer
 *  rational).
 *
 *  usage: ./engine_sqfree XMAX NMAX [stride off]
 */
#include "common.h"

typedef unsigned long long u64;

static u64 mulmod(u64 a, u64 b, u64 p) { return (u64)((u128)a * b % p); }
static u64 powmod(u64 a, u64 e, u64 p) {
    u64 r = 1; a %= p;
    while (e) { if (e & 1) r = mulmod(r, a, p); a = mulmod(a, a, p); e >>= 1; }
    return r;
}

static int *spf; static long long SPFMAX;
static void sieve_spf(long long lim) {
    SPFMAX = lim;
    spf = (int*)calloc((size_t)lim + 1, sizeof(int));
    for (long long i = 2; i <= lim; i++)
        if (!spf[i]) for (long long j = i; j <= lim; j += i) if (!spf[j]) spf[j] = (int)i;
}

/* roots of 36 n^3 = 65 (mod p), p prime, p != 2,3.  returns count (0..3) */
static int roots_mod_p(u64 p, u64 *out) {
    u64 inv36 = powmod(36 % p, p - 2, p);
    u64 a = mulmod(65 % p, inv36, p);
    if (a == 0) { out[0] = 0; return 1; }
    if (p % 3 == 2) { out[0] = powmod(a, (2 * p - 1) / 3, p); return 1; }
    if (powmod(a, (p - 1) / 3, p) != 1) return 0;
    int c = 0;                                  /* p = 1 (mod 3) and a is a cube */
    for (u64 r = 0; r < p && c < 3; r++)
        if (mulmod(mulmod(r, r, p), r, p) == a) out[c++] = r;
    return c;
}

#define MAXR 4096
static long long roots[MAXR]; static int nroots;

/* CRT-combine the root sets of the primes of the squarefree s */
static int build_roots(long long s) {
    roots[0] = 0; nroots = 1;
    long long mod = 1, t = s;
    while (t > 1) {
        int p = spf[t]; t /= p;
        u64 rp[3]; int c = roots_mod_p((u64)p, rp);
        if (c == 0) return 0;
        long long newr[MAXR]; int nn = 0;
        /* CRT: n = roots[i] (mod mod), n = rp[j] (mod p) */
        long long inv = 0;
        { /* inverse of mod modulo p */
            long long g = ((mod % p) + p) % p;
            inv = (long long)powmod((u64)g, (u64)(p - 2), (u64)p);
        }
        for (int i = 0; i < nroots; i++)
            for (int j = 0; j < c; j++) {
                long long diff = ((long long)rp[j] - roots[i]) % p; if (diff < 0) diff += p;
                long long k = (long long)mulmod((u64)diff, (u64)inv, (u64)p);
                long long v = roots[i] + mod * k;
                if (nn < MAXR) newr[nn++] = v;
            }
        mod *= p; nroots = nn;
        for (int i = 0; i < nn; i++) roots[i] = newr[i];
    }
    return nroots;
}

/* scan n in [-N, N], n = r (mod s), for the given x */
static void scan_class(i128 x, long long s, long long r, long long N) {
    /* first n >= -N with n = r (mod s) */
    long long start = -N;
    long long rem = ((start - r) % s + s) % s;
    long long n0 = start + (rem ? (s - rem) : 0);
    if (n0 > N) return;
    long long cnt = (N - n0) / s + 1;
    i128 a = 36 * x, b = 36 * x * x, c = 12 * x * x * x, e = x * x * x * x - 65 * x;
    i128 f[4];
    for (int i = 0; i < 4; i++) {
        i128 nn = (i128)n0 + (i128)i * s;
        f[i] = ((a * nn + b) * nn + c) * nn + e;
    }
    i128 D = f[0], d1 = f[1] - f[0], d2 = f[2] - 2 * f[1] + f[0],
         d3 = f[3] - 3 * f[2] + 3 * f[1] - f[0];
    i128 n = n0;
    for (long long k = 0; k < cnt; k++) {
        if (quick_square_filter(D)) {
            i128 T = exact_sqrt_or_neg(D);
            if (T >= 0) report(n, x, T);
        }
        D += d1; d1 += d2; d2 += d3;
        n += s;
    }
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s XMAX NMAX [stride off]\n", argv[0]); return 1; }
    long long X = atoll(argv[1]), N = atoll(argv[2]);
    long long stride = (argc > 3) ? atoll(argv[3]) : 1;
    long long off = (argc > 4) ? atoll(argv[4]) : 0;
    init_tables();
    sieve_spf(X);

    long long job = 0;   /* work is distributed per (s,t) pair: better balance */
    for (long long s = 1; s <= X; s += 1) {
        if (s % 2 == 0 || s % 3 == 0) continue;            /* s must be odd, 3 ∤ s */
        /* squarefree test */
        long long t = s, ok = 1;
        while (t > 1) { int p = spf[t]; int e = 0; while (t % p == 0) { t /= p; e++; } if (e > 1) { ok = 0; break; } }
        if (!ok) continue;
        if (!build_roots(s)) continue;                     /* no n at all for this kernel */
        for (long long tt = 1; s * tt * tt <= X; tt++) {
            if ((job++ % stride) != off) continue;
            i128 xabs = (i128)s * tt * tt;
            for (int sg = 0; sg < 2; sg++) {
                i128 x = sg ? -xabs : xabs;
                for (int i = 0; i < nroots; i++) scan_class(x, s, roots[i] % s, N);
            }
        }
    }
    return 0;
}
