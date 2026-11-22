\\ CE375: unconditional, UNBOUNDED certification of single values of d.
\\ For d = p/q (reduced, q > 0) solves the Thue equation
\\   S^3 - 6 p q S g^2 + 3 p q (p+q) g^3 = K
\\ with PARI's thue() (thueinit(.,1): no GRH assumption), and prints every
\\ accepted point of the original equation in either chart:
\\   x = -q g / 2,  s = (2p+q) g / 2 - S >= 0,  n = (S - 3)/6,
\\   integer chart when q g is even, half chart when q g is odd.
\\ Each point ends with [gcd_point, gcd_cubes]: gcd(n,x) (integer chart) or
\\ gcd(X,Y) (half chart), and gcd(A,B,C). DESIRED means both equal 1.
\\ K = 375 = 3*5^3 is not cube-free: thue() also returns the non-primitive
\\ solutions (5 | S and 5 | g), and they are listed with gcd_cubes = 5.
\\ Usage:  gp -q tools/certify_d.gp   then   certify(p, q)   or   certify(p, q, K)
certify(p, q, K = 375) =
{
  my(P, sols, out = List(), x, s, n, g, S, N, d, chart, gp, gc);
  if (q <= 0 || p == 0 || gcd(p, q) != 1, error("need reduced p/q with q > 0"));
  P = 'T^3 - 6*p*q*'T + 3*p*q*(p+q);
  sols = thue(thueinit(P, 1), K);
  for (i = 1, #sols,
    S = sols[i][1]; g = sols[i][2];
    if (g == 0 || (S - 3) % 6 != 0, next);
    x = -q*g/2; s = (2*p+q)*g/2 - S; n = (S - 3)/6; d = p/q;
    if (s < 0, next);
    N = 36*n^3 + 54*n^2 + 27*n + (27 - K)/6;
    if (s^2 != (x + S)^2 + N/x || N != -2*d*x^2*(-(x + S) + s), error("verification failed"));
    chart = if (denominator(x) == 1, "integer", "half");
    gp = if (chart == "integer", gcd(n, x), gcd(2*x, 2*s));
    gc = gcd([-x + s, -x - s, 2*x + S]);
    listput(out, [if (gp == 1 && gc == 1, "DESIRED", "non-primitive"), chart, d, n, x, s,
                  [-x + s, -x - s, 2*x + S], [gp, gc]]));
  Vec(out);
}
