# CE627: from the d-equation to one Thue equation per d

**Target.** Rational `d` for which

```text
N(n) := 36n^3 + 54n^2 + 27n - 100
N(n) = -2*d*x^2*( -(x+6n+3) + s ),     s = sqrt( (x+6n+3)^2 + N(n)/x ) >= 0
```

has a point in **either** accepted chart:

| Chart | Requirement |
| --- | --- |
| integer (result 1) | `n, x` integers and `s` an integer |
| half (result 2) | `n` integer, `x = X/2`, `s = Y/2`, with `X, Y` odd |

Throughout, `S = 6n+3` and `K = 627`. All statements below are proved for
any odd `K = +-3 (mod 9)`; production uses `K = 627 = 3*11*19`.
The worker's `--k` parameter exists only so the identical code can be run
on small `K` with known representations (3, 15, 21, 57) as detection tests.

## 1. The constant and the cube identity

```text
(6n+3)^3 = 216n^3 + 324n^2 + 162n + 27,   so   N(n) = (S^3 - 627)/6.
```

Put `U = x + S`, `A = -x+s`, `B = -x-s`, `C = 2x+S`. Expanding,

```text
A^3 + B^3 + C^3 - 627 = -6x * ( s^2 - U^2 - N/x ).
```

So the square-root condition is exactly `A^3+B^3+C^3 = 627`. In the integer
chart `A, B, C` are obviously integers; in the half chart
`A = (Y-X)/2`, `B = -(X+Y)/2`, `C = X+S` are integers because `X, Y` are odd.

## 2. The closed form of d

Since `N != 0` (627 is not a cube), `s - U != 0`. From the equation,
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
`(A+B+C)^3 - (A^3+B^3+C^3) = 3uvw`, so `uvw = (S^3 - 627)/3`. Also `d = w/u`.
Write `d = p/q` in lowest terms, `q > 0`. Then `u = q g`, `w = p g` for an
integer `g`, and `v = 2S - (p+q) g`. Substituting:

```text
F_d(S, g) = S^3 - 6 p q S g^2 + 3 p q (p+q) g^3 = 627.        (Thue)
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
independently, by `common627.verify_hit`.

## 4. `n` is automatically an integer, and `n = 1 (mod 3)`

Cubes are `0, +-1 (mod 9)`. Since `627 = 6 (mod 9)`, the only possibility is
`A = B = C = -1 (mod 3)`. So `3 | A+B+C = S`; and `S = 627 (mod 2)` is odd.
Hence `S = 3 (mod 6)` and `n = (S-3)/6` is an integer. Further, for
`t = -1 (mod 3)`, `t^3 = 3t + 2 (mod 27)`, so `627 = 3S + 6 (mod 27)`, i.e.
`S = 0 (mod 9)` and **`n = 1 (mod 3)`**. The worker and verifier assert this.

## 5. Both charts are populated by any representation

`A+B+C = S` is odd, so 1 or 3 components are odd. Choosing which component
plays `C` (and ordering the other two so that `A >= B`, i.e. `s >= 0`):

* the two remaining components have the same parity -> integer chart;
* they have different parity -> half chart.

With 3 odd components, all three choices are integer-chart points. With one
odd component, `C` = the odd one gives an integer-chart point, and `C` = either
even one gives a half-chart point. So **every** integer representation of
627 produces integer-chart `d` values, and most also produce half-chart ones.
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
| primes `l = 1 (mod 3)`, `l !| 627`, dividing `p` or `q`: `627` must be a cube mod `l` | `u, w | 3uvw = S^3 - 627`, so `S^3 = 627 (mod l)` |
| `121 !| pq`, `361 !| pq` | `v_l(S^3 - 627) <= 1` for `l = 11, 19` (`v_l(627) = 1`) |
| `(p mod 11, q mod 11)` and `(p mod 19, q mod 19)` in the locally solvable set | (Thue) must be solvable mod `l` with `(S, g) != (0, 0)` |

The last row uses primitivity: a common factor `e` of `S, g` would give
`e^3 | 627`, and 627 is cube-free, so `gcd(S, g) = 1`. The worker builds the
local tables at start-up by exhaustive search mod `l`; `common627.py` builds
them independently, and the test suite checks that both implementations give
identical admissible counts shell by shell. Primes `l = 2 (mod 3)` impose no
condition (cubing is a bijection mod `l`). **No parity filter is applied**:
`q` even is needed for the integer chart.

Measured at k = 627: about **2.1-2.9 %** of raw pairs `(p, q)` survive
(heights 2*10^4 and 10^5).

## 7. Solving one Thue equation completely up to |g| <= G

`f(t) = F_d(t, 1) = t^3 - 6pq t + 3pq(p+q)` has discriminant
`-27 p^2 q^2 (9p^2 - 14pq + 9q^2) < 0`, so one real root `alpha` and complex
roots `beta, conj(beta)` with `eta^2 = (Im beta)^2 = 3 alpha^2/4 - 6pq > 0`.
Then `f(t) = (t-alpha)|t-beta|^2`, so `sign f(t) = sign(t - alpha)` (exact
sign tests isolate `alpha`), and a solution satisfies

```text
|S/g - alpha| <= 627 / (eta^2 |g|^3).
```

* **|g| > g0 = 8*627/(3 alpha^2 - 24 pq):** the bound is below `1/(2g^2)`, so
  by Legendre `S/g` is a continued-fraction convergent of `alpha`. Convergents
  are generated from an exactly certified bracket of `alpha`; a partial
  quotient is accepted only when both bracket ends agree, otherwise precision
  is doubled. The pass ends only when the next denominator exceeds
  `G = 10^g_max_digits` (default `10^100`).
* **1 <= |g| <= g0:** all integer roots of the cubic in `S` are found by exact
  binary search on its monotone intervals (`g0` uses a rigorous lower bound of
  `3 alpha^2 - 24pq` from the bracket). `g` divisible by 3 is skipped (§6).
* **Rational alpha** (then an integer) is detected exactly and handled with the
  bound `g^2 <= 4*627*b/(3 alpha^2 - 24pq)`.

**Scope of a completed run:** every point with `d` in the assigned height
shells `H(d) = max(|p|, q)` and `1 <= |g| <= G`, hence `|x| <= q G / 2`.
That is not a statement about arbitrary `g`. For an **unbounded** certificate
of one particular `d`, use `tools/certify_d.gp` (PARI `thue()` with
`thueinit(., 1)`, no GRH assumption). The test suite checks that the worker's
raw solver returns exactly PARI's solution set (restricted to `|g| <= 10^60`)
for 60 values of `d`, including the d values of small known representations of k = 15 and 57.
