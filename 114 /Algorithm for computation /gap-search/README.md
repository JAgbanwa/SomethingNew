# CE114 gap search: the recommended 1,800-core-hour computation

The detailed write-up (proofs, figures, validation) is [`../ce114_rationale.pdf`](../ce114_rationale.pdf).

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
give about a **1 in 145,000 – 165,000** chance of a solution
(0.223–0.255 µs per step; it was 1 in 190,000 – 200,000 before the 2-adic rule and wheel of §3). That is small, but it is
about 10^5 times the chance from the folder's earlier engines on the same
hours. A completed run also produces a new, exact
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
The three components are also distinct: two equal ones would give
`2a^3 + c^3 = 114`, which has no integer solution. PARI's unconditional
Thue solver, `thue(thueinit(x^3+2,1),114)`, returns `[]`. And `A + B = 0`
would force `C^3 = 114`. Every representation therefore gives **one point of
result 1** (the even component as `C`) **and two of result 2**, and so three
distinct rational `d`. (For other `6m` with a repeated component, `to_d.py`
lists the two distinct points.)
`to_d.py` performs this conversion and checks every point exactly against
(E).

Consequences for the older engines in this folder:

* `dsweep` and `dsmooth` do have integral modes (`--integral`, and the
  default in the half chart). But they enumerate the certificate `U = 2dx^2`
  (resp. `V = dX^2`). By Booker–Sutherland's bound, any integral solution
  needs a certificate of at least 25 digits (`|V| >= 5.8·10^24`,
  `../HALF_INTEGER.md`), while `dsweep` stops at 18 digits and `dsmooth`
  reaches such sizes only for B-smooth certificates. `xscan` scans windows
  of `n` far below the `|n| >= 9.8·10^15` that any acceptable result needs.
  So these three cannot reach one.
* `xcurve` (the Mordell curve of a fixed `x`) is not bounded in `n`, so it
  could in principle find one at small `|x|`. But `|x| = |A+B|/2`, and for
  pair sums up to 1.85×10^17 Booker–Sutherland already excluded
  `|c| <= 10^19`. Under their heuristic, all `|x| <= 5000` together hold
  about 7×10^-9 expected solutions beyond that bound, even if every curve
  were solved completely.
* `xroots` (Algorithm D) does search integral radicals, but along small pair
  sums `|X| < 10^6` with `|n|` pushed past 10^18. That is the least fertile
  direction, discussed next.

## 2. What is already excluded, and where to search

Booker and Sutherland (PNAS 2021, arXiv:2007.01209) use `δ = |a + b|` for a
solution with `|a| > |b| > |c|`. They show `0 < δ < α|c|`, with
`α = 2^(1/3) − 1`, and `c^3 ≡ 114 (mod δ)` (equivalently `|c|^3 ≡ 114·sign(c)`). For 114 they searched:

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
| **This engine**: `δ` from 1.852e17, `|c| <= 64δ` (0.223 µs per `δ`, 2.90e13 `δ`) | **6.9e-6 (1 in 145,000)**; at 0.255 µs, 1 in 165,000 |
| Algorithm D (`xroots`) spending the same 1,800 h in its planned box (`|X| < 10^6`, `|n|` 1.7e18 – 1.7e19); the whole box is 9.5e6 core-hours by its own cost model and worth ~5e-8 | ~1e-11; ~3–6e-11 if spent on its best slice |
| `dsweep`, `dsmooth`, `xscan` | 0: they cannot reach the certificate size or `n` any solution needs (above) |
| `xcurve` on every `|x| <= 5000`, solved completely | ~7e-9 in total |

For scale: the chance grows linearly with hours. This code can reach at most
about 0.9% (δ up to about 2.25×10^17, where `(R + 18)·δ` hits 2^64 at
`R = 64`), in about 2.5×10^6 core-hours.

## 3. The engine

`src/gap_worker.cpp` is the CE390 gap engine with `k = 114` as the default.
Its method, proofs, measurements and independent review are documented in
[`../../../390 /Scripts for large-scale computations /GAP_SEARCH.md`](../../../390%20/Scripts%20for%20large-scale%20computations%20/GAP_SEARCH.md).
For each `δ` it:

