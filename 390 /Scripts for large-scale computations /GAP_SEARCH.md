# CE390 gap search: Booker–Sutherland's method on the region they skipped

**Goal.** Spend about 2,000 core-hours where they have the highest chance of
finding integers with `x^3 + y^3 + z^3 = 390`, outside everything already
searched.

**Short answer.** The best place we know of per core-hour is the slice of the
`(d, z)` plane, `d = |x+y|`, just above Booker and Sutherland's
`d_max = 10^19/54`, with `3.847 d <= |z| <= 64 d`. Under their own heuristic
model, 2,000 core-hours there with this code give about a **1 in 270,000**
chance of a solution for k = 390. The same hours give about **1 in 89,000**
for k = 627.

No method we know of does much better with 2,000 hours. A 1% chance for 390
would need about 7×10^6 core-hours; the region already searched cost
Booker and Sutherland a comparable scale per k. A completed run still
produces a new, exact exclusion region, and its chance is about 10^8 times
that of the d-first campaign it replaces.

## 1. Why the earlier d-first scripts were replaced

For a solution `A^3+B^3+C^3 = k` the d-first parameter is `d = (A+C)/(A+B)` in
lowest terms, with `g = gcd(A+B, A+C)` and height
`H = max(|A+B|,|A+C|)/g`. The record solutions for k = 33, 42, 3, 165, 579
and 906 all have `g = 1` and `H ~ 10^15 – 10^20`. For 795 the largest is
`g = 16`.

A height-ordered d-first search reaches `H ~ 10^6`. The components it can
find are of size about `H·g`. Booker and Sutherland already excluded every
solution with `min(|x|,|y|,|z|) <= 10^17`, so such a search would need
`g >= 10^11`. For random pair sums, `P(gcd >= G) ~ 6/(π² G)`, which puts the
expected yield near 10^-14. Bogdan Grechuk's objection is correct.

## 2. What has already been searched for k = 390

Booker and Sutherland (PNAS 2021, arXiv:2007.01209) work as follows. For a
solution with `|x| > |y| > |z|`:

```text
d = |x + y|,   0 < d < α|z|,   α = 2^(1/3) − 1 ≈ 0.25992,
z^3 ≡ k (mod d),   (x − y)^2 = (4(z^3 − K)/d − d^2)/3,   K = k·sign(z).
```

They ran:

* **Sept 2019:** `z_max = 10^17` with `d_max = α z_max`, over all eleven open
  k at that time. This is complete for `|z| <= 10^17`.
* **2020:** `z_max = 10^19` with `d_max = z_max/54`, over the eight k still
  open: 114, 390, 579, 627, 633, 732, 921 and 975. It found 579. The paper
  names 390 in this batch by elimination: it is one of the eight still open.

So **for `d > 10^19/54 = 1.852 × 10^17`, nothing has been searched for any
`z`.** No later search has been published: Wikipedia and a 2025 survey still
list 390 with no newer bounds. Before launching, it is still worth asking
Booker and Sutherland, or Charity Engine (who ran their 2020 search),
whether anything beyond the paper was run.

## 3. Where a solution is most likely per core-hour

Their model (paper §2.2) is that among solutions with a given `d`, the share
with `|z|/d >= R` is `c K(R)`, with `K(R) ~ R^(−1/2)` and `c ≈ 1.96084`, so
`c K(1/α) = 1`. Normalized with Heath-Brown's `e(B) = ρ log B`, this gives:

* **Solutions are log-uniform in `d`.** Each `d` carries `ρ/d` expected
  solutions over all `z`.
* **A band `|z| <= R d` keeps a share `1 − 1/√(αR)` of them.** So

```text
E(d in [D0, D1), |z| <= R d) = ρ (1 − 1/√(αR)) log(D1/D0).
```

Because about three quarters of the cost is a fixed cost per `d` (sieving,
early rejection, roots), the figure that matters is **yield per `d`**, and
that is `ρ(1 − 1/√(αR))/d`. It is largest for the smallest unsearched `d`,
which is exactly `d = 10^19/54 + 1`.

Extending their rectangle to `|z| > 10^19` for `d <= 1.852e17` is far worse.
Every one of those 1.85e17 values of `d` would have to be processed again,
which costs millions of core-hours even with their code, before any new `z`
is reached. (An earlier draft of this document claimed otherwise; that row
was wrong.)

