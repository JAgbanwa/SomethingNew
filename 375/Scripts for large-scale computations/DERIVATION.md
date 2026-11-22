# CE375: from the d-equation to one Thue equation per d

**Target.** Rational `d` for which

```text
N(n) := 36n^3 + 54n^2 + 27n - 58
N(n) = -2*d*x^2*( -(x+6n+3) + s ),     s = sqrt( (x+6n+3)^2 + N(n)/x ) >= 0
```

has a point in **either** accepted chart:

| Chart | Requirement |
| --- | --- |
| integer (result 1) | `n, x` integers and `s` an integer |
| half (result 2) | `n` integer, `x = X/2`, `s = Y/2`, with `X, Y` odd |

Both results also require **primitivity**; see section 8. The search itself
finds every point, primitive or not, and labels each one.

Throughout, `S = 6n+3` and `K = 375`. All statements below are proved for
any odd `K = +-3 (mod 9)`; production uses `K = 375 = 3*5^3`, which is **not
cube-free** (sections 6-8).
The worker's `--k` parameter exists only so the identical code can be run
on small `K` with known representations (3, 15, 21, 57) as detection tests.

## 1. The constant and the cube identity

```text
(6n+3)^3 = 216n^3 + 324n^2 + 162n + 27,   so   N(n) = (S^3 - 375)/6.
```

Put `U = x + S`, `A = -x+s`, `B = -x-s`, `C = 2x+S`. Expanding,

```text
A^3 + B^3 + C^3 - 375 = -6x * ( s^2 - U^2 - N/x ).
```

So the square-root condition is exactly `A^3+B^3+C^3 = 375`. In the integer
chart `A, B, C` are obviously integers; in the half chart
`A = (Y-X)/2`, `B = -(X+Y)/2`, `C = X+S` are integers because `X, Y` are odd.

## 2. The closed form of d

Since `N != 0` (375 is not a cube), `s - U != 0`. From the equation,
`s - U = -N/(2 d x^2)`, and from the definition of `s`,
`(s-U)(s+U) = N/x`. Dividing,

```text
s + U = -2 d x,     d = -(x + s + 6n + 3)/(2x) = (A+C)/(A+B).
```

Conversely, if `s >= 0` satisfies the square-root condition and `d` is defined
this way, the original equation holds. So **every point of either chart
determines its `d` uniquely**, and searching for `d` is the same as searching
for points.

## 3. Pair sums and the Thue equation

Let `u = A+B = -2x`, `v = B+C`, `w = C+A`. Then `u+v+w = 2(A+B+C) = 2S` and
`(A+B+C)^3 - (A^3+B^3+C^3) = 3uvw`, so `uvw = (S^3 - 375)/3`. Also `d = w/u`.
Write `d = p/q` in lowest terms, `q > 0`. Then `u = q g`, `w = p g` for an
integer `g`, and `v = 2S - (p+q) g`. Substituting:

```text
F_d(S, g) = S^3 - 6 p q S g^2 + 3 p q (p+q) g^3 = 375.        (Thue)
```

**Conversely**, every integer solution `(S, g)` of (Thue) with `g != 0` and

```text
x = -q g / 2,      s = (2p+q) g / 2 - S >= 0
```

is a point with this `d`: `q g` even gives the **integer chart** (then
`(2p+q) g` is even too), and `q g` odd gives the **half chart** (then
`X = -qg` and `Y = (2p+q)g - 2S` are both odd). Solutions with `s < 0`
belong to the conjugate value `v/u` of `d`; the worker counts them as
`other_branch` and reports them when that conjugate `d` is processed.
Every reported point is re-checked exactly against the **original, unsquared**
equation, its chart, and the cube sum, by the C++ worker and again,
independently, by `common375.verify_hit`.

## 4. `n` is automatically an integer, and `n = 2 (mod 3)`

