/* Divisor-based exhaustive search for integer solutions (n,x) of
       V = x^2 (x+6n)^2 + x (36 n^3 - 19)  = perfect square.

   Structure used (see SEARCH_NOTES.md):
     write x = sigma * e * y^2 with e squarefree, sigma = +-1, y >= 1.  Then V is a
     square iff  y^2 s^2 + A/e  is a square (s = x + 6n, A = 36n^3 - 19), which forces
     e | A, and amounts to a factorisation
        A/e = g * h,      h - g = 2 y s .
     So for every squarefree divisor e of A and every (signed) divisor g of A/e we set
     z = (h-g)/2 and solve the cubic   sigma*e*y^3 + 6 n y = z   for an integer y >= 1.

   All arithmetic stays inside 128 bits; hits are re-verified exactly afterwards.
*/
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "u128.h"

typedef __int128 i128;
typedef long long ll;

/* ---------- primality / factorisation for u128 ---------- */

static int small_primes[2000], nsp;
static void init_small(void){
  char *sieve = calloc(20000,1);
  nsp=0;
  for(int i=2;i<20000;i++) if(!sieve[i]){ small_primes[nsp++]=i; for(int j=2*i;j<20000;j+=i) sieve[j]=1; }
  free(sieve);
}

static u64 mulmod64(u64 a,u64 b,u64 m){ return (u64)((u128)a*b%m); }
static u64 powmod64(u64 a,u64 e,u64 m){u64 r=1;a%=m;while(e){if(e&1)r=mulmod64(r,a,m);a=mulmod64(a,a,m);e>>=1;}return r;}
static int isprime64(u64 n){
  if(n<2) return 0;
  static const u64 sp[12]={2,3,5,7,11,13,17,19,23,29,31,37};
  for(int i=0;i<12;i++){ if(n%sp[i]==0) return n==sp[i]; }
  u64 d=n-1; int r=0; while(!(d&1)){d>>=1;r++;}
  for(int i=0;i<12;i++){
    u64 a=sp[i], x=powmod64(a,d,n);
    if(x==1||x==n-1) continue;
    int ok=0; for(int j=1;j<r;j++){ x=mulmod64(x,x,n); if(x==n-1){ok=1;break;} }
    if(!ok) return 0;
  }
  return 1;
}
static u64 gcd64(u64 a,u64 b){ while(b){u64 t=a%b;a=b;b=t;} return a; }
static u64 rho64(u64 n){
  if(!(n&1)) return 2;
  static unsigned sd=123456789u;
  for(;;){
    sd = sd*1103515245u + 12345u;
    u64 c = (u64)(sd % 1000) + 1, x = (u64)(sd % 997) + 2, y=x, d=1;
    do{
      x = (mulmod64(x,x,n)+c)%n;
      y = (mulmod64(y,y,n)+c)%n; y = (mulmod64(y,y,n)+c)%n;
      u64 diff = x>y? x-y : y-x;
      if(!diff){ d=n; break; }
      d = gcd64(diff,n);
    }while(d==1);
    if(d!=n) return d;
  }
}
static int isprime_mr128(u128 n){
  if(n >> 64 == 0) return isprime64((u64)n);
  mont_t M; mont_init(&M,n);
  u128 d=n-1; int r=0; while(!(d&1)){d>>=1;r++;}
  static const u64 bases[]={2,3,5,7,11,13,17,19,23,29,31,37,41};
  u128 none = n - M.one;
  for(int bi=0; bi<13; bi++){
    u128 a = to_mont(&M,(u128)bases[bi] % n);
    if(a==0) continue;
    u128 x = montpow(&M,a,d);
    if(x==M.one || x==none) continue;
    int ok=0;
    for(int i=1;i<r;i++){ x = montmul(&M,x,x); if(x==none){ok=1;break;} }
    if(!ok) return 0;
  }
  return 1;
}
static u128 gcd128(u128 a, u128 b){ while(b){ u128 t=a%b; a=b; b=t; } return a; }
static u128 rho128(u128 n){
  if(!(n&1)) return 2;
  mont_t M; mont_init(&M,n);
  static unsigned seed = 987654321u;
  for(;;){
    seed = seed*1664525u + 1013904223u;
    u128 c = to_mont(&M,(u128)(seed % 1000000) + 1);
    u128 x = to_mont(&M,(u128)(seed % 100000) + 2), y=x, q=M.one, g=1, ys=y;
    int m=128, r=1;
    do{
      x = y;
      for(int i=0;i<r;i++){ y = montmul(&M,y,y); y += c; if(y>=n) y-=n; }
      int k=0;
      while(k<r && g==1){
        ys = y;
        int lim = (m < r-k)? m : r-k;
        for(int i=0;i<lim;i++){
          y = montmul(&M,y,y); y += c; if(y>=n) y-=n;
          u128 diff = (x>y)? x-y : y-x;
          if(diff==0) diff = 1;
          q = montmul(&M,q,diff);
        }
        g = gcd128(from_mont(&M,q), n);
        k += lim;
      }
      r <<= 1;
    } while(g==1 && r < (1<<24));
    if(g==n){
      g=1;
      do{
        ys = montmul(&M,ys,ys); ys += c; if(ys>=n) ys-=n;
        u128 diff = (x>ys)? x-ys : ys-x;
        if(diff) g = gcd128(diff,n); else break;
      }while(g==1);
    }
    if(g!=n && g!=1) return g;
  }
}

