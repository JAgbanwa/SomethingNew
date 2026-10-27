# d-first search for half-integer points (`dthue_worker`)

**Target.** Rational values of `d` for which the equation

```text
36n^3 - 65 = -2*d*x^2*( -(x+6n) + sqrt( (x+6n)^2 + (36n^3-65)/x ) )
```

has a point with integer `n = 1 (mod 3)`, `x = X/2` (`X` odd) and
`sqrt((x+6n)^2 + (36n^3-65)/x) = y = Y/2` (`Y` odd and positive).
Both signs of `n` and `X` are eligible. Production uses `m=65`.

This engine enumerates **`d` itself**, ordered by height `H(d) = max(|p|, q)` for
`d = p/q` in lowest terms. For each `d` it solves one binary cubic Thue
equation and reports every such point with `1 <= |g| <= 10^100`, where `g`
(defined below) satisfies `|x| = q|g|/2`. Every reported point is checked
exactly against the original, unsquared equation. There is no selected `n,x`
rectangle. A processed `d` is settled only up to the stated `g` bound, not
for arbitrary coordinates.

This is the primary production workflow. Its project ceiling is **1,800
aggregate core-hours**, with **200 separate hours reserved for other projects**.
The default estimated-work plan is 1,600 hours inside that ceiling. The
remaining 200 project hours provide headroom; they are distinct from the 200
hours outside this project. See [README.md](README.md) for the budgeted runner.

| File | Role |
| --- | --- |
| `src/dthue_worker.cpp` | Native GMP worker: shells of `d`, Thue solver, exact certificates |
| `d_campaign.py` | Writes task files (disjoint height-shell ranges) and `page.json` |
| `run_d_task.py` | Restartable runner: per-shell checkpoint, continuation, status |
| `run_d_campaign.py` | Serial campaign controller with durable attempt accounting and the project ceiling |
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

**The production residue class.** When `m=65`, the cube sum is
`390 = 3 (mod 9)`, so `A = B = C = 1 (mod 3)`. For every such integer `t`,
`t^3 = 3t-2 (mod 27)`. Thus

```text
390 = 3(A+B+C)-6 = 18n-6 (mod 27),
```

which implies `n = 1 (mod 3)`. The production native and Python verifiers
also check that residue explicitly. This production-only assertion is not
applied to the `m=1` known-answer tests.

**Every representation has a half-integer chart.** `A+B+C` is even, so the number of
odd cubes is 0 or 2, and it cannot be 0 because `8 ∤ 6m` for odd `m`. So
exactly one cube is even. Pairing it with either odd cube gives an odd pair
sum `u`. So each representation admits two choices of the odd component left as `C`;
these produce half-chart points, although repeated components can make the
points or `d` values coincide. Order the other pair so `A>B`; then `Y>0` and
`X` is odd. No integer representation of 390 is lost by the half-chart
requirement when all signed coordinates are allowed. In the k = 6 test, `(-43, -58, 65)` gives
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
  empty range as complete. With `G = 10^100`, the historical runs below used their initial
  precision without refinement. That observation is not a universal precision
  guarantee; the exact enclosure and refinement checks remain required.
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

All of the following are necessary for a half-chart point with reduced
`d = p/q`, `q>0`. The earlier filter admitted about 1.9% of raw pairs in its
recorded samples. The current modulo-4 filter is stronger; its runtime effect
must be measured rather than inferred from that historical percentage.

| Condition | Reason |
| --- | --- |
| `q` odd, `g` odd | `u = qg = -X` is odd |
| `3 ∤ p q g`, `p ≡ q (mod 3)` | `A ≡ B ≡ C ≡ ε (mod 3)`, so `u ≡ w ≡ 2ε ≢ 0` |
| `p(p+q) = 2 (mod 4)` (m odd) | Reduce (Thue) modulo 4 with odd `q,g`; this also implies `4 ∤ p` |
| `25 ∤ pq`, `169 ∤ pq` (m = 65) | for `l | m`: `v_l(36n^3 - m) <= v_l(m)` when `v_l(m) <= 2` |
| every prime `l ≡ 1 (mod 3)`, `l ∤ m`, dividing `p` **or** `q` must allow `36t^3 ≡ m (mod l)` | `u, w` divide `2(36n^3 - m)` |

The last row generalizes the repository's 733-prime q-sieve. It applies to
**all** primes (not only those below 20,000) and to the numerator `p` as well
as `q`. The test suite checks that, restricted to primes below 20,000, it
reproduces `q_sieve.forbidden_primes()` exactly.


### Proof and implementation of the stronger modulo-4 filter

For odd `m`, reduce the Thue equation modulo 4:

