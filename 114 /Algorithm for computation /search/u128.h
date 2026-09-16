#ifndef U128_H
#define U128_H
#include <stdint.h>
typedef unsigned __int128 u128;
typedef unsigned long long u64;

static inline void mul128(u128 a, u128 b, u128 *hi, u128 *lo){
  u64 a0=(u64)a, a1=(u64)(a>>64), b0=(u64)b, b1=(u64)(b>>64);
  u128 p00=(u128)a0*b0, p01=(u128)a0*b1, p10=(u128)a1*b0, p11=(u128)a1*b1;
  u128 mid = (p00>>64) + (u64)p01 + (u64)p10;
  *lo = (p00 & 0xFFFFFFFFFFFFFFFFull) | (mid<<64);
  *hi = p11 + (p01>>64) + (p10>>64) + (mid>>64);
}
/* Montgomery for odd modulus m, R = 2^128 */
typedef struct { u128 m, mprime, r2, one; } mont_t;

static u128 inv128(u128 m){ /* -m^{-1} mod 2^128 */
  u128 x = m;                 /* x = m^{-1} mod 2^3 */
  for(int i=0;i<7;i++) x *= 2 - m*x;   /* Newton doubling to 2^128 */
  return (u128)0 - x;
}
static inline u128 montmul(const mont_t*M, u128 a, u128 b){
  u128 hi, lo; mul128(a,b,&hi,&lo);
  u128 t = lo * M->mprime;
  u128 h2, l2; mul128(t, M->m, &h2, &l2);
  u128 lowsum = lo + l2;            /* == 0 mod 2^128 */
  int c1 = (lowsum < lo);
  u128 s = hi + h2; int c2 = (s < hi);
  u128 s2 = s + (u128)c1; int c3 = (s2 < s);
  if(c2 || c3 || s2 >= M->m) s2 -= M->m;
  return s2;
}
static void mont_init(mont_t*M, u128 m){
  M->m = m; M->mprime = inv128(m);
  /* r mod m = 2^128 mod m */
  u128 r = (u128)0 - m;   /* 2^128 - m  == 2^128 mod m if m > 2^127 else need reduce */
  r %= m;
  M->one = r;
  /* r2 = r^2 mod m by repeated doubling */
  u128 t = r;
  for(int i=0;i<128;i++){
    u128 d = t;
    u128 sm = d + d;
    if(sm < d || sm >= m) sm -= m;
    t = sm;
  }
  M->r2 = t;
}
static inline u128 to_mont(const mont_t*M, u128 a){ return montmul(M, a % M->m, M->r2); }
static inline u128 from_mont(const mont_t*M, u128 a){ return montmul(M, a, 1); }
static u128 montpow(const mont_t*M, u128 a, u128 e){
  u128 r = M->one, base=a;
  while(e){ if(e&1) r = montmul(M,r,base); base = montmul(M,base,base); e >>= 1; }
  return r;
}
#endif
