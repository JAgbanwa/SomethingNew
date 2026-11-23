# EJ at large heights: measured bands, honest coverage, and cost

**The exact lattice backend was benchmarked at heights `10^15` and `10^16`.
A complete shell at those heights is not a practical single-machine run of
this reference implementation.** Its arithmetic accepts arbitrary-precision
heights, subject to the mathematical shell conditions. Large numeric support
and affordable full-region coverage are different properties. The measurements
below exercise the actual native search at the two stated heights.

This EJ implementation provides selected ratio-band searches, an independent
method, and precise coverage accounting. The campaign also includes a separate
native Booker--Sutherland backend; the measurements here characterize EJ and
establish no relative speed between the two implementations. Planning a large
EJ region does not establish that completing it is economical.

## What a large-height band means

The canonical magnitude variables are `0<a<=b<c`; signed cube triples satisfy
`a^3+b^3-c^3=+/-375`. A shell/band task covers

\[
H\le c<2H,\qquad L\le (5H)a/c<R.
\]

Only the global upper endpoint `R=4H` is included. Thus `H=10^15` means
largest cube-coordinate magnitudes between `10^15` and `2*10^15`, even if a
task's ratio-index width `R-L` is only `1000`. It is not a coordinate bound of
`1000`.

A width `W` corresponds to ratio width `W/(5H)`. At `H=10^15`, a band of
width `100000` is only `2*10^-11` wide in `a/c`, but spans the entire shell in
`c`. For each fixed `c`, it covers roughly `W/5` to `2W/5` possible integer
values of `a` before the curve and arithmetic conditions are used. The lattice
method processes this thin geometric region without iterating over all `c`.

The lower ratio index is the exact integer

\[
L_{\min}(H)=
\left\lfloor\frac52\left\lceil
\sqrt[3]{3H^2-3H+1-375}\right\rceil\right\rfloor.
\]

The full shell requires all indices from this lower bound to `4H`. The proof
and boundary conventions are in [EJ_METHOD.md](EJ_METHOD.md).

## Actual calibration at `10^15` and `10^16`

The machine used an AMD EPYC 9V45 processor, GCC 14.2.0, GMP 6.3.0, and Python
3.12.14. These are single-process local measurements from 23 November 2026.
Compiler flags were `-O3 -std=c++17`. Complete machine metadata, source and
binary fingerprints, exact band endpoints, terminal records, and timings are
in [large_ej_bench.json](large_ej_bench.json).

Each row searched a **complete 1000-index band**, with primitive filtering
enabled. The middle band begins at `2H`, so its ratio is near `0.4`; the upper
band ends at `4H`, so its ratio is near `0.8`. Times include native process
launch and Python validation, but exclude starting the surrounding Python
interpreter. They are one-run calibration observations, not averaged benchmark
scores. Each process group had a five-second hard limit. All eighteen samples
completed successfully; none needed that limit, and none reported a hit.

| Height `H` | Band | Tile scale | Completed tiles | Covered lattice points | Seconds |
|---:|:---|---:|---:|---:|---:|
| `10^15` | Middle | `11/2` | 36 | 887 | 0.130 |
| `10^15` | Middle | `55` | 4 | 78,251 | 0.151 |
| `10^15` | Middle | `550` | 1 | 1,080,103 | 0.401 |
| `10^15` | Upper | `11/2` | 67 | 2,184 | 0.172 |
| `10^15` | Upper | `55` | 7 | 150,106 | 0.268 |
| `10^15` | Upper | `550` | 1 | 6,395,800 | 2.301 |
| `10^16` | Middle | `11/2` | 36 | 827 | 0.125 |
| `10^16` | Middle | `55` | 4 | 78,322 | 0.202 |
| `10^16` | Middle | `550` | 1 | 1,080,131 | 0.699 |
| `10^16` | Upper | `11/2` | 67 | 1,417 | 0.190 |
| `10^16` | Upper | `55` | 7 | 149,807 | 0.357 |
| `10^16` | Upper | `550` | 1 | 6,396,148 | 2.481 |

At each height, a 1000-index band beginning at `L_min(H)` also completed for
all three scales. Each needed one tile, contained zero lattice points, and
took about `0.005`--`0.008` seconds. Those unusually empty lower-bound bands
are not a representative throughput estimate for the rest of the shell.

The lattice-point counter includes intervals handled by exact polynomial root
isolation. It does not mean every point incurred an individual cube evaluation.
Changing tile scale changes the enclosing regions, so these counters need not
agree between scales; exact hits and region coverage must agree. Repeating the
same band at three scales supplies three measurements, not three times the
mathematical coverage.

## Why much wider tiles did not make this faster

The adaptive native step is approximately

\[
\Delta I=\left\lfloor\sqrt[3]{125S^3/C}\right\rfloor,
\qquad C=2t/(1-t^3)^{5/3},
\]

where `S` is `tile_scale` and `t` is the tile's right-hand ratio. The actual
code uses exact rational lower bounds and integer roots. At the default
`S=11/2`, this gives about 28 index units per tile near `t=0.4` and 15 near
`t=0.8`, almost independently of `H`. This explains the 36 and 67 tiles in
the measured width-1000 bands.