```text
p*q*(p+q)*g^3 = 2*m = 2 (mod 4).
```

The half-chart requires `q,g` odd. Also `p(p+q)` is even because `q` is odd.
Multiplication of an even residue by the odd residue `q*g^3` preserves
whether it is 0 or 2 modulo 4. Therefore

```text
p*(p+q) = 2 (mod 4)
```

is necessary. With odd `q`, it is equivalent to `p = 2 (mod 4)` when `p` is
even, or `p = q (mod 4)` when `p` is odd. For example `p=-1,q=5` satisfies
the old `4 ∤ p` condition but fails the new condition; negative numerators
must not be interpreted using an unnormalized language remainder.

The native worker normalizes signed residues before evaluating the small
modulo-4 product, avoiding large integer multiplication and overflow.
`dfirst_common.admissible` implements the same necessary condition independently
in Python; `tools/certify_d.gp` applies it before the PARI solve. The test suite
covers signed cases, residue exhaustion against the Thue equation, agreement
between worker and Python counts, and preservation of the known-answer hits.
It does not apply this odd-`m` rule to even-`m` validation modes.

At `m=65`, height at most 120 contains **517** currently admissible fractions,
compared with **789** under the historical filter: 272 additional exclusions
(34.47% of the earlier survivors). All seven recorded `k=6` half-chart points
survive. This comparison measures solver candidates, not wall-time speedup.

## 4. What a completed task proves

For a returned shell range `[a, b)`, `collect_d.py` states:

> every `d = p/q` with `a <= max(|p|, q) < b` has **no** point with integer
> `n = 1 (mod 3)`, `x = X/2`, `y = Y/2` (`X, Y` odd, `Y>0`) and `1 <= |g| <= 10^100` (so
> `|x| <= q * 10^100 / 2`) other than the listed, exactly verified hits.

Inadmissible `d` have no such points at all (section 3). The shell order makes
the statement cumulative: completing shells `1 .. H` settles **every** `d` of
height at most `H`.

## 5. Historical results for k = 390 (m = 65)

These are retained records from the earlier filter and worker version. Their
original counts and hashes are not relabeled as current runs. The strengthened
filter retains the mathematical scope while excluding more impossible cases.

| Range | Method | `d` checked | Result |
| --- | --- | --- | --- |
| height <= 20,000 | `run_d_task.py` campaign task, `|g| <= 10^100` | 14,168,321 admissible `d` (800,020,000 pairs) | **no point**; no solution of (Thue) at all |
| height <= 120 | PARI `thue()`, unconditional, **no bound on n or g** | 789 admissible `d` | **no point** |

Files and details are in `validation/dfirst/`.

## 6. Planning inside the 1,800-core-hour project ceiling

The committed earlier-worker timings (x86-64, g++ 13 `-O3`, GMP 6.3, one core
of a shared cloud sandbox) are calibration references:

| Height range | Historical admissible `d` | Microseconds per admissible `d` | Microseconds per raw pair |
| --- | --- | --- | --- |
| 1–2,000 | 160,117 | 213 | 4.3 |
| 1–12,000 | 5,252,925 | 218 | 3.97 |
| 1–20,000 | 14,168,321 | 223 | 3.96 |
| 100,000–100,004 | 37,795 | 211 | 4.0 |

Short native comparisons of the old and strengthened worker are recorded in
[validation/dfirst-v1.1/benchmark.json](validation/dfirst-v1.1/benchmark.json):

| Height range | Version 1.0.0: admissible / seconds | Version 1.1.0: admissible / seconds |
| --- | ---: | ---: |
| 1–1,000 | 44,281 / 9.762334 | 29,633 / 5.399138 |
| 100,000–100,004 | 37,795 / 8.630058 | 22,695 / 3.854018 |

Both versions used the same CPU affinity, target `m=65`, and `G=10^100`.
These are short, unrepeated samples on a shared host; they are not a production
throughput guarantee. Keep the 4.5-microsecond planning rate until deployment
measurements justify changing it.

These measurements do not establish a height-independent cost at arbitrary
scale or performance on other hosts. Recalibrate the strengthened worker from
returned statuses: `1e6 * elapsed_seconds / counters.pairs` is microseconds per
raw pair. Account for runner and host overhead separately.

Shell `H` has `4H-1` raw pairs, so cumulative pair count and projected work are

```text
P(H) = 2*H^2 + H,
estimated core-hours = P(H) * microseconds_per_pair / 3,600,000,000.
```

At the conservative generator default of 4.5 microseconds per pair:

| Cumulative height | Estimated search core-hours |
| --- | ---: |
| 100,000 | 25.000125 |
| 300,000 | 225.000375 |
| 500,000 | 625.000625 |
| 799,999 | 1599.997000 |
| 800,000 | 1600.001000 |
| 900,000 | 2025.001125 |
| 950,000 | 2256.251188 |

