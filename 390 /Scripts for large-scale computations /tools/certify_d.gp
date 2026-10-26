\\ Unconditional, UNBOUNDED certification of individual values of d with PARI/GP.
\\
\\ The campaign engine (bin/dthue_worker) finds every half-chart point with
\\ 1 <= |g| <= 10^g_max_digits. For a particular d = p/q this script removes the
\\ bound: thue() with thueinit(...,1) returns ALL integer solutions of
\\     F_d(n,g) = 72 n^3 - 12 p q n g^2 + p q (p+q) g^3 = 2m
\\ without assuming GRH (Bilu-Hanrot / Baker bounds). Expect ~0.01 s per d at
\\ height 20 and ~1 minute at height 200, growing with the height of d.
\\
\\ Usage:   gp -q tools/certify_d.gp
\\          then e.g.  certify(-22, 101, 1)   or   certify_all(60, 65)
default(parisize, "1G");

\\ Half-chart points with d = p/q: q*g odd and Y = (2p+q) g - 12 n > 0.
certify(p, q, m) =
{
  my(S = thue(thueinit(72*'x^3 - 12*p*q*'x + p*q*(p+q), 1), 2*m), pts = List(), n, g, Y);
  for (i = 1, #S, n = S[i][1]; g = S[i][2]; Y = (2*p + q)*g - 12*n;
    if ((q*g) % 2 && Y > 0, listput(pts, [p/q, n, -q*g/2, Y/2])));
  pts;
}

\\ All admissible d with max(|p|, q) <= H (same filters as the worker, see D_FIRST.md).
admissible(p, q, m) =
{
  my(f, l, e, c);
  if (p == 0 || q <= 0 || gcd(p, q) != 1 || q % 2 == 0, return(0));
  if (p % 3 == 0 || q % 3 == 0 || (p - q) % 3 != 0, return(0));
  if (m % 2 && p % 4 == 0, return(0));
  f = factor(abs(p*q));
  for (i = 1, #f~, l = f[i,1]; e = f[i,2];
    if (l <= 3, next);
    if (m % l == 0, c = valuation(m, l); if (c <= 2 && e > c, return(0)); next);
    if (l % 3 == 1 && Mod(m, l)^((l-1)/3) != Mod(36, l)^((l-1)/3), return(0)));
  1;
}

certify_all(H, m) =
{
  my(c = 0, all = List(), t0 = getabstime());
  for (q = 1, H, for (p = -H, H, if (!admissible(p, q, m), next); c++;
    foreach(certify(p, q, m), pt, listput(all, pt); print("POINT d=", pt[1], " n=", pt[2], " x=", pt[3], " y=", pt[4]))));
  print(c, " admissible d with height <= ", H, " certified (all n, no bound on g) in ",
        (getabstime() - t0)/1000., " s; half-chart points: ", #all);
  all;
}
