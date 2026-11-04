# CE192: from the d-equation to one Thue equation per d

**Target.** Rational `d` for which

```text
N(n) := 36n^3 - 32
N(n) = -2*d*x^2*( -(x+6n) + s ),     s = sqrt( (x+6n)^2 + N(n)/x ) >= 0
```

has a point in **either** accepted chart:

| Chart | Requirement |
| --- | --- |
| integer (result 1) | `n, x` integers and `s` an integer |
| half (result 2) | `n` integer, `x = X/2`, `s = Y/2`, with `X, Y` odd |

Throughout, `S = 6n` and `K = 192`. All statements below are proved for any
**even** `K = +-3 (mod 9)`; production uses `K = 192 = 2^6 * 3 = 4^3 * 3`.
The worker's `--k` parameter exists only so the identical code can be run on
other such `K` with known representations (6, 12, 24, 66, 120) as detection
tests.

## 1. The constant and the cube identity

```text
(6n)^3 = 216 n^3,   so   N(n) = 36n^3 - 32 = (S^3 - 192)/6.
```

Put `U = x + S`, `A = -x+s`, `B = -x-s`, `C = 2x+S`. Expanding,

```text
A^3 + B^3 + C^3 - 192 = -6x * ( s^2 - U^2 - N/x ).
```

So the square-root condition is exactly `A^3+B^3+C^3 = 192`. In the integer
chart `A, B, C` are obviously integers; in the half chart
`A = (Y-X)/2`, `B = -(X+Y)/2`, `C = X+S` are integers because `X, Y` are odd.

## 2. The closed form of d

Since `N != 0` (192 is not a cube), `s - U != 0`. From the equation,
`s - U = -N/(2 d x^2)`, and from the definition of `s`,
`(s-U)(s+U) = N/x`. Dividing,

```text
s + U = -2 d x,     d = -(x + s + 6n)/(2x) = (A+C)/(A+B).
```

Conversely, if `s >= 0` satisfies the square-root condition and `d` is defined
this way, the original equation holds. So **every point of either chart
determines its `d` uniquely**, and searching for `d` is the same as searching
for points.

## 3. Pair sums and the Thue equation

Let `u = A+B = -2x`, `v = B+C`, `w = C+A`. Then `u+v+w = 2(A+B+C) = 2S` and
`(A+B+C)^3 - (A^3+B^3+C^3) = 3uvw`, so `uvw = (S^3 - 192)/3`. Also `d = w/u`.
Write `d = p/q` in lowest terms, `q > 0`. Then `u = q g`, `w = p g` for an
integer `g`, and `v = 2S - (p+q) g`. Substituting:

