import random, math
# unknowns v = (q, r, s, a)  [a = alpha]; p = 1
def F(v):
    q,r,s,a=v
    return [ 1/a - a*r**3 - 72 - 12*r,
             3*q/a - 3*a*r*r*s - 12*(s+q*r),
             3*q*q/a - 3*a*r*s*s - 12*q*s,
             q**3/a - a*s**3 + 38 ]
def J(v):
    h=1e-7; n=len(v); f0=F(v); m=[]
    for j in range(n):
        w=list(v); w[j]+=h*max(1,abs(v[j])); f1=F(w)
        m.append([(f1[i]-f0[i])/(h*max(1,abs(v[j]))) for i in range(n)])
    # m[j][i] -> transpose to Jac[i][j]
    return [[m[j][i] for j in range(n)] for i in range(n)], f0
def solve(v):
    for it in range(200):
        try:
            A,f0=J(v)
        except Exception: return None
        if max(abs(x) for x in f0)<1e-11: return v
        # gaussian elim 4x4
        n=4
        M=[A[i][:]+[-f0[i]] for i in range(n)]
        for c in range(n):
            piv=max(range(c,n),key=lambda i:abs(M[i][c]))
            if abs(M[piv][c])<1e-14: return None
            M[c],M[piv]=M[piv],M[c]
            for i in range(n):
                if i!=c:
                    f=M[i][c]/M[c][c]
                    for k in range(c,n+1): M[i][k]-=f*M[c][k]
        d=[M[i][n]/M[i][i] for i in range(n)]
        nrm=max(abs(x) for x in d)
        if nrm>1e6: d=[x*1e6/nrm for x in d]
        v=[v[i]+d[i] for i in range(n)]
        if any(abs(x)>1e12 for x in v) or abs(v[3])<1e-12: return None
    return None
sols=[]
random.seed(1)
for trial in range(200000):
    v=[random.uniform(-20,20) for _ in range(3)]+[random.choice([1,-1])*math.exp(random.uniform(-5,5))]
    r=solve(v)
    if r:
        if max(abs(x) for x in F(r))<1e-9:
            key=tuple(round(x,6) for x in r)
            if key not in [tuple(round(y,6) for y in z) for z in sols]:
                sols.append(r); print("SOL",r)
    if trial%20000==0 and trial: print("trial",trial,"found",len(sols))
print("total",len(sols))
