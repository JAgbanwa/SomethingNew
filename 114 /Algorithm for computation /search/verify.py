import sys
from math import isqrt
from fractions import Fraction
def info(n,x):
    A=36*n**3-19; s=x+6*n
    V=x*x*s*s+x*A
    if V<0: return None
    t=isqrt(V)
    if t*t!=V: return None
    tt = -t if x>0 else t          # need e = t/x <= 0
    U = tt - x*s
    d = Fraction(U, 2*x*x)
    assert 36*n**3-19 == 4*d*d*x**3 + 4*d*x**3 + 24*d*n*x*x
    assert 2*d*x + x + 6*n <= 0
    return d,U
if __name__=="__main__":
    for line in sys.stdin:
        p=line.split()
        n=int(p[0].split('=')[1]); x=int(p[1].split('=')[1])
        r=info(n,x)
        print(f"n={n} ({len(str(abs(n)))} digits)  x={x} ({len(str(abs(x)))} digits)  d={r[0]}  U={r[1]}")
