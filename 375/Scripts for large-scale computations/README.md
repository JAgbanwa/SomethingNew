# CE375: primitive-point search with g = -1 or +1

Production searches use exactly **`g in {-1, +1}`**. There is no configurable
large-g range. This is an explicit search restriction, separate from the
point-primitivity tests below.

## Accepted results: either case is enough

Find a point on

```text
y^2 = (x+6n+3)^2 + (36n^3 + 54n^2 + 27n - 58)/x
```

satisfying either of these alternatives:

| Case | Required conditions |
| --- | --- |
| Integer | `n, x, y` integers, `x != 0`, `gcd(n, x, y) = 1` |
| Half-integer | `n` integer, `x = X/2`, `y = Y/2`, `X, Y` odd, `X != 0`, `gcd(X, Y) = 1` |

A point only needs to meet its own row. Both signs of `n`, `x`, and `y` are
allowed. A record stores nonnegative `y`; its negative gives the same square.
The `desired` flag means that the point passes the relevant row.
`primitive_cubes` remains an independent diagnostic, not an additional
acceptance condition. Fixed `g = -1 or +1` already implies primitive cube
components in this parameterization.

## Modes

| `--mode` | Search |
| --- | --- |
| **`xy` (default)** | Both alternative cases, accepting either sign branch of `y` |
| `xy-half` | Half-integer case only |
| `both` | Diagnostic mode: both charts on the principal square-root branch |

Within each height shell, half-integer candidates are visited first.
Every production mode uses only `g = -1` and `g = +1`. The `xy-half` mode
also requires odd `q`. Points that fail the applicable gcd test may be retained
as diagnostics, but never appear in `desired_d_values.txt`.

## Exact search parameters

Write the enumerated auxiliary fraction as `d = p/q` in lowest terms, `q > 0`,
and put `S = 6n+3`. The worker solves the two integer-root problems

```text
S^3 - 6pq S + 3pq(p+q)g = 375,      g = -1, +1,
x = -qg/2,                         s = (2p+q)g/2 - S.
```

It reconstructs `n = (S-3)/6` and `y = abs(s)` and verifies the original
equation exactly. Both branches are accepted in the `xy` modes. The reported
principal `d` can differ from the fraction that found the point; `thue_p`,
`thue_q`, and `g` retain the actual search parameters.

Fractions are enumerated by `H = max(abs(p), q)` with
`h_start <= H < h_stop`. Consequently **`abs(x) = q/2`**. There is no guessed
interval for `n` or `y`: all integer roots `S` of each selected cubic are found.
A completed task establishes coverage only for its selected height interval,
mode, and the two allowed values of `g`.

The normal worker accepts heights through `200000000`. Thus it can return
`abs(x) <= 100000000`; reaching `abs(x)` near `10^14` with this restriction
would require `q` near `2*10^14`, beyond the current height enumerator.

The production option `--g-max-digits` has been removed. Tasks and result
metadata instead state **`"g_values": [-1, 1]`**. Version-2 schemas prevent
old broad-range tasks or checkpoints from being reused as fixed-g coverage.
See [DERIVATION.md](DERIVATION.md) for the identities and coverage proof.

## Build and test

Requires a C++17 compiler, GNU Make, GMP (`libgmp-dev`) and Python 3.9+.
PARI/GP is optional for the independent raw-solver cross-check.

```sh
make
make test
```

The tests compare the fixed-g worker with independent enumeration on the
original equation, check both signs of `g`, both charts, the three-coordinate
integer gcd, rejected legacy settings, and task/resume/collect behavior.
General continued-fraction checks use the separate raw diagnostic solver.

## Plan and run a campaign

Choose a height interval explicitly. For example, prioritize half-integer
points with:

```sh
python3 make_campaign.py --campaign-id ce375-unit-half --mode xy-half   --h-start 1 --h-stop 20000 --output-dir ce375-unit-half
python3 run_task.py --task ce375-unit-half/tasks/ce375-unit-half-0.json   --output-dir results/ce375-unit-half-0
```

Use `--mode xy` to search both alternatives. Run every generated task to cover
the whole plan. The generator also accepts `--core-hours` in place of
`--h-stop`; measure `--us-per-pair` for this version and target CPU before
using that estimate. Historical timings were for a different search scope.
The raw pair count through height `H` is `2H^2 + H`.

Generation writes task files and `page.json`; it does not submit jobs.
`--deadline-seconds 0` disables a time deadline, while the assigned height
endpoint still applies. Each completed shell is checkpointed, and rerunning
a task in the same output directory resumes it. Interrupted tasks produce a
`continuation.task.json` when shells remain.

For Charity Engine, the entry point remains:

```sh
python3 /app/run_task.py --task /local/input/task.json --output-dir /local/output
```

## Collect and independently verify

```sh
python3 collect.py --results results/ --page ce375-unit-half/page.json --output-dir collected
python3 verify_hits.py collected/hits.jsonl
```

`collected/desired_d_values.txt` lists acceptable points from either selected
case. `collected/summary.json` records the height coverage, gaps, and fixed
`g_values`. The Python verifier checks exact arithmetic, the point gcd, and
that the actual enumerated `g` is one of the two permitted values.

## Historical evidence and diagnostics

The existing `validation/*pilot*` records and `examples/*pilot*` task files
are archived version-1 evidence. Their original ranges, gcd definitions, and
results are preserved; they are not version-2 task inputs. Generate fresh
fixed-g tasks rather than editing historical records or resuming their
checkpoints. No new completed campaign is claimed by this code change.

The worker's `--raw --target T --g-max G` interface is a separate mathematical
test harness for general Thue equations, not a production campaign. The
optional `tools/certify_d.gp` helper independently checks the two allowed g
values for one selected fraction. Neither diagnostic expands production
coverage.
