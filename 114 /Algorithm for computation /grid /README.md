# `grid/` — the programs that are shipped to the grid nodes

The mathematics and the choice of algorithms are described in [`../README.md`](../README.md)
(section *Searching for rational `d`*), the half-integer chart and the integral-radical
case in [`../HALF_INTEGER.md`](../HALF_INTEGER.md); the integer-chart facts the programs
rely on are proved in [`../RequestProject/Algorithm.lean`](../RequestProject/Algorithm.lean).

Two **charts** are supported throughout: the *integer chart* (`x` an integer — Aristotle's
original setting, the default) and the *half chart* (`x = X/2` with `X` odd, flag `--half`).
Two **targets**: *rational radical* (any rational `y = √((x+6n)² + (36n³−19)/x)`) and
*integral radical* (`y` an integer, resp. `y = Y/2` with `Y` odd — exactly the solutions
that give `114 = A³+B³+C³` with `A = −x+y`, `B = −x−y`, `C = 2x+6n`).

| file | what it is |
|---|---|
| `dsweep.c` | Algorithm A, the d‑first sweep over the certificate `G` (`U = 2dx²`, or `V = dX²` with `--half`). Work unit = an interval of `\|G\|`. `--integral` restricts to `x \| U` (resp. `X \| V`); in the half chart that is the default and `--rational-sqrt` widens it. |
| `dsmooth.c` | Algorithm A′, the same sweep restricted to `B`‑smooth certificates; reaches twenty to thirty digits. Same flags. Work unit = one shard of a `(lo, hi, B)` box. |
| `xroots.c` | **Algorithm D (new)**, integral radicals in either chart: for each `X`, `n` runs only over the cube-root classes `36n³ ≡ 19 (mod \|X\|)`, with the 2‑/3‑adic conditions folded in and a wheel of quadratic-residue tests. Work unit = a range of `\|X\|` × a window of `n` (128‑bit). Complete for its box. |
| `xscan.c` | Algorithm B, the per‑`x` scan (any rational radical). `--half` scans `X = 6u+5`; `--xneg`/`--nneg` cover negative `x`/`n` (the original covered only `x > 0`, `n ≥ 0`). |
| `xcurve.gp` | Algorithm C, the Mordell‑curve phase, for PARI/GP; `XCURVE_HALF=1` for the half chart (`V² = Z³ − 432X³(X³+456)`). |
| `xcurve.py` | Pure‑Python reference implementation of Algorithm C and its self test (both charts). |
| `filter.h` | The one‑sided modular pre‑filter shared by `dsweep` and `dsmooth`, for either chart's cubic. |
| `local.h` | The 2‑adic and 3‑adic necessary conditions for integral radicals, computed at start‑up for the given `K` (for `K = 19` they contain `x ≡ 7 (mod 12)`, `n ≡ 0 (mod 3)`, `U ≡ 5, 11 (mod 12)`, and `X ≡ 5, 11`, `V ≡ 1, 10 (mod 12)` in the half chart). |
| `verify.py` | Exact verifier: turns any reported line (`HIT`, `HHIT`, `CAND`, `HCAND`, `ICAND`) into a certified rational `d`, prints `y`, and for an integral radical the triple `(A, B, C)` and `A³+B³+C³`. `--triple A B C` lists the three solutions attached to a representation. |
| `validate.py` | End‑to‑end validation on equations `36n³ − K` with known integral solutions (several `K`, and the Booker–Sutherland solutions of 42 and 906). |
| `selftest.sh` | Runs every self test (about two minutes). |
| `make_jobs.py` | Work‑unit generator: digit bands for the rational target (`--chart int\|half\|both`), or `--target integral` for `xroots` units. |
| `run_task.sh` | Runs one manifest line on a node and writes `<id>.out` / `<id>.done`. |
| `Makefile` | `make`, `make test`, `make validate`. |

Every program takes `--K k` (default 19): it replaces `36n³ − 19` by `36n³ − k`, i.e. 114 by
`6k`, which is how the integral-radical code is validated on equations whose solutions are
known.

## Build

```sh
make            # or:
cc -O3 -o dsweep  dsweep.c  -lm
cc -O3 -o dsmooth dsmooth.c -lm -lquadmath
cc -O3 -o xscan   xscan.c   -lm
cc -O3 -o xroots  xroots.c  -lm
```

No libraries beyond libm (and libquadmath for `dsmooth`); 128‑bit integers require gcc or
clang on a 64‑bit host.  `xcurve.gp` needs PARI/GP ≥ 2.13 (if `gp` is absent, `run_task.sh`
falls back to `xcurve.py`).

## Self tests (run these before shipping a binary)

```sh
./selftest.sh
```