Increasing the scale is mathematically safe: the enclosure is recomputed for
the entire wider tile. It reduces the number of LLL reductions, but the
curvature contribution to the transverse enclosure grows quadratically with
tile width. Consequently the enclosure volume grows roughly cubically with
width. Across a fixed ratio interval this can increase candidate work roughly
quadratically. The measurements show this tradeoff directly: scales `55` and
`550` created much larger candidate enclosures and were slower in these
middle and upper bands. They are not a shortcut to finishing a huge shell.

Elkies gives a **heuristic** work estimate
`(N + delta*N^3) * log(N)^O(1)` for enumerating points of height at most `N`
within distance `delta` of a curve. Taking `delta` on the scale `N^-2` gives
near-linear heuristic work. A tile width of order `1/H` and order `H` tiles
is consistent with that estimate. It is not a rigorous worst-case runtime
guarantee for this worker.

Elsenhans and Jahnel report using 128-bit fixed-point arithmetic for most
computations, reusing reduced bases to perform LLL incrementally, and searching
targets below 1000 together. Booker also explicitly describes Elkies' method
as suitable for finding many targets simultaneously. This reference
implementation uses arbitrary-precision rational enclosures and Gram--Schmidt
arithmetic throughout. It does not claim the historical implementation's
throughput. The geometric reduction remains substantial relative to a
quadratic coordinate scan, but linear work at `H=10^15` is still enormous.

References for these methodological comparisons:

- [Elkies, sections 1 and 2.1](https://arxiv.org/abs/math/0005139).
- [Elsenhans--Jahnel, implementation and search details](https://wwwuser.gwdguser.de/~jjahnel/Arbeiten/elk_ants6c.pdf).
- [Booker, introduction and comparison of search methods](https://arxiv.org/abs/1903.04284).

## Full-shell cost: a warning from the measured arithmetic

The middle and upper default-scale samples processed about 5,300--8,000 ratio
index units per second. Merely multiplying the **local measured time per
index** by the entire shell width gives the following illustrative figures:

| Shell height | Full ratio-index width | Linear extrapolation from its two local samples |
|---:|---:|:---|
| `10^15` | 3,999,963,943,760,740 | About 16,500--21,800 single-core years |
| `10^16` | 39,999,832,641,762,478 | About 159,000--241,000 single-core years |

These are **not full-shell runtime predictions or bounds**. Work varies with
ratio, arithmetic coincidences, hardware, process overhead, and future
optimizations; only three small bands at each height were measured. Their
purpose is to make the scale of the present reference code explicit. A
complete large shell is not recommended as a single-machine run.

A width-100000 band would take roughly 13--19 seconds if the measured middle
and upper rates persisted. That figure is a local linear extrapolation; no
width-100000 band was timed for this calibration. A 1000-tile attempt budget
would ordinarily cover only part of such a band near these ratios, and must
leave a partial checkpoint rather than claim the band is finished. Exact
`next_index` values determine subsequent attempts.

## Compact plans for very large regions

The shell sequence

\[
H=10^{15},\;2\cdot10^{15},\;4\cdot10^{15},\;8\cdot10^{15}
\]

describes exactly the cube-coordinate region

\[
10^{15}\le\max(|u|,|v|,|w|)<1.6\cdot10^{16}.
\]

This is a **chosen planned region**, not a claim that it is an unsearched
frontier, nor that all smaller heights have been covered by this campaign.
Writing its manifest searches no points and completes no interval.

For a band width `W`, let `N_H=ceil((4H-L_min(H))/W)`. Logical shard `j`,
where `0<=j<N_H`, can be calculated directly as

\[
L_j=L_{\min}(H)+jW,\qquad R_j=\min(L_j+W,4H).
\]

These bands partition the entire shell with the endpoint convention above.
The descriptor needs only `H`, `W`, and the relevant target/options. Jobs are
materialized lazily as they are requested; a plan does **not** require one
file per possible job.

For `W=100000`, the logical counts are:

| `H` | `L_min(H)` | Logical shards |
|---:|---:|---:|
| `10^15` | 36,056,239,260 | 39,999,639,438 |
| `2*10^15` | 57,235,712,130 | 79,999,427,643 |
| `4*10^15` | 90,856,029,642 | 159,999,091,440 |
| `8*10^15` | 144,224,957,032 | 319,998,557,751 |
| **Total** | | **599,996,716,272** |

The manifest is compact; the underlying work is still that large. These
counts make no throughput promise. Request selected bands for actual work,
retain verified completion/partial records, and distinguish the union of
completed intervals from the much larger planned scope. Parallel workers can
run disjoint bands, but a missing or partial job leaves a genuine coverage gap.

To reproduce a single measured native band without requesting a full shell:

```sh
./build/ej_worker --height 1000000000000000 \
  --index-start 2000000000000000 --index-stop 2000000000001000 \
  --target 375 --tile-scale 11/2 --max-tiles 256 --progress-every 0
```

For validated application use, call the main campaign/CLI interface or
`elkies_jahnel.iter_shell`; the direct command above shows the exact native
measurement region. Every candidate still needs Algorithm II's common
original-equation verifier before it is an accepted solution.
