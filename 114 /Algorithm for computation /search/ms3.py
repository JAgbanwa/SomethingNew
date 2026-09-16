import sympy as sp
m = sp.symbols('m')
lam,a,c = sp.symbols('lam a c')
h0,h1,h2,h3 = sp.symbols('h0 h1 h2 h3')
b = 1
n = a*m**2+b*m+c
x = lam*m**2
H = h0+h1*m+h2*m**2+h3*m**3
F = x*(x+6*n)**2 + 36*n**3 - 19
eqs = sp.Poly(sp.expand(lam*F - H**2), m).all_coeffs()
G = sp.groebner(eqs, lam,a,c,h0,h1,h2,h3, order='lex')
print("GB size", len(G.exprs))
for g in G.exprs[:5]:
    print(sp.factor(g))