* factors `δ` with a segmented sieve, with early rejection when 114 is not a
  cube modulo a prime `p ≡ 1 (mod 3)` of `δ`. A mod-24 wheel sieves only the 10
  allowed classes of `δ` mod 24 (`1, 5, 7, 11, 13, 17, 19, 23` and `10, 14`). Each prime
  `p ≥ 5` steps only through multipliers `m` with `m·p` in an allowed class, and the
  bucket entries carry `m mod 24`. Peak memory is 0.232 GB over 4·10^9 `δ`;
* skips, before factoring, the even `δ` excluded by the 2-adic rule: for
  `k ≡ 2 (mod 4)`, an even `δ` makes `a, b` odd and `c` even, so
  `a + b = −sign(c)·δ ≡ k (mod 8)`. For 114 only `δ ≡ 10, 14 (mod 24)` survive among
  the even `δ`. This is the 2-adic half of Result 1's `x ≡ 7 (mod 12)`. Its other
  condition, `n ≡ 0 (mod 3)` (`z ≡ δ mod 9`), is already implied by the walk's classes.
  The rule removes a quarter of all `δ` and makes the engine about 1.26× faster
  (0.319 → 0.250 µs per `δ`, back to back on one host). The wheel adds about 3%
  (0.250 → 0.243), so the total is about 1.31×. Counter: `d_skipped_2adic`.
  `--no-filter` turns it off;
* finds every cube root of `±114` mod `δ` (AMM, Hensel, CRT);
* walks `c` in the classes forced modulo `9δ` (or `18δ` for odd `δ`) over
  `3.847δ <= |c| <= 64δ`;
* applies 16 exact quadratic-residue filters;
* decides the survivors exactly with GMP and verifies `a^3 + b^3 + c^3 = 114`.

The filters are necessary conditions, so nothing in the region is lost. For
`k = 114`, all three components are ≡ 2 (mod 3), `3 ∤ δ`, and
`sign(c) = +1` exactly when `δ ≡ 2 (mod 3)`.

## 4. Validation (`make test`, 20 tests)

* **Engine.**
  * Rediscovers the record solutions for k = 33, 42, 3, 165, 579, 795 and 906
    from narrow windows.
  * Matches a brute force for every `k ≡ ±3 (mod 9)` up to 100.
  * Every filter decision equals exact arithmetic on production-size
    candidates for k = 114, 390, 627 and 33.
  * Cube-root sets and factorizations are checked at production size for
    k = 114 and 390, including `δ` divisible by 2^25, 5^14, 7^12 and 13^10.
  * 2-adic rule: identical hits to the engine before the rule for all 55
    `k < 1000` with `k ≡ 2 (mod 4)`, `k ≡ ±3 (mod 9)` (`1 ≤ δ < 3·10^6`,
    `|c| ≤ 1000δ`, 143 representations); `make test` repeats this against
    `--no-filter` for k = 6, 42, 222, 438, 618.
  * Wheel: on production windows every deterministic counter equals the
    pre-wheel engine's (same `δ` with roots, roots, candidates, exact checks).
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
  * End to end, raw worker output for k = 42 becomes exactly 1 + 2 points, even when the same
    hit is given twice; a representation with a repeated component gives its two distinct points.
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
  At 0.223 µs (the development host's 0.293 µs divided by the 1.31 speed-up), the
  plan is 1,800 tasks of about one hour each covering `δ` in
  [185185185185185186, 185214218177221591). Per-task set-up
  (about 1–3 s) and a 2% audit (about 36 core-hours) come on top; keep them
  in the project's headroom.
* **Robustness:** tasks checkpoint every 2^24 `δ` (fsynced) and resume in
  place. A checkpoint records exactly the interval its directory searched.
  `audit_gap.py` re-runs a sample of returned chunks to catch faulty hosts;
  re-issue any that disagree.
* **Resources:** about 0.23–0.24 GB of memory and 1–3 s of set-up per task.
  `docker build .` builds the image and runs the tests during the build.

## 6. What a completed run proves

A completed, audited run proves that **(E) has no point of result 1 or 2
coming from a representation with `δ = |a+b|` in the covered range and
`3.847δ <= |c| <= 64δ`**. In particular it rules out every rational `d`
those points would give. It does not cover other representations. The odds
in §2 are heuristic: they rest on Heath-Brown's conjecture and
Booker–Sutherland's model.