`ρ_sol`, from their Table 1: **k = 390: 0.032935**; **k = 627: 0.129565**.

| k | R | µs per `d` (this host) | 1,800 h | 2,000 h |
| --- | --- | --- | --- | --- |
| 390 | 64 | 0.264 | 3.3e-6 (1 in 300,000) | 3.7e-6 (1 in 270,000) |
| 627 | 48 | 0.321 | 1.0e-5 (1 in 99,000) | 1.1e-5 (1 in 89,000) |

627 has 3.9× the density but costs about 1.2–1.4× more per `d`: more `d`
survive the early rejection. Per core-hour it is about 3× better. Calibrate
each k separately (`--calibrate --k 627`).

For scale: the whole slice `d in [1.852e17, 3.7e17)`, `|z| <= 64 d`, holds
`0.017` expected solutions for k = 390 and would take about 1.4×10^7
core-hours with this code. 2,000 hours covers about 1/7000 of it.

## 4. The algorithm (`src/gap_worker.cpp`)

For `k ≡ 3ε (mod 9)`, `ε = ±1`, every solution has `x ≡ y ≡ z ≡ ε (mod 3)`.
Hence `3 ∤ d` and `z ≡ d (mod 3)` for `z = |Z|`. Also `sign(Z) = +1` exactly
when `d ≡ ε (mod 3)`, matching their `s = ε(d/3)`. Put `K = k·sign(Z)` and
`Δ = (4(z^3 − K)/d − d^2)/3 = (x − y)^2`. For each `d` in the task:

1. **Factor `d`** with a segmented sieve over blocks of 2^16 values of `d`.
   Primes below 2^16 are applied directly; primes up to `√d_stop` sit in
   paged buckets from a free pool, which keeps memory bounded at about
   0.24 GB. The leftover cofactor is a prime.
2. **Reject early.** A prime `p ≡ 1 (mod 3)` dividing `d`, with `k` not a cube
   mod `p`, means there is no root. That flag is precomputed per prime, so no
   division is done for those `d`. Likewise `p | k` with
   `v_p(k) ≢ 0 (mod 3)` and `p^(v+1) | d` means no root. About 85% of `d`
   stop here.
3. **All cube roots of `K` mod `d`.**
   * `p ≡ 2 (mod 3)`: `K^((2p−1)/3)`.
   * `p ≡ 1 (mod 3)`: Adleman–Manders–Miller, with a one-exponentiation fast
     path when `p ≡ 4, 7 (mod 9)`.
   * Then Hensel lifting to `p^e`, and CRT.
4. **Fix `z` modulo `9d`, or `18d` for odd `d`.** `x ≡ y (mod 3)` gives
   `9 | Δ`, which depends only on `z mod 9d` (via `3dΔ mod 27d`). For odd `d`,
   `t = x − y` is odd, so `Δ ≡ 1 (mod 8)`, which depends only on `z mod 2`.
   Each root keeps at most one or two classes. This gives 4.5× fewer
   candidates than stepping by `3d`.
5. **Walk** those classes over `floor(3.847 d) <= z <= R d`. Since
   `3.847 < 1/α = 3.8473`, the band contains every admissible `z`: the `k`
   correction to `d < α|z|` is about 10^-30 relative.
6. **Filter** with 16 exact quadratic-residue tests of `Δ` mod 5 … 61, as
   constant-modulus code. Survivors, about 1 in 10^5 candidates, are decided
   with GMP.
7. **Verify.** Set `s = −sign(Z) d`, `x = (s + t)/2`, `y = (s − t)/2`, and
   re-check `x^3 + y^3 + Z^3 = k` exactly in C++, then again in Python.

Measured on the development host (one core, `d ≈ 1.85e17`):
* **k = 390:** 0.26 µs per `d` at `R = 64`.
* **k = 627:** 0.32 µs per `d` at `R = 48`.
* **Yield per core-second** is flat for `R` between 32 and 80.
* **Per task:** sieve set-up takes 1–3 s, and peak memory is 0.24 GB, which
  stays bounded across a full bucket cycle.

`(R + 18)·d` must fit in 64 bits, so `R <= 80` near `d = 1.85e17`.

## 5. Validation (`tests/test_gap.py`, run by `make test`)

