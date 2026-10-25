/* xroots.c --- Algorithm D: solutions with an INTEGRAL radical, by cube roots, in both charts.
 *
 *   36 n^3 - K = -2 d x^2 ( -(x+6n) + y ),   y = sqrt( (x+6n)^2 + (36n^3-K)/x ) >= 0   (E)
 *
 * (K = 19 is the original equation; 6K = 114.)  The radical is called integral when
 *
 *   integer chart:  x = X is an integer and y is an integer, or
 *   half chart:     x = X/2, y = Y/2 with X and Y odd            (the case added here).
 *
 * In both charts this forces  X | 36n^3 - K :
 *   integer chart:  y^2 - (x+6n)^2 = (36n^3-K)/x must be an integer;
 *   half chart:     Y^2 - (X+12n)^2 = 8(36n^3-K)/X must be an integer and X is odd.
 * So for a fixed X the admissible n lie in the residue classes  n = r (mod |X|)  with
 * 36 r^3 = K (mod |X|): at most 3^omega(X) classes out of |X|, typically about one.  Inside
 * those classes n is tested for
 *
 *   integer chart:  T(n) = (x+6n)^2  + (36n^3-K)/x   a perfect square   (then y = sqrt T)
 *   half chart:     T(n) = (X+12n)^2 + 8(36n^3-K)/X  a perfect square   (then Y = sqrt T)
 *
 * and then d = -(y + x + 6n)/(2x) (HALF_INTEGER.md §3).  This is the Booker-Sutherland
 * search for 114 = A^3+B^3+C^3 written in the coordinates of (E): with A = -x+y, B = -x-y,
 * C = 2x+6n one has A+B = -2x (the pair sum Booker calls d, of either parity: even <-> the
 * integer chart, odd <-> the half chart) and C = 2x+6n (the third cube, Booker's z).
 * The search therefore fixes the DENOMINATOR side of d = (A+C)/(A+B) and solves for the rest.
 *
 * Filters, all one sided (a genuine solution always passes):
 *   1. the cube-root congruence above (exact);
 *   2. the 2-adic and 3-adic conditions of local.h on (X mod 64, n mod 64) and
 *      (X mod 243, n mod 243), computed at start-up for the given K and folded into the
 *      progressions by the CRT, so the excluded classes are never visited (for K = 19 only
 *      about 3.4% of n survive in the integer chart and 13.6% in the half chart);
 *   3. T(n) must be a square modulo 8 front primes (5..29, incremental residues) and then
 *      modulo 70 further primes (31..409) -- a non-square survives all of them with
 *      probability about 2^-70.
 * What survives is printed as "ICAND <chart> X n" and confirmed exactly by verify.py, which
 * prints d, y and the triple (A,B,C) with A^3+B^3+C^3 = 6K.
 *
 * A work unit is a range of |X| (both signs of X unless --xsign is given) times a window of
 * n; it is complete: every integral solution in that box is reported.
 *
 * Build:  cc -O3 -o xroots xroots.c -lm
 * Run:    ./xroots [--half] --X0 a --X1 b --n0 N0 --n1 N1 [--K k] [--general]
 *                  [--xsign +1|-1] [--out f] [--progress]
 *         ./xroots --selftest
 * Numbers may be written in decimal or as 17e17, -2e18, ...; |X| < 2^62, |n| < 2^120.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <math.h>
#include "local.h"

typedef __int128 i128;
typedef unsigned __int128 u128;
typedef uint64_t u64;

/* ------------------------------------------------------------ arithmetic mod m < 2^63 */

static inline u64 mulmod(u64 a, u64 b, u64 m) { return (u64)((u128)a * b % m); }
static u64 powmod(u64 a, u64 e, u64 m) {
  u64 r = 1 % m; a %= m;
  while (e) { if (e & 1) r = mulmod(r, a, m); a = mulmod(a, a, m); e >>= 1; }
  return r;
}
static inline u64 imod(i128 v, u64 m) { i128 r = v % (i128)m; if (r < 0) r += m; return (u64)r; }
/* inverse of a modulo m (gcd(a,m) = 1), 0 if none */
static u64 invmod(u64 a, u64 m) {
  i128 t = 0, nt = 1, r = m, nr = a % m;
  while (nr) { i128 q = r / nr, tmp;
    tmp = t - q * nt; t = nt; nt = tmp;
    tmp = r - q * nr; r = nr; nr = tmp; }
  if (r != 1) return 0;
  if (t < 0) t += m;
  return (u64)t;
}

/* ------------------------------------------------------------------ factorisation */

