# CE375 primitive gap search: finding primitive representations of 375

**Goal.** Find primitive integer representations `a^3+b^3+c^3=375`, then convert
them to points on

```text
y² = (x + 6n + 3)² + (36n³ + 54n² + 27n − 58)/x,     36n³ + 54n² + 27n − 58 = ((6n+3)³ − 375)/6,
```

With `A = −x + y`, `B = −x − y`, `C = 2x + 6n + 3`, the equation is equivalent to
`A³ + B³ + C³ = 375`. The integer chart has integer `n,x,y`; the half-integer chart
has `x=X/2`, `y=Y/2` with odd `X,Y`. `to_points375.py` checks the equation exactly
and records cube primitivity separately from point primitivity. The latter is
`gcd(n,x,y)=1` in the integer chart and `gcd(X,Y)=1` in the half chart. This
folder's `desired` flag requires both primitive cubes and a primitive point.
The fixed-`g` folder's diagnostic `desired` flag tests point primitivity alone;
its production restriction already forces primitive cubes.

**Notation:** the original discussion's integer `x` is **`n` here**; its rational
`m` is **`x` here**. Thus original `abs(x)>=10^14` is a filter on `abs(n)`, not a
gap bound or a cube-height frontier. See the [search selection guide](../README.md).

**Charity Engine:** start with the reproducible local/container pilot in
[`CHARITY_ENGINE_HANDOFF.md`](CHARITY_ENGINE_HANDOFF.md). Campaign generation does
not submit jobs. The guide covers finite work units, build identity, collection,
restarts, calibration, and the CE execution contract.

## 1. Why this folder exists

This engine enumerates the cancellation gap `δ = |a+b|` and cube roots of 375
modulo `δ`, using a Booker–Sutherland-style search adapted to the cube factor
`5³` in 375. It searches primitive representations directly in an assigned
gap/ratio region and has a compiled worker plus a distributed-task pipeline.
It is the recommended starting point for a CE pilot.

The current engine in
[`../Scripts for large-scale computations/`](../Scripts%20for%20large-scale%20computations/)
has a different contract: it searches reduced slopes `(A+C)/(A+B)=p/q` with
**only `g=-1,+1`**, through slope height `H=max(abs(p),q)`. Its normal height
limit is `200000000`. It is useful for that restricted family, not general
primitive-cube coverage. The complementary compiled
[Elkies–Jahnel backend](../Scripts%20for%20large-scale%20computations/elkies-jahnel/)
organizes its search by cube-height shells and lattice tiles. It should be
benchmarked as a separate method before allocating a large campaign to it.

The historical rationale is retained as
[`ce375_rationale.pdf`](ce375_rationale.pdf) (source
[`ce375_rationale.tex`](ce375_rationale.tex)). Its quantitative d-first comparison
predates the current fixed-`g` contract. Section 4 below preserves historical
timings and model outputs with that qualification; they are not a measured
speedup or discovery probability for the current engines. The current frontier
interpretation is corrected in section 3.

## 2. Mathematics

Write a solution with `|a| ≥ |b| > |c|`, `δ = |a+b|`, `z = |c|`. Booker–Sutherland: `δ < α z`
(`α = 2^(1/3) − 1`), `z³ ≡ ±375 (mod δ)`, and `Δ = (4(z³ − K)/δ − δ²)/3 = (a−b)²`. Since
`375 ≡ 6 (mod 9)`, all of `a, b, c ≡ 2 (mod 3)`, exactly as for 114, so the sign and residue
rules of the 114 engine apply unchanged.

**Lemma (primitive δ).** Let `p ≠ 3` be a prime with `p³ | k` and `p ≡ 2 (mod 3)` (for 375: `p = 5`).
If `gcd(a, b, c) = 1`, then `v_p(δ) = 0` or `v_p(δ) ≥ 3`.

*Proof.* If `p ∤ c`, then `a³ + b³ = k − c³ ≢ 0 (mod p)`, so `p ∤ a + b`. If `p | c`, then `p ∤ a`
(otherwise `p | b³ = k − a³ − c³`, and `p | gcd`), likewise `p ∤ b`, so `a ≡ −b (mod p)` gives
`a² − ab + b² ≡ 3b² ≢ 0 (mod p)`. Hence `v_p(a+b) = v_p(a³+b³) = v_p(k − c³) ≥ min(v_p(k), 3) = 3`. ∎

