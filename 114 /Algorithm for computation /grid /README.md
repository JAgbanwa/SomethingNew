# `grid/` — the programs that are shipped to the grid nodes

The mathematics and the choice of algorithms are described in
[`../ALGORITHMS.md`](../ALGORITHMS.md); the facts the programs rely on are proved in
[`../RequestProject/Algorithm.lean`](../RequestProject/Algorithm.lean).

| file | what it is |
|---|---|
| `dsweep.c` | Algorithm A, the d‑first sweep over the certificate `U = 2dx²`. Work unit = an interval of `|U|`. |
| `dsmooth.c` | Algorithm A′, the same sweep restricted to `B`‑smooth certificates `U`; reaches twenty to thirty digits. Work unit = one shard of a `(lo, hi, B)` box. |
| `filter.h` | The one‑sided modular pre‑filter shared by `dsweep` and `dsmooth`. |
| `xscan.c` | Algorithm B, the per‑`x` scan. Work unit = a block of `u` (`x = 12u+7`) × a window of `m` (`n = 3m`). |
| `xcurve.gp` | Algorithm C, the Mordell‑curve phase, for PARI/GP. Work unit = a block of `u`. |
| `xcurve.py` | Pure‑Python reference implementation of Algorithm C (correspondence, group law, point search) and its self test. |
| `verify.py` | Exact verifier: turns a reported hit into a certified rational `d`, or rejects it. |
| `make_jobs.py` | Work‑unit generator for a digit band (writes a manifest). |
| `run_task.sh` | Runs one manifest line on a node and writes `<id>.out` / `<id>.done`. |

## Build

```sh
cc -O3 -o dsweep dsweep.c -lm
cc -O3 -o xscan  xscan.c  -lm
cc -O3 -o dsmooth dsmooth.c -lm -lquadmath
```

No libraries beyond libm; 128‑bit integers require gcc or clang on a 64‑bit host.
`xcurve.gp` needs PARI/GP ≥ 2.13 (if `gp` is absent, `run_task.sh` falls back to
`xcurve.py`).  Memory footprint: `dsweep` ≈ 40 MB, `xscan` ≈ 1 MB, `xcurve` ≈ 500 MB as
configured (`parisize`).

## Self tests (run these before shipping a binary)

```sh
./dsweep --ulo 2 --uhi 20000 --general | ./verify.py /dev/stdin   # finds the three
                                                                  # smallest known d
./xscan --selftest                                                # residue arithmetic +
                                                                  # "no square is rejected"
./dsmooth --lo 2 --hi 20000 --B 20000 --test | ./verify.py /dev/stdin
                                                                  # same five certificates,
                                                                  # independent code path
./xcurve.py --selftest                                            # Mordell correspondence
                                                                  # on all 11 known solutions
```

## Running a work unit

```sh
python3 make_jobs.py --band-lo 10 --band-hi 20 --hours 1.5 --out jobs/
head -1 jobs/band10_20.manifest
#   000000 dsweep --ulo 3000000000 --uhi 5280719686
./run_task.sh "$(head -1 jobs/band10_20.manifest)" results/
python3 verify.py results/000000.out
```

A unit reads nothing but its command line and writes one output file, so units can be run
in any order, duplicated for validation, or re‑issued after a timeout.  The last line of
every output file is `DONE …`; a file without it is an incomplete unit.

## Measured throughput (one core, gcc ‑O3)

| program | rate |
|---|---|
| `dsweep`, `\|U\| ~ 10⁹` | 2.4 × 10⁹ values of `\|U\|` per core‑hour |
| `dsweep`, `\|U\| ~ 10¹²` | 1.9 × 10⁹ per core‑hour |
| `dsweep`, `\|U\| ~ 10¹⁴` | 1.6 × 10⁹ per core‑hour |
| `dsmooth` | 2.5 × 10⁹ `(U,x)` pairs per core‑hour, at any size of `U` |
| `xscan` | 5.4 × 10¹¹ values of `m` per core‑hour and per `x` |

`make_jobs.py` uses these numbers to size the units for the requested 1–2 h per task.

## Limits of the implementations

* `dsweep` requires `|U| < 10¹⁸` (then `U²` still fits in a signed 128‑bit integer). Since
  `|n| ≤ |U|` is a theorem, it cannot in any case produce more than 18‑digit `n`.
* `xscan` requires `m < 2⁶⁴`.
* `dsmooth` needs `x` and `c = U²/x` to fit in 128 bits (`|x| ≤ 8.5·10³⁷`), so for very
  large `U` the most lopsided divisor splittings are not tried.
* `xcurve` has no size limit; this is the unit type for the 20‑digit bands and beyond.
* Every hit must pass `verify.py` before being believed: the search programs deliberately
  use floating point and modular filters, which are one‑sided (they never reject a genuine
  solution, but they may in principle pass a spurious one).
