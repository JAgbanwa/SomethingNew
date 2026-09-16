// Search for integer solutions (n,x) of  t^2 = x^2(x+6n)^2 + x(36n^3-19)
// via the parametrization U = t - x(x+6n):  x | U^2  and
//    36 n^3 - 12 U n - 19 = 2 U x + U^2/x.
// Enumerate U (|U| <= UMAX) and all divisors x of U^2 (both signs), solve the cubic for n.
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>

typedef __int128 i128;
typedef long long ll;

static int *spf;
static ll UMAX;

static ll divs[100000];

static int gen_divisors(ll U){
  // divisors of U^2
  ll u = U;
  int nd = 1; divs[0]=1;
  while(u>1){
    int p = spf[u]; int e=0;
    while(u% (ll)p==0){u/= (ll)p; e++;}
    e*=2;
    int cur=nd;
    ll pk=1;
    for(int k=1;k<=e;k++){
      pk *= (ll)p;
      for(int i=0;i<cur;i++){
        divs[nd++] = divs[i]*pk;
      }
    }
  }
  return nd;
}

static inline int check_n(i128 n, i128 U, i128 C){
  // 36 n^3 - 12 U n - C == 0 ?
  i128 v = 36*n*n*n - 12*U*n - C;
  return v==0;
}

static void print_i128(i128 v){
  if(v<0){putchar('-'); v=-v;}
  char buf[64]; int i=0;
  if(v==0){putchar('0');return;}
  while(v>0){buf[i++]='0'+(int)(v%10); v/=10;}
  while(i>0) putchar(buf[--i]);
}

static void report(i128 n, ll x, ll U){
  printf("SOL n="); print_i128(n);
  printf(" x=%lld U=%lld\n", x, U);
  fflush(stdout);
}

int main(int argc,char**argv){
  UMAX = atoll(argv[1]);
  ll UMIN = (argc>2)? atoll(argv[2]) : 1;
  spf = malloc((UMAX+1)*sizeof(int));
  for(ll i=0;i<=UMAX;i++) spf[i]=0;
  for(ll i=2;i<=UMAX;i++){
    if(spf[i]==0){ for(ll j=i;j<=UMAX;j+=i) if(spf[j]==0) spf[j]=(int)i; }
  }
  for(ll Uabs=UMIN; Uabs<=UMAX; Uabs++){
    int nd = gen_divisors(Uabs);
    i128 U2 = (i128)Uabs*(i128)Uabs;
    for(int di=0; di<nd; di++){
      ll xa = divs[di];
      i128 comp = U2/(i128)xa;   // U^2 / |x|
      for(int su=0; su<2; su++){
        i128 U = su? -(i128)Uabs : (i128)Uabs;
        for(int sx=0; sx<2; sx++){
          i128 x = sx? -(i128)xa : (i128)xa;
          // C = 19 + 2 U x + U^2/x
          i128 C = 19 + 2*U*x + (sx? -comp : comp);
          // solve 36 n^3 - 12 U n - C = 0
          // main root via cbrt
          long double Cd = (long double)C;
          long double Ud = (long double)U;
          long double n0 = cbrtl(Cd/36.0L);
          for(int it=0; it<40; it++){
            long double f = 36.0L*n0*n0*n0 - 12.0L*Ud*n0 - Cd;
            long double fp = 108.0L*n0*n0 - 12.0L*Ud;
            if(fp==0) break;
            long double step = f/fp;
            n0 -= step;
            if(fabsl(step) < 0.1L) break;
          }
          ll nc = (ll)llroundl(n0);
          for(ll dn=-2; dn<=2; dn++){
            if(check_n((i128)(nc+dn), U, C)) report((i128)(nc+dn), (ll)(sx? -xa: xa), (ll)(su? -Uabs: Uabs));
          }
          // extra real roots exist only when |C| <= 8*U^{3/2}/3 (U>0)
          if(U>0){
            long double a = sqrtl((long double)U/9.0L);
            long double bound = 8.0L*(long double)U*a;
            if((long double)(C<0?-C:C) <= bound){
              ll L = (ll)(2.0L*a)+3;
              for(ll n2=-L;n2<=L;n2++){
                if(n2>=nc-2 && n2<=nc+2) continue;
                if(check_n((i128)n2,U,C)) report((i128)n2,(ll)(sx? -xa: xa),(ll)(su? -Uabs: Uabs));
              }
            }
          }
        }
      }
    }
    if(Uabs % 100000 == 0){ fprintf(stderr,"U=%lld\n",Uabs); }
  }
  return 0;
}
