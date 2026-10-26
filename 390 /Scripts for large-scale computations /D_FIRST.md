# d-first search for half-integer points (`dthue_worker`)

**Target.** Rational values of `d` for which the equation

```text
36n^3 - 65 = -2*d*x^2*( -(x+6n) + sqrt( (x+6n)^2 + (36n^3-65)/x ) )
```

has a point with integer `n`, `x = X/2` (`X` odd) and
`sqrt((x+6n)^2 + (36n^3-65)/x) = y = Y/2` (`Y` odd).

This engine enumerates **`d` itself**, ordered by height `H(d) = max(|p|, q)` for
`d = p/q` in lowest terms. For each `d` it solves one binary cubic Thue
equation and reports every such point with `1 <= |g| <= 10^100`, where `g`
(defined below) satisfies `|x| = q|g|/2`. Every reported point is checked
exactly against the original, unsquared equation. Every `d` that is processed
is *settled* up to that bound, including all points inside the historical
`10^43 <= |n| <= 10^45`, `10^53 <= |x| <= 10^55` rectangle.

It runs alongside the existing a/q rectangle search. No existing file's
behaviour is changed.

| File | Role |
| --- | --- |
| `src/dthue_worker.cpp` | Native GMP worker: shells of `d`, Thue solver, exact certificates |
| `d_campaign.py` | Writes task files (disjoint height-shell ranges) and `page.json` |
| `run_d_task.py` | Restartable runner: per-shell checkpoint, continuation, status |
| `collect_d.py` | Coverage union, gaps, verified hit list for a campaign |
| `verify_d.py` | Independent exact re-verification of `hits.jsonl` |
| `dfirst_common.py` | Independent Python admissibility, shell order, verifier |
| `tools/certify_d.gp` | PARI/GP: unconditional, *unbounded* certification of single `d` |
| `tests/test_dfirst.py` | Known-answer, brute-force, planted-solution and lifecycle tests |

The constant 65 is a parameter `m` (k = 6m) **only** so that the identical code
can be run on m = 1 (k = 6), where half-integer points are known, as a
detection test. Production tasks use m = 65.

## 1. From `d` to a Thue equation

Put `A = -x+y`, `B = -x-y`, `C = 2x+6n`. Expanding gives the identity

```text
A^3 + B^3 + C^3 - 6m = -6x * ( y^2 - (x+6n)^2 - (36n^3-m)/x ),
```

so a point of the equation is the same thing as `A^3+B^3+C^3 = 6m`. When
`x = X/2` and `y = Y/2` with `X, Y` odd, then `A = (Y-X)/2`, `B = -(X+Y)/2` and
`C = X+6n` are integers.

**Pair sums.** Let `u = A+B = -2x`, `v = B+C`, `w = C+A`. Then
`u + v + w = 2(A+B+C) = 12n`, and the identity
`(A+B+C)^3 - (A^3+B^3+C^3) = 3(A+B)(B+C)(C+A)` gives

```text
u*v*w = (216 n^3 - 6m)/3 = 2*(36n^3 - m).
```

**The closed form of d.** `y >= 0` means `A >= B`, so `Y = A - B = w - v`. Then

```text
d = -(y + x + 6n)/(2x) = -(Y + X + 12n)/(2X) = (A + C)/(A + B) = w/u.
```

So `d` is the ratio of two pair sums. Write `d = p/q` in lowest terms with
`q > 0`. Then `u = q*g` and `w = p*g` for an integer `g`, and
`v = 12n - (p+q)g`. Substituting into `uvw = 2(36n^3-m)` gives

```text
F_d(n, g) = 72 n^3 - 12 p q n g^2 + p q (p+q) g^3 = 2m.        (Thue)
```

**Conversely**, every integer solution `(n, g)` of (Thue) with `q*g` odd and
`Y = (2p+q)g - 12n > 0` gives a half-chart point with this `d`:

```text
x = -q g / 2,   y = ((2p+q) g - 12 n)/2,   d = p/q.
```

The worker re-checks every such point exactly against the original equation,
the denominators, and the cube sum. Solutions with `Y < 0` belong to the
conjugate value `v/u` of `d`, and solutions with `g` even belong to the
integer chart. Both are counted (`other_branch`, `other_chart`) but not
reported.

**`n` is an integer.** If 3 does not divide `m`, then `6m == 3 or 6 (mod 9)`.
Cubes are `0, +-1 (mod 9)`, so `A == B == C (mod 3)`, which gives
`3 | A+B+C`. And `A+B+C == A^3+B^3+C^3 = 6m (mod 2)` is even. So `6 | A+B+C`
and `n = (A+B+C)/6` is an integer, even if `n` is allowed denominators
2, 3 or 6. The worker refuses `m` divisible by 3.

**Each representation appears twice.** `A+B+C` is even, so the number of
odd cubes is 0 or 2, and it cannot be 0 because `8 ∤ 6m` for odd `m`. So
exactly one cube is even. Pairing it with either odd cube gives an odd pair
sum `u`. So every representation yields exactly two half-chart points,
with two different values of `d`. In the k = 6 test, `(-43, -58, 65)` gives
`d = -22/101` and `d = 22/7`.

## 2. Solving one Thue equation completely up to |g| <= G

Let `f(t) = F_d(t, 1) = 72t^3 - 12pq t + pq(p+q)`. Its discriminant is
`-15552 (pq)^2 (9p^2 - 14pq + 9q^2) < 0` (the quadratic form is positive
definite), so `f` has **one real root** `alpha` and complex roots
`beta, conj(beta)` with

```text
eta^2 = (Im beta)^2 = 3 alpha^2/4 - p q/6 > 0.
```

Since `f(t) = 72 (t - alpha) |t - beta|^2`, we have `sign f(t) = sign(t - alpha)`,
which lets exact integer sign tests isolate `alpha`. For a solution with
target `T = 2m` and real `t = n/g`, the bound `|t - beta| >= eta` gives

```text
|n/g - alpha| <= |T| / (72 eta^2 |g|^3).
```

* **Large g (Legendre).** For `|g| > g0 = |T|/(36 eta^2)` the right side is
  below `1/(2g^2)`, so `n/g` is a continued-fraction convergent of `alpha`.
  For k = 390, `T = 130 = 2*5*13` is cube-free, so every solution has
  `gcd(n, g) = 1` (a common factor `e` forces `e^3 | T`). The code handles
  general `T` by testing `F = +-T/e^3` for every `e^3 | T`.
* **Certified convergents.** `alpha` is bracketed in `(z/2^b, (z+1)/2^b)` by
  exact sign tests: a floating-point guess and Newton steps only *propose*
  `z`, and an exact galloping or bisection search then establishes the
  bracket. A partial quotient is accepted only when both endpoints agree on
  it. On disagreement the precision is doubled and the expansion is replayed.
  The pass ends only when the next possible denominator exceeds
  `G = 10^g_max_digits`. A precision cap raises an error and never reports an
  empty range as complete. With `G = 10^100`, 730 bits suffice. No
  refinement was needed in any of the 5.25 million k=390 runs below.
* **Small g (exhaustive).** For `1 <= |g| <= g0` (a rigorous rational upper
  bound computed from the bracket), all integer roots `n` of the cubic
  `F_d(n, g) = T` are found by exact binary search on its at most three
  monotone integer intervals. For `T = 130`, `g0` is usually 0 or 1. It is
  larger only when `d` is close to 1, where `eta` is small (`d = 1` gives
  `g0 ~ 1640`).
