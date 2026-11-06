# CE114 gap search: the recommended 1,800-core-hour computation

**Problem.** Find rational `d` for which

```text
36n^3 − 19 = −2d·x^2·( −(x + 6n) + s ),     s = sqrt( (x + 6n)^2 + (36n^3 − 19)/x ) >= 0,     (E)
```

has a point in either acceptable chart:

1. **integer chart:** `n, x` integers and `s` an integer;
2. **half chart:** `n` an integer, `x = X/2`, `s = Y/2`, with `X, Y` odd.

**Answer in brief.** Both acceptable results are the same thing as an
integer solution of `a^3 + b^3 + c^3 = 114`. So the best algorithm for this
problem is the best algorithm for 114 = sum of three cubes on 1,800 hours.
That algorithm is the Booker–Sutherland method aimed at the part of the search
space their 2020 run for 114 left out. Under their own heuristic, 1,800 hours
give about a **1 in 190,000** chance of a solution on the development host's
speed. That is small, but it is more than 10^5 times the chance from the folder's
earlier engines on the same hours. A completed run also produces a new, exact
exclusion region. Every solution found is turned into its three rational `d`:
one of result 1 and two of result 2.

## 1. Why the problem is exactly 114 = a³ + b³ + c³

Put `A = −x + s`, `B = −x − s`, `C = 2x + 6n`. Identically,

```text
A^3 + B^3 + C^3 − 114 = −6x · ( s^2 − (x+6n)^2 − (36n^3 − 19)/x ).
```

So the square-root condition holds exactly when `A^3 + B^3 + C^3 = 114`.

* **Result 1:** `x, s` integers, so `A, B, C` are integers.
* **Result 2:** `A = (Y − X)/2`, `B = −(X + Y)/2`, `C = X + 6n` are integers
  because `X, Y` are odd.

From (E), `s + (x + 6n) = −2dx`, so `d` is determined by the point:

```text
d = −(x + s + 6n)/(2x) = (A + C)/(A + B).
```

Conversely, let `114 = a^3 + b^3 + c^3`. Since 114 ≡ 6 (mod 9), all three
components are ≡ 2 (mod 3), and since 114 is even the sum is even, so
`6 | a + b + c` and `n = (a+b+c)/6` is an integer. Choose a component as `C`,
order the other two so that `A >= B` (so `s >= 0`), and put
`x = −(A+B)/2` and `s = (A−B)/2`. That pair is in:

* the **integer chart** when `A + B` is even;
* the **half chart** when `A + B` is odd.

114 ≡ 2 (mod 8) rules out three even components, so exactly one is even.
Every representation therefore gives **one point of result 1** (the even
component as `C`) **and two of result 2**, and so three rational `d`.
`to_d.py` performs this conversion and checks every point exactly against
(E).

Consequences for the older engines in this folder:

* `dsweep`, `dsmooth`, `xscan` and `xcurve` find **rational** radicals. A
  rational radical that is not integral (resp. not `Y/2` with `Y` odd) is
  neither result 1 nor result 2. So those runs cannot produce an acceptable
  result unless they stumble on a representation of 114.
* `xroots` (Algorithm D) does search integral radicals, but along small pair
  sums `|X| < 10^6` with `|n|` pushed past 10^18. That is the least fertile
  direction, discussed next.

## 2. What is already excluded, and where to search

Booker and Sutherland (PNAS 2021, arXiv:2007.01209) use `δ = |a + b|` for a
solution with `|a| > |b| > |c|`. They show `0 < δ < α|c|`, with
`α = 2^(1/3) − 1`, and `c^3 ≡ 114·sign(c) (mod δ)`. For 114 they searched:

* `|c| <= 10^17` completely (2019);
* `|c| <= 10^19` with `δ <= 10^19/54` (2020).

Nothing with `δ > 10^19/54 = 1.852 × 10^17` has been searched for any `c`,
and no later search has been published. It is still worth asking them, or
Charity Engine (who ran the 2020 search), before launch.

Their heuristic (`c K(R)`, `K(R) ~ R^(−1/2)`, normalized by Heath-Brown's
`ρ log B`) makes solutions log-uniform in `δ`, with `ρ/δ` per `δ`. A band
`|c| <= Rδ` keeps a share `1 − 1/√(αR)` of them, so

```text
E(δ in [D0, D1), |c| <= Rδ) = ρ (1 − 1/√(αR)) ln(D1/D0),      ρ_114 = 0.058459 (their Table 1).
```

Most of the cost is per `δ`, so the best `δ` to search are the smallest
unsearched ones: from `185185185185185186` upward.

| Use of 1,800 core-hours (k = 114) | Expected solutions |
| --- | --- |
| **This engine**: `δ` from 1.852e17, `|c| <= 64δ` (0.293 µs per `δ`, 2.2e13 `δ`) | **5.3e-6 (1 in 190,000)** |
| Algorithm D (`xroots`): its planned box `|X| < 10^6`, `|n|` 1.7e18 – 1.7e19 (9.5e6 core-hours by its own cost model) | ~1e-11 (rough mapping of `n` to `|c|`) |
| Any rational-radical sweep (`dsweep`, `dsmooth`, `xscan`, `xcurve`) | 0 acceptable results unless the radical happens to be integral |