Cubes are `0, +-1 (mod 9)`. Since `375 = 6 (mod 9)`, the only possibility is
`A = B = C = -1 (mod 3)`. So `3 | A+B+C = S`; and `S = 375 (mod 2)` is odd.
Hence `S = 3 (mod 6)` and `n = (S-3)/6` is an integer. Further, for
`t = -1 (mod 3)`, `t^3 = 3t + 2 (mod 27)`, so `375 = 3S + 6 (mod 27)`, i.e.
`3S = 18 (mod 27)`, `S = 6 (mod 9)` and **`n = 2 (mod 3)`**. The worker and
verifier assert this (for general `K` they derive the forced residue the same
way; `K = 627` gives `n = 1`). This uses only cubes mod 27, so it holds for
non-primitive points too.

## 5. Both charts are populated by any representation

`A+B+C = S` is odd, so 1 or 3 components are odd. Choosing which component
plays `C` (and ordering the other two so that `A >= B`, i.e. `s >= 0`):

* the two remaining components have the same parity -> integer chart;
* they have different parity -> half chart.

With 3 odd components, all three choices are integer-chart points. With one
odd component, `C` = the odd one gives an integer-chart point, and `C` = either
even one gives a half-chart point. So **every** integer representation of
375 produces integer-chart `d` values, and most also produce half-chart ones.
Searching both charts at once costs nothing extra: they are the same Thue
equation, separated only by the parity of `q g`.

Example (k = 15 test, representation `2^3 + 2^3 + (-1)^3`):
`d = 1/4` (integer chart, `n = 0, x = -2, s = 0`) and
`d = 4` (half chart, `n = 0, x = -1/2, s = 3/2`). The test suite checks both.

## 6. Which d need to be tried (proved filters)

All of the following are necessary for any point with `d = p/q` reduced:

| Condition | Proof |
| --- | --- |
| `3 !| p q g`, `p = q (mod 3)` | §4: `u = qg = A+B = -2 = 1 (mod 3)`, likewise `w = pg`; so `d = w/u = 1 (mod 3)` |
| primes `l = 1 (mod 3)`, `l !| 375`, dividing `p` or `q`: `375` must be a cube mod `l` | `u, w | 3uvw = S^3 - 375`, so `S^3 = 375 (mod l)` |
| **no condition at `l = 5`** | `v_5(375) = 3`: a point may have `5 | S` and `5 | g` |

For `K = 627 = 3*11*19` the engine also used a valuation cap and a local
solvability table at each `l | K`. Both rely on `gcd(S, g) = 1`, which holds
only when `l^3 !| K`. At `K = 375` the only such prime is `l = 5` with
`v_5 = 3`, so **both are switched off for 5** (the code does this automatically
from `v_l(K) >= 3`): a common factor `e` of `S, g` must satisfy `e^3 | 375`,
i.e. `e in {1, 5}`, and `e = 5` is possible. These are exactly the points
coming from `5*(a, b, c)` with `a^3+b^3+c^3 = 3`, e.g. `5^3+5^3+5^3` and
`20^3+20^3+(-25)^3`. `common375.py` mirrors the filter independently, and the
test suite checks that both implementations give identical admissible counts
shell by shell. Primes `l = 2 (mod 3)` impose no
condition (cubing is a bijection mod `l`). **No parity filter is applied**:
`q` even is needed for the integer chart.

Measured at k = 375: about **3.8 %** (heights below 4000) and **2.6 %** (around 2*10^4) of raw pairs survive
(more than at k = 627, where the local tables at 11 and 19 also prune).

## 7. Solving one Thue equation completely up to |g| <= G

`f(t) = F_d(t, 1) = t^3 - 6pq t + 3pq(p+q)` has discriminant
`-27 p^2 q^2 (9p^2 - 14pq + 9q^2) < 0`, so one real root `alpha` and complex
roots `beta, conj(beta)` with `eta^2 = (Im beta)^2 = 3 alpha^2/4 - 6pq > 0`.
Then `f(t) = (t-alpha)|t-beta|^2`, so `sign f(t) = sign(t - alpha)` (exact
sign tests isolate `alpha`), and a solution satisfies

```text
|S/g - alpha| <= 375 / (eta^2 |g|^3).
```

