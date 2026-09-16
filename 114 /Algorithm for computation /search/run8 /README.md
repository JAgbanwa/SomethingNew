# run8 — the d-first sweeps of the grid session

Both runs use the criterion proved in `RequestProject/Algorithm.lean`
(`DEquation.sat_iff_dSweep`): enumerate the integer certificate `U = 2dx²`, run over the
divisors `x` of `U²` with `x ≡ 7 (mod 12)`, and solve the cubic `36n³ − 12Un = c + 2Ux + 19`
for `n`.  Nothing is assumed about the size of `x` or of `n`.

* `h0.txt … h7.txt` — `grid/dsweep`, the **exhaustive** sweep, contiguous over
  `2 ≤ |U| < 2·10¹⁰` (eight shards of 2.5·10⁹), 1.16·10¹¹ `(U,x)` pairs, **no hit**.
  By `DEquation.abs_n_le_abs_U` (`|n| ≤ |U|`) this settles every solution of the family
  whose certificate has at most ten digits.

* `s0.txt … s7.txt` — `grid/dsmooth`, the **50-smooth** sweep over `10¹⁰ ≤ |U| < 10¹⁸`
  (eight shards), 18 369 950 certificates, 3.99·10¹¹ `(U,x)` pairs, **no hit**.  723 304 of
  the certificates exceeded the divisor cap (`--maxdiv 200000`) and are only partly covered;
  they are listed by the `skipped=` count of each shard.

Total for the session: about 5·10¹¹ `(U,x)` pairs, no solution with `x ≡ 7 (mod 12)`.
