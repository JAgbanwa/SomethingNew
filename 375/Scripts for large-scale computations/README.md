# CE375: rational-d search on y² = (x+6n+3)² + (36n³+54n²+27n−58)/x

> **For finding a primitive representation, use [`../gap-search/`](../gap-search/README.md).**
> This engine enumerates `d = (A+C)/(A+B)` by height, so a representation of size `M` is reached
> only if its pair sums share a factor `g ≥ M/H`. On 1,800 core-hours (`H ≈ 1.5·10⁶`) its
> heuristic yield is about `5·10⁻⁹·ρ` for a frontier of `10¹⁵`; the gap search, which enumerates
> `δ = |a+b|` with a primitivity filter from the frontier on, gives about `1.07·ρ` on the same hours
> (with `ρ = 0.0586` for primitive 375, about a 6 % chance; rationale in `../gap-search/ce375_rationale.pdf`).
> This engine remains the tool for exact statements about `d` of small height.

**Target.** Find rational `d` coming from points of

```text
y^2 = (x+6n+3)^2 + (36n^3 + 54n^2 + 27n - 58)/x,        d = -(x + 6n+3 + y)/(2x)   (y >= 0)
```

with **either** acceptable result:

1. **Integer chart:** `n, x` integers with `gcd(n, x) = 1`, and `y` an integer.
2. **Half chart:** `n` an integer, `x = X/2`, `y = Y/2`, `X, Y` odd with `gcd(X, Y) = 1`.

Both charts are searched in the same pass, with both signs of `n`, `x`, `y`
and `d`. Each hit is one point `(n, x, ±y)`, labelled with its chart and its
`d`. Since `y` is fixed only up to sign, `d` is reported for `y >= 0`
(the principal square root), which is exactly the `d` of the equation
`36n³+54n²+27n−58 = −2d·x²·(−(x+6n+3) + √(…))`.

**Primitivity.** `375 = 3*5^3` is not cube-free, so the equation has
non-primitive points, for example `5^3+5^3+5^3 = 375` gives `n = 2, x = -5,
y = 0, d = 1`: `gcd(n, x) = 1`, yet it is just 5 times `1^3+1^3+1^3 = 3`.
So every hit carries

* `primitive_point`: `gcd(n, x) = 1` (integer chart) or `gcd(X, Y) = 1` (half chart),
* `primitive_cubes`: `gcd(A, B, C) = 1` for the underlying cube components,
* `desired`: both of the above. **A desired hit is a result.**

Non-desired hits are still written out, tagged `non-primitive`.

## Modes

| `--mode` | Searches | Cost at height `2*10^4` |
| --- | --- | ---: |
| **`xy` (default for campaigns)** | desired points of **both charts**, both signs of `y` | **1.5 us/pair** |
| `xy-half` | desired points of the half chart only | 0.8 us/pair |
| `both` | every point of either chart, primitive or not (no primitivity shortcuts) | 5.0 us/pair |

`xy` gets its speed from proved consequences of `gcd(A, B, C) = 1`: only the
trivial cube factor needs testing, both branches of each Thue solution are
used, and a 5-adic filter modulo 125 discards about 65 % of the `d`.
`xy-half` adds odd `q` and odd `g`. Proofs and the exact coverage statements:
[DERIVATION.md §8-10](DERIVATION.md).

## Go beyond what is already covered

Everything below height 20,000 is already done for this target (pilots at
the end), so a campaign starts at 20,000:

```sh
python3 make_campaign.py --campaign-id ce375-xy --h-start 20000 \
  --core-hours <HOURS> --us-per-pair <MEASURED> --task-hours 1 --output-dir ce375-xy-tasks
```

| `h_stop` (from 20,000) | raw pairs | core-hours at 1.5 us | at 2.5 us |
| ---: | ---: | ---: | ---: |
| 200,000 | 7.9e10 | 33 | 55 |
| 500,000 | 5.0e11 | 208 | 347 |
| 1,000,000 | 2.0e12 | 833 | 1,388 |
| 1,500,000 | 4.5e12 | 1,875 | 3,124 |

Measure `us/pair` on the target CPU first (see "Plan a campaign" below).
Results land in `collected/desired_d_values.txt`, one line per point:
`d = ..  chart=..  n=..  x=..  y=+-..`.

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
./bin/thue375_worker --mode xy --h-start 20000 --h-stop 20200 \
  | python3 -c "import sys,json; r=[json.loads(l) for l in sys.stdin if '\"shell\"' in l]; \
print(sum(x['seconds'] for x in r)/sum(x['pairs'] for x in r)*1e6, 'us/pair')"
```

On the development host this gave **1.5 us/pair** in mode `xy` at height
2*10^4 (4.6-5.0 in mode `both`). The generator's default of 9 us/pair is a
conservative figure for mode `both`; always pass your measured value. The
table below is for mode `both`; for mode `xy` see the table at the top.

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

Mode `both`, heights `1 <= H < 4000` at `k = 375` (`|g| <= 10^100`): **0 desired hits**;
the only points are the three non-primitive ones (`d = 1, -8, -1/8`). See
[validation/pilot-h4000.md](validation/pilot-h4000.md).

`--mode xy-half`, heights `4000 <= H < 20000`: **0 hits** (1.31 us/pair on
the shared VM). See [validation/xy-pilot-h4000-20000.md](validation/xy-pilot-h4000-20000.md).

Mode `xy` (both charts), heights `4000 <= H < 20000`: **0 hits** (2.0 us/pair
on the shared VM). See [validation/xy-both-pilot-h4000-20000.md](validation/xy-both-pilot-h4000-20000.md).
So **no desired point has a `d` of height below 20,000**, and a new campaign
starts at `--h-start 20000`.