* **|g| > g0 = 8*375/(3 alpha^2 - 24 pq):** the bound is below `1/(2g^2)`, so
  by Legendre `S/g` is a continued-fraction convergent of `alpha`. Legendre
  gives `S/g` in lowest terms, i.e. `(S, g) = e (S', g')` with `(S', g')` a
  convergent and `F(S', g') = 375/e^3`; the CF pass tests both `e = 1` and
  `e = 5` at every convergent, so non-primitive solutions are found too. Convergents
  are generated from an exactly certified bracket of `alpha`; a partial
  quotient is accepted only when both bracket ends agree, otherwise precision
  is doubled. The pass ends only when the next denominator exceeds
  `G = 10^g_max_digits` (default `10^100`).
* **1 <= |g| <= g0:** all integer roots of the cubic in `S` are found by exact
  binary search on its monotone intervals (`g0` uses a rigorous lower bound of
  `3 alpha^2 - 24pq` from the bracket). `g` divisible by 3 is skipped (§6).
* **Rational alpha** (then an integer) is detected exactly and handled with the
  bound `g^2 <= 4*375*b/(3 alpha^2 - 24pq)`.

**Scope of a completed run:** every point with `d` in the assigned height
shells `H(d) = max(|p|, q)` and `1 <= |g| <= G`, hence `|x| <= q G / 2`.
That is not a statement about arbitrary `g`. For an **unbounded** certificate
of one particular `d`, use `tools/certify_d.gp` (PARI `thue()` with
`thueinit(., 1)`, no GRH assumption). The test suite checks that the worker's
raw solver returns exactly PARI's solution set (restricted to `|g| <= 10^60`)
for 60 values of `d`, including the d values of small known representations of k = 15 and 57.

## 8. Primitivity: what counts as a desired result

Every reported point carries two independent flags, computed in C++ and
recomputed in `common375.verify_hit` (a mismatch rejects the hit):

| Flag | Integer chart | Half chart |
| --- | --- | --- |
| `primitive_point` | `gcd(n, x) = 1` | `gcd(X, Y) = 1`, `X = 2x`, `Y = 2s` |
| `primitive_cubes` | `gcd(A, B, C) = 1` | `gcd(A, B, C) = 1` |

A hit is **desired** when both hold. Non-desired hits are kept in
`hits.jsonl` and `d_values.txt` (tagged `non-primitive`) and never dropped,
so the definition can be changed after the run without recomputation.

Why both: `5^3+5^3+5^3 = 375` gives `d = 1`, `n = 2`, `x = -5`, `s = 0`, which
has `gcd(n, x) = 1` although it is just 5 times `1^3+1^3+1^3 = 3`. The cube
flag rejects it. At `K = 375`, `primitive_cubes` fails exactly when
`5 | gcd(S, g)`.

All three non-primitive points with height below 4000 (`d = 1, -8, -1/8`,
from `5*(1,1,1)` and `5*(4,4,-5)`) are recovered by the worker; the test suite
requires this and requires them to be labelled non-desired.

## 9. Rational (x, y) mode: `--mode xy-half`

Target of this mode: rational `x, y` with `n` an integer on

```text
y^2 = (x+6n+3)^2 + (36n^3 + 54n^2 + 27n - 58)/x,     x = X/2, y = Y/2, X, Y odd, gcd(X, Y) = 1,
```

**both signs of `y`**. A point with `y >= 0` is exactly a half-chart point with
`s = y`; a point with `y < 0` is the half-chart point `(n, x, -y)`. So the
solution set is the half chart up to the sign of `y`, and each point has two
values of `d`:

```text
principal   d = -(x + S + |y|)/(2x),       conjugate   d' = -(x + S - |y|)/(2x).
```

The mode accepts Thue solutions of **both** branches (`s >= 0` and `s < 0`),
so a point is found when either of its two `d` values is processed. Hits are
reported once per point `(n, X, |Y|)` with the principal `d` for reference
and `branch` saying which one produced it.

Proved restrictions used only in this mode (all necessary for `gcd(X, Y) = 1`):

| Restriction | Proof |
| --- | --- |
| `q` odd and `g` odd | `X = -q g` is odd |
| `gcd(S, g) = 1`, so the CF pass tests only `e = 1` | a prime `l` dividing `S` and `g` divides `X = -qg` and `Y = (2p+q)g - 2S` |
| `F_d(S, g) = 375 (mod 125)` solvable with `5 !| g` | `5 | g` would give `S^3 = F = 375 = 0 (mod 5)`, so `5 | S`, contradicting the row above |

