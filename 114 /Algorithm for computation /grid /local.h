/* local.h --- 2-adic and 3-adic necessary conditions for solutions with an INTEGRAL radical.
 *
 * For the equation (6K = 114 is the original K = 19)
 *
 *     36 n^3 - K = -2 d x^2 ( -(x+6n) + y ),     y = sqrt( (x+6n)^2 + (36n^3-K)/x ) >= 0,
 *
 * put A = -x+y, B = -x-y, C = 2x+6n.  Then identically
 *
 *     A^3 + B^3 + C^3 - 6K = -6x ( y^2 - (x+6n)^2 - (36n^3-K)/x ),
 *
 * so a solution whose radical is "integral" -- y an integer with x an integer (integer chart),
 * or y = Y/2, x = X/2 with X, Y odd (half chart) -- is the same thing as an integer triple
 * with A^3+B^3+C^3 = 6K and A+B+C = 6n.  The chart is decided by the parity of the pair sum
 * Q = A+B = -2x:  Q even -> integer chart (x = -Q/2),  Q odd -> half chart (X = -Q).
 * The certificate of d is G = P*Q/2 (integer chart, G = U = 2dx^2) or G = P*Q (half chart,
 * G = V = dX^2), where P is one of A+C, B+C (the larger one, by the branch condition y >= 0).
 * See HALF_INTEGER.md for the derivation.
 *
 * This header enumerates every triple (A,B,C) modulo 2^8 and modulo 3^6 with
 * A^3+B^3+C^3 = 6K and records which residues of
 *
 *     X (the chart coordinate: x itself in the integer chart, X = 2x in the half chart),
 *     n, and G
 *
 * occur, singly and in the pairs (X,n) and (G,X).  Every integral solution satisfies all of
 * these congruences; nothing else is assumed, so a filter built on them is one sided.  For
 * K = 19 they reproduce, in the integer chart, x = 7 (mod 12) and U = 5, 11 (mod 12) (the
 * family that Aristotle's programs were asked to search, DEquation.sat_U_mod_twelve) and
 * n = 0 (mod 3), and they add the joint conditions on (x mod 64, n mod 64) and
 * (X mod 243, n mod 243).
 *
 * Usage:  local_t L; local_init(&L, chart, K);   chart = 1 (integer) or 2 (half)
 *         local_X_ok(&L,X), local_G_ok(&L,G), local_GX_ok(&L,G,X), local_Xn_ok(&L,X,n)
 */
#ifndef DEQ_LOCAL_H
#define DEQ_LOCAL_H

#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#define LOC2 64          /* residues kept modulo 2^6 */
#define LOC3 243         /* residues kept modulo 3^5 */

typedef struct {
  int chart;
  long long K;
  uint8_t X2[LOC2], n2[LOC2], G2[LOC2];
  uint8_t X3[LOC3], n3[LOC3], G3[LOC3];
  uint8_t Xn2[LOC2][LOC2], GX2[LOC2][LOC2];
  uint8_t Xn3[LOC3][LOC3], GX3[LOC3][LOC3];
  int nX2, nX3, nn2, nn3, nG2, nG3;      /* how many residues are allowed (statistics)  */
} local_t;

static inline int loc_mod(__int128 v, int m) {
  __int128 r = v % (__int128)m;
  if (r < 0) r += m;
  return (int)r;
}

/* one pass over all (A,B) modulo L; for every C with A^3+B^3+C^3 = 6K (mod L) call back */
static void local_enum(int L, long long K, void (*cb)(void *, int, int, int), void *ctx) {
  int *c3 = malloc(sizeof(int) * L);
  int *head = malloc(sizeof(int) * L), *next = malloc(sizeof(int) * L);
  for (int r = 0; r < L; r++) head[r] = -1;
  for (int a = 0; a < L; a++) {
    c3[a] = (int)((long long)a * a % L * a % L);
    next[a] = head[c3[a]];
    head[c3[a]] = a;
  }
  int k6 = loc_mod((__int128)6 * K, L);
  for (int A = 0; A < L; A++)
    for (int B = 0; B < L; B++) {
      int t = ((k6 - c3[A] - c3[B]) % L + 2 * L) % L;
      for (int C = head[t]; C >= 0; C = next[C]) cb(ctx, A, B, C);
    }
  free(c3); free(head); free(next);
}

