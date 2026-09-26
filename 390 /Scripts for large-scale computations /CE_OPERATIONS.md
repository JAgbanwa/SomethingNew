# Charity Engine operations

This package produces independent CPU tasks with bounded wall time, exact arithmetic,
verifiable hit records and explicit continuations. It does not submit jobs or invent
an API for the Charity Engine service. The CE team should attach the container,
input files and output collection policy through its supported submission process.

**All retrievable output is written under `/local/output/`.** The default input is
`/local/input/task.json`. Neither path is `/output/`.

If the CE application configuration overrides Docker entrypoint behavior, its
explicit executable and arguments are:

```text
/app/run_task.sh --task /local/input/task.json --output-dir /local/output
```

The deployment reference is [Computing with Charity Engine — Input / Output Files](https://www.charityengine.com/docs/Computing%2Bwith%2BCharity%2BEngine#ComputingwithCharityEngine-Input+OutputFiles).
Confirm the actual external task limit with the team. The supervisor's defaults
reserve time for launch, checkpointing and output collection:

| CE external task allowance | `--seconds` in campaign generation | Reserved margin |
| --- | ---: | ---: |
| 1 hour | 3000 (50 minutes, default) | 10 minutes |
| 2 hours | 6000 (100 minutes) | 20 minutes |

The budget measures elapsed wall time, not CPU time. Its maximum accepted value is
6600 seconds. A watchdog also stops a worker that is still computing one fiber when
the budget expires. Task time on an unfamiliar host cannot be predicted exactly;
use pilot measurements, and retain the safety margin.

## Search units and honest coverage

A fiber is a reduced rational value `d = -1 - a/(2q)`, with positive odd `a,q` and
`gcd(a,q)=1`. The mathematical reductions and their completeness conditions are
in `MATHEMATICS.md`. A task enumerates the chosen finite set of numerators and an
inclusive interval of odd denominators. Noncoprime pairs occupy an index but are
skipped. Pairs excluded by the proved modulo-3 conditions are also skipped
before worker dispatch. This makes sharding deterministic and reproducible.

For `Q = (q_max-q_min)/2+1`, candidate index `i` maps to:

```text
a = a_values[i // Q]
q = q_min + 2*(i % Q)
```

A task's slice is the half-open index interval `[start, stop)`. Distinct initial
slices are disjoint. The candidate list is implicit; no enormous manifest or
array of all candidates is allocated. Each completed fiber is searched against
the exact inclusive rectangle in its task. **A completed selected-fiber campaign
is not an exhaustive search of the whole `n,x` rectangle.** There is no promise
that any chosen finite campaign will find a solution.

The default bounds are the requested positive intervals `10^43 <= n <= 10^45`
and `10^54 <= x <= 10^55`. The heuristic `x ~ n^(5/4)` imposes no additional cut.
The default accepts a rational nonnegative square root. Add
`--require-integer-sqrt` to restrict the search to the integer-square-root subset.

## Build and generate a pilot

On a build host with Docker:

```sh
docker build -t ce390:3.0.0 .
```

For an amd64 CE image from an Apple Silicon build host, use
`docker build --platform linux/amd64 -t ce390:3.0.0 .`; a local emulated benchmark
is not representative of CE CPU speed. Image building downloads Debian packages;
the running computation makes no network requests. The Docker build runs `make test` in its build stage. Preserve the resulting image
digest and use that same image for every task and continuation in the campaign.

A native build requires a C++17 compiler, GNU Make, GMP headers and Python 3.10+
(the Debian image uses Python 3.11):

```sh
make -j2
make test
```

Generate only ten pilot tasks. The interval below is an illustrative selection,
not a statistically justified best region and not a guarantee of discovery:

```sh
python3 campaign.py \
  --campaign-id ce390-pilot-001 \
  --a-values 1,5,7 \
  --q-min 100000001 \
  --q-max 100000000001 \
  --candidates-per-task 10000 \
  --page-start 0 \
  --task-count 10 \
  --seconds 3000 \
  --output-dir tasks
```

The default rectangle is embedded in every task using exact decimal strings.
`--page-start` is a zero-based **task ordinal**. To generate the next page, use
`--page-start 10` with all other campaign parameters unchanged. The page manifest
reports the next ordinal. The generator refuses to replace a different task at
an existing task filename; a fresh output directory is advisable when changing
parameters. Numerator order is part of the campaign definition.

Run one pilot after selecting a task file:

```sh
mkdir -p ce-input ce-output
cp tasks/task-000000000000-*.json ce-input/task.json
docker run --rm --network none --cpus 1 --memory 512m \
  --mount type=bind,src="$(pwd)/ce-input",dst=/local/input,readonly \
  --mount type=bind,src="$(pwd)/ce-output",dst=/local/output \
  ce390:3.0.0
```

Use one worker process per allocated core and separate task/output directories.
The worker itself is single threaded; the package does not oversubscribe a host.
If the local output directory has restricted ownership, set a suitable Docker
`--user` and ensure that identity can write it. CE's own output directory should
be provisioned by the CE runtime.

Native equivalent:

```sh
python3 run_task.py --task ce-input/task.json --output-dir ce-output
```

## Calibrate candidate counts

Pilot tasks are intentionally small. A task with too few candidate indices may
finish in seconds; that is useful for calibration, but not a production task size.
Use the elapsed time and `invocation_coverage` in `status.json` to estimate
candidate indices per second. Do not divide by `fibers_completed` alone because
some indices are noncoprime and are skipped.

A starting production count is `floor(0.8 * measured_indices_per_second * 3000)`
for a 50-minute budget, or substitute 6000 for a 100-minute budget. Time several
separated regions of the chosen `a,q` space and use the slowest representative
rate. Fiber costs and host speeds vary, so the supervisor always enforces the
budget and writes a continuation. Increasing precision or changing numerators
requires new measurements. An index count is a scheduling choice, not a bound
on the mathematics checked within a completed fiber.

The following reads a retrieved pilot status and prints an estimated count:

```sh
python3 - ce-output/status.json <<'PY'
import json, math, sys
s = json.load(open(sys.argv[1]))
c = s['invocation_coverage']
count = int(c['stop']) - int(c['start'])
seconds = s['elapsed_seconds']
if s['state'] != 'complete' or count <= 0 or seconds <= 0:
    raise SystemExit('Use a completed nonempty representative pilot.')
print(max(1, math.floor(0.8 * count / seconds * 3000)))
PY
```

Supply that count to `campaign.py --candidates-per-task ...` for the production
campaign. Keep the campaign parameters fixed while generating its pages. Upload
inputs through immutable, versioned locations as required by the CE submission
workflow; changing the content behind an already submitted input URL can make
an execution irreproducible.

## Output and continuation contract

| File under `/local/output/` | Meaning |
| --- | --- |
| `task.json` | Exact task used by this invocation |
| `status.json` | Authoritative completion state, covered interval, elapsed time and counters |
| `checkpoint.json` | Next uncompleted candidate index, durable unique-hit count, task identity and worker SHA256 |
| `continuation.task.json` | Present when work remains; submit it as a new task input |
| `hits.jsonl` | One independently checked certificate per line; an empty file is valid |
| `run.log` | Supervisor progress and errors |
| `worker.stderr.log` | Worker diagnostics |
| `worker_error.json`, `error.json` | Failure detail, when applicable |
| `startup-error-*.json` | Startup/configuration failure, retained when the output path is writable |

Big integers and index counts are decimal strings in JSON. Small scheduling
values are JSON numbers. `fibers_completed` counts completed worker replies; `cf_fibers_completed`
counts replies that required the continued-fraction search. `bounds_excluded`,
`congruence_excluded` and `non_coprime_skipped` identify their respective
exclusions. Certificate rational values are reduced and have positive
denominators. `sqrt_integer` explicitly states which subset a hit belongs to.

Interpret states precisely:

* `complete`: the selected suffix through `slice.stop` was finished. Read
  `invocation_coverage` for work done in this process and `output_coverage` for
  contiguous coverage retained in this output directory across in-place restarts.
  A new-host continuation does not claim its predecessors' intervals.
* `partial` with reason `time_limit` or `signal`: work remains, and
  `continuation.task.json` is required. The process exits zero so this intentional
  task boundary can return its artifacts.
* `error`: a worker or validation failure prevented certification. The cursor does
  not advance past that fiber. The process exits 2; preserve failure artifacts,
  diagnose the cause and then resume. A configuration error also exits 2.

**Process exit zero alone does not mean that a slice is complete.** CE orchestration
must retrieve and inspect `status.json` for every invocation. Ensure its failure
output collection also preserves `/local/output/` for nonzero exits. No silent
success state is substituted for a failed or interrupted fiber.

Resume on a new host by placing the retrieved `continuation.task.json` at the
next host's `/local/input/task.json`. It carries the next index and exact worker
SHA256, and uses the same logical task ID. Retain all earlier output batches:
continuation does not copy earlier hosts' hit files into the new output directory.
A reused existing output directory resumes automatically from its checkpoint.
Alternatively provide an original task plus a retrieved checkpoint:

```sh
python3 run_task.py \
  --task /local/input/task.json \
  --checkpoint /local/input/checkpoint.json \
  --output-dir /local/output
```

Checkpoints and status are written with `fsync` and atomic replacement. A hard
kill replays the interrupted fiber in full, plus any completed work since the last
durable checkpoint. Five seconds is the default checkpoint interval checked
between fibers; it is not a strict upper bound on lost work for one slow fiber.
A fiber in progress is never marked completed. New hit records are flushed to
disk before the corresponding cursor can advance. Replay into the same output
directory deduplicates by a certificate SHA256; interrupted trailing JSONL writes
are discarded and can be regenerated. Complete malformed records are treated as
errors. Resumption also rejects missing whole hit records when the recovered
unique count is below the retained checkpoint or status count. Aggregation across returned output batches must also deduplicate by
`certificate_sha256` and retain provenance. Read all status intervals to ensure
there are no gaps; never infer completed coverage from the absence of hits.

The supervisor rejects conflicting task identities, mismatched binary hashes,
unknown configuration keys, invalid decimal strings and overlapping use of one
output directory by two supervisors. The continuation is intentionally bound to
the binary that created it. If upgrading software, start a separately reviewed
campaign or explicitly reassess which intervals need rerunning.

## Exact certificate verification

The Python supervisor verifies every worker hit with standard-library integers
and `fractions.Fraction` directly in the original equation. This verification is
independent of the C++ continued-fraction implementation. A separate `verify.py`
is included for rechecking retrieved records; consult `python3 verify.py --help`
for bounds and input options. A rational square root is checked for nonnegativity
before the original unsquared equation is accepted, so an extraneous branch
cannot be reported as a solution.

Do not call a lack of hits a proof that the whole rectangle has no solutions.
The exact result of a completed campaign is coverage of its explicitly selected
rational fibers.