static const u64 MRB[12] = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37};
static int is_prime(u64 n) {
  if (n < 2) return 0;
  for (int i = 0; i < 12; i++) if (n % MRB[i] == 0) return n == MRB[i];
  u64 d = n - 1; int s = 0;
  while (!(d & 1)) { d >>= 1; s++; }
  for (int i = 0; i < 12; i++) {
    u64 x = powmod(MRB[i], d, n);
    if (x == 1 || x == n - 1) continue;
    int ok = 0;
    for (int j = 1; j < s; j++) { x = mulmod(x, x, n); if (x == n - 1) { ok = 1; break; } }
    if (!ok) return 0;
  }
  return 1;
}
static u64 gcd64(u64 a, u64 b) { while (b) { u64 t = a % b; a = b; b = t; } return a; }
static u64 rho(u64 n) {
  if (!(n & 1)) return 2;
  for (u64 c = 1;; c++) {
    u64 x = 2, y = 2, d = 1;
    while (d == 1) {
      x = (mulmod(x, x, n) + c) % n;
      y = (mulmod(y, y, n) + c) % n;
      y = (mulmod(y, y, n) + c) % n;
      d = gcd64(x > y ? x - y : y - x, n);
    }
    if (d != n) return d;
  }
}
static int SMALLP[4000], NSMALL = 0;          /* primes below 2^15 for trial division */
static void factor_rec(u64 n, u64 *pf, int *pe, int *nf) {
  if (n == 1) return;
  if (is_prime(n)) {
    for (int i = 0; i < *nf; i++) if (pf[i] == n) { pe[i]++; return; }
    pf[*nf] = n; pe[*nf] = 1; (*nf)++; return;
  }
  u64 d = rho(n);
  factor_rec(d, pf, pe, nf); factor_rec(n / d, pf, pe, nf);
}
static int factor(u64 n, u64 *pf, int *pe) {
  int nf = 0;
  for (int i = 0; i < NSMALL; i++) {
    u64 p = (u64)SMALLP[i];
    if (p * p > n) break;
    if (n % p == 0) { int e = 0; while (n % p == 0) { n /= p; e++; } pf[nf] = p; pe[nf] = e; nf++; }
  }
  if (n > 1) {
    if (n < (u64)32768 * 32768) { pf[nf] = n; pe[nf] = 1; nf++; }
    else factor_rec(n, pf, pe, &nf);
  }
  /* sort by prime (factor_rec may append out of order) */
  for (int i = 1; i < nf; i++) for (int j = i; j > 0 && pf[j] < pf[j - 1]; j--) {
    u64 t = pf[j]; pf[j] = pf[j - 1]; pf[j - 1] = t; int e = pe[j]; pe[j] = pe[j - 1]; pe[j - 1] = e; }
  return nf;
}

/* ------------------------------------------------- roots of 36 r^3 = K (mod p^e) */

static long long KK = 19;

/* f(r) = 36 r^3 - K mod m */
static inline u64 fmodm(u64 r, u64 m) {
  u64 v = mulmod(36 % m, mulmod(r, mulmod(r, r, m), m), m);
  u64 k = imod(KK, m);
  return v >= k ? v - k : v + m - k;
}

/* all cube roots of a (nonzero) mod the prime p > 3 */
static int cuberoots_p(u64 a, u64 p, u64 *out) {
  a %= p;
  if (p % 3 == 2) { out[0] = powmod(a, (2 * p - 1) / 3, p); return 1; }
  if (powmod(a, (p - 1) / 3, p) != 1) return 0;
  u64 t = p - 1; int s = 0;
  while (t % 3 == 0) { t /= 3; s++; }
  u64 c = 2;
  while (powmod(c, (p - 1) / 3, p) == 1) c++;
  u64 z = powmod(c, t, p);                      /* generator of the 3-Sylow subgroup */
  u64 u = (t == 1) ? 0 : invmod(3 % t, t);      /* 3u = 1 (mod t) */
  u64 x0 = powmod(a, u, p);                     /* x0^3 = a * (a^t)^m, m = (3u-1)/t */
  u64 m = (3 * (u128)u - 1 + (t == 1 ? 1 : 0)) / t;
  if (t == 1) { m = 0; x0 = 1; }                /* then x0^3 = 1 and we need y^3 = a */
  u64 b = powmod(a, t, p);
  /* beta = b^(-m) (or a itself when t == 1), an element of the 3-Sylow subgroup */
  u64 beta = (t == 1) ? a : powmod(invmod(b, p), m, p);
  /* discrete log of beta to base z (order 3^s), digit by digit */
  u64 pow3[64]; pow3[0] = 1; for (int i = 1; i <= s; i++) pow3[i] = pow3[i - 1] * 3;
  u64 gamma = powmod(z, pow3[s - 1], p);        /* element of order 3 */
  u64 g2 = mulmod(gamma, gamma, p);
  u64 L = 0;
  u64 zinv = invmod(z, p);
  for (int i = 0; i < s; i++) {
    u64 h = mulmod(beta, powmod(zinv, L, p), p);
    h = powmod(h, pow3[s - 1 - i], p);
    int dgt = (h == 1) ? 0 : (h == gamma) ? 1 : (h == g2) ? 2 : -1;
    if (dgt < 0) return 0;                      /* cannot happen for a cube */
    L += (u64)dgt * pow3[i];
  }
  if (L % 3) return 0;                          /* not a cube: cannot happen */
  u64 y = powmod(z, L / 3, p);
  u64 r = mulmod(x0, y, p);
  out[0] = r; out[1] = mulmod(r, gamma, p); out[2] = mulmod(out[1], gamma, p);
  return 3;
}