static u128 fprimes[64]; static int fexp[64]; static int nfac;
static void addfac(u128 p){
  for(int i=0;i<nfac;i++) if(fprimes[i]==p){ fexp[i]++; return; }
  fprimes[nfac]=p; fexp[nfac]=1; nfac++;
}
static void factor_big(u128 n){
  if(n==1) return;
  if(n >> 64 == 0){
    u64 m = (u64)n;
    if(isprime64(m)){ addfac(m); return; }
    u64 d = rho64(m); factor_big(d); factor_big(m/d); return;
  }
  if(isprime_mr128(n)){ addfac(n); return; }
  u128 d = rho128(n);
  factor_big(d); factor_big(n/d);
}
static void factor128(u128 n){
  for(int i=0;i<nsp && small_primes[i] < 300; i++){
    u64 p = small_primes[i];
    while(n % p == 0){ n /= p; addfac(p); }
  }
  factor_big(n);
}
/* ---------- printing ---------- */
static void pr_i128(i128 v){ if(v<0){putchar('-'); v=-v;} char b[64]; int i=0; if(!v){putchar('0');return;} while(v){b[i++]='0'+(int)(v%10); v/=10;} while(i) putchar(b[--i]); }

/* ---------- cubic solver:  c3 y^3 + c1 y + c0 = 0, real roots ---------- */
static int cubic_roots(long double c3, long double c1, long double c0, long double *out){
  long double p = c1/c3, q = c0/c3;
  long double disc = -4.0L*p*p*p - 27.0L*q*q;
  int cnt=0;
  if(disc < 0){
    long double t = q*q/4.0L + p*p*p/27.0L;
    long double sq = sqrtl(t);
    long double u = cbrtl(-q/2.0L + sq);
    long double v = cbrtl(-q/2.0L - sq);
    out[cnt++] = u+v;
  } else {
    long double m = 2.0L*sqrtl(-p/3.0L);
    long double arg = 3.0L*q/(p*m);
    if(arg>1.0L) arg=1.0L; if(arg<-1.0L) arg=-1.0L;
    long double th = acosl(arg)/3.0L;
    for(int k=0;k<3;k++) out[cnt++] = m*cosl(th - 2.0L*3.14159265358979323846L*k/3.0L);
  }
  return cnt;
}

