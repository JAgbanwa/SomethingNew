# Family c = U^2/x = -19 :  x = -19 k^2, U = -19k, d = -1/(38 k^3),
# n = k*m with m = p/q, k = 114 p q^2 / D, n = 114 p^2 q / D, D = 361 q^3 - 18 p^3.
from math import isqrt
Q=3_000_000
alpha=(361/18)**(1/3)
hits=[]
for q in range(1,Q+1):
    p0=int(alpha*q)
    for p in (p0-1,p0,p0+1,p0+2):
        if p==0: continue
        if __import__('math').gcd(abs(p),q)!=1: continue
        D=361*q**3-18*p**3
        if D==0: continue
        t=114*p*q
        if t % D: continue
        k=114*p*q*q//D
        n=114*p*p*q//D
        if k==0: continue
        x=-19*k*k
        # verify
        A=36*n**3-19
        V=x*x*(x+6*n)**2+x*A
        if V<0: continue
        s=isqrt(V)
        if s*s!=V: continue
        hits.append((q,p,D,k,n,x))
        print("HIT q,p,D",q,p,D,"k",k,"n",n,"x",x,"digits n,x",len(str(abs(n))),len(str(abs(x))))
print("done",len(hits))