#define MAXR (1 << 20)
static u64 POOL[1 << 21];         /* roots of all prime powers of the current M */
static size_t POOLUSED = 0;
static u64 TMPR[MAXR];

/* roots of f mod p^e, written to out (room for cap); returns the count, or -1 if > cap */
static int roots_pp(u64 p, int e, u64 *out, int cap) {
  u64 pe = 1; for (int i = 0; i < e; i++) pe *= p;
  int brute = (p < 64) || (imod(6 * (i128)KK, p) == 0);
  if (brute) {
    /* roots mod p by scanning, then lift one level at a time by trying all p lifts */
    int nr = 0;
    for (u64 r = 0; r < p; r++) if (fmodm(r, p) == 0) { if (nr >= cap) return -1; out[nr++] = r; }
    u64 pl = p;
    for (int l = 2; l <= e && nr; l++) {
      u64 pn = pl * p;
      int nn = 0;
      for (int i = 0; i < nr; i++)
        for (u64 j = 0; j < p; j++) {
          u64 r = out[i] + j * pl;
          if (fmodm(r, pn) == 0) { if (nn >= cap || nn >= MAXR) return -1; TMPR[nn++] = r; }
        }
      memcpy(out, TMPR, sizeof(u64) * nn);
      nr = nn; pl = pn;
    }
    return nr;
  }
  if (cap < 3) return -1;
  /* p > 3, p does not divide 6K: r^3 = K/36 mod p, then Hensel (f' = 108 r^2 is a unit) */
  u64 a = mulmod(imod(KK, p), invmod(36 % p, p), p);
  u64 r0[3];
  int nr = cuberoots_p(a, p, r0);
  for (int i = 0; i < nr; i++) {
    u64 r = r0[i];
    for (int prec = 1; prec < 2 * e + 2 && e > 1; prec *= 2) {
      u64 fr = fmodm(r, pe);
      u64 fp = mulmod(108 % pe, mulmod(r, r, pe), pe);
      u64 inv = invmod(fp, pe);
      r = (r + pe - mulmod(fr, inv, pe)) % pe;
    }
    out[i] = r % pe;
  }
  return nr;
}

/* ------------------------------------------------------------------ the search */

static int CHART = 1;            /* 1 = integer chart, 2 = half chart */
static int GENERAL = 0;
static local_t LT;
static FILE *OUT;
static i128 N0, N1;
static long long cntX = 0, cntXr = 0, cntProg = 0, cntCand = 0, cntSkip = 0;
static unsigned long long cntTested = 0;

#define NFRONT 8
static const int FRONTP[NFRONT] = {5, 7, 11, 13, 17, 19, 23, 29};
#define NTAIL 70
static int TAILP[NTAIL];
static uint8_t *SQ[512];          /* SQ[q][v] = 1 iff v is a square mod q (incl. 0) */

/* T(n) mod q for the current X, given n mod q (q prime, q does not divide 2X) */
static i128 CUR_X;
static inline u64 Tmod(u64 nq, u64 q, u64 Xq, u64 Xinv) {
  u64 n3 = nq * nq % q * nq % q;
  u64 A = (36 % q * n3 % q + q - imod(KK, q)) % q;          /* 36n^3 - K */
  if (CHART == 1) {
    u64 s = (Xq + 6 * nq) % q;
    return (s * s + A * Xinv) % q;
  }
  u64 s = (Xq + 12 * nq) % q;
  return (s * s + 8 * A % q * Xinv) % q;
}

static void print_i128(FILE *f, i128 v) {
  if (v < 0) { fputc('-', f); v = -v; }
  char buf[64]; int k = 0;
  if (v == 0) buf[k++] = '0';
  while (v > 0) { buf[k++] = (char)('0' + (int)(v % 10)); v /= 10; }
  while (k--) fputc(buf[k], f);
}

/* per-X state */
static uint32_t FMASK[NFRONT];    /* bit j set iff T is a square mod q when n = j (mod q) */
static int FUSE[NFRONT];
static u64 TXq[NTAIL], TXinv[NTAIL];
static int TUSE[NTAIL];

