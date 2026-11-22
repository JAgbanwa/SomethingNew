# CE375: rational-d search for 36n³+54n²+27n−58

**Target.** Find rational `d` such that

```text
36n^3 + 54n^2 + 27n - 58 = -2*d*x^2*( -(x+6n+3) + s ),
s = sqrt( (x+6n+3)^2 + (36n^3+54n^2+27n-58)/x )
```

has a point satisfying **either** acceptable result:

1. **Integer chart:** `n, x` primitive integers and `s` an integer.
2. **Half chart:** `n` an integer, `x = X/2` and `s = Y/2` with `X, Y` odd and primitive.

Both are searched in the same pass and every hit is labelled with its chart.
Both signs of `n`, `x` and `d` are covered.

**Primitivity.** `375 = 3*5^3` is not cube-free, so the equation has
non-primitive points (for example `5^3+5^3+5^3 = 375` gives `d = 1`,
`(n, x) = (2, -5)`, `s = 0`). Every hit carries

* `primitive_point`: `gcd(n, x) = 1` (integer chart) or `gcd(X, Y) = 1` (half chart),
* `primitive_cubes`: `gcd(A, B, C) = 1` for the underlying cubes (see below),
* `desired`: both of the above.

A **desired** hit is a result. Non-primitive hits are still recorded
(tagged `non-primitive`), never discarded, so nothing has to be rerun if the
definition is tightened or loosened. Details: [DERIVATION.md §8](DERIVATION.md).

## Rational (x, y) mode: `--mode xy-half`

The second target is rational `x, y` with `n` an integer on

```text
y^2 = (x+6n+3)^2 + (36n^3 + 54n^2 + 27n - 58)/x,      x = X/2,  y = Y/2,  X, Y odd,  gcd(X, Y) = 1,
```

both signs of `y`. Every task, file and command below takes `--mode xy-half`
(or `"mode": "xy-half"` in a task file); the default mode `both` is unchanged.
In this mode the engine uses only odd `q` and odd `g`, a proved 5-adic filter
modulo 125, and both Thue branches, so it does about **5x less work per height**
(0.9 against 4.8 us per `(p, q)` pair at height `2*10^4`).
Each hit is one point `(n, X, |Y|)`; `collected/desired_d_values.txt` lists
them as `n=..  x=X/2  y=+-Y/2`. Proofs and the exact coverage statement:
[DERIVATION.md §9](DERIVATION.md).

To go **beyond what is already covered**, start above the heights already
searched (everything below 20,000 is done for this target, see the pilots at the end):

```sh
python3 make_campaign.py --campaign-id ce375-xy --mode xy-half --h-start 20000 \
  --core-hours <HOURS> --us-per-pair <MEASURED> --task-hours 1 --output-dir ce375-xy-tasks
```

| `h_stop` (from 20,000) | raw pairs | core-hours at 1 us | at 1.5 us |
| ---: | ---: | ---: | ---: |
| 200,000 | 7.9e10 | 22 | 33 |
| 500,000 | 5.0e11 | 139 | 208 |
| 1,000,000 | 2.0e12 | 555 | 833 |
| 1,500,000 | 4.5e12 | 1,250 | 1,875 |

Measure `us/pair` on the target CPU first, as below but with `--mode xy-half`.

## How the search works (one paragraph)

With `S = 6n+3` the left side is `(S^3 - 375)/6`. Every point determines
`d = -(x+s+6n+3)/(2x)` uniquely, and for `d = p/q` in lowest terms the
points with that `d` are **exactly** the integer solutions `(S, g)` of

```text
S^3 - 6pq S g^2 + 3pq(p+q) g^3 = 375,      x = -q g/2,   s = (2p+q) g/2 - S >= 0,
```

with `q g` even for the integer chart and `q g` odd for the half chart. The
engine therefore enumerates `d` itself, in increasing height
`H(d) = max(|p|, q)`, discards `d` that provably cannot work, and solves one
Thue equation per surviving `d`: all solutions with `1 <= |g| <= 10^100`
(non-primitive ones with `5 | gcd(S, g)` included),
using exact GMP arithmetic and certified continued fractions. There is no
`(n, x)` rectangle. `n` is automatically an integer (in fact `n = 2 (mod 3)`).
Proofs: [DERIVATION.md](DERIVATION.md).

## Files

| File | Role |
| --- | --- |
| `src/thue375_worker.cpp` | Native GMP worker: height shells of `d`, filters, Thue solver, exact certificates |
| `make_campaign.py` | Writes disjoint height-range task files and `page.json` (budget planning) |
| `run_task.py` | Restartable task runner: per-shell checkpoint, SIGTERM-safe, continuation file, re-verifies hits |
| `collect.py` | Merges returned outputs: coverage, gaps, verified hits, **desired (primitive) `d` values** |
| `verify_hits.py` | Independent exact re-verification of any `hits.jsonl` |
| `common375.py` | Independent Python implementation of filters, verifier, task schema |
| `tools/certify_d.gp` | PARI/GP: unconditional, **unbounded** certification of individual `d` |
| `tests/test_375.py` | Known-answer, brute-force, PARI cross-check and lifecycle tests |
| `Dockerfile`, `container_entrypoint.sh` | Charity Engine container |