```text
F_d(S, g) = S^3 - 6 p q S g^2 + 3 p q (p+q) g^3 = 192.        (Thue)
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
independently, by `common192.verify_hit`.

## 4. `n` is automatically an integer, and `n = 2 (mod 3)`

Cubes are `0, +-1 (mod 9)`. Since `192 = 3 (mod 9)`, the only possibility is
`A = B = C = 1 (mod 3)`, so `3 | A+B+C = S`. Since `t^3 = t (mod 2)`,
`S = 192 = 0 (mod 2)`. Hence `S = 0 (mod 6)` and `n = S/6` is an integer.
Further, for `t = 1 (mod 3)`, `t^3 = 3t - 2 (mod 27)`, so
`192 = 3S - 6 (mod 27)`, i.e. `S = 3 (mod 9)`. With `S = 0 (mod 6)` this is
`S = 12 (mod 18)`, so **`n = 2 (mod 3)`**. The worker and verifier assert this
(`n_mod3(K)` computes the forced residue for every test `K` too).

## 5. Which chart a representation populates

`A+B+C = S` is even, so 0 or 2 components are odd. Choosing which component
plays `C` (and ordering the other two so that `A >= B`, i.e. `s >= 0`):

* the two remaining components have the same parity -> integer chart;
* they have different parity -> half chart.

With 0 odd components, every choice is an integer-chart point. With 2 odd
components, `C` = the even one gives an integer-chart point, and `C` = either
odd one gives a half-chart point. **So a half-chart point for 192 exists only
if 192 has a representation with exactly two odd components.**

All-even representations of 192 are `2 x` representations of 24, and
all-even representations of 24 are `2 x` representations of 3. So every
representation of 192 is one of

```text
4 x (representation of 3),   2 x (two-odd representation of 24),   two-odd representation of 192,
```

and only the last kind produces half-chart `d`. Searching both charts at once
costs nothing extra: they are the same Thue equation, separated only by the
parity of `q g`.

**Known answers (why 192 is a test case).** The three known representations
of 3 give representations of 192:

| Representation of 192 | `d` (integer chart) | height `max(|p|,q)` |
| --- | --- | ---: |
| `4^3 + 4^3 + 4^3` | `1` (`n=2, x=-4, s=0`) | 1 |
| `16^3 + 16^3 + (-20)^3` | `-1/8` (`n=2, x=-16, s=0`) | 8 |
| | `-8` (`n=2, x=2, s=18`) | 8 |
| `4 x` (Booker-Sutherland representation of 3) | three values, see README | ~5.7*10^20 |

The production pilot (heights `< 4000`) recovers exactly the first three.
Brute force finds no other representation of 192 with all `|components| <= 3000`.

## 6. Which d need to be tried (proved filters)

All of the following are necessary for any point with `d = p/q` reduced:

| Condition | Proof |
| --- | --- |
| `3 !| p q g`, `p = q (mod 3)` | §4: `u = qg = A+B = 2 (mod 3)`, likewise `w = pg`; so `d = w/u = 1 (mod 3)` |
| primes `l = 1 (mod 3)` dividing `p` or `q`: `3` must be a cube mod `l` | `u, w | 3uvw = S^3 - 192`, so `S^3 = 192 = 4^3 * 3 (mod l)` |

Primes `l = 2 (mod 3)` impose no condition (cubing is a bijection mod `l`).
No prime `l >= 5` divides 192, so there are no local tables of the kind used
for 627. An exhaustive check found **no further local obstruction** on
`(p, q)` modulo 27 (with `3 !| g`) or modulo `2^3 ... 2^7`, so no 2-adic or
9-adic filter is applied. **No parity filter is applied**: `q` even is needed
for the integer chart.

Measured at k = 192: **3.83 %** of raw pairs `(p, q)` survive (heights below 4000).

## 7. Solving one Thue equation completely up to |g| <= G

`f(t) = F_d(t, 1) = t^3 - 6pq t + 3pq(p+q)` has discriminant
`-27 p^2 q^2 (9p^2 - 14pq + 9q^2) < 0`, so one real root `alpha` and complex
roots `beta, conj(beta)` with `eta^2 = (Im beta)^2 = 3 alpha^2/4 - 6pq > 0`.
Then `f(t) = (t-alpha)|t-beta|^2`, so `sign f(t) = sign(t - alpha)` (exact
sign tests isolate `alpha`), and a solution satisfies

```text
|S/g - alpha| <= 192 / (eta^2 |g|^3).
```

* **|g| > g0 = 8*192/(3 alpha^2 - 24 pq):** the bound is below `1/(2g^2)`.
  **192 is not cube-free**, so a solution may be non-primitive:
  `(S, g) = e (S', g')` with `gcd(S', g') = 1` and `e^3 | 192`, i.e.
  `e in {1, 2, 4}`, and `F(S', g') = 192/e^3`. The bound for the primitive
  pair is `(192/e^3) / (eta^2 |g'|^3)`, and Legendre needs
  `|g'| > g0 / e^3`, which holds because `|g'| = |g|/e > g0/e >= g0/e^3`. So
  `S'/g'` is a continued-fraction convergent of `alpha`, and each convergent
  `(P, Q)` is tested against `F(P, Q) = +-192/e^3` for all three `e`.
  Convergents are generated from an exactly certified bracket of `alpha`; a
  partial quotient is accepted only when both bracket ends agree, otherwise
  precision is doubled. The pass ends only when the next denominator exceeds
  `G = 10^g_max_digits` (default `10^100`).
* **1 <= |g| <= g0:** all integer roots of the cubic in `S` are found by exact
  binary search on its monotone intervals (`g0` uses a rigorous lower bound of
  `3 alpha^2 - 24pq` from the bracket). This path finds non-primitive
  solutions directly. `g` divisible by 3 is skipped (§6).
* **Rational alpha** (then an integer) is detected exactly and handled with the
  bound `g^2 <= 4*192*b/(3 alpha^2 - 24pq)`.

**Scope of a completed run:** every point with `d` in the assigned height
shells `H(d) = max(|p|, q)` and `1 <= |g| <= G`, hence `|x| <= q G / 2`.
That is not a statement about arbitrary `g`. For an **unbounded** certificate
of one particular `d`, use `tools/certify_d.gp` (PARI `thue()` with
`thueinit(., 1)`, no GRH assumption; it returns non-primitive solutions too).
The test suite checks that the worker's raw solver returns exactly PARI's
solution set (restricted to `|g| <= 10^60`) for at least 60 values of `d` at
`k = 192, 12, 66`, including every `d` of the small known representations.