/* tail filter for a survivor of the front primes, then print */
static int TREADY;                /* tail tables of the current X built? (lazily: rare) */
static u64 MCUR;
static u64 FOLDL;                 /* modulus of the folded 2-adic/3-adic classes (1 if none) */
static void build_tail(void) {
  for (int i = 0; i < NTAIL; i++) {
    u64 q = (u64)TAILP[i];
    TUSE[i] = (MCUR % q != 0);
    if (!TUSE[i]) continue;
    TXq[i] = imod(CUR_X, q); TXinv[i] = invmod(TXq[i], q);
  }
  TREADY = 1;
}
static void emit(i128 n) {
  if (!TREADY) build_tail();
  for (int i = 0; i < NTAIL; i++) {
    if (!TUSE[i]) continue;
    u64 q = (u64)TAILP[i];
    if (!SQ[q][Tmod(imod(n, q), q, TXq[i], TXinv[i])]) return;
  }
  if (!GENERAL && !local_Xn_ok(&LT, CUR_X, n)) return;      /* only matters when not folded */
  fprintf(OUT, "ICAND %s ", CHART == 1 ? "int" : "half");
  print_i128(OUT, CUR_X); fputc(' ', OUT); print_i128(OUT, n); fputc('\n', OUT);
  fflush(OUT);
  cntCand++;
}

#define WHEEL 5005                 /* 5*7*11*13: front primes 0..3 combined in one wheel */
static u64 WHEELMIN = 4 * WHEEL;   /* progressions at least this long use the wheel (--wheelmin) */

/* residues of the progression data modulo the front primes, kept as u64 so that setting
   up a progression costs two 128-bit divisions instead of sixteen 128-bit remainders */
static u64 SQq[NFRONT];           /* S mod q for the current X (folded step)  */
static u64 N0q[NFRONT];           /* N0 mod q                                 */

static void scan_progression(i128 rho, i128 S, const u64 *rhoq) {
  /* n = rho (mod S), N0 <= n < N1;  rho mod q = rhoq[i] */
  i128 j;                                   /* ceil((N0 - rho) / S), any sign */
  if (N0 >= rho) j = (N0 - rho + S - 1) / S;
  else j = -((rho - N0) / S);
  i128 n = rho + S * j;
  if (n >= N1) return;
  cntProg++;
  u64 cnt = (u64)((N1 - 1 - n) / S) + 1;
  cntTested += cnt;
  u64 res[NFRONT], stp[NFRONT];
  for (int i = 0; i < NFRONT; i++) {
    u64 q = (u64)FRONTP[i];
    u64 jq = (j >= 0 && j < ((i128)1 << 63)) ? (u64)j % q : imod(j, q);
    res[i] = (rhoq[i] + SQq[i] * jq) % q;
    stp[i] = SQq[i];
  }
  if (cnt <= 4) {
    /* very short progression (large |X|): test each n directly, cheapest checks first */
    for (u64 t = 0; t < cnt; t++, n += S) {
      int ok = 1;
      for (int i = 0; i < NFRONT; i++) {
        if (FUSE[i] && !((FMASK[i] >> res[i]) & 1)) ok = 0;
        res[i] += stp[i]; if (res[i] >= (u64)FRONTP[i]) res[i] -= FRONTP[i];
      }
      if (!ok) continue;
      if (!GENERAL && FOLDL == 1 && !local_Xn_ok(&LT, CUR_X, n)) continue;
      emit(n);
    }
    return;
  }
  if (cnt < 400) {
    /* short progression: all eight front primes with incremental residues */
    uint32_t mk[NFRONT];
    for (int i = 0; i < NFRONT; i++) mk[i] = FUSE[i] ? FMASK[i] : 0xFFFFFFFFu;
    for (u64 t = 0; t < cnt; t++, n += S) {
      uint32_t ok = 1;
      for (int i = 0; i < NFRONT; i++) {
        ok &= mk[i] >> res[i];
        res[i] += stp[i]; res[i] -= (res[i] >= (u64)FRONTP[i]) ? (u64)FRONTP[i] : 0;
      }
      if (!(ok & 1)) continue;
      if (!GENERAL && FOLDL == 1 && !local_Xn_ok(&LT, CUR_X, n)) continue;
      emit(n);
    }
    return;
  }
  /* longer progression: the positions w in [0, Wh) (Wh = 385 = 5*7*11, or 5005 = 5*7*11*13
     for long progressions) where t = w (mod Wh) passes the wheel primes are listed once,
     with the gap to the next position and the corresponding advance of the residues modulo
     the remaining front primes; the loop then visits only those t and never the others */
  {
    static uint16_t pos[WHEEL], gap[WHEEL];
    static uint8_t adv[WHEEL][NFRONT];
    const int nw = (cnt >= WHEELMIN) ? 4 : 3;
    const u64 Wh = (nw == 4) ? WHEEL : 385;
    const int nr = NFRONT - nw;
    int npos = 0;
    u64 r[4] = {res[0], res[1], res[2], res[3]};
    uint32_t mk[NFRONT];
    for (int i = 0; i < NFRONT; i++) mk[i] = FUSE[i] ? FMASK[i] : 0xFFFFFFFFu;
    for (u64 w = 0; w < Wh; w++) {
      uint32_t ok = 1;
      for (int i = 0; i < nw; i++) {
        ok &= mk[i] >> r[i];
        r[i] += stp[i]; if (r[i] >= (u64)FRONTP[i]) r[i] -= FRONTP[i];
      }
      if (ok & 1) pos[npos++] = (uint16_t)w;
    }
    if (npos == 0) return;
    for (int i = 0; i < npos; i++) {
      u64 g = (i + 1 < npos) ? (u64)(pos[i + 1] - pos[i]) : (u64)(Wh - pos[i] + pos[0]);
      gap[i] = (uint16_t)g;
      for (int j = 0; j < nr; j++) {
        u64 q = (u64)FRONTP[nw + j];
        adv[i][j] = (uint8_t)(g % q * stp[nw + j] % q);
      }
    }
    u64 t = pos[0];
    u64 rr[NFRONT], qq[NFRONT];
    uint32_t mm[NFRONT];
    for (int j = 0; j < nr; j++) {
      u64 q = (u64)FRONTP[nw + j];
      qq[j] = q; mm[j] = mk[nw + j];
      rr[j] = (res[nw + j] + t % q * stp[nw + j]) % q;
    }
    const i128 n0 = n;
    int i = 0;
    if (nr == 4) {
      u64 r4 = rr[0], r5 = rr[1], r6 = rr[2], r7 = rr[3];
      const uint32_t m4 = mm[0], m5 = mm[1], m6 = mm[2], m7 = mm[3];
      while (t < cnt) {
        if (((m4 >> r4) & (m5 >> r5) & (m6 >> r6) & (m7 >> r7)) & 1) emit(n0 + (i128)S * (i128)t);
        t += gap[i];
        r4 += adv[i][0]; r4 -= (r4 >= 17) ? 17 : 0;
        r5 += adv[i][1]; r5 -= (r5 >= 19) ? 19 : 0;
        r6 += adv[i][2]; r6 -= (r6 >= 23) ? 23 : 0;
        r7 += adv[i][3]; r7 -= (r7 >= 29) ? 29 : 0;
        if (++i == npos) i = 0;
      }
    } else {
      while (t < cnt) {
        uint32_t ok = 1;
        for (int j = 0; j < nr; j++) {
          ok &= mm[j] >> rr[j];
          rr[j] += adv[i][j]; rr[j] -= (rr[j] >= qq[j]) ? qq[j] : 0;
        }
        if (ok & 1) emit(n0 + (i128)S * (i128)t);
        t += gap[i];
        if (++i == npos) i = 0;
      }
    }
  }
}

