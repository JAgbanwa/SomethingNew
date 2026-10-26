# Validation record: d-first half-chart engine

All runs: `dthue_worker` 1.0.0 built from `src/dthue_worker.cpp` with
`g++ -O3 -std=c++17` (GMP 6.3), one core of a shared cloud sandbox, 26 October 2026.
`g_max_digits = 100`, so every statement below covers `1 <= |g| <= 10^100`,
that is `|x| <= q*10^100/2` with no bound on `n`, unless it says "unbounded".

## k = 390 (m = 65)

| Run | `d` covered | Admissible `d` solved | Half-chart points | Files |
| --- | --- | --- | --- | --- |
| campaign task via `run_d_task.py` | every `d` with height `max(|p|,q) <= 20,000` | 14,168,321 | **none** | `k390-h1-20000/` |
| PARI `thue()`, unconditional, **unbounded** | every admissible `d` with height <= 120 | 789 (420 + 369) | **none** | `pari-certify-k390-h90.txt`, `pari-certify-k390-h91-120.txt` |

The 20,000 run checked 800,020,000 pairs `(p, q)` in 3,166 s (3.96 µs per
pair, 223 µs per admissible `d`). It found no solution at all of any of the
Thue equations (`thue_solutions = 0`, so `other_chart = other_branch = 0`),
tested 2,763,493,506 certified convergents, and needed no precision
refinement (`refinements = 0`). `collect_d.py` reports full coverage
`[1, 20001)` and no gaps. The worker binary (sha256 `1573188e…`) is
reproduced bit for bit by building the committed `src/dthue_worker.cpp` with
the same compiler and flags.

## Known-answer test, k = 6 (m = 1)

`k6-h1-449/` is the same campaign code for m = 1, heights 1–449. Its 7
verified hits are the single point of `2^3-1-1` (both of its pairings give the
same point) and both half-chart pairings of each of `65^3-58^3-43^3`,
`236^3-235^3-55^3` and `644^3-637^3-205^3`:
`d = 1, 22/7, -22/101, 1/181, 181, 7/439, 439/7`. They include the target
points `(n, x) = (-6, 101/2), (-9, -181/2), (-33, -439/2)`.

## Independent cross-checks

* `pari-crosscheck.txt`: `tools/pari_compare.py` on the output of
  `tools/pari_crosscheck.gp`. 1,934 Thue equations, 679 solutions (10 beyond
  the exhaustive range, so found only via convergents), **0 mismatches**
  against PARI's unconditional `thue()`.
* The admissible-`d` counts up to heights 90 (420) and 120 (789) agree between
  `dfirst_common.admissible` and the PARI script's own `admissible()`, and the
  worker's per-shell counts agree with `dfirst_common` (tests).
* `make test`: 228 tests pass (217 existing + 11 in `tests/test_dfirst.py`).

`benchmark.json` holds the throughput measurements used in D_FIRST.md
section 6.
