/* Exhaustive search, for each n in a range, over ALL integers x, of solutions of
      V = x^2 (x+6n)^2 + x (36 n^3 - 19)  =  perfect square.
   Key facts used:
     * if V is a square then the squarefree kernel e of x divides A = 36n^3-19,
       so x = +- e*y^2 with e a squarefree divisor of |A|;
     * |x| <= ~7 n^2 (else no U with x | U^2 exists);
   Test: V square  <=>  U^2 + 2*U*x*s - x*A = 0 has an integer root U (s = x+6n).
*/
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <stdint.h>

typedef __int128 i128;
typedef unsigned __int128 u128;
typedef unsigned long long u64;
typedef long long ll;

static u64 mulmod(u64 a,u64 b,u64 m){ return (u64)((u128)a*b%m); }
static u64 powmod(u64 a,u64 e,u64 m){u64 r=1;a%=m;while(e){if(e&1)r=mulmod(r,a,m);a=mulmod(a,a,m);e>>=1;}return r;}
static int isprime(u64 n){
  if(n<2)return 0;
  static const u64 sp[12]={2,3,5,7,11,13,17,19,23,29,31,37};
  for(int i=0;i<12;i++){ u64 p=sp[i]; if(n%p==0) return n==p; }
  u64 d=n-1;int r=0; while(!(d&1)){d>>=1;r++;}
  for(int ai=0;ai<12;ai++){ u64 a=sp[ai];
    u64 x=powmod(a,d,n); if(x==1||x==n-1)continue;
    int ok=0; for(int i=1;i<r;i++){x=mulmod(x,x,n); if(x==n-1){ok=1;break;} }
    if(!ok) return 0;
  }
  return 1;
}
static u64 pollard(u64 n){
  if(!(n&1)) return 2;
  for(;;){
    u64 x=rand()%n, c=rand()%n+1, y=x, d=1;
    do{ x=(mulmod(x,x,n)+c)%n; y=(mulmod(y,y,n)+c)%n; y=(mulmod(y,y,n)+c)%n;
        u64 diff = x>y? x-y : y-x; if(diff==0){d=n;break;}
        u64 a=diff,b=n; while(b){u64 t=a%b;a=b;b=t;} d=a;
    }while(d==1);
    if(d!=n) return d;
  }
}
static void factor(u64 n, u64*pr, int*np){
  if(n==1) return;
  if(isprime(n)){ pr[(*np)++]=n; return; }
  u64 d=pollard(n); factor(d,pr,np); factor(n/d,pr,np);
}

static int sqmod16[65536/8+1];
static inline int is_sq_mod16(unsigned v){ return (sqmod16[v>>3]>>(v&7))&1; }

static void print_i128(i128 v){ if(v<0){putchar('-');v=-v;} char b[64];int i=0; if(v==0){putchar('0');return;} while(v>0){b[i++]='0'+(int)(v%10);v/=10;} while(i)putchar(b[--i]); }

int main(int argc,char**argv){
  ll NLO=atoll(argv[1]), NHI=atoll(argv[2]);
  int SIGN_N = (argc>3)? atoi(argv[3]) : 1;   /* +1 or -1 */
  for(unsigned v=0; v<65536; v++){ }
  for(unsigned r=0;r<65536;r++){ unsigned v=(r*r)&0xFFFF; sqmod16[v>>3] |= 1<<(v&7); }

  u64 primes[64]; int np;
  u64 dist[64]; int nd;
  u64 sqfree[4096];

  for(ll na=NLO; na<=NHI; na++){
    if(na==0) continue;
    ll n = SIGN_N>0? na : -na;
    i128 A = (i128)36*n*n*n - 19;
    u64 Aabs = (u64)(A<0? -A : A);
    np=0; factor(Aabs, primes, &np);
    nd=0;
    for(int i=0;i<np;i++){ int seen=0; for(int j=0;j<nd;j++) if(dist[j]==primes[i]) seen=1; if(!seen) dist[nd++]=primes[i]; }
    /* squarefree divisors */
    int ns=1; sqfree[0]=1;
    for(int i=0;i<nd;i++){ int cur=ns; for(int j=0;j<cur;j++){ if(ns<4096) sqfree[ns++]=sqfree[j]*dist[i]; } }
    u128 XMAX = (u128)20*(u128)na*(u128)na + 1000000;
    for(int si=0; si<ns; si++){
      u64 e = sqfree[si];
      if((u128)e > XMAX) continue;
      u64 ymax = (u64)sqrtl((long double)XMAX/(long double)e);
      for(u64 y=1; y<=ymax; y++){
        u128 xa = (u128)e*(u128)y*(u128)y;
        for(int sx=0; sx<2; sx++){
          i128 x = sx? -(i128)xa : (i128)xa;
          i128 s = x + 6*(i128)n;
          u64 xl=(u64)x, sl=(u64)s, Al=(u64)A;
          u64 v16 = (xl*xl*sl*sl + xl*Al) & 0xFFFFu;
          if(!is_sq_mod16((unsigned)v16)) continue;
          long double xs = (long double)x*(long double)s;
          long double xA = (long double)x*(long double)A;
          long double disc = xs*xs + xA;
          if(disc < 0) continue;
          long double sq = sqrtl(disc);
          long double c0, c1;
          int ncand;
          if(fabsl(xs) < sq*0.5L){ c0 = -xs + sq; c1 = -xs - sq; ncand=2; }
          else { c0 = xA/(xs + (xs>0? sq : -sq)); c1 = -2.0L*xs - c0; ncand=1; }
          long double cand[2]={c0,c1};
          for(int ci=0; ci<ncand; ci++){
            long double uc = cand[ci];
            if(fabsl(uc) > 1e37L) continue;
            i128 U0 = (i128)uc;
            for(int dd=-2; dd<=2; dd++){
              i128 U = U0 + dd;
              if(U*U + 2*U*x*s - x*A == 0){
                printf("SOL n=%lld x=", (long long)n); print_i128(x); printf(" U="); print_i128(U); printf("\n"); fflush(stdout);
              }
            }
          }
        }
      }
    }
    if(na % 5000 == 0){ fprintf(stderr,"n=%lld\n",(long long)n); }
  }
  return 0;
}