/* residues mod M from the per-prime-power root lists, combined by the CRT */
static int NPP;
static u64 PPm[64];               /* prime powers */
static u64 *PPr[64];              /* their roots */
static int PPn[64];
static int FOLDC[15552];          /* allowed classes mod FOLDL */
static int NFOLD;
static u64 MINVF;

static u64 MQ[NFRONT];            /* M mod q */
static void emit_residue(u64 r) {
  /* n = r (mod M); fold with the allowed classes mod FOLDL */
  u64 rq[NFRONT];
  for (int i = 0; i < NFRONT; i++) rq[i] = r % (u64)FRONTP[i];
  if (FOLDL == 1) { scan_progression((i128)r, (i128)MCUR, rq); return; }
  u64 rhoq[NFRONT];
  for (int c = 0; c < NFOLD; c++) {
    u64 jc = (u64)FOLDC[c];
    u64 k = (jc + FOLDL - r % FOLDL) % FOLDL * MINVF % FOLDL;
    i128 rho = (i128)r + (i128)MCUR * (i128)k;
    for (int i = 0; i < NFRONT; i++) {
      u64 q = (u64)FRONTP[i];
      rhoq[i] = (rq[i] + MQ[i] * (k % q)) % q;
    }
    scan_progression(rho, (i128)MCUR * (i128)FOLDL, rhoq);
  }
}

static void crt_rec(int idx, u64 r, u64 m) {
  if (idx == NPP) { emit_residue(r); return; }
  u64 pm = PPm[idx];
  u64 minv = invmod(m % pm, pm);
  for (int i = 0; i < PPn[idx]; i++) {
    u64 a = PPr[idx][i];
    /* x = r (mod m), x = a (mod pm):  x = r + m * ((a - r) * minv mod pm) */
    u64 k = mulmod((a + pm - r % pm) % pm, minv, pm);
    crt_rec(idx + 1, r + m * k, m * pm);
  }
}

