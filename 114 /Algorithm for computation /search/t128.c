#include <stdio.h>
#include <stdlib.h>
#include "u128.h"
static void pr(u128 v){ char b[64]; int i=0; if(!v){printf("0");return;} while(v){b[i++]='0'+(int)(v%10); v/=10;} while(i)putchar(b[--i]); }
int main(){
  srand(12345);
  for(int t=0;t<20;t++){
    u128 m=0; for(int i=0;i<4;i++) m=(m<<32)|(u128)(unsigned)rand();
    m |= 1; if(m< (u128)1000) m += 1000;
    mont_t M; mont_init(&M,m);
    u128 a=0,b=0; for(int i=0;i<4;i++){a=(a<<32)|(u128)(unsigned)rand(); b=(b<<32)|(u128)(unsigned)rand();}
    a%=m; b%=m;
    u128 r = from_mont(&M, montmul(&M, to_mont(&M,a), to_mont(&M,b)));
    printf("m="); pr(m); printf(" a="); pr(a); printf(" b="); pr(b); printf(" mul="); pr(r); printf("\n");
  }
  return 0;
}