So for 375 every `δ` with `5 ∥ δ` or `25 ∥ δ` is skipped (`--primitive`), 19.2 % of the `δ` prime
to 3. Every `δ` with `5 ∤ δ` can only carry primitive solutions; for `125 | δ`, the worker tags each
hit with `primitive = [gcd(x, y, z) = 1]`.

**Roots modulo `p^e` for `p | k`.** With `k = p^v u`, `p ∤ u`: for `e ≤ v` the roots of `z³ ≡ k` are
the multiples of `p^⌈e/3⌉`; for `e > v` they need `3 | v`, and then `z = p^(v/3) z'` with
`z'³ ≡ u (mod p^(e−v))` (cube roots and Hensel lifting as for other primes), `z'` free modulo
`p^(e−v/3)`. For 375 this gives 25 roots modulo `5^e` for every `e ≥ 3`. The worker builds these
directly, for any `e` (the inherited brute force refused `5^11 | δ`).

## 3. The frontier and the yield model

The [Booker–Sutherland paper](https://arxiv.org/abs/2007.01209) treats cube-free
targets; its search limits must not automatically be attributed to primitive
375. Historical height searches are described in
[Sutherland's 2022 survey](https://math.mit.edu/~drew/Mordell2022.pdf) and
[Huisman's 2016 paper](https://arxiv.org/abs/1604.07746), the latter reporting a
search for `k<1000` through coordinate magnitude `10^15`. These historical
reports do not establish the entire currently unsearched gap/ratio region.
Record the source and exact scope of any assumed exclusion before a production
campaign; the planner's default is not a verification of the present frontier.

The planner takes a cube-coordinate **frontier** `N` as `--frontier` (default
`10^14`) and models the expected yield beyond it. It uses the asymptotic
expression

```text
z³ > δ (3 (2N − δ)² + δ²) / 4.
```

This is a **planning approximation**, not an exact exclusion filter. In the
normalization `Δ=(4(z³−K)/δ−δ²)/3`, where `K` is the appropriate signed target,
the largest coordinate is `(δ+√Δ)/2`. For `δ<=2N`, its exact threshold includes
the additional term `+K` on the right; for `δ>2N` it exceeds `N` automatically.
The planner neglects the signed constant at large scale. The worker does not
use `--frontier` to prune candidates: it checks the actual target exactly.

Integrating the Booker–Sutherland density
`ρ/(2√α) δ^(−1/2) z^(−3/2)` over the planned region gives a heuristic expected
count `E`. Applying that distribution model to primitive 375 and converting
`E` to `1-exp(-E)` are modeling assumptions. They do not give a verified
discovery probability or a guarantee that a representation will be found.

The recorded truncated-product estimate is **`ρ ≈ 0.0586`** for primitive
solutions of 375 (`tools/rho.py`, record in `validation/rho-P1e8.txt`). Booker and
Sutherland tabulate `ρ` only for cube-free `k`, so this estimate is computed
from local densities, `ρ = C ∏_p σ_p`:

* `p ≡ 2 (mod 3)`, `p ∤ 3k`: `σ_p = 1`.
* `p ≡ 1 (mod 3)`, `p ∤ 3k`: `σ_p = N_p/p²` with `N_p = p² + 6p − L` if `k` is a cube mod `p` and
  `p² − 3p − L` otherwise, `4p = L² + 27M²`, `L ≡ 1 (mod 3)` (Jacobi sums; checked by brute force).
* `p | 3k`: exact counts of solutions mod `p^e` *not all divisible by p*. For 375: `σ₃ = 1/3` and
  `σ₅ = 24/25` (primitive; the same value as for 390, where `5 ∥ k`).
* `C` does not depend on `k`. Calibrated on Booker–Sutherland's `ρ` for 114, 390 and 627, the three
  values of `C` agree to **0.01 %** (`C = 0.58886`), which checks the whole computation.

The Euler product over `p ≡ 1 (mod 3)` converges conditionally; truncated at `10⁵, 10⁶, 10⁷, 10⁸`
it gives `ρ₃₇₅ = 0.05865, 0.05862, 0.05862, 0.05861`. For comparison `ρ₁₁₄ = 0.05846`.

## 4. Historical timing records and model illustrations

The following figures are retained from the earlier repository report. They
have not been re-audited as part of this handoff, are not CE hardware
measurements, and do not benchmark the new Elkies–Jahnel backend. The d-first
column refers to the older general-`g` comparison, not today's fixed-`g` worker.
Use new measurements and a documented frontier for a proposed allocation.

Calibration (`gap_campaign.py --calibrate`, k = 375, `--primitive`, development host, one core):

| ratio_max | µs per δ at δ = 10¹⁰ | µs per δ at δ = 10¹² |
| ---: | ---: | ---: |
| 1024 | 0.211 | 0.221 |
| 2048 | 0.245 | 0.238 |
| 4096 | 0.271 | 0.289 |
| 8192 | 0.385 | 0.367 |
| 16384 | 0.463 | 0.553 |
| 32768 | 0.700 | 0.690 |
| 65536 | 1.206 | 1.186 |

Historical model illustrations (`gap_campaign.py --optimize`, 1,800 core-hours):

| assumed frontier N | historical plan | E/ρ | E (ρ = 0.0586) | model P(≥ 1) | old general-g d-first model (H ≈ 1.5·10⁶) |
| --- | --- | ---: | ---: | ---: | ---: |
| 10¹⁴ | δ from 5.6·10⁸ to 2.4·10¹³, R = 4096 | 2.66 | 0.156 | **14.4 %** | ~3·10⁻⁹ |
| 10¹⁵ | δ from 5.6·10⁹ to 2.4·10¹³, R = 4096 | 1.07 | 0.063 | **6.1 %** | ~3·10⁻¹⁰ |
| 10¹⁶ | δ from 5.6·10⁹ to 1.4·10¹³, R = 16384 | 0.39 | 0.023 | **2.3 %** | ~3·10⁻¹¹ |

The value of these illustrations depends on their model and frontier
assumptions. Existing coverage of the proposed `(δ,z)` region can make a
campaign redundant. Resolving that scope, measuring current throughput, and
validating the image and retry workflow are separate prerequisites for a large
allocation. No contact or new verification of the frontier is claimed here.

## 5. Running

```sh
make && make test                                    # run the current suite
python3 gap_campaign.py --calibrate --calibration-d 1e10 --save-calibration calib.json   # on the grid's CPU
python3 gap_campaign.py --optimize calib.json --core-hours 1800 --frontier <confirmed N>
python3 gap_campaign.py --campaign-id ce375-gap --core-hours 1800 --d-start <D0> --ratio-max <R> \
    --us-per-d <measured> --frontier <N> --output-dir ce375-gap-tasks
# each task (Charity Engine: the container's default command on /local/input/task.json)
python3 run_gap_task.py --task ce375-gap-tasks/tasks/ce375-gap-0000.json --output-dir results/ce375-gap-0000
# afterwards
python3 collect_gap.py --page ce375-gap-tasks/page.json --results results --output-dir collected --require-complete
python3 audit_gap.py   --page ce375-gap-tasks/page.json --results results --fraction 0.02
python3 to_points375.py collected/hits.jsonl              # when the hit file is nonempty
```

Tasks are primitive by default (`"primitive": true`). Use the
[handoff guide](CHARITY_ENGINE_HANDOFF.md) for a fixed, small pilot before a
production-sized page. It also distinguishes application checkpoints from CE
CLI checkpoints, describes release hashes and finite-task continuation, and
explains the limits of a sampled audit. The runner and collector accept
`--expected-worker-sha256`; changed-binary resumes and mixed-binary collections
are rejected. Completion also requires a matching worker terminal record and
a successful exit. An indefinite controller can keep
issuing more tasks; extending one gap interval with a fixed ratio cap is not
complete coverage of all cube triples.

## 6. Validation fixtures and historical pilot

`make test` is the source of truth for the current test count and result. The
following list describes the inherited mathematical fixtures; new deployment
regressions are also included in the suite.

* **Inherited engine tests (16):** the record solutions of 33, 42, 3, 165, 579, 795, 906; a brute
  force for every `k ≡ ±3 (mod 9)` up to 100; filter verdicts against exact arithmetic (including
  `z ≥ 2⁶⁴`); factorizations and roots at production size; plan / run / interrupt / resume /
  collect; coverage accounting and the audit.
* **Cube-factor, primitive and ρ tests (18):**
  * roots modulo every `δ < 2500` against brute force for `k = 24, 375, 1875, 3000, 7125, −375`, and
    root counts at `δ ≈ 10¹³` divisible by `5^e`, `e` up to 17;
  * the lemma checked on every primitive solution with coordinates up to 600 for those `k`;
  * a brute force over coordinates up to 1500 for `k = 24, 48, 375, 750, 1875, 3000, 6000, 7125`:
    without `--primitive` the worker finds exactly the solutions in its region with correct
    `primitive` flags; with it, exactly the primitive ones;
  * `--no-filter` gives identical hits; `5 × (the k = 3 record)` is found and tagged non-primitive
    without `--primitive` and skipped with it; cube-free `k` are unaffected; `k = 3·7³` is refused
    (`7 ≡ 1 mod 3`, where the lemma does not hold);
  * counters are identical however a range is split (the audit's precondition);
  * the converter is cross-checked against the d-first folder on reconstructed points and point-gcd tests; `desired` retains this folder's additional cube-primitivity condition;
  * the yield model reduces to its closed form without a frontier and implements its asymptotic frontier expression;
  * `ρ`: the point-count formula against brute force for eight primes, the exact local factors
    (`σ₃ = 1/3`, `σ₅ = 24/25`), and the calibration constant equal for 114, 390, 627 to 0.5 % at
    `P = 10⁶`, with `ρ₃₇₅` in `[0.0580, 0.0592]` (3 tests);
  * an end-to-end campaign at `k = 7125 = 57·5³` finds its primitive solution `(−67)³ + (−46)³ + 74³`,
    collects it as PRIMITIVE, audits cleanly and converts it to two desired half-chart points.

**Historical pilot at k = 375** (recorded as worker 1.2.0, 22 Nov 2026, through plan / run / collect / audit; not re-audited for this handoff):
`δ ∈ [5623413252, 7623413252)`, `R = 4096`, `--primitive`, two tasks in parallel on the two-core
development host.

| Quantity | Value |
| --- | --- |
| `δ` values | 2,000,000,000 (gaps: none) |
| skipped: `3 \| δ` / primitivity lemma / no cube root | 666,666,667 / 256,000,000 / 700,605,724 |
| `δ` processed, cube roots | 376,727,609, 953,402,561 |
| candidates `z` | 325,122,046,498 (163 per `δ`) |
| exact GMP checks | 9,953,920 |
| worker time | 0.154 core-hours (0.28 µs per `δ`) |
| audit (5 %) | 6 / 6 chunks reproduce exactly |
| representations of 375 | 0 |

Heuristic weight of the pilot region: `E/ρ = 1.06·10⁻⁴` (frontier `10¹⁵`). The first audit of an
earlier build caught a split-dependent accounting difference (the primitivity skip was read from
sieve factor lists); it was fixed, and a regression test now requires identical counters however a
range is split.

## 7. What a completed run proves

A fully completed and validated campaign with no hits excludes primitive
representations within its recorded gap/ratio region, with the worker's exact
integer endpoint conventions. The displayed decimal `3.847` is a rounded
description; keep the
task manifest and worker version for the precise coverage statement. It does
not exclude representations outside that region, prove that no primitive
representation exists, or certify every unsampled worker execution merely
because a sampled audit passed.

An individual reported hit is checked exactly. The historical yield figures
in section 4 remain heuristic and conditional on their assumptions. For a
height-shell exclusion or a complementary implementation check, use and
benchmark the separate Elkies–Jahnel backend with its own coverage contract.