static void local_cb2(void *ctx, int A, int B, int C) {
  local_t *L = (local_t *)ctx;
  const int M = 256;
  int s = A + B + C;
  if (s & 1) return;                                 /* A+B+C = 6n is even            */
  int Q = (A + B) % M;
  if (L->chart == 1 && (Q & 1)) return;              /* integer chart: A+B even       */
  if (L->chart == 2 && !(Q & 1)) return;             /* half chart:    A+B odd        */
  int negQ = (M - Q) % M;
  int X = (L->chart == 1) ? (negQ / 2) % LOC2 : negQ % LOC2;
  int inv3 = 43;                                     /* 3*43 = 129 = 1 (mod 128)      */
  int n = (int)(((long long)((s % M) / 2) * inv3) % 128) % LOC2;
  L->X2[X] = 1; L->n2[n] = 1; L->Xn2[X][n] = 1;
  int Ps[2] = {(A + C) % M, (B + C) % M};
  for (int i = 0; i < 2; i++) {
    long long PQ = (long long)Ps[i] * Q % M;
    int G = (L->chart == 1) ? (int)((PQ / 2) % LOC2) : (int)(PQ % LOC2);
    L->G2[G] = 1; L->GX2[G][X] = 1;
  }
}

static void local_cb3(void *ctx, int A, int B, int C) {
  local_t *L = (local_t *)ctx;
  const int M = 729;
  int s = A + B + C;
  if (s % 3) return;                                 /* A+B+C = 6n is divisible by 3  */
  int Q = (A + B) % M;
  int negQ = (M - Q) % M;
  const int inv2 = 365;                              /* 2*365 = 730 = 1 (mod 729)     */
  int X = (L->chart == 1) ? (int)((long long)negQ * inv2 % M) % LOC3 : negQ % LOC3;
  int n = (int)((long long)((s % M) / 3) * 122 % LOC3);   /* 2*122 = 244 = 1 (mod 243) */
  L->X3[X] = 1; L->n3[n] = 1; L->Xn3[X][n] = 1;
  int Ps[2] = {(A + C) % M, (B + C) % M};
  for (int i = 0; i < 2; i++) {
    long long PQ = (long long)Ps[i] * Q % M;
    int G = (L->chart == 1) ? (int)(PQ * inv2 % M) % LOC3 : (int)(PQ % LOC3);
    L->G3[G] = 1; L->GX3[G][X] = 1;
  }
}

static void local_init(local_t *L, int chart, long long K) {
  memset(L, 0, sizeof(*L));
  L->chart = chart;
  L->K = K;
  local_enum(256, K, local_cb2, L);
  local_enum(729, K, local_cb3, L);
  for (int i = 0; i < LOC2; i++) { L->nX2 += L->X2[i]; L->nn2 += L->n2[i]; L->nG2 += L->G2[i]; }
  for (int i = 0; i < LOC3; i++) { L->nX3 += L->X3[i]; L->nn3 += L->n3[i]; L->nG3 += L->G3[i]; }
}

static inline int local_X_ok(const local_t *L, __int128 X) {
  return L->X2[loc_mod(X, LOC2)] && L->X3[loc_mod(X, LOC3)];
}
static inline int local_G_ok(const local_t *L, __int128 G) {
  return L->G2[loc_mod(G, LOC2)] && L->G3[loc_mod(G, LOC3)];
}
static inline int local_GX_ok(const local_t *L, __int128 G, __int128 X) {
  return L->GX2[loc_mod(G, LOC2)][loc_mod(X, LOC2)] && L->GX3[loc_mod(G, LOC3)][loc_mod(X, LOC3)];
}
static inline int local_Xn_ok(const local_t *L, __int128 X, __int128 n) {
  return L->Xn2[loc_mod(X, LOC2)][loc_mod(n, LOC2)] && L->Xn3[loc_mod(X, LOC3)][loc_mod(n, LOC3)];
}

#endif
