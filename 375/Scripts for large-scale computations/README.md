# CE375: primitive-point search with g = -1 or +1

**This README describes the existing d-first/unit-g worker.** Its directory
name does not mean that it searches all large primitive cube representations.
The complementary [Elkies--Jahnel backend](elkies-jahnel/README.md) now provides
a separate C++/GMP geometric lattice search in cube-height/ratio tiles, with
its own task schema, exact verification, checkpoints and coverage collector.
It does not change this worker's fixed-g contract or reuse its coverage records.

For the practical choice between engines, read [the 375 overview](../README.md).
The recommended first Charity Engine pilot is the hardened
[`gap-search`](../gap-search/CHARITY_ENGINE_HANDOFF.md) package. Benchmark the
new lattice backend before allocating a large campaign to it.

Production searches use exactly **`g in {-1, +1}`**. There is no configurable
large-g range. This is an explicit search restriction, separate from the
point-primitivity tests below.

## Accepted results: either case is enough

Here `n` is the integer called `x` in the original conversation, and this
folder's `x` is the rational parameter originally called `m`.

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

The normal worker accepts heights through `200000000`. Together with unit
`g`, this gives the following safe outer bounds at `K = 375`:

| Quantity | Bound |
| --- | --- |
| Original integer `x`, called `n` here | `abs(n) <= 100000000` |
| Original rational `m`, called `x` here | `abs(x) <= 100000000` |
| `y` | `abs(y) < 900000000` |
| Each cube component `A, B, C` | Magnitude less than `1000000000` |

These bounds follow from the selected slope domain; they are not claims
that the maxima occur. [DERIVATION.md](DERIVATION.md#6-coverage-and-run-records)
proves them. Finding all roots for each selected slope therefore remains a
bounded search. A primitive cube representation can have `abs(g) > 1`, so
the unit-g domain does not cover every primitive representation.

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
Failure-injection tests cover missing or inconsistent terminal records,
nonzero exits, final-shell replay, signal interruptions, continuation
coverage, and mismatched binary provenance. A real-worker positive control
checks that exact hit certificates survive running, resuming, and collection.
The optional PARI/GP test is skipped when `gp` is unavailable.

## Plan and run a campaign

Choose a height interval explicitly. For example, prioritize half-integer
points with:

```sh
python3 make_campaign.py --campaign-id ce375-unit-half --mode xy-half \
  --h-start 1 --h-stop 20000 --output-dir ce375-unit-half
WORKER_SHA="$(sha256sum bin/thue375_worker | cut -d ' ' -f 1)"
python3 run_task.py --task ce375-unit-half/tasks/ce375-unit-half-0.json \
  --output-dir results/ce375-unit-half-0 --expected-worker-sha256 "$WORKER_SHA"
```

Use `--mode xy` to search both alternatives. Run every generated task to cover
the whole plan. The generator also accepts `--core-hours` in place of
`--h-stop`; measure `--us-per-pair` for this version and target CPU before
using that estimate. Historical timings were for a different search scope.
The raw pair count through height `H` is `2H^2 + H`.

Generation writes task files and `page.json`; it does not submit jobs.
`--deadline-seconds 0` disables a time deadline, while the assigned height
endpoint still applies. This planner generates finite pages; it does not
expand the parent worker's height domain indefinitely.

### Completion, checkpoints, and continuations

A successful task must produce a start record matching its exact scope,
ordered shell records, one consistent `complete` terminal record, and worker
exit code zero. Missing terminal records, nonzero normal exits, malformed
progress, and output after a terminal record are errors, even if the worker
reported the last height.

The most recently reported shell remains pending until another ordered shell
arrives or a valid terminal record is followed by exit zero. The runner
records only committed shells in its checkpoint. Rerunning with the same
output directory replays an uncommitted final shell; a crash between the
shell-log append and checkpoint replacement is handled by truncating that
uncommitted log tail before resuming.

A valid `partial` terminal record or a legitimate signal interruption leaves
explicit remaining work in `continuation.task.json`. The runner exits zero
for complete or deliberately partial work and nonzero for errors. Use the
status and continuation files to distinguish completion from a partial run.

The continuation can run in the same directory or a fresh directory. Each
directory records its actual `covered_h_start` and durable `next_h`; a fresh
directory holding only a continuation cannot claim its predecessor's work.
Collect both directories to recover their combined coverage.

### Binary provenance and existing outputs

`--expected-worker-sha256` checks the executable before touching the output
directory. The runner saves the actual hash in status, checkpoint, hit, and
shell records, and pins saved task and continuation manifests with
`expected_worker_sha256`. A resume must use that same binary. Conflicting
task pins, command-line pins, or saved hashes cause refusal without modifying
existing results. Compute the hash from the worker actually used on the
target runtime; a separately built copy can have a different hash.

These are additive reliability fields within the existing version-2
mathematical task contract. **Older version-2 outputs without the required
hashes and terminal proof are refused.** Rerun their requested work in fresh
output directories; do not manufacture provenance or completion fields for
old results. Version-1 general-g records remain historical evidence only.

For Charity Engine, the entry point remains:

```sh
python3 /app/run_task.py --task /local/input/task.json --output-dir /local/output
```

## Collect and independently verify

```sh
python3 collect.py --results results/ --page ce375-unit-half/page.json \
  --output-dir collected --expected-worker-sha256 "$WORKER_SHA" --require-complete
python3 verify_hits.py collected/hits.jsonl
```

`collected/desired_d_values.txt` lists acceptable points from either selected
case. `collected/summary.json` records the height coverage, gaps, and fixed
`g_values`, together with worker hashes and errors. The collector checks the
committed contiguous shell records against the checkpoint and rejects
inconsistent metadata, error-status directories, and mixed binary hashes.
Returned results must retain `status.json` and `hits.jsonl`, including an empty
hit file for a zero-hit run. A completed or partial status must report exactly
the number of unique saved points. Checkpoints record a durable unique-hit
count as well, so missing hits cannot be hidden by a stale running status.
With `--expected-worker-sha256`, an unexpected binary invalidates the returned
coverage. The Python verifier checks exact arithmetic, the point gcd, and
that the actual enumerated `g` is one of the two permitted values; it verifies
hit certificates independently of campaign completeness.

Collector exit codes are `1` for errors, `2` for gaps when `--require-complete`
is supplied, and `0` otherwise. Without `--require-complete`, a successful
collection may describe a partial page, so inspect `summary.json` for gaps.

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
