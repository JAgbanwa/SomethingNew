\\ xcurve.gp --- Algorithm C, phase 2: the Mordell-Weil amplification.
\\
\\ For a fixed x the solutions (n, x) of
\\
\\    36 n^3 - 19 = -2 d x^2 ( -(x+6n) + sqrt( (x+6n)^2 + (36n^3-19)/x ) )
\\
\\ correspond (theorem DEquation.mordell_of_sat, RequestProject/Algorithm.lean) to the
\\ integral points of the Mordell curve
\\
\\    E_x :  V^2 = Z^3 - 432 x^3 (x^3 + 57),      Z = 12 x (3n + x),   V = 36 x Y,
\\
\\ where Y^2 = x^2 (x+6n)^2 + x (36 n^3 - 19).  Recovering (n, d) from a point is
\\
\\    n = (Z - 12 x^2) / (36 x),        d = (Y - x(x+6n)) / (2 x^2),   Y = V / (36 x)
\\
\\ and the solution is in the requested family exactly when x = 7 (mod 12) and 3 | n.
\\
\\ Phase 1 (grid/xscan.c) enumerates *small* n for each x.  This script is the part that
\\ can reach ten to twenty digit solutions: it computes the Mordell-Weil group of E_x (or
\\ at least some generators of it) and then walks through small linear combinations of the
\\ generators.  Heights multiply by k^2 under P -> kP, so a generator of naive height 10^5
\\ already produces points of height 10^20 at its fourth multiple: this is the only known
\\ mechanism that produces solutions of that size without an exhaustive search.
\\
\\ Usage:   XCURVE_U0=0 XCURVE_U1=1000 XCURVE_KMAX=8 gp -q xcurve.gp
\\   scans x = 12u+7 for u in [XCURVE_U0, XCURVE_U1) and multiples up to XCURVE_KMAX.
\\ Requires PARI/GP >= 2.13 (ellrank, ellratpoints).  Every hit printed here must still be
\\ confirmed by  grid/verify.py --nx n x.

default(parisize, 500*10^6);

recover(x, Z, V) =
{
  my(n, Y, s, U, num, den);
  if ((Z - 12*x^2) % (36*x) != 0, return(0));
  n = (Z - 12*x^2) / (36*x);
  if (V % (36*x) != 0, return(0));
  Y = V / (36*x);
  if (Y^2 != x^2*(x+6*n)^2 + x*(36*n^3-19), return(0));
  if (n % 3 != 0, return(0));            \\ the requested family: n = 3m
  s = x + 6*n;
  U = Y - x*s;
  if ((U + x*s)*x > 0, U = -Y - x*s);    \\ pick the branch of the square root
  if ((U + x*s)*x > 0, return(0));
  print("HIT x=", x, " n=", n, " m=", n/3, " u=", (x-7)/12, " d=", U/(2*x^2));
  1;
}

scanx(x, kmax) =
{
  my(k, E, pts, gens, P, Q, R, found = 0);
  k = -432*x^3*(x^3+57);
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
  kmax = if (s == "", 8, eval(s));
  for (u = u0, u1 - 1,
    tot += scanx(12*u + 7, kmax)
  );
  print("DONE u=[", u0, ",", u1, ") hits=", tot);
}