static void do_X(i128 X, u64 M, int nf, const u64 *pf) {
  CUR_X = X;
  cntXr++;
  /* front and tail tables for this X */
  for (int i = 0; i < NFRONT; i++) {
    u64 q = (u64)FRONTP[i];
    FUSE[i] = (M % q != 0);
    FMASK[i] = 0;
    if (!FUSE[i]) continue;
    u64 Xq = imod(X, q), Xi = invmod(Xq, q);
    for (u64 j = 0; j < q; j++) if (SQ[q][Tmod(j, q, Xq, Xi)]) FMASK[i] |= 1u << j;
  }
  TREADY = 0;
  /* fold the 2-adic and 3-adic (X, n) conditions into the progressions, when the window
     is long enough for the folded progressions to be non-empty (else test them per n) */
  FOLDL = 1; NFOLD = 0;
  if (!GENERAL) {
    int x64 = loc_mod(X, LOC2), x243 = loc_mod(X, LOC3);
    int n2 = 0, n3 = 0;
    for (int j = 0; j < LOC2; j++) n2 += LT.Xn2[x64][j];
    for (int j = 0; j < LOC3; j++) n3 += LT.Xn3[x243][j];
    if (n2 == 0 || n3 == 0) return;                       /* impossible X */
    u64 L2 = (M % 2 && n2 < LOC2) ? LOC2 : 1, L3 = (M % 3 && n3 < LOC3) ? LOC3 : 1;
    i128 W = N1 - N0;
    if (W < (i128)M * (i128)(L2 * L3) * 2) L2 = 1;       /* drop the 2-adic fold first */
    if (W < (i128)M * (i128)(L2 * L3) * 2) L3 = 1;
    FOLDL = L2 * L3;
    if (FOLDL > 1)
      for (u64 j = 0; j < FOLDL; j++)
        if ((L2 == 1 || LT.Xn2[x64][j % LOC2]) && (L3 == 1 || LT.Xn3[x243][j % LOC3]))
          FOLDC[NFOLD++] = (int)j;
  }
  MCUR = M;
  MINVF = (FOLDL > 1) ? invmod(M % FOLDL, FOLDL) : 0;
  for (int i = 0; i < NFRONT; i++) {
    u64 q = (u64)FRONTP[i];
    MQ[i] = M % q;
    SQq[i] = MQ[i] * (FOLDL % q) % q;
  }
  crt_rec(0, 0, 1);
  (void)nf; (void)pf;
}

/* --brute: the same box by direct enumeration of every n (no cube roots, no sieves, no
   filters) -- an independent oracle for the validation runs; needs |n| < 10^6, |X| < 10^6 */
static int isqrt_exact(i128 v, i128 *r) {
  if (v < 0) return 0;
  long double s = sqrtl((long double)v);
  i128 t = (i128)s;
  for (i128 u = t - 2; u <= t + 2; u++) if (u >= 0 && u * u == v) { *r = u; return 1; }
  return 0;
}
static void brute_box(u64 X0, u64 X1, int xsign) {
  for (u64 M = X0; M < X1; M++) {
    if (CHART == 2 && !(M & 1)) continue;
    for (int s = 0; s < 2; s++) {
      int sign = s ? -1 : 1;
      if (xsign && sign != xsign) continue;
      i128 X = (i128)sign * (i128)M;
      for (i128 n = N0; n < N1; n++) {
        i128 A = 36 * n * n * n - KK;
        if (A % X) continue;
        i128 T = (CHART == 1) ? (X + 6 * n) * (X + 6 * n) + A / X
                              : (X + 12 * n) * (X + 12 * n) + 8 * (A / X);
        i128 r;
        if (!isqrt_exact(T, &r)) continue;
        fprintf(OUT, "ICAND %s ", CHART == 1 ? "int" : "half");
        print_i128(OUT, X); fputc(' ', OUT); print_i128(OUT, n); fputc('\n', OUT);
        cntCand++;
      }
    }
  }
}

static i128 parse_i128(const char *s) {
  int neg = 0;
  while (*s == ' ') s++;
  if (*s == '-') { neg = 1; s++; } else if (*s == '+') s++;
  i128 m = 0;
  const char *e = strchr(s, 'e');
  const char *end = e ? e : s + strlen(s);
  for (const char *p = s; p < end; p++) if (*p >= '0' && *p <= '9') m = m * 10 + (*p - '0');
  if (e) { int k = atoi(e + 1); for (int i = 0; i < k; i++) m *= 10; }
  return neg ? -m : m;
}

