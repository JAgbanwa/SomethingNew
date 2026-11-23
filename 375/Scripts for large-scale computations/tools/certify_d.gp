\\ CE375: independent fixed-g certificates for one specified fraction d = p/q.
\\ PARI solves the Thue equation exactly; only solutions with g = -1 or +1
\\ are retained, matching the production campaign restriction.
\\ Both signs of the square root are accepted. The returned d uses y >= 0;
\\ [g,p,q] at the end retains the actual enumerated branch parameters.
\\ DESIRED means gcd(n,x,y) = 1 for integer points, or gcd(X,Y) = 1
\\ for odd half-integer points. Cube gcd is reported as a diagnostic.
\\ Usage: gp -q tools/certify_d.gp, then certify(p,q) or certify(p,q,K).
certify(p, q, K = 375) =
{
  my(P, sols, out = List(), x, s, n, g, S, N, d, chart, gp, gc);
  if (q <= 0 || p == 0 || gcd(p, q) != 1, error("need reduced p/q with q > 0"));
  P = 'T^3 - 6*p*q*'T + 3*p*q*(p+q);
  sols = thue(thueinit(P, 1), K);
  for (i = 1, #sols,
    S = sols[i][1]; g = sols[i][2];
    if (abs(g) != 1 || (S - 3) % 6 != 0, next);
    x = -q*g/2; s = abs((2*p+q)*g/2 - S); n = (S - 3)/6;
    d = -(x + S + s)/(2*x);
    N = 36*n^3 + 54*n^2 + 27*n + (27 - K)/6;
    if (s^2 != (x + S)^2 + N/x || N != -2*d*x^2*(-(x + S) + s), error("verification failed"));
    chart = if (denominator(x) == 1, "integer", "half");
    gp = if (chart == "integer", gcd([n, x, s]), gcd(2*x, 2*s));
    gc = gcd([-x + s, -x - s, 2*x + S]);
    listput(out, [if (gp == 1, "DESIRED", "non-primitive"), chart, d, n, x, s,
                  [-x + s, -x - s, 2*x + S], [gp, gc], [g, p, q]]));
  Vec(out);
}
