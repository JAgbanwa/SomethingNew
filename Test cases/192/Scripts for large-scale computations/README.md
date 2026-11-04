# CE192: rational-d search for 36n³ − 32 (test case)

**Target.** Find rational `d` such that

```text
36n^3 - 32 = -2*d*x^2*( -(x+6n) + s ),
s = sqrt( (x+6n)^2 + (36n^3 - 32)/x )
```

has a point satisfying **either** acceptable result:

1. **Integer chart:** `n, x` integers and `s` an integer.
2. **Half chart:** `n` an integer, `x = X/2` and `s = Y/2` with `X, Y` odd.

Both are searched in the same pass and every hit is labelled with its chart.
Both signs of `n`, `x` and `d` are covered.

This is a **test case**: the equation is the `k = 192` member of the same
family as 390 and 627, and 192 has known representations
(`4^3+4^3+4^3`, `16^3+16^3+(-20)^3`), so the pipeline has answers it must find.
It does: see [Local pilot](#local-pilot-already-run).

## How the search works (one paragraph)

With `S = 6n` the left side is `(S^3 - 192)/6`. Every point determines
`d = -(x+s+6n)/(2x)` uniquely, and for `d = p/q` in lowest terms the
points with that `d` are **exactly** the integer solutions `(S, g)` of

```text
S^3 - 6pq S g^2 + 3pq(p+q) g^3 = 192,      x = -q g/2,   s = (2p+q) g/2 - S >= 0,
```

with `q g` even for the integer chart and `q g` odd for the half chart. The
engine therefore enumerates `d` itself, in increasing height
`H(d) = max(|p|, q)`, discards `d` that provably cannot work, and solves one
Thue equation per surviving `d`: all solutions with `1 <= |g| <= 10^100`
(non-primitive ones included, since `192 = 4^3 * 3` is not cube-free), using
exact GMP arithmetic and certified continued fractions. There is no
`(n, x)` rectangle. `n` is automatically an integer (in fact `n = 2 (mod 3)`).
Proofs: [DERIVATION.md](DERIVATION.md).

## Differences from the 627 scripts

The code is the 627 pipeline with the constant changed and the following
consequences handled:

| | 627 | 192 |
| --- | --- | --- |
| `S` | `6n+3` (odd) | `6n` (even); worker requires even `K = +-3 (mod 9)` |
| forced residue | `n = 1 (mod 3)` | `n = 2 (mod 3)` |
| cube-free `K` | yes | no: `e^3 | 192` for `e = 1, 2, 4`; CF path tests `192/e^3` |
| local tables | mod 11, 19 | none (no prime `>= 5` divides 192; none found mod 27 or mod `2^7`) |
| charts of a representation | 1 or 3 odd components | 0 or 2 odd; all-even ones give integer chart only |
| test `K` | 3, 15, 21, 57 | 6, 12, 24, 66, 120 and 192 itself |

## Files

| File | Role |
| --- | --- |
| `src/thue192_worker.cpp` | Native GMP worker: height shells of `d`, filters, Thue solver, exact certificates |
| `make_campaign.py` | Writes disjoint height-range task files and `page.json` (budget planning) |
| `run_task.py` | Restartable task runner: per-shell checkpoint, SIGTERM-safe, continuation file, re-verifies hits |
| `collect.py` | Merges returned outputs: coverage, gaps, verified hit list, distinct `d` values |
| `verify_hits.py` | Independent exact re-verification of any `hits.jsonl` |
| `common192.py` | Independent Python implementation of filters, verifier, task schema |
| `tools/certify_d.gp` | PARI/GP: unconditional, **unbounded** certification of individual `d` |
| `tests/test_192.py` | Known-answer, brute-force, PARI cross-check and lifecycle tests |
| `Dockerfile`, `container_entrypoint.sh` | Charity Engine container |
| `examples/pilot/` | The task files of the local pilot |
| `validation/` | Pilot report, collector summary, verified hits |

## Build and test

Needs a C++17 compiler, GNU Make, GMP (`libgmp-dev`) and Python 3.9+.
PARI/GP (`pari-gp`) is optional; it enables the PARI cross-check test.

```sh
make
make test
```

The tests run the identical code at `k = 6, 12, 24, 66, 120` and at
`k = 192`, and require the worker to recover **every** `d` predicted from the
known representations, in both charts (the half chart is exercised by
`k = 6, 12, 66`, whose representations have two odd components), through both
the small-`g` and the continued-fraction code paths. At `k = 192` they
require exactly `d = 1, -1/8, -8`. They also check against an independent
`(n, x)` brute force of the original equation, check the raw Thue solver
against PARI's unconditional `thue()`, and run an interrupt/resume/collect
cycle. All 11 tests pass.

## Plan a campaign

Cost model: shells `1..H` contain `2H^2 + H` raw pairs `(p, q)`. Measure the
rate on the target CPU first (one core, about a minute):

```sh
./bin/thue192_worker --h-start 20000 --h-stop 20200 \
  | python3 -c "import sys,json; r=[json.loads(l) for l in sys.stdin if '\"shell\"' in l]; \
print(sum(x['seconds'] for x in r)/sum(x['pairs'] for x in r)*1e6, 'us/pair')"
```

The local pilot measured **8.5 us/pair** (two tasks in parallel on a shared
two-core VM; more `d` survive the filter than for 627, 3.8 % against 2.6 %).
The generator defaults to 9 us/pair; pass your measured value.

| `h_stop` | raw pairs | core-hours at 6 us | at 9 us |
| ---: | ---: | ---: | ---: |
| 50,000 | 5.0e9 | 8 | 13 |
| 100,000 | 2.0e10 | 33 | 50 |
| 200,000 | 8.0e10 | 133 | 200 |
| 400,000 | 3.2e11 | 533 | 800 |

Either fix the height range:

```sh
python3 make_campaign.py --campaign-id ce192-h100k --h-stop 100000 \
  --us-per-pair 9 --task-hours 1 --output-dir ce192-tasks
```

or fix the core-hours and let it derive the largest height that fits:

```sh
python3 make_campaign.py --campaign-id ce192-budget --core-hours <HOURS> \
  --us-per-pair <MEASURED> --task-hours 1 --output-dir ce192-tasks --plan-only
```

Drop `--plan-only` to write `ce192-tasks/tasks/*.json` and
`ce192-tasks/page.json`. Generation does not start or submit anything.
`--deadline-seconds` writes a per-attempt time limit into every task; the
worker then stops cleanly after the shell in progress and the runner writes a
continuation task.

## Run a task (locally or on Charity Engine)

```sh
python3 run_task.py --task ce192-tasks/tasks/ce192-h100k-000.json --output-dir results/ce192-h100k-000
```

Container (CE layout: task staged at `/local/input/task.json`):

```sh
docker build -t ce192-dfirst:1.0.0 .
docker run --rm -v "$PWD/in:/local/input" -v "$PWD/out:/local/output" ce192-dfirst:1.0.0
# equivalent explicit command inside the image:
python3 /app/run_task.py --task /local/input/task.json --output-dir /local/output
```

The image build compiles the worker and runs the test suite; a failing test
fails the build.

Output directory: `status.json` (`complete`, `partial` or `error`),
`checkpoint.json` (next height), `hits.jsonl` (verified hits), `shells.jsonl`
(per-shell counters), `run.log`, `worker.stderr.log`, and
`continuation.task.json` when shells remain. Re-running with the same output
directory resumes after the last finished shell; SIGTERM loses at most the
shell in progress.

A hit is printed as one JSON line, for example (from the pilot):

```json
{"type":"hit","chart":"integer","source":"small_g","k":"192","d_num":"-8","d_den":"1","g":"-4","n":"2",
 "x_num":"2","x_den":"1","s_num":"18","s_den":"1","cube_a":"16","cube_b":"-20","cube_c":"16"}
```

## Collect and verify

```sh
python3 collect.py --results results/ --page ce192-tasks/page.json --output-dir collected
python3 verify_hits.py collected/hits.jsonl
cat collected/d_values.txt        # one line per d: chart, n, x, s, cube components
```

`collected/summary.json` lists covered heights and any **gaps** against the
page, which must be re-issued (use each directory's `continuation.task.json`).

To certify a particular `d` with no bound on `g`:

```sh
gp -q tools/certify_d.gp
? certify(-8, 1)          \\ k = 192; certify(p, q, K) for a test value
%1 = [["integer", -8, 2, 2, 18, [16, -20, 16]]]
```

## What a completed run establishes

Every point, in either chart, with `d` in the processed height range and
`1 <= |g| <= 10^g_max_digits` (so `|x| <= q * 10^100 / 2`). It does not say
anything about larger `g` for those `d`, nor about `d` of larger height.

That limit is real for 192: the Booker-Sutherland representation of 3,
scaled by 4, gives three further integer-chart `d` (all with `n = -315143590036293214`,
`g = +-4`), checked exactly against the original equation:

```text
d = -569464105728509053688/570409536607016820541   x = 1140819073214033641082   s = 1138928211240220332954
d =  108398887211/569464105728509053688            x = -1138928211457018107376  s = 1140819073430831415504
d =  569464105728509053688/108398887211            x = -216797774422            s = 2279747284671051748458
```

Their heights (~5.7*10^20) are far beyond any height-ordered sweep, so a
campaign of any feasible size will not reach them.

## Local pilot already run

Heights `1 <= H < 4000` at `k = 192` (`|g| <= 10^100`): **3 hits, the
predicted `d = 1, -1/8, -8`**, all integer chart, `n = 2`; no half-chart
point. Details: [validation/pilot-h4000.md](validation/pilot-h4000.md).