which checks: `dsweep --general` and `dsmooth --test` re-find the three smallest known `d`
(integer chart); `dsweep --half --rational-sqrt` and `dsmooth --half --rational-sqrt` re-find
`d = −142/4913`, `−9671/625` (half chart); the residue arithmetic of `xscan` in both charts
and signs; the cube roots of `xroots` modulo every `M < 12000` against brute force; the
Mordell correspondence of `xcurve.py` on 14 solutions (both charts); and `validate.py
--quick` (integral radicals against a brute-force oracle, plus 42 and 906).

## Running a work unit

```sh
python3 make_jobs.py --band-lo 10 --band-hi 20 --hours 1.5 --out jobs/              # Aristotle's plan
python3 make_jobs.py --chart half --band-lo 10 --band-hi 20 --out jobs/             # same, half chart
python3 make_jobs.py --target integral --x-max 1e6 --n-lo 1.667e18 --n-hi 1.667e19 --out jobs/
head -2 jobs/integral_both.manifest
#   000000 xroots --X0 1 --X1 10 --n0 1667000000000000000 --n1 1667335027167755946
#   000001 xroots --half --X0 1 --X1 10 --n0 1667000000000000000 --n1 1667031269201508804
./run_task.sh "$(head -1 jobs/integral_both.manifest)" results/
python3 verify.py results/000000.out
```

A unit reads nothing but its command line and writes one output file, so units can be run
in any order, duplicated for validation, or re‑issued after a timeout.  The last line of
every output file is `DONE …` and records the chart, the target, the congruence family and
`K`; a file without it is an incomplete unit.  Integral manifests are written epoch by
epoch, so any prefix of one covers a complete box (all `|X| < x-max`, the first slices of
`n`).

## Measured throughput (one core of the machine used for this session, gcc ‑O3)

| program | rate |
|---|---|
| `dsweep`, integer chart, family, `\|U\| ~ 10⁹` | 2.5·10⁹ values of `\|U\|` per core‑hour (1.5× the original program on the same machine: a prime cofactor left by the sieve is no longer re-tested by Miller–Rabin) |
| `dsweep --integral` / `--half` (integral), `\|G\| ~ 10⁹` | 3.6·10⁹ / 3.4·10⁹ values of `\|G\|` per core‑hour |
| `dsweep --half --rational-sqrt`, `\|V\| ~ 10⁸` | 2.5·10⁸ values of `\|V\|` per core‑hour (no family restriction exists here) |
| `dsmooth`, `B = 60`, `\|U\| ∈ [10²⁰, 10²¹)`, one shard of 20 000 | unchanged: 4541 certificates, 3.1·10⁸ pairs in 37 s |
| `xscan`, one `x` | 4.2·10¹¹ values of `m` per core‑hour (integer chart), 1.5·10¹¹ (half chart, `X = 5`) |
| `xroots`, `n ≈ 2·10¹⁸`, window 10¹⁰ | half chart: `\|X\| < 10³` in 5.2 s, `[10³, 10⁵)` in 5.6 s, `[10⁵, 10⁶)` in 10.5 s; integer chart: 0.5 s, 2.2 s, 5.2 s |

(This machine is about 1.6× slower than the one Aristotle measured on: the original
`dsweep` took 4.2 s here for what it took 2.5 s there.)  `make_jobs.py` uses these numbers to
size the units.  Re-measure on the grid hardware with one pilot unit (`xroots` prints `secs=`
in its `DONE` line) and rescale.

## Limits of the implementations

* `dsweep` requires `|G| < 10¹⁸` (`G²` must fit in a signed 128‑bit integer).  Since
  `|n| ≤ |G|`, it cannot produce more than 18‑digit `n`; for an integral radical with
  `K = 19` it cannot produce anything at all (such a certificate has ≥ 25 digits,
  `HALF_INTEGER.md` §5) — `--integral` is there for completeness and validation.
* `dsmooth` needs `X` and `c = G²/X` to fit in 128 bits, so for very large `G` the most
  lopsided divisor splittings are not tried.  It now honours `--B` for every `B` (the
  original kept only the first 512 primes, i.e. silently used `B ≤ 3671`).
* `xscan` requires `m < 2⁶⁴`.
* `xroots` requires `|X| < 2⁶²` and `|n| < 2¹²⁰`; its per‑`X` overhead (≈ 10–20 µs) makes it
  the tool for small and moderate `|X|` with long windows of `n`, not for sweeping `|X|` into
  the 10¹⁵–10¹⁷ range.
* `xcurve` has no size limit, but `xcurve.gp` only finds generators that `ellratpoints` sees,
  and both scripts scan positive `x` only.  `xcurve.gp` now skips non-integral points
  explicitly (a rational point whose denominator shares a factor with `36x` used to raise a
  PARI error) and its `XCURVE_KMAX` default really is 8 (an unset variable used to give 0).
* Every hit must pass `verify.py` before being believed: the search programs use floating
  point and modular filters, which are one‑sided (they never reject a genuine solution, but
  they may in principle pass a spurious one).
