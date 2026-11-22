# CE375: the n-first search and why it is complete

**Target.** Rational `x, y` with `n` an integer on

```text
y^2 = (x + 6n+3)^2 + N(n)/x,        N(n) = 36n^3 + 54n^2 + 27n - 58,
```

in either accepted form:

| Form | Requirement |
| --- | --- |
| integer (result 1) | `n, x, y` integers, `(n, x)` primitive: `gcd(n, x) = 1` |
| half (result 2) | `n` integer, `x = X/2`, `y = Y/2`, `X, Y` odd, `(X, Y)` primitive: `gcd(X, Y) = 1` |

Both signs of `n`, `x` and `y` are covered. Throughout, `S = 6n+3`; then
`N(n) = (S^3 - 375)/6`. The worker's `--k` parameter replaces 375 by another
odd `k = +-3 (mod 9)` only so the tests can run the identical code on values
with known solutions.

## 1. Every point has x among the divisors of N(n)

* **Integer form.** `y^2` and `(x+S)^2` are integers, so `N/x` is an integer:
  `x` divides `N(n)`.
* **Half form.** Multiply by 4: `Y^2 = (X + 2S)^2 + 8N/X`. Again `8N/X` is an
  integer, and `X` is odd, so `X` divides `N(n)`.

So for a fixed `n` there are only finitely many candidates: `x = +-D` and
(for odd `D`) `x = +-D/2`, with `D` running over the positive divisors of
`|N(n)|`. Once `N(n)` is factored, testing them all finds **every** point with
that `n`, however large `x` and `y` are.

## 2. Only n = 2 (mod 3) can have a point

Put `A = -x + y`, `B = -x - y`, `C = 2x + S`. Expanding,

```text
A^3 + B^3 + C^3 - 375 = -6x * ( y^2 - (x+S)^2 - N/x ),
```

so every point gives integers `A, B, C` (in the half form `A = (Y-X)/2`,
`B = -(X+Y)/2`, `C = X + S`) with `A^3 + B^3 + C^3 = 375` and
`A + B + C = S`. Cubes are `0, +-1 (mod 9)` and `375 = 6 (mod 9)`, so
`A = B = C = -1 (mod 3)`. For `t = -1 (mod 3)`, `t^3 = 3t + 2 (mod 27)`, hence
`375 = 3S + 6 (mod 27)`, `S = 6 (mod 9)`, and `n = (S-3)/6 = 2 (mod 3)`.
The worker skips the other two residues. (The tests confirm this on the
brute-force solution sets, which are computed without the filter.)

`A, B, C` are also used for the second primitivity flag (section 5) and as an
extra exact check of every reported point.

## 3. Algorithm per block of n

1. **Sieve.** For every prime `p <= 2^14` the roots of `N(t) = 0 (mod p)` are
   precomputed; each `N(n)` in the block is divided by every such `p`, to full
   multiplicity, at exactly the `n` where `p` divides it.
2. **Cofactor.** What is left has no prime factor `<= 2^14`. If it is below
   `2^28` it is prime. Otherwise: primality test; perfect-square check;
   Brent-Pollard rho (64-bit Montgomery arithmetic below `2^63`, 128-bit
   above); and, for cofactors rho does not split quickly, PARI's
   `Z_factor`. PARI is only trusted to *propose*: each factor it returns is
   re-tested by the worker's own primality test and their product must equal
   the cofactor.
3. **Divisors.** All positive divisors `D` of `|N(n)|`; for each sign, test
   the integer form `x = +-D` and, if `D` is odd, the half form `X = +-D`.
4. **Square test.** `v = (x+S)^2 + N/x` (or `(X+2S)^2 + 8N/X`) must be a
   square modulo 64, 63, 65 and 11 (computed exactly from 128-bit values);
   survivors get an exact GMP perfect-square test.
5. **Certificate.** Every point is re-verified in exact rational arithmetic
   against the original equation, its form, and `A^3+B^3+C^3 = 375`, before
   it is printed. The runner and the collector verify it again, independently,
   in Python (`common375.verify_hit`).

If some `N(n)` cannot be factored within the budget, the worker prints an
`incomplete` record for that `n` instead of skipping it; the collector lists
such `n` in `incomplete.txt` and they are **not** counted as covered. None
occurred in any test or pilot.

## 4. How certain is the coverage

* Primality is **proved** for every number below `3.317 * 10^24`: the worker
  uses strong-pseudoprime tests to the 13 prime bases `2, ..., 41`, which are
  deterministic below that bound (Sorenson and Webster). `|N(n)|` itself is
  below that bound for `|n| < 4.5 * 10^7`, so for those `n` the factorisation
  is proved.
* For a factor above `3.317 * 10^24` the worker additionally applies GMP's
  BPSW test plus 30 Miller-Rabin rounds. No BPSW pseudoprime is known, but
  this is not a proof. Only a **missed point** could result from such an
  error; a **false point** cannot, because every point is verified exactly.
* The tests compare the worker's divisor count of `N(n)` with PARI's
  `numdiv` for hundreds of `n` near `10^9`, `-10^10` and `10^11`, and its
  complete solution sets with an independent Python brute force over
  `|n| <= 300` for `k = 375, 15, 57, 1875, 7125`.

## 5. Primitivity, and what counts as a result

Every point carries:

| Flag | Integer form | Half form |
| --- | --- | --- |
| `primitive_point` | `gcd(n, x) = 1` | `gcd(X, Y) = 1` |
| `primitive_cubes` | `gcd(A, B, C) = 1` | `gcd(A, B, C) = 1` |
| `desired` | both | both |

The second flag matters because `375 = 3*5^3`: `5^3 + 5^3 + 5^3 = 375` gives
the point `n = 2, x = -5, y = 0`, which has `gcd(n, x) = 1` but is just 5
times `1^3+1^3+1^3 = 3`. In the half form, `gcd(X, Y) = 1` already implies
`gcd(A, B, C) = 1` (a common prime divides `A - B = Y` and `A + B = -X`).
Points failing either flag are still reported, tagged `non-primitive`, so the
definition can be changed later without recomputation.

## 6. What a completed range establishes

For every `n` in a completed range with no `incomplete` record: **all**
rational points `(x, y)` of both forms, with **no bound on `x` or `y`**, are
in `hits.jsonl`; the primitive ones are in `desired_points.txt`.
