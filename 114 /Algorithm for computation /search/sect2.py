import random, math
# K2^3 - K1^3 - 12 n K1 K2 = 72 n^3 - 38 ; K1=p1 n+q1, K2=p2 n+q2
def F(v):
    p1,q1,p2,q2=v
    return [ p2**3-p1**3-12*p1*p2-72,
             3*p2*p2*q2-3*p1*p1*q1-12*(p1*q2+q1*p2),
             3*p2*q2*q2-3*p1*q1*q1-12*q1*q2,
             q2**3-q1**3+38 ]
def newton(v):
    for it in range(300):
        f0=F(v)
        if max(abs(t) for t in f0)<1e-12: return v
        n=4; A=[]
        h=1e-6
        cols=[]
        for j in range(n):
            w=list(v); dh=h*max(1.0,abs(v[j])); w[j]+=dh; f1=F(w)
            cols.append([(f1[i]-f0[i])/dh for i in range(n)])
        M=[[cols[j][i] for j in range(n)]+[-f0[i]] for i in range(n)]
        for c in range(n):
            piv=max(range(c,n),key=lambda i:abs(M[i][c]))
            if abs(M[piv][c])<1e-15: return None
            M[c],M[piv]=M[piv],M[c]
            for i in range(n):
                if i!=c:
                    f=M[i][c]/M[c][c]
                    for k in range(c,n+1): M[i][k]-=f*M[c][k]
        d=[M[i][n]/M[i][i] for i in range(n)]
        nn=max(abs(t) for t in d)
        if nn>10: d=[t*10/nn for t in d]
        v=[v[i]+d[i] for i in range(n)]
        if any(abs(t)>1e8 for t in v): return None
    return None
sols=[]
random.seed(7)
for trial in range(60000):
    v=[random.uniform(-15,15) for _ in range(4)]
    r=newton(v)
    if r and max(abs(t) for t in F(r))<1e-10:
        key=tuple(round(t,5) for t in r)
        if key not in sols:
            sols.append(key)
            print("SOL p1,q1,p2,q2 =", [round(t,8) for t in r], " ratios q1/p1,q2/p2 =",
                  round(r[1]/r[0],8) if abs(r[0])>1e-9 else None,
                  round(r[3]/r[2],8) if abs(r[2])>1e-9 else None,
                  " p1*p2=",round(r[0]*r[2],8), " q1*q2=", round(r[1]*r[3],8), flush=True)
print("total",len(sols))
