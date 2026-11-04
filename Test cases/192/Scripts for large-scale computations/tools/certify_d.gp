\\ CE192: unconditional, UNBOUNDED certification of single values of d.
\\ For d = p/q (reduced, q > 0) solves the Thue equation
\\   S^3 - 6 p q S g^2 + 3 p q (p+q) g^3 = K
\\ with PARI's thue() (thueinit(.,1): no GRH assumption), and prints every
\\ accepted point of the original equation  36n^3 - K/6 = -2 d x^2 (-(x+6n) + s)
\\ in either chart:
\\   x = -q g / 2,  s = (2p+q) g / 2 - S >= 0,  n = S/6,
\\   integer chart when q g is even, half chart when q g is odd.
\\ thue() returns ALL integer solutions, including non-primitive ones
\\ (192 = 4^3 * 3, so gcd(S, g) can be 2 or 4).
\\ Usage:  gp -q tools/certify_d.gp   then   certify(p, q)   or   certify(p, q, K)
certify(p, q, K = 192) =
{
  my(P, sols, out = List(), x, s, n, g, S, N, d, chart);
  if (q <= 0 || p == 0 || gcd(p, q) != 1, error("need reduced p/q with q > 0"));
  P = 'T^3 - 6*p*q*'T + 3*p*q*(p+q);
  sols = thue(thueinit(P, 1), K);
  for (i = 1, #sols,
    S = sols[i][1]; g = sols[i][2];
    if (g == 0 || S % 6 != 0, next);
    x = -q*g/2; s = (2*p+q)*g/2 - S; n = S/6; d = p/q;
    if (s < 0, next);
    N = 36*n^3 - K/6;
    if (s^2 != (x + S)^2 + N/x || N != -2*d*x^2*(-(x + S) + s), error("verification failed"));
    chart = if (denominator(x) == 1, "integer", "half");
    listput(out, [chart, d, n, x, s, [-x + s, -x - s, 2*x + S]]));
  Vec(out);
}
