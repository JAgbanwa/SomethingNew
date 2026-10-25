\\ xcurve.gp --- Algorithm C, phase 2: the Mordell-Weil amplification (both charts).
\\
\\ For a fixed x the solutions (n, x) of
\\
\\    36 n^3 - K = -2 d x^2 ( -(x+6n) + sqrt( (x+6n)^2 + (36n^3-K)/x ) )      (K = 19)
\\
\\ correspond (theorem DEquation.mordell_of_sat, RequestProject/Algorithm.lean, for the
\\ integer chart; HALF_INTEGER.md for the half chart) to the integral points of
\\
\\  integer chart (x = X):   E_X : V^2 = Z^3 - 432 X^3 (X^3 + 3K),   Z = 12X(3n + X)
\\  half chart (x = X/2):    E_X : V^2 = Z^3 - 432 X^3 (X^3 + 24K),  Z = 12X(6n + X)
\\
\\ with V = 36 X W and W^2 = X^2(X+6n)^2 + X(36n^3-K), resp. X^2(X+12n)^2 + 8X(36n^3-K).
\\ Recovering (n, d) from a point:  n = (Z - 12X^2)/(36X)  resp.  (Z - 12X^2)/(72X),
\\ y = |W|/|X| resp. |W|/(2|X|),  d = -(y + x + 6n)/(2x).
\\ A hit is in the requested family when 3 | n and x = 7 (mod 12) (integer chart), resp.
\\ X = 5 (mod 6) (half chart); the radical is integral when y is an integer, resp. 2y odd.
\\
\\ Phase 1 (grid/xscan.c) enumerates *small* n for each x.  This script is the part that
\\ is not bounded in n: it computes generators of E_X and walks through small linear
\\ combinations of them (only integral points can give a solution; see HOW_IT_WORKS.md
\\ section 2.4 for what this can and cannot do).
\\
\\ Usage:   XCURVE_U0=0 XCURVE_U1=1000 XCURVE_KMAX=8 [XCURVE_HALF=1] [XCURVE_K=19] gp -q xcurve.gp
\\   scans x = 12u+7 (half chart: X = 6u+5) for u in [XCURVE_U0, XCURVE_U1) and multiples
\\   up to XCURVE_KMAX.  Requires PARI/GP >= 2.13 (ellratpoints).  Every hit printed here
\\   must still be confirmed by  grid/verify.py.

default(parisize, 500*10^6);

HALF = 0; KK = 19;

recover(x, Z, V) =
{
  my(b, n, W, F, y, xx, d);
  b = if (HALF, 2, 1);
  if (denominator(Z) != 1 || denominator(V) != 1, return(0));   \\ integral points only
  if ((Z - 12*x^2) % (36*b*x) != 0, return(0));
  n = (Z - 12*x^2) / (36*b*x);
  if (V % (36*x) != 0, return(0));
  W = V / (36*x);
  F = if (HALF, x^2*(x+12*n)^2 + 8*x*(36*n^3-KK), x^2*(x+6*n)^2 + x*(36*n^3-KK));
  if (W^2 != F, return(0));
  if (KK == 19 && n % 3 != 0, return(0)); \\ the requested family n = 3m (forced for 114)
  xx = x / b;
  y = abs(W) / (b*abs(x));
  d = -(y + xx + 6*n) / (2*xx);
  if (HALF,
    print("HIT chart=half X=", x, " n=", n, " m=", n/3, " u=", (x-5)/6, " d=", d,
          " integral=", denominator(y) == 2),
    print("HIT x=", x, " n=", n, " m=", n/3, " u=", (x-7)/12, " d=", d,
          " integral=", denominator(y) == 1));
  1;
}

scanx(x, kmax) =
{
  my(k, E, pts, gens, P, Q, R, found = 0);
  k = -432*x^3*(x^3 + if (HALF, 24, 3)*KK);
  E = ellinit([0, 0, 0, 0, k]);
  if (E == 0, return(0));
  \\ small points first (cheap, covers the small-n range)
  pts = ellratpoints(E, 12);
  gens = [];
  for (i = 1, #pts,
    P = pts[i];
    if (#P == 2 && ellorder(E, P) == 0, gens = concat(gens, [P]));
    if (#P == 2, found += recover(x, P[1], P[2]))
  );
  \\ multiples and small combinations of the generators
  for (i = 1, #gens,
    P = gens[i];
    Q = P;
    for (t = 2, kmax,
      Q = elladd(E, Q, P);
      if (#Q == 2, found += recover(x, Q[1], Q[2]))
    );
    for (j = i+1, #gens,
      R = elladd(E, P, gens[j]);
      if (#R == 2, found += recover(x, R[1], R[2]));
      R = ellsub(E, P, gens[j]);
      if (#R == 2, found += recover(x, R[1], R[2]))
    )
  );
  found;
}

{
  my(u0, u1, kmax, s, tot = 0);
  u0 = eval(getenv("XCURVE_U0"));
  u1 = eval(getenv("XCURVE_U1"));
  s = getenv("XCURVE_KMAX");
  kmax = if (s == "" || s == 0, 8, eval(s));
  s = getenv("XCURVE_HALF");
  HALF = if (s == "" || s == 0, 0, eval(s));
  s = getenv("XCURVE_K");
  KK = if (s == "" || s == 0, 19, eval(s));
  for (u = u0, u1 - 1,
    tot += scanx(if (HALF, 6*u + 5, 12*u + 7), kmax)
  );
  print("DONE u=[", u0, ",", u1, ") chart=", if (HALF, "half", "int"), " K=", KK, " hits=", tot);
}