## Build and test

Needs a C++17 compiler, GNU Make, GMP (`libgmp-dev`) and Python 3.9+.
PARI/GP (`pari-gp`) is optional; it enables the PARI cross-check test.

```sh
make
make test
```

The tests run the identical code with small `k` that have known
representations (`k = 3, 15, 21, 57`), and at `k = 375` itself, where the
non-primitive points from `5*(1,1,1)` and `5*(4,4,-5)` must all be found and
labelled non-desired, the primitivity flags must match an independent Python
computation, and an `(n, x)` divisor brute force over `|n| <= 60` on the
original equation must agree; and require the worker to recover
**every** `d` predicted from those representations, in both charts, through
both the small-`g` and the continued-fraction code paths; they check against
an independent `(n, x)` brute force of the original equation, check the raw
Thue solver against PARI's unconditional `thue()`, and run an
interrupt/resume/collect cycle.

## Plan a campaign

Cost model: shells `1..H` contain `2H^2 + H` raw pairs `(p, q)`. Measure the
rate on the target CPU first (one core, about a minute):

```sh
./bin/thue375_worker --h-start 20000 --h-stop 20200 \
  | python3 -c "import sys,json; r=[json.loads(l) for l in sys.stdin if '\"shell\"' in l]; \
print(sum(x['seconds'] for x in r)/sum(x['pairs'] for x in r)*1e6, 'us/pair')"
```

On the development host this gave **4.6 us/pair** at height 2*10^4, and the
whole `H < 4000` pilot averaged **7.3 us/pair** (two tasks sharing a
two-core cloud VM). The generator defaults to
a conservative 9 us/pair; pass your measured value.

| `h_stop` | raw pairs | core-hours at 6 us | at 9 us |
| ---: | ---: | ---: | ---: |
| 50,000 | 5.0e9 | 8 | 13 |
| 100,000 | 2.0e10 | 33 | 50 |
| 200,000 | 8.0e10 | 133 | 200 |
| 400,000 | 3.2e11 | 533 | 800 |

Either fix the height range:

```sh
python3 make_campaign.py --campaign-id ce375-h100k --h-stop 100000 \
  --us-per-pair 9 --task-hours 1 --output-dir ce375-tasks
```

or fix the core-hours and let it derive the largest height that fits:

```sh
python3 make_campaign.py --campaign-id ce375-budget --core-hours <HOURS> \
  --us-per-pair <MEASURED> --task-hours 1 --output-dir ce375-tasks --plan-only
```

Drop `--plan-only` to write `ce375-tasks/tasks/*.json` and
`ce375-tasks/page.json`. Generation does not start or submit anything.
`--deadline-seconds` writes a per-attempt time limit into every task; the
worker then stops cleanly after the shell in progress and the runner writes a
continuation task.

## Run a task (locally or on Charity Engine)

```sh
python3 run_task.py --task ce375-tasks/tasks/ce375-h100k-000.json --output-dir results/ce375-h100k-000
```

Container (CE layout: task staged at `/local/input/task.json`):

```sh
docker build -t ce375-dfirst:1.0.0 .
docker run --rm -v "$PWD/in:/local/input" -v "$PWD/out:/local/output" ce375-dfirst:1.0.0
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

A hit is printed as one JSON line, for example (the non-primitive `5^3+5^3+5^3`):

```json
{"type":"hit","chart":"integer","desired":false,"primitive_point":true,"primitive_cubes":false,
 "point_gcd":"1","cube_gcd":"5","k":"375","d_num":"1","d_den":"1","n":"2",
 "x_num":"-5","x_den":"1","s_num":"0","s_den":"1","cube_a":"5","cube_b":"5","cube_c":"5", ...}
```

## Collect and verify

```sh
python3 collect.py --results results/ --page ce375-tasks/page.json --output-dir collected
python3 verify_hits.py collected/hits.jsonl
cat collected/desired_d_values.txt   # THE RESULT: d with a primitive point (chart, n, x, s, cubes)
cat collected/d_values.txt           # every hit, tagged DESIRED or non-primitive
```

`collected/summary.json` lists covered heights and any **gaps** against the
page, which must be re-issued (use each directory's `continuation.task.json`).

To certify a particular `d` with no bound on `g` (useful for any `d` that is
reported, or for spot checks):

```sh
gp -q tools/certify_d.gp
? certify(p, q)          \\ k = 375; each point tagged DESIRED / non-primitive
```

## What a completed run establishes

Every point, in either chart, primitive or not, with `d` in the processed height range and
`1 <= |g| <= 10^g_max_digits` (so `|x| <= q * 10^100 / 2`). It does not say
anything about larger `g` for those `d`, nor about `d` of larger height.

## Local pilot already run

Heights `1 <= H < 4000` at `k = 375` (`|g| <= 10^100`): **0 desired hits**;
the only points are the three non-primitive ones (`d = 1, -8, -1/8`). See
[validation/pilot-h4000.md](validation/pilot-h4000.md).

`--mode xy-half`, heights `4000 <= H < 20000`: **0 hits** (1.31 us/pair on
the shared VM). See [validation/xy-pilot-h4000-20000.md](validation/xy-pilot-h4000-20000.md).
So a new xy-half campaign should start at `--h-start 20000`.