* **Record solutions.** From ±25-wide `d` windows the worker rediscovers the
  known solutions for k = 33, 42, 3, 165, 579, 795 and 906. That includes
  k = 579, found by Booker–Sutherland in the same 2020 run that covered 390,
  and k = 3 at `|z|/d ≈ 4.4 × 10^6`. Excluding the window loses the hit;
  disabling every filter gives identical hits.
* **Brute force.** For every `k ≡ ±3 (mod 9)` up to 100, every solution with
  coordinates up to 2000 that lies in the searched region is found, and
  nothing else.
* **Filter verdicts.** For 12,000 production-size candidates, every residue
  decision equals the one computed from the exact integer `Δ`.
* **Arithmetic.**
  * Factorizations near the production start and near 2^58 are checked by
    product and primality.
  * Cube-root sets are checked by brute force for `d < 1500`, and by
    multiplicativity at production size, including `d` divisible by 2^25,
    5^14, 7^12 and 13^10.
* **Lifecycle and coverage.**
  * Plan, run, SIGTERM, resume and collect rediscover the k = 906 record
    with no gaps.
  * Re-running an original task in the directory where its continuation
    ran is refused, and leaves that directory untouched.
  * A continuation in the same directory produces no false gap.
  * The audit tool detects a chunk whose counters were altered by one.
* **Independent review.** A separate review re-checked roots, factorizations,
  the `z` walk and the filter verdicts on several million more `d` and
  100,000 more candidates (k = 390, 627, −390, odd and even `d`). It found
  no way to miss a solution in the region. Its findings on coverage
  accounting, durability and the figures in this document are fixed here.

## 6. Running it

```sh
make -j2 && make test
python3 gap_campaign.py --calibrate --k 390            # on the target CPU type; prints R and us/d
python3 gap_campaign.py --campaign-id ce390-gap --core-hours 1800 \
    --ratio-max 64 --us-per-d <measured> --task-hours 1 --output-dir gap-tasks --plan-only
python3 gap_campaign.py --campaign-id ce390-gap --core-hours 1800 \
    --ratio-max 64 --us-per-d <measured> --task-hours 1 --output-dir gap-tasks
# one task (locally, or on Charity Engine via the container):
python3 run_gap_task.py --task gap-tasks/tasks/ce390-gap-0000.json --output-dir gap-results/ce390-gap-0000
# afterwards:
python3 collect_gap.py --page gap-tasks/page.json --results gap-results --output-dir gap-collected
python3 audit_gap.py --page gap-tasks/page.json --results gap-results --fraction 0.02
```

* **Budget and k.** Use `--core-hours 2000` if all 2,000 hours go to 390.
  `--k 627` plans the same search for 627; calibrate it separately, since it
  costs more per `d`.
* **Task ranges.** Tasks cover consecutive, disjoint `d` ranges from
  `d_start = 185185185185185186`.
* **Interruption and coverage.** A task checkpoints every 2^24 values of `d`
  (fsynced). Re-running the same command in the same directory resumes it.
  A checkpoint records the interval its directory actually searched, and the
  collector credits only that interval.
* **Hardware audit.** Booker and Sutherland met detected hardware errors on
  their grid. `audit_gap.py` re-runs a random 2% of returned chunks and
  compares their deterministic counters; re-issue any task that disagrees.
* **Exit codes.** Partial tasks exit 0 by default; set `--partial-exit-code`
  if the grid should retry them. `collect_gap.py --require-complete` exits 2
  while gaps remain.

Charity Engine container: the image's default command runs
`python3 /app/run_gap_task.py --task /local/input/task.json --output-dir /local/output`
for a gap task.

## 7. What a run establishes, and what it does not

A completed and audited campaign proves that **no solution exists with
`d = |x+y|` in the covered range and `3.847 d <= |z| <= R d`**. That is a new,
exact exclusion region. It says nothing about other `d`, or about `|z|`
outside the band. The yield figures in §3 are heuristic: they rest on
Heath-Brown's conjecture and Booker–Sutherland's model, not on a theorem.

## 8. What would raise the odds

* **More speed.** Yield is linear in `d` covered. Booker–Sutherland's own
  implementation (cubic-reciprocity admissibility mod `27k`, auxiliary-prime
  sieving) may be several times faster per `d`. A rough comparison with their
  k = 33 benchmark suggests about 3×, but the regimes differ. If they share
  it, run their code on this region.
* **k = 627 instead of 390** gives about 3× the chance per core-hour, if any
  open k is acceptable.
* **More hours.** The chance is linear in hours at this scale.