The default generator derives height **799,999** and 1,901 tasks from a
**1,600-hour estimated work allocation**. The project ledger's separate hard ceiling is **1,800 hours**.
The **200 hours for other projects are outside that ceiling** and are never
used for this project's retries or headroom. A budget can expire before all
planned heights finish; the collector then reports the actual covered ranges.

On Linux, `run_d_campaign.py` pins each runner and worker to one available CPU
and reserves each invocation's full possible duration before
launch and charges elapsed wall time after termination. Its serial one-worker
accounting includes continuations, errors, and shutdown allowance. An unresolved
crash reservation stays held against the allowance and blocks automatic restart. Preserve the
ledger and manifest; do not start a fresh ledger to evade an exhausted budget.

The controller bounds only invocations it launches. Manual distributed CE jobs
need centralized accounting for the actual provider allocation or charges,
including multiple cores and startup/output time. A per-task soft deadline or
an estimated page cost cannot enforce a global external-service bill. See
[CE_OPERATIONS.md](CE_OPERATIONS.md).

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

Run from this directory:

```sh
make -j2
make test
python3 d_campaign.py --campaign-id ce390-dfirst-1800 \
    --output-dir dfirst-tasks --plan-only
python3 d_campaign.py --campaign-id ce390-dfirst-1800 \
    --budget-core-hours 1800 --planned-core-hours 1600 \
    --us-per-pair 4.5 --g-max-digits 100 --output-dir dfirst-tasks
python3 run_d_campaign.py --page dfirst-tasks/page.json \
    --output-dir dfirst-results --max-attempts 1
```

The last command runs one charged pilot attempt. Continue the same ledger by
omitting `--max-attempts 1`; then collect all returned attempt directories:

```sh
python3 run_d_campaign.py --page dfirst-tasks/page.json --output-dir dfirst-results
python3 collect_d.py --page dfirst-tasks/page.json \
    --results-dir dfirst-results --output-dir dfirst-collected
python3 verify_d.py dfirst-collected/hits.jsonl --m 65
```

An explicit `--h-stop` selects a smaller finite range; endpoints are half-open.
The generator creates files only and does not submit CE jobs. Directly running
`run_d_task.py` bypasses the local campaign ledger and therefore requires
separate project-level resource accounting.

On a Charity Engine host, stage one task as `/local/input/task.json` and use

```text
python3 /app/run_d_task.py --task /local/input/task.json --output-dir /local/output
```

The rebuilt container selects that command by default. Use an image whose
source, worker version, and tests correspond to this change; a previously
published image does not acquire the new filter or entrypoint automatically.
An external two-hour allowance has historically been used for a 3,600-second
internal task budget. Confirm provider limits and account for its actual
resource charges inside 1,800 hours; see [CE_OPERATIONS.md](CE_OPERATIONS.md).

The task runner checkpoints each completed shell and writes
`continuation.task.json` if work remains. Continuations pin the worker and
Python hashes. A hit is accepted only after the independent verifier reproduces
it exactly and is then flushed to `hits.jsonl`.

## 9. Relation to the historical rectangle search

The production campaign no longer restricts `n,x` to the old large rectangle.
Those interfaces and fixtures remain explicitly historical; see
[HISTORICAL_RECTANGLE_SEARCH.md](HISTORICAL_RECTANGLE_SEARCH.md).

For the old defaults `abs(n)<=10^45` and `abs(x)>=10^54`, put
`r=abs(n)/abs(x)<=10^-9` and

```text
E = (36*r^3 + 65/abs(x)^3) / (2*(1-6*r)).
```

Rationalizing the radical gives `0<abs(d+1)<=6*r+E` when `x>0`, and
`0<abs(d)<=E` when `x<0`. Since a reduced nonzero numerator has magnitude at
least 1, a point in that rectangle needs `q>=166666667` in the positive-`x`
case, and `q` at least approximately `5.55*10^25` in the negative-`x` case.
These conservative bounds already exceed the height affordable in this
campaign. Opening coordinate ranges therefore explores a different region;
it does not make the old rectangle exhaustible.

The unreduced pair sums can share large factors. Their size does not prove
that the reduced rational height must be near `10^55`. A campaign reaches a
point only after visiting the height of its reduced `d` and a sufficient `g`
bound. Every finite run covers only its recorded heights and scale bound.

The half-chart search retains every integer representation of 390 after an
appropriate permutation of its components, but does not list every integer
coordinate chart of that representation. Neither this parameter ordering nor
a finite compute allowance guarantees finding a solution.