`F_d` depends on `d` modulo 125 only through `a = pq` and `b = pq(p+q)`. The
worker tabulates the allowed `(a, b)` by exhaustive search over
`(S, g, a, b) mod 125`; `common375.py` builds the same table independently by
solving for `b` (`3g^3` is a unit), and the test suite checks both give
identical admissible counts shell by shell (at `k = 375`, at `k = 7125 = 57*5^3`
and at `k = 15`). The 5-adic table keeps about 35 % of residue pairs.

Also, `gcd(X, Y) = 1` already implies primitive cube components (a common
prime of `A, B, C` divides `A - B = Y` and `A + B = -X`), so in this mode
`desired` is the same as `gcd(X, Y) = 1`. Non-primitive points that the small-`g`
path still meets (for example `X = 5, Y = 45` from `20^3+20^3+(-25)^3`) are
reported with `desired = false`.

Measured at `k = 375`, height `2*10^4`: **0.52 %** of raw pairs are solved
(against 2.56 % in the default mode) and the cost is **0.9 us/pair** (against
4.8 us/pair), so the same core-hours reach about `sqrt(5.3) = 2.3` times the
height.

**Scope of a completed xy-half run:** every point `(n, X/2, +-Y/2)` with
`X, Y` odd and `gcd(X, Y) = 1` such that its principal or conjugate `d` has
height in the processed range and, for that `d`, `1 <= |g| <= G`
(so `|X| <= q G`).

The tests cover this mode with `k = 15, 21, 57` and with `k = 7125 = 57*5^3`,
whose primitive representation `(-67)^3 + (-46)^3 + 74^3` gives the half
points `x = -7/2, y = +-141/2` and `x = 113/2, y = +-21/2`; an `(n, X)`
divisor brute force over `|n| <= 40` on the `y^2` equation must agree.

## 10. The production mode: `--mode xy` (both charts, desired points only)

`--mode xy` searches the `y^2` equation of section 9 in **both** charts and
reports each point `(n, X/2, ±Y/2)` once (`X = 2x`, `Y = 2|y|`, both even in
the integer chart, both odd in the half chart). It drops only things a
**desired** point cannot need. Since desired requires `gcd(A, B, C) = 1`:

| Restriction | Proof |
| --- | --- |
| `gcd(S, g) = 1`, so the CF pass tests only `e = 1` | a common factor `e` of `S, g` divides `u = qg`, `w = pg`, `v = 2S - (p+q)g`, hence `2A, 2B, 2C`; `e` is odd (`S` odd) so `e | gcd(A, B, C)` |
| `F_d(S, g) = 375 (mod 125)` solvable with `5 !| g` | as in section 9: `5 | g` forces `5 | S` |
| both Thue branches accepted | the `y^2` equation does not fix the sign of `y` (section 9) |

There is **no parity restriction**: `q` even is needed for the integer chart.
The `(a, b) mod 125` table is the same as in section 9, built the same two
independent ways and compared shell by shell in the tests (at `k = 375`,
`k = 1875 = 3*5^4` and `k = 15`).

Measured at `k = 375`, height `2*10^4`: **0.85 %** of raw pairs solved and
**1.5 us/pair**, against 2.56 % and 5.0 us/pair in mode `both`.

**Scope of a completed xy run:** every desired point, in either chart, such
that its principal or conjugate `d` has height in the processed range and,
for that `d`, `1 <= |g| <= G` (so `|X| <= q G`).

Tests for this mode use `k = 15, 57` and the two non-cube-free values
`k = 1875` (primitive `(-29)^3+(-29)^3+37^3` gives the integer-chart point
`n = -4, x = 29, y = 0, d = -4/29`, with `gcd(n, x) = 1`) and `k = 7125`
(half-chart points, section 9). Every desired point that mode `both` finds
must also be found by `xy`, and an `(n, x)` divisor brute force over
`|n| <= 40` on the `y^2` equation, in both charts, must agree.