* **Rational alpha.** A rational `alpha` whose denominator is a power of 2 is
  detected exactly and handled by the bound `g^2 <= 2|T| b/(36 eta^2)` (`b`
  the denominator of `alpha`). This is the case for `d = -1`, where
  `alpha = 0`, and it is checked against PARI. Any other rational root would
  make the certified continued fraction fail to converge, so the worker would
  stop with a precision-cap error instead of certifying. Among all
  `|p|, q <= 300` the only rational root is that of `d = -1`, which is not
  admissible, and no k = 390 run has reported such an error.

By Thue's theorem each `d` has only finitely many points. The engine
certifies `1 <= |g| <= G`. For an **unbounded** certificate of a particular
`d`, `tools/certify_d.gp` calls PARI's `thue()` with unconditional bounds
(`thueinit(...,1)`).

## 3. Which d need to be tried (proved filters)

All of the following are necessary for a half-chart point with `d = p/q`. Only
about **1.9 %** of all pairs `(p, q)` survive them.

| Condition | Reason |
| --- | --- |
| `q` odd, `g` odd | `u = qg = -X` is odd |
| `3 ∤ p q g`, `p ≡ q (mod 3)` | `A ≡ B ≡ C ≡ ε (mod 3)`, so `u ≡ w ≡ 2ε ≢ 0` |
| `4 ∤ p` (m odd) | `v_2(uvw) = v_2(2(36n^3 - m)) = 1` |
| `25 ∤ pq`, `169 ∤ pq` (m = 65) | for `l | m`: `v_l(36n^3 - m) <= v_l(m)` when `v_l(m) <= 2` |
| every prime `l ≡ 1 (mod 3)`, `l ∤ m`, dividing `p` **or** `q` must allow `36t^3 ≡ m (mod l)` | `u, w` divide `2(36n^3 - m)` |

The last row generalizes the repository's 733-prime q-sieve. It applies to
**all** primes (not only those below 20,000) and to the numerator `p` as well
as `q`. The test suite checks that, restricted to primes below 20,000, it
reproduces `q_sieve.forbidden_primes()` exactly.

## 4. What a completed task proves

For a returned shell range `[a, b)`, `collect_d.py` states:

> every `d = p/q` with `a <= max(|p|, q) < b` has **no** point with integer
> `n`, `x = X/2`, `y = Y/2` (`X, Y` odd) and `1 <= |g| <= 10^100` (so
> `|x| <= q * 10^100 / 2`) other than the listed, exactly verified hits.

Inadmissible `d` have no such points at all (section 3). The shell order makes
the statement cumulative: completing shells `1 .. H` settles **every** `d` of
height at most `H`.

## 5. Results so far for k = 390 (m = 65)

| Range | Method | `d` checked | Result |
| --- | --- | --- | --- |
| height <= 20,000 | `run_d_task.py` campaign task, `|g| <= 10^100` | 14,168,321 admissible `d` (800,020,000 pairs) | **no point**; no solution of (Thue) at all |
| height <= 120 | PARI `thue()`, unconditional, **no bound on n or g** | 789 admissible `d` | **no point** |

Files and details are in `validation/dfirst/`.

## 6. Throughput and the reach of a 2,000 core-hour budget

Measured on one core here (x86-64, g++ 13 `-O3`, GMP 6.3):

| Height range | Admissible `d` | µs per admissible `d` | µs per `(p, q)` pair |
| --- | --- | --- | --- |
| 1 – 2,000 | 160,117 | 213 | 4.3 |
| 1 – 12,000 | 5,252,925 | 218 | 3.97 |
| 1 – 20,000 (campaign task) | 14,168,321 | 223 | 3.96 |
| 100,000 – 100,004 | 37,795 | 211 | 4.0 |

The cost per `d` does not grow with height, because the precision is set by
`G`, not by `d`. Shell `H` has `4H - 1` pairs, so completing every shell up to
`H` costs about `2H^2 * 4 µs`:

| Every `d` of height up to | Core-hours |
| --- | --- |
| 100,000 | ≈ 22 |
| 300,000 | ≈ 200 |
| 500,000 | ≈ 560 |
| 950,000 | ≈ 2,000 |

`d_campaign.py --us-per-pair` (default 4.5) sizes the tasks. Recalibrate it
from the first returned `status.json` files: `elapsed_seconds / counters.pairs`.

## 7. Validation

* **Known answers (k = 6, m = 1).** Shells `1 <= H < 450` report exactly
  `d = 1, 22/7, -22/101, 1/181, 181, 7/439, 439/7`: the one point of
  `2^3-1-1` (its two pairings coincide) and both half-chart pairings of each of
  `65^3-58^3-43^3`, `236^3-235^3-55^3` and `644^3-637^3-205^3`, as section 1
  predicts. They include
  the three points `n=-6, x=101/2`; `n=-9, x=-181/2`; `n=-33, x=-439/2`.
* **PARI cross-check.** On 1,934 Thue equations, the worker's solution sets
  equal PARI's unconditional `thue()` sets exactly: 679 solutions, 10 of them
  beyond `g0`, where only the continued-fraction path can find them. The
  equations were every coprime `p/q` with `|p|, q <= 20` at targets 130 and 2,
  every one with `|p|, q <= 12` at targets -7 and 1000, and 550 equations
  (`|p|, q <= 9`) with planted solutions. Scripts:
  `tools/pari_crosscheck.gp` and `tools/pari_compare.py`.
* **Brute force and planted convergents** (`tests/test_dfirst.py`): an
  independent search over `|g| <= 120` and `|g| <= 3000` (for `d = 1`, where
  `eta` is smallest), and solutions with `g >= 10^4` planted at large partial
  quotients, which must come back with `source = "convergent"`.
* **Filters.** Per-shell admissible counts equal an independent
  factorisation-based Python implementation (shells 1–120 for m = 65, 1–79
  for m = 1).
* **Lifecycle.** A deliberately interrupted task resumes from
  `continuation.task.json`. `collect_d.py` reports gaps and full coverage. A
  continuation refuses a different worker binary.

## 8. Running it

```sh
make -j2 && make test                       # builds bin/dthue_worker too
python3 d_campaign.py --campaign-id ce390-dfirst-001 --h-start 1 --h-stop 300001 \
    --seconds 3600 --target-seconds 3000 --output-dir dfirst-tasks
python3 run_d_task.py --task dfirst-tasks/task-000000-*.json --output-dir out/t0
python3 collect_d.py --page dfirst-tasks/page.json --results-dir out --output-dir collected
python3 verify_d.py collected/hits.jsonl --m 65
```

On a Charity Engine host, with the task staged as `/local/input/task.json`:

```sh
python3 /app/run_d_task.py --task /local/input/task.json --output-dir /local/output
```

Use `--hours 2` for `seconds: 3600`, as for the other task types. The runner
stops starting new shells `--reserve-seconds` (default 60) before the budget.
It checkpoints after every shell (a few seconds of work at `H ~ 10^5`) and
writes `continuation.task.json` when shells remain. A continuation pins the
worker and Python hashes. A worker hit is accepted only after the Python
verifier reproduces it exactly, and it is `fsync`ed to `hits.jsonl` at once.

## 9. Relation to the a/q rectangle search, and limits

For `x > 0` the old slope is `a/q = 2|d + 1|` (for `x < 0` it parametrizes
the conjugate `v/u`), so the existing search was already organised around `d`.
Its rectangle, however, forces `d` to heights near `10^55`, about
`4.5*10^100` slopes. The new engine visits `d` in order of height and lets the
size of `n, x` be unbounded up to `|g| <= 10^100`.

Limits, stated plainly. A point is reached only once the campaign reaches the
height of its `d = (A+C)/(A+B)` (reduced). The integer chart (`x` integral)
is not searched by this engine. Adding it means allowing even `q` or even `g`.
