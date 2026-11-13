# rational-d-search: every rational `d`, both charts, complete in `x` for each `n`

This is a supporting tool, **not** the 1,800-hour computation. The target (Results 1 and 2,
k = 114) is computed by [`../gap-search/`](../gap-search/README.md). This engine covers the
wider case, where the square root

```text
y = sqrt((x+6n)^2 + (36n^3-19)/x)
```

only has to be **rational**. It is used to cross-check the integral and half-integral
targets and to list the rational `d` for small `n`.

## Mathematics

Put `X = 2x` (even means the integer chart, odd means the half chart) and `N = 36n^3 − 19`. Then

```text
d rational  ⇔  F(X) = X²(X+12n)² + 8XN = W²,     d = −(W/|X| + X + 12n)/(2X)    (unique)
```

(To see this, clear the radical: `y + (x+6n) = −2dx`, and `y = W/(2|X|)`.) If a prime divides
`X` to an odd power, it divides `N`. So `X = σ e y₀²` with `e | N` squarefree, and every
factorisation `g·h = 8σeN` (half chart) or `σeN` (integer chart) gives a cubic
`σ e y₀³ + c₁ n y₀ = (h−g)/(2e)` for `y₀` (`c₁ = 12` or `6`). This is `search/search_xl.c`
extended to the half chart. Two changes make it complete for every `n` it reports as done:

* **The sieve cofactor is always split**, by Brent rho followed by GMP-ECM. The old sweeps
  kept it opaque, which lost about 15–46% of the divisor combinations.
* **The half chart (`x = X/2`) is searched for every `X`.** The only earlier coverage was
  `|n| ≤ 300` (brute force) and certificates `|V| < 10⁸`.

The pruning bounds `|x|(x+6n)² ≤ N²` (integer chart, Lean `sat_abs_x_mul_sq_le`) and
`|X|(X+12n)² ≤ 16N²` (half chart: `V = dX²` is an integer, `X | V²`, `VV′ = −2XN` and
`|V|+|V′| ≥ |X(X+12n)|`) are theorems, so pruning never drops a solution.

## Results so far

* For `|n| ≤ 450`, the output is identical to an independent brute force over every `X`
  (`tests/brute.c`).
* It re-finds all eleven known integer-chart solutions.
* It found a **new half-chart solution**: `n = 309`, `x = 15125/2`, `y = 207327/22`,
  `d = −41449/33275`.

None of these is a Result 1 or 2: in every one, `y` is not an integer in the integer chart,
nor an odd half in the half chart.

## Use

```sh
make && make test
./bin/rd_worker --n0 -100000 --n1 100000 [--chart both|int|half] > hits.txt   # DONE/SKIP/OPAQUE lines too
python3 verify_rd.py hits.txt          # exact check of (E), prints d and y as JSON
python3 verify_rd.py --nx 309 15125/2
```

`SKIP` (too many divisor combinations, about 1 in 10⁴ `n`) and `OPAQUE` (ECM gave up, never
observed) lines name `n` that still need `--list` with a larger `--cap`.

Measured on one core: about 0.2 ms per `n` at `|n| ≈ 10⁵`, 0.9 ms at 10⁷ and 3 ms at 10⁹
(both charts). About half of the time at 10⁹ is ECM.
