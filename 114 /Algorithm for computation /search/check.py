from math import isqrt
sols=[(1,-9),(-54,-9),(909,784),(14709,10816),(-29317,507456),(798,-1642284)]
for n,x in sols:
    V = x*x*(x+6*n)**2 + x*(36*n**3-19)
    t = isqrt(V); assert t*t==V, (n,x,V)
    for tt in (t,-t):
        U = tt - x*(x+6*n)
        ok = (U*U) % x == 0
        lhs = 36*n**3-12*U*n-19
        rhs = 2*U*x + (U*U)//x if ok else None
        e = tt/x
        d = U/(2*x*x)
        print(n,x,"t=",tt,"U=",U,"x|U^2:",ok,"eq:",(lhs==rhs) if ok else None,"e<=0:", e<=0, "d=",d)
    print()
