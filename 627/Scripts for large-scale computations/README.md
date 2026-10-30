# CE627: rational-d search for 36n³+54n²+27n−100

**Target.** Find rational `d` such that

```text
36n^3 + 54n^2 + 27n - 100 = -2*d*x^2*( -(x+6n+3) + s ),
s = sqrt( (x+6n+3)^2 + (36n^3+54n^2+27n-100)/x )
```

has a point satisfying **either** acceptable result:

1. **Integer chart:** `n, x` integers and `s` an integer.
2. **Half chart:** `n` an integer, `x = X/2` and `s = Y/2` with `X, Y` odd.

Both are searched in the same pass and every hit is labelled with its chart.
Both signs of `n`, `x` and `d` are covered.

## How the search works (one paragraph)

With `S = 6n+3` the left side is `(S^3 - 627)/6`. Every point determines
`d = -(x+s+6n+3)/(2x)` uniquely, and for `d = p/q` in lowest terms the
points with that `d` are **exactly** the integer solutions `(S, g)` of

```text
S^3 - 6pq S g^2 + 3pq(p+q) g^3 = 627,      x = -q g/2,   s = (2p+q) g/2 - S >= 0,
```

with `q g` even for the integer chart and `q g` odd for the half chart. The
engine therefore enumerates `d` itself, in increasing height
`H(d) = max(|p|, q)`, discards `d` that provably cannot work, and solves one
Thue equation per surviving `d`: all solutions with `1 <= |g| <= 10^100`,
using exact GMP arithmetic and certified continued fractions. There is no
`(n, x)` rectangle. `n` is automatically an integer (in fact `n = 1 (mod 3)`).
Proofs: [DERIVATION.md](DERIVATION.md).

## Files

| File | Role |
| --- | --- |
| `src/thue627_worker.cpp` | Native GMP worker: height shells of `d`, filters, Thue solver, exact certificates |
| `make_campaign.py` | Writes disjoint height-range task files and `page.json` (budget planning) |
| `run_task.py` | Restartable task runner: per-shell checkpoint, SIGTERM-safe, continuation file, re-verifies hits |
| `collect.py` | Merges returned outputs: coverage, gaps, verified hit list, distinct `d` values |
| `verify_hits.py` | Independent exact re-verification of any `hits.jsonl` |
| `common627.py` | Independent Python implementation of filters, verifier, task schema |
| `tools/certify_d.gp` | PARI/GP: unconditional, **unbounded** certification of individual `d` |
| `tests/test_627.py` | Known-answer, brute-force, PARI cross-check and lifecycle tests |
| `Dockerfile`, `container_entrypoint.sh` | Charity Engine container |

## Build and test

Needs a C++17 compiler, GNU Make, GMP (`libgmp-dev`) and Python 3.9+.
PARI/GP (`pari-gp`) is optional; it enables the PARI cross-check test.

```sh
make
make test
```

The tests run the identical code with small `k` that have known
representations (`k = 3, 15, 21, 57`) and require the worker to recover
**every** `d` predicted from those representations, in both charts, through
both the small-`g` and the continued-fraction code paths; they check against
an independent `(n, x)` brute force of the original equation, check the raw
Thue solver against PARI's unconditional `thue()`, and run an
interrupt/resume/collect cycle.

## Plan a campaign

Cost model: shells `1..H` contain `2H^2 + H` raw pairs `(p, q)`. Measure the
rate on the target CPU first (one core, about a minute):

```sh
./bin/thue627_worker --h-start 20000 --h-stop 20200 \
  | python3 -c "import sys,json; r=[json.loads(l) for l in sys.stdin if '\"shell\"' in l]; \
print(sum(x['seconds'] for x in r)/sum(x['pairs'] for x in r)*1e6, 'us/pair')"
```

On the development host this gave **5.0 us/pair** at height 2*10^4 and
**6.4 us/pair** at 10^5 (one core, shared machine). The generator defaults to
a conservative 9 us/pair; pass your measured value.

| `h_stop` | raw pairs | core-hours at 6 us | at 9 us |
| ---: | ---: | ---: | ---: |
| 50,000 | 5.0e9 | 8 | 13 |
| 100,000 | 2.0e10 | 33 | 50 |
| 200,000 | 8.0e10 | 133 | 200 |
| 400,000 | 3.2e11 | 533 | 800 |

Either fix the height range:

```sh
python3 make_campaign.py --campaign-id ce627-h100k --h-stop 100000 \
  --us-per-pair 9 --task-hours 1 --output-dir ce627-tasks
```

or fix the core-hours and let it derive the largest height that fits:

```sh
python3 make_campaign.py --campaign-id ce627-budget --core-hours <HOURS> \
  --us-per-pair <MEASURED> --task-hours 1 --output-dir ce627-tasks --plan-only
```

Drop `--plan-only` to write `ce627-tasks/tasks/*.json` and
`ce627-tasks/page.json`. Generation does not start or submit anything.
`--deadline-seconds` writes a per-attempt time limit into every task; the
worker then stops cleanly after the shell in progress and the runner writes a
continuation task.

## Run a task (locally or on Charity Engine)

```sh
python3 run_task.py --task ce627-tasks/tasks/ce627-h100k-000.json --output-dir results/ce627-h100k-000
```

Container (CE layout: task staged at `/local/input/task.json`):

```sh
docker build -t ce627-dfirst:1.0.0 .
docker run --rm -v "$PWD/in:/local/input" -v "$PWD/out:/local/output" ce627-dfirst:1.0.0
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

A hit is printed as one JSON line, for example (from the `k = 15` test):

```json
{"type":"hit","chart":"half","k":"15","d_num":"4","d_den":"1","n":"0",
 "x_num":"-1","x_den":"2","s_num":"3","s_den":"2","cube_a":"2","cube_b":"-1","cube_c":"2", ...}
```

## Collect and verify

```sh
python3 collect.py --results results/ --page ce627-tasks/page.json --output-dir collected
python3 verify_hits.py collected/hits.jsonl
cat collected/d_values.txt        # one line per d: chart, n, x, s, cube components
```

`collected/summary.json` lists covered heights and any **gaps** against the
page, which must be re-issued (use each directory's `continuation.task.json`).

To certify a particular `d` with no bound on `g` (useful for any `d` that is
reported, or for spot checks):

```sh
gp -q tools/certify_d.gp
? certify(p, q)          \\ k = 627; certify(p, q, 15) for the test value
```

## What a completed run establishes

Every point, in either chart, with `d` in the processed height range and
`1 <= |g| <= 10^g_max_digits` (so `|x| <= q * 10^100 / 2`). It does not say
anything about larger `g` for those `d`, nor about `d` of larger height.

## Local pilot already run

Heights `1 <= H < 4000` at `k = 627` (`|g| <= 10^100`): see
[validation/pilot-h4000.md](validation/pilot-h4000.md).
