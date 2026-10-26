\\ Complete solution sets of F_d(n,g) = T from PARI's unconditional thue(), for
\\ comparison with `bin/dthue_worker --raw` (tools/pari_compare.py does both).
\\ Output lines: "T p q n g" for each solution, then "T p q END".
default(parisize, "1G");
F(p,q,n,g) = 72*n^3 - 12*p*q*n*g^2 + p*q*(p+q)*g^3;
one(T,p,q) = { my(S = thue(thueinit(72*'x^3 - 12*p*q*'x + p*q*(p+q), 1), T));
  for (i = 1, #S, print(T, " ", p, " ", q, " ", S[i][1], " ", S[i][2])); print(T, " ", p, " ", q, " END"); }
grid(T,H) = { for (q = 1, H, for (p = -H, H, if (p && gcd(p,q) == 1, one(T,p,q)))); }
planted(H) = { my(T); for (q = 1, H, for (p = -H, H, if (p && gcd(p,q) == 1,
  foreach([[1,1],[2,-1],[-3,2],[5,3],[7,-4]], v, T = F(p,q,v[1],v[2]); if (T, one(T,p,q)))))); }
grid(130, 20); grid(2, 20); grid(-7, 12); grid(1000, 12); planted(9);
