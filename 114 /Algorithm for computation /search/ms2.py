import sympy as sp
m = sp.symbols('m')
lam,a,b,c = sp.symbols('lam a b c')
h = sp.symbols('h0:4')
n = a*m**2+b*m+c
x = lam*m**2
H = sum(h[i]*m**i for i in range(4))
F = x*(x+6*n)**2 + 36*n**3 - 19
expr = sp.expand(lam*F - H**2)
eqs = sp.Poly(expr, m).all_coeffs()
for i,e in enumerate(eqs): print(i, sp.factor(e))
