import sympy as sp

m = sp.symbols('m')
lam, mu, a, b, c = sp.symbols('lam mu a b c', rational=True)
ts = sp.symbols('t0:5', rational=True)

x = lam*m**2 + mu
n = a*m**2 + b*m + c
t = sum(ts[i]*m**i for i in range(5))

V = x**4 + 12*n*x**3 + 36*n**2*x**2 + (36*n**3 - 19)*x
expr = sp.expand(V - t**2)
poly = sp.Poly(expr, m)
eqs = poly.all_coeffs()
print(len(eqs))
# normalize scaling symmetry: try lam = 1
eqs1 = [sp.expand(e.subs(lam, 1)) for e in eqs]
sol = sp.solve(eqs1, [mu, a, b, c, *ts], dict=True)
print(sol)