For scale, a 1% chance would take about 3.8×10^6 core-hours with this code.

## 3. The engine

`src/gap_worker.cpp` is the CE390 gap engine with `k = 114` as the default.
Its method, proofs, measurements and independent review are documented in
[`../../../390 /Scripts for large-scale computations /GAP_SEARCH.md`](../../../390%20/Scripts%20for%20large-scale%20computations%20/GAP_SEARCH.md).
For each `δ` it:

* factors `δ` with a segmented sieve, with early rejection when 114 is not a
  cube modulo a prime `p ≡ 1 (mod 3)` of `δ`;
* finds every cube root of `±114` mod `δ` (AMM, Hensel, CRT);
* walks `c` in the classes forced modulo `9δ` (or `18δ` for odd `δ`) over
  `3.847δ <= |c| <= 64δ`;
* applies 16 exact quadratic-residue filters;
* decides the survivors exactly with GMP and verifies `a^3 + b^3 + c^3 = 114`.

The filters are necessary conditions, so nothing in the region is lost. For
`k = 114`, all three components are ≡ 2 (mod 3), `3 ∤ δ`, and
`sign(c) = +1` exactly when `δ ≡ 2 (mod 3)`.

## 4. Validation (`make test`, 17 tests)

* **Engine.**
  * Rediscovers the record solutions for k = 33, 42, 3, 165, 579, 795 and 906
    from narrow windows.
  * Matches a brute force for every `k ≡ ±3 (mod 9)` up to 100.
  * Every filter decision equals exact arithmetic on production-size
    candidates for k = 114, 390, 627 and 33.
  * Cube-root sets and factorizations are checked at production size for
    k = 114 and 390, including `δ` divisible by 2^25, 5^14, 7^12 and 13^10.
  * Resume, coverage-accounting and audit regressions pass.
* **Converter.**
  * For the record solutions of 42 = 6·7 and 906 = 6·151, it gives one
    result-1 and two result-2 points, each satisfying (E) exactly, with odd
    `X, Y`. These are the same `d` values as the folder's independent
    `grid/verify.py --triple`.
  * A brute force over (E) itself (every `|n| <= 25`, `x = X/2`,
    `0 < |X| <= 120`, both charts, `36n^3 − m` for nine values of `m`, 19
    included) finds that every acceptable point is a representation and is
    listed by `to_d.py`. For `m = 19` it finds none, as Booker–Sutherland's
    bound implies.
  * End to end, a worker hit for k = 42 becomes 1 + 2 points.
* **Pilot.** `validation/pilot/`: 2×10^9 `δ` of the production region,
  0 hits, no gaps, audit agrees.

## 5. Running the 1,800 core-hours

```sh
make && make test
python3 gap_campaign.py --calibrate                 # on Charity Engine's CPU type: prints R and us/d
python3 gap_campaign.py --campaign-id ce114-gap --ratio-max 64 --us-per-d <measured> --plan-only
python3 gap_campaign.py --campaign-id ce114-gap --ratio-max 64 --us-per-d <measured> --output-dir gap-tasks
# each task (Charity Engine: the container's default command on /local/input/task.json)
python3 run_gap_task.py --task gap-tasks/tasks/ce114-gap-0000.json --output-dir gap-results/ce114-gap-0000
# afterwards
python3 collect_gap.py --page gap-tasks/page.json --results gap-results --output-dir gap-collected
python3 audit_gap.py   --page gap-tasks/page.json --results gap-results --fraction 0.02
python3 to_d.py gap-collected/hits.jsonl            # the rational d of results 1 and 2, verified on (E)
```

* **Defaults:** `k = 114` and 1,800 core-hours. The planner sizes the `δ`
  range from the measured µs per `δ`, so calibrate on the grid's hardware.
  At this host's 0.293 µs, the plan is 1,801 one-hour tasks covering
  `δ` in [185185185185185186, 185207301226140817).
* **Robustness:** tasks checkpoint every 2^24 `δ` (fsynced) and resume in
  place. A checkpoint records exactly the interval its directory searched.
  `audit_gap.py` re-runs a sample of returned chunks to catch faulty hosts;
  re-issue any that disagree.
* **Resources:** about 0.24 GB of memory and 1–3 s of set-up per task.
  `docker build .` builds the image and runs the tests during the build.

## 6. What a completed run proves

A completed, audited run proves that **(E) has no point of result 1 or 2
coming from a representation with `δ = |a+b|` in the covered range and
`3.847δ <= |c| <= 64δ`**. In particular it rules out every rational `d`
those points would give. It does not cover other representations. The odds
in §2 are heuristic: they rest on Heath-Brown's conjecture and
Booker–Sutherland's model.