static int selftest(void) {
  int bad = 0;
  long long Ks[4] = {19, 65, 1, -37};
  for (int ki = 0; ki < 4; ki++) {
    KK = Ks[ki];
    for (u64 M = 1; M < 12000; M++) {
      u64 pf[64]; int pe[64];
      int nf = factor(M, pf, pe);
      /* count roots via the CRT of prime-power roots, compare with brute force */
      long long prod = 1;
      for (int i = 0; i < nf; i++) {
        u64 *buf = POOL;
        int c = roots_pp(pf[i], pe[i], buf, MAXR);
        u64 pp = 1; for (int j = 0; j < pe[i]; j++) pp *= pf[i];
        for (int j = 0; j < c; j++) if (fmodm(buf[j], pp) != 0) { printf("bad root M=%llu\n", (unsigned long long)M); bad = 1; }
        prod *= c;
      }
      long long brute = 0;
      for (u64 r = 0; r < M; r++) if (fmodm(r, M) == 0) brute++;
      if (brute != prod) { printf("root count mismatch K=%lld M=%llu: %lld vs %lld\n", KK, (unsigned long long)M, prod, brute); bad = 1; }
    }
  }
  /* large primes: compare cube roots with r^3 = a */
  KK = 19;
  u64 tests[] = {1000000007ULL, 998244353ULL, 1000000000000000003ULL, 4611686018427387847ULL, 2305843009213693951ULL};
  for (int i = 0; i < 5; i++) {
    u64 p = tests[i];
    if (!is_prime(p)) continue;
    for (u64 a = 2; a < 200; a++) {
      u64 out[3]; int c = cuberoots_p(a, p, out);
      for (int j = 0; j < c; j++) if (mulmod(out[j], mulmod(out[j], out[j], p), p) != a % p) { printf("cube root wrong p=%llu a=%llu\n", (unsigned long long)p, (unsigned long long)a); bad = 1; }
      int expect = (p % 3 == 2) ? 1 : (powmod(a, (p - 1) / 3, p) == 1 ? 3 : 0);
      if (c != expect) { printf("cube root count p=%llu a=%llu got %d want %d\n", (unsigned long long)p, (unsigned long long)a, c, expect); bad = 1; }
    }
  }
  printf(bad ? "selftest FAILED\n" : "selftest ok\n");
  return bad;
}

