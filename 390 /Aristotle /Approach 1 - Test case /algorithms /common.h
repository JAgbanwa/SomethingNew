/* common.h -- shared helpers for the d-search engines.
 *
 *  MATHEMATICAL BACKGROUND (see README.md for the full derivation)
 *  ---------------------------------------------------------------
 *  The equation
 *        36n^3 - 65 = -2 d x^2 ( -(x+6n) + sqrt( (x+6n)^2 + (36n^3-65)/x ) )
 *  is equivalent (for x != 0) to
 *        d = ( -A - sgn(x) * T ) / (2 x^2),
 *  where
 *        K = 36n^3 - 65,   A = x(x+6n),   T = sqrt(D),   D = A^2 + xK.
 *  Hence:  d is RATIONAL  <=>  D = x^2 (x+6n)^2 + x(36n^3-65) is a perfect square.
 *  The whole search is therefore a search for integer points on the surface
 *        T^2 = x^4 + 12 n x^3 + 36 n^2 x^2 + (36n^3-65) x .
 */
#ifndef COMMON_H
#define COMMON_H
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>

typedef __int128 i128;
typedef unsigned __int128 u128;

/* ---- fast "is this a square?" pre-filters -------------------------------
 * Residue tables modulo 64, 63, 65 and 11.  A perfect square must be a
 * quadratic residue modulo each of them; the four tests together let through
 * only about 1 in 1000 non-squares, and each test costs a few ns.
 */
static unsigned char sq64[64], sq63[63], sq65[65], sq11[11];

static void init_tables(void) {
    memset(sq64, 0, sizeof sq64); memset(sq63, 0, sizeof sq63);
    memset(sq65, 0, sizeof sq65); memset(sq11, 0, sizeof sq11);
    for (int i = 0; i < 64; i++) sq64[(i * i) & 63] = 1;
    for (int i = 0; i < 63; i++) sq63[(i * i) % 63] = 1;
    for (int i = 0; i < 65; i++) sq65[(i * i) % 65] = 1;
    for (int i = 0; i < 11; i++) sq11[(i * i) % 11] = 1;
}

/* exact integer square root of a non-negative __int128 */
static i128 isqrt128(i128 v) {
    if (v < 0) return -1;
    if (v < 2) return v;
    long double lv = (long double)v;
    i128 r = (i128)sqrtl(lv);
    /* Newton polish -- long double has 64 bits of mantissa, so r is close. */
    for (int it = 0; it < 6; it++) {
        if (r <= 0) { r = 1; }
        i128 q = v / r;
        i128 nr = (r + q) >> 1;
        if (nr == r) break;
        r = nr;
    }
    while (r > 0 && r * r > v) r--;
    while ((r + 1) * (r + 1) <= v) r++;
    return r;
}

/* Combined test: returns T >= 0 with T*T == v, or -1. */
static inline i128 exact_sqrt_or_neg(i128 v) {
    if (v < 0) return -1;
    i128 t = isqrt128(v);
    return (t * t == v) ? t : -1;
}

/* cheap filter on a (possibly huge) non-negative value */
static inline int quick_square_filter(i128 v) {
    if (v < 0) return 0;
    unsigned lo = (unsigned)((u128)v & 63u);
    if (!sq64[lo]) return 0;
    unsigned r63 = (unsigned)(v % 63); if (!sq63[r63]) return 0;
    unsigned r65 = (unsigned)(v % 65); if (!sq65[r65]) return 0;
    unsigned r11 = (unsigned)(v % 11); if (!sq11[r11]) return 0;
    return 1;
}

static void print_i128(char *buf, i128 v) {
    /* buf must hold >= 45 chars */
    char tmp[64]; int p = 0, neg = 0;
    u128 u;
    if (v < 0) { neg = 1; u = (u128)(-v); } else u = (u128)v;
    if (u == 0) tmp[p++] = '0';
    while (u) { tmp[p++] = (char)('0' + (int)(u % 10)); u /= 10; }
    int q = 0;
    if (neg) buf[q++] = '-';
    while (p) buf[q++] = tmp[--p];
    buf[q] = 0;
}

/* report a hit: n, x, and D (so the caller can recompute d exactly) */
static inline void report(i128 n, i128 x, i128 T) {
    char b1[64], b2[64], b3[64];
    print_i128(b1, n); print_i128(b2, x); print_i128(b3, T);
    printf("HIT n=%s x=%s T=%s\n", b1, b2, b3);
    fflush(stdout);
}
#endif