int main(int argc, char**argv){
  ll NLO = atoll(argv[1]), NHI = atoll(argv[2]);
  int SGN = (argc>3)? atoi(argv[3]) : 1;
  init_small();
  static u128 divs[1<<17], cofs[1<<17];
  for(ll na=NLO; na<=NHI; na++){
    ll n = (SGN>0)? na : -na;
    i128 A = (i128)36*n*n*n - 19;
    u128 Aabs = (u128)(A<0? -A : A);
    nfac=0; factor128(Aabs);
    /* total work estimate */
    long long tot=1; for(int i=0;i<nfac;i++) tot *= (2*fexp[i]+3);
    if(tot > 2000000){ fprintf(stderr,"skip n=%lld tot=%lld\n",(long long)n,tot); continue; }
    u128 XMAX = (u128)13*(u128)na*(u128)na + 1000000;
    /* keep all intermediate products inside 128 bits */
    u128 XCAP = (u128)10000000000000000000ULL * (u128)1000000000000000000ULL / Aabs;  /* 1e37/|A| */
    if(XMAX > XCAP) XMAX = XCAP;
    for(int mask=0; mask < (1<<nfac); mask++){
      u128 e = 1; int okE=1;
      for(int i=0;i<nfac;i++) if(mask>>i & 1){
        if(e > XMAX / fprimes[i]){ okE=0; break; }
        e *= fprimes[i];
      }
      if(!okE || e > XMAX) continue;
      long double ymax = sqrtl((long double)XMAX/(long double)e);
      long double zmax = ymax*((long double)e*ymax*ymax + 6.0L*(long double)na) + 4.0L;
      /* divisors of e*|A| together with their cofactors */
      u128 Pabs = e * Aabs;
      int nd=1; divs[0]=1; cofs[0]=Pabs;
      for(int i=0;i<nfac;i++){
        int ex = fexp[i] + ((mask>>i)&1);
        int cur=nd; u128 pk=1;
        for(int k=1;k<=ex;k++){
          pk *= fprimes[i];
          for(int j=0;j<cur;j++){
            if(nd < (1<<17)){ divs[nd] = divs[j]*pk; cofs[nd] = cofs[j]/pk; nd++; }
          }
        }
      }
      long double difmaxl = 2.0L*(long double)e*zmax;
      for(int di=0; di<nd; di++){
        u128 dpos = divs[di], cpos = cofs[di];
        /* four sign combinations of (g,h) with g*h = P = sigma*e*A */
        for(int so=0; so<2; so++){
          i128 sigma = so? -1 : 1;
          i128 Psign = ((A<0)?-1:1) * sigma;    /* sign of P */
          for(int sg=0; sg<2; sg++){
            i128 g = sg? -(i128)dpos : (i128)dpos;
            i128 h = (i128)cpos * ((sg? -1 : 1) * Psign);
            i128 dif = h - g;
            long double difl = (long double)dif;
            if(difl > difmaxl || difl < -difmaxl) continue;
            if(dif & 1) continue;
            if(e > 1 && (dif % (i128)e)) continue;
            i128 z = dif/(2*(i128)e);
            long double roots[3];
            int nr = cubic_roots((long double)(sigma*(i128)e), (long double)(6*(i128)n), (long double)(-z), roots);
            for(int ri=0; ri<nr; ri++){
              long double rv = roots[ri];
              if(!(rv > 0.5L) || rv > ymax + 2.0L) continue;
              i128 y0 = (i128)(rv + 0.5L);
              for(int dd=-1; dd<=1; dd++){
                i128 y = y0 + dd;
                if(y < 1) continue;
                if((long double)y > ymax) continue;
                if(sigma*(i128)e*y*y*y + 6*(i128)n*y - z == 0){
                  i128 x = sigma*(i128)e*y*y;
                  printf("SOL n=%lld x=", (long long)n); pr_i128(x);
                  printf(" e="); pr_i128((i128)e); printf(" y="); pr_i128(y);
                  printf(" g="); pr_i128(g); printf("\n"); fflush(stdout);
                }
              }
            }
          }
        }
      }
    }
    if(na % 2000 == 0) fprintf(stderr,"n=%lld\n",(long long)n);
  }
  return 0;
}
