# CE375: rational x, y with integer n on y² = (x+6n+3)² + (36n³+54n²+27n−58)/x

**Target.** Find rational `x, y`, with `n` an integer, on

```text
y^2 = (x + 6n+3)^2 + (36n^3 + 54n^2 + 27n - 58)/x
```

meeting **either** condition:

1. `n, x, y` integers with `(n, x)` primitive, i.e. `gcd(n, x) = 1`;
2. `n` an integer, `x = X/2`, `y = Y/2` with `X, Y` odd and `(X, Y)` primitive, i.e. `gcd(X, Y) = 1`.

Both signs of `n`, `x` and `y` are covered.

## How the search works

The search runs over `n`. For each `n`, every point has `x` among the
divisors of `N(n) = 36n^3 + 54n^2 + 27n - 58` (integer form: `x | N`; half
form: `X | N`, `X` odd), so the worker factors `N(n)` completely and tests
**every** divisor, both signs, in both forms, for a square right-hand side.
A completed range of `n` therefore contains **all** points with those `n`,
with no bound on the size of `x` or `y`. Only `n = 2 (mod 3)` can have a
point, so two thirds of the `n` are skipped.

Factoring: a sieve removes primes up to `2^14`, Pollard rho splits easy
cofactors, PARI factors the hard ones, and every factor is re-checked.
Every reported point is verified exactly three times (worker, runner,
collector). Details and proofs: [METHOD.md](METHOD.md).

**Primitivity.** `375 = 3*5^3`, so there are non-primitive points (`5^3+5^3+5^3`
gives `n = 2, x = -5, y = 0`, with `gcd(n, x) = 1`). Each point is therefore
tagged with `primitive_point` (`gcd(n, x)` or `gcd(X, Y)` is 1),
`primitive_cubes` (`gcd(A, B, C) = 1` for `A = -x+y`, `B = -x-y`, `C = 2x+6n+3`)
and `desired` (both). **Desired points are the results**; the others are kept,
tagged `non-primitive`.

## Files

| File | Role |
| --- | --- |
| `src/xy375_worker.cpp` | Native worker: sieve, factoring, divisor and square tests, exact certificates |
| `src/fac128.h` | 128-bit Montgomery arithmetic (from the 114 search) |
| `make_campaign.py` | Splits a range of `n` into task files plus `page.json` |
| `run_task.py` | Restartable task runner: per-block checkpoint, SIGTERM-safe, continuation file, re-verifies every point |
| `collect.py` | Merges returned outputs: coverage, gaps, `desired_points.txt` |
| `verify_hits.py` | Independent exact re-verification of any `hits.jsonl` |
| `common375.py` | Independent Python verifier, task schema, counting helpers |
| `tests/test_375.py` | Brute-force agreement, large-`n` factoring checks against PARI, lifecycle |
| `Dockerfile`, `container_entrypoint.sh` | Charity Engine container |

## Build and test

Needs a C++17 compiler, GNU Make, GMP (`libgmp-dev`), the PARI library
(`libpari-dev`) and Python 3.9+. The large-`n` tests also need `gp` (`pari-gp`).

```sh
make
make test
```

The tests require the worker to find **exactly** the points of an
independent Python brute force over `-300 <= n < 300` for `k = 375, 15, 57,
1875, 7125` (the last two are, like 375, divisible by `5^3`, and have
primitive points of both forms); require the worker's divisor count of
`N(n)` to equal PARI's `numdiv` for hundreds of `n` near `10^9`, `-10^10` and
`10^11`; and run an interrupt, resume and collect cycle.

## Plan a campaign

Cost per processed `n` grows slowly with `|n|`. Measured on the development
host (one core of a shared cloud VM):

| `|n|` near | 10^6 | 10^7 | 10^8 | 10^9 | 10^10 | 10^11 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| us per processed `n` | 86 | 163 | 384 | 540-840 | 1,340 | 1,990 |

Estimated core-hours to cover **all `n` with `|n| < B`** (both signs):

| `B` | 10^8 | 3*10^8 | 10^9 | 2*10^9 | 3*10^9 | 10^10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| core-hours | 6 | 22 | 100 | 240 | 380 | 1,840 |

Measure on the target CPU near the largest `|n|` you plan to reach:

```sh
./bin/xy375_worker --n-start 1000000000 --n-stop 1000030000 --block 3000 \
  | python3 -c "import sys,json; r=[json.loads(l) for l in sys.stdin if '\"block\"' in l]; \
print(sum(x['seconds'] for x in r)/sum(x['ns'] for x in r)*1e6, 'us per processed n')"
```

Then write the tasks. `|n| < 10^7` is already done (see the pilot below), so
extend outwards on both sides, for example to `|n| < 10^9`:

```sh
python3 make_campaign.py --campaign-id ce375-pos --n-start 10000000 --n-stop 1000000000 \
  --us-per-n <MEASURED> --task-hours 1 --output-dir ce375-pos
python3 make_campaign.py --campaign-id ce375-neg --n-start -1000000000 --n-stop -10000000 \
  --us-per-n <MEASURED> --task-hours 1 --output-dir ce375-neg
```

`--plan-only` prints the plan without writing files. Nothing is submitted.
`--deadline-seconds` writes a per-attempt time limit into every task; the
worker then stops after the block in progress and the runner writes a
continuation task.

## Run a task (locally or on Charity Engine)

```sh
python3 run_task.py --task ce375-pos/tasks/ce375-pos-000.json --output-dir results/ce375-pos-000
```

Container (CE layout: task staged at `/local/input/task.json`):

```sh
docker build -t ce375-xy:1.0.0 .
docker run --rm -v "$PWD/in:/local/input" -v "$PWD/out:/local/output" ce375-xy:1.0.0
```

The image build compiles the worker and runs the test suite; a failing test
fails the build. Output directory: `status.json` (`complete`, `partial` or
`error`), `checkpoint.json` (next `n`), `hits.jsonl` (verified points),
`incomplete.jsonl` (only if some `N(n)` was not factored), `blocks.jsonl`,
`run.log`, `worker.stderr.log`, and `continuation.task.json` when `n` remain.
Re-running with the same output directory resumes after the last finished
block (32,768 consecutive `n`, about 3-15 s of work).

A point is one JSON line, for example the non-primitive `5^3+5^3+5^3`:

```json
{"type":"hit","form":"integer","desired":false,"primitive_point":true,"primitive_cubes":false,
 "point_gcd":"1","cube_gcd":"5","k":"375","n":"2","x_num":"-5","x_den":"1","y_num":"0","y_den":"1",
 "X":"-10","Y":"0","cube_a":"5","cube_b":"5","cube_c":"5"}
```

## Collect and verify

```sh
python3 collect.py --results results/ --page ce375-pos/page.json --output-dir collected
python3 verify_hits.py collected/hits.jsonl
cat collected/desired_points.txt    # THE RESULT: n, x, y (y up to sign), one per line
cat collected/points.txt            # every point, tagged DESIRED or non-primitive
```

`collected/summary.json` lists covered `n`, **gaps** against the page (re-issue
them from each directory's `continuation.task.json`) and any `incomplete_n`.

## Local pilot already run

All `n` with `|n| < 10^7`: see [validation/pilot-n1e7.md](validation/pilot-n1e7.md).