int main(int argc, char **argv) {
  u64 X0 = 1, X1 = 1000;
  int xsign = 0, progress = 0, dotest = 0, dobrute = 0;
  const char *outname = NULL;
  N0 = 0; N1 = 1000000;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--half")) CHART = 2;
    else if (!strcmp(argv[i], "--X0") && i + 1 < argc) X0 = (u64)parse_i128(argv[++i]);
    else if (!strcmp(argv[i], "--X1") && i + 1 < argc) X1 = (u64)parse_i128(argv[++i]);
    else if (!strcmp(argv[i], "--n0") && i + 1 < argc) N0 = parse_i128(argv[++i]);
    else if (!strcmp(argv[i], "--n1") && i + 1 < argc) N1 = parse_i128(argv[++i]);
    else if (!strcmp(argv[i], "--K") && i + 1 < argc) KK = atoll(argv[++i]);
    else if (!strcmp(argv[i], "--general")) GENERAL = 1;
    else if (!strcmp(argv[i], "--xsign") && i + 1 < argc) xsign = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--progress")) progress = 1;
    else if (!strcmp(argv[i], "--selftest")) dotest = 1;
    else if (!strcmp(argv[i], "--brute")) dobrute = 1;
    else if (!strcmp(argv[i], "--wheelmin") && i + 1 < argc) WHEELMIN = (u64)atoll(argv[++i]);
    else if (!strcmp(argv[i], "--out") && i + 1 < argc) outname = argv[++i];
    else {
      fprintf(stderr, "usage: %s [--half] --X0 a --X1 b --n0 N0 --n1 N1 [--K k] [--general]\n"
                      "          [--xsign +1|-1] [--out f] [--progress] | --selftest\n", argv[0]);
      return 1;
    }
  }
  for (int p = 2; p < 32768; p++) {
    int ok = 1;
    for (int q = 2; q * q <= p; q++) if (p % q == 0) { ok = 0; break; }
    if (ok) SMALLP[NSMALL++] = p;
  }
  if (dotest) return selftest();
  if (X0 < 1) X0 = 1;
  if (X1 > ((u64)1 << 62)) { fprintf(stderr, "xroots: |X| must stay below 2^62\n"); return 1; }
  OUT = outname ? fopen(outname, "w") : stdout;
  if (!OUT) { perror("open"); return 1; }
  if (!GENERAL) local_init(&LT, CHART, KK);
  if (dobrute) {
    i128 lim = 1000000;
    if (X1 > 1000000 || N0 < -lim || N1 > lim) { fprintf(stderr, "xroots --brute: box too large\n"); return 1; }
    brute_box(X0, X1, xsign);
    fprintf(OUT, "DONE brute chart=%s K=%lld cand=%lld\n", CHART == 1 ? "int" : "half", KK, cntCand);
    if (outname) fclose(OUT);
    return 0;
  }

  for (int i = 0; i < NFRONT; i++) N0q[i] = imod(N0, (u64)FRONTP[i]);
  /* square tables for the filter primes */
  int nt = 0;
  for (int p = 31; nt < NTAIL; p++) {
    int ok = 1;
    for (int q = 2; q * q <= p; q++) if (p % q == 0) { ok = 0; break; }
    if (ok) TAILP[nt++] = p;
  }
  for (int i = 0; i < NFRONT + NTAIL; i++) {
    int q = i < NFRONT ? FRONTP[i] : TAILP[i - NFRONT];
    SQ[q] = calloc(q, 1);
    for (int v = 0; v < q; v++) SQ[q][(long long)v * v % q] = 1;
  }

  /* the X of the unit are factored by a segmented sieve (as in dsweep.c): primes up to
     min(sqrt(X1), 10^7) are divided out; a cofactor below sieved_to^2 is then prime */
  u64 lim = 2;
  while ((u128)lim * lim < (u128)X1 && lim < 10000000ULL) lim++;
  uint32_t *SP = NULL; size_t NSP = 0;
  {
    char *comp = calloc(lim + 1, 1);
    SP = malloc(sizeof(uint32_t) * (lim / 2 + 2));
    for (u64 p = 2; p <= lim; p++) {
      if (comp[p]) continue;
      SP[NSP++] = (uint32_t)p;
      for (u64 q = p * p; q <= lim; q += p) comp[q] = 1;
    }
    free(comp);
  }
  const u64 BLK = 1u << 16;
  u64 *rem = malloc(sizeof(u64) * BLK);
  u64 *pfs = malloc(sizeof(u64) * BLK * 16);
  uint8_t *pes = malloc(BLK * 16), *nfs = malloc(BLK);

  clock_t t0 = clock();
  for (u64 blo = X0; blo < X1; blo += BLK) {
    u64 bhi = blo + BLK; if (bhi > X1) bhi = X1;
    u64 len = bhi - blo;
    for (u64 i = 0; i < len; i++) { rem[i] = blo + i; nfs[i] = 0; }
    u64 sieved_to = lim + 1;
    for (size_t k = 0; k < NSP; k++) {
      u64 p = SP[k];
      if ((u128)p * p > bhi) { sieved_to = 1ULL << 32; break; }
      for (u64 v = (blo + p - 1) / p * p; v < bhi; v += p) {
        u64 i = v - blo;
        int e = 0;
        while (rem[i] % p == 0) { rem[i] /= p; e++; }
        if (nfs[i] < 16) { pfs[i * 16 + nfs[i]] = p; pes[i * 16 + nfs[i]] = (uint8_t)e; nfs[i]++; }
      }
    }
    for (u64 i = 0; i < len; i++) {
      u64 M = blo + i;
      if (CHART == 2 && !(M & 1)) continue;          /* half chart: X is odd */
      int sg[2], nsg = 0;
      for (int s = 0; s < 2; s++) {
        int sign = s ? -1 : 1;
        if (xsign && sign != xsign) continue;
        i128 X = (i128)sign * (i128)M;
        if (!GENERAL && !local_X_ok(&LT, X)) continue;
        sg[nsg++] = sign;
      }
      if (!nsg) continue;
      cntX++;
      u64 pf[64]; int pe[64]; int nf = 0;
      for (int t = 0; t < nfs[i]; t++) { pf[nf] = pfs[i * 16 + t]; pe[nf] = pes[i * 16 + t]; nf++; }
      if (rem[i] > 1) {
        if ((u128)rem[i] < (u128)sieved_to * sieved_to) { pf[nf] = rem[i]; pe[nf] = 1; nf++; }
        else factor_rec(rem[i], pf, pe, &nf);
      }
      int ok = 1;
      NPP = 0; POOLUSED = 0;
      for (int k = 0; k < nf && ok; k++) {
        u64 pp = 1; for (int j = 0; j < pe[k]; j++) pp *= pf[k];
        u64 *buf = POOL + POOLUSED;
        size_t room = (sizeof(POOL) / sizeof(u64)) - POOLUSED;
        int c = roots_pp(pf[k], pe[k], buf, room > MAXR ? MAXR : (int)room);
        if (c == 0) { ok = 0; break; }
        if (c < 0) { fprintf(stderr, "xroots: too many roots at |X| = %llu, skipped\n", (unsigned long long)M); cntSkip++; ok = 0; break; }
        POOLUSED += c;
        PPm[NPP] = pp; PPr[NPP] = buf; PPn[NPP] = c; NPP++;
      }
      if (ok)
        for (int s = 0; s < nsg; s++) do_X((i128)sg[s] * (i128)M, M, nf, pf);
    }
    if (progress) {
      fprintf(stderr, "\r[xroots] |X| < %llu, %llu n tested, %lld cand", (unsigned long long)bhi,
              cntTested, cntCand);
      fflush(stderr);
    }
  }
  double secs = (double)(clock() - t0) / CLOCKS_PER_SEC;
  if (progress) fprintf(stderr, "\n");
  fprintf(OUT, "DONE chart=%s K=%lld family=%s X=[%llu,%llu) n=[", CHART == 1 ? "int" : "half", KK,
          GENERAL ? "none" : "local", (unsigned long long)X0, (unsigned long long)X1);
  print_i128(OUT, N0); fputc(',', OUT); print_i128(OUT, N1);
  fprintf(OUT, ") xsign=%d Xvals=%lld Xwithroots=%lld progressions=%lld tested=%llu cand=%lld skipped=%lld secs=%.1f\n",
          xsign, cntX, cntXr, cntProg, cntTested, cntCand, cntSkip, secs);
  if (outname) fclose(OUT);
  return 0;
}
