# Continuing search for a primitive representation of 375

`search375.py` is a local coordinator around the exact Elkies--Jahnel worker.
It creates finite jobs, executes them, resumes partial attempts, independently
collects their results, and continues until the requested number of qualifying
cube triples is found or execution is paused. It has no final height bound.
It does not submit Charity Engine jobs or publish container images.

## Start and resume

From the repository root, build the native worker and start:

```sh
make -C '375/Scripts for large-scale computations/elkies-jahnel'
python3 375/search375.py start --output-dir search-375
```

The default goal is one primitive cube triple that supplies the original
half-integer chart: integer original `x`, `m=M/2`, `y=Y/2`, and odd `M,Y`.
No magnitude cutoff is imposed on the returned variables. Point primitivity
`gcd(M,Y)=1` is an additional optional condition, enabled only by
`--primitive-point`. Both signs of the original `y` are recorded; they count as
one cube triple, not two discoveries.

To stop on any primitive cube representation, including all-odd triples that
only supply integer charts, use `--chart any`. Every primitive cube discovery
is printed and saved in `cube_solutions.json` even when it does not match the
selected chart. `solutions.json` contains the qualifying subset.

Press Ctrl-C to pause. The active runner finishes its current native tile,
validates partial results and saves its checkpoint. Resume with:

```sh
python3 375/search375.py resume --output-dir search-375
```

`--solutions N` specifies the number of distinct qualifying triples; zero
keeps searching after discoveries. On resume, this option may increase the
goal or set it to zero. A previously satisfied goal does not launch more work
unless its solution target is changed.

## How the search visits large heights

The default initial shell is `H=25`. The controller also performs exact
enumeration of the finite exception `max(abs(cube coordinates))<25`: its only
375 triple is `(5,5,5)`, which has gcd 5. The lattice construction covers
subsequent shells `[H,2H)`.

The default `--schedule interleave` visits shell levels in diagonal rounds:

```text
round 0: level 0
round 1: level 1, level 0
round 2: level 2, level 1, level 0
round 3: level 3, level 2, level 1, level 0
```

Level `j` means `H=initial_height*2^j`. Each visit completes one finite ratio
band; completed shells are skipped. Thus unfinished shells keep receiving
work while larger shells are introduced. Every fixed shell receives further
visits until its finite bands finish, provided execution continues and each
job finishes. This is a deterministic coverage schedule, not a prediction of
which region has the highest discovery probability.

`--schedule sweep` completes one shell before advancing to the next. That
mode is useful when the priority is a contiguous completed height range.

`--height H` chooses a different starting region. For example, to investigate
a large region immediately:

```sh
python3 375/search375.py start --output-dir large-region \
  --height 1000000000000000000 --grid-span 100000
```

That number is illustrative. Starting there does not establish coverage of
the skipped shells below it. It also imposes no final upper bound or extra
magnitude filter on a solution found in the assigned regions. The shell upper
ratio is calculated from the exact feasible bound; the old empty prefix near
`a/c=0.8` is no longer scheduled by default.

## Finite pilots and execution budgets

These options pause the invocation while preserving the continuing search:

```sh
python3 375/search375.py start --output-dir pilot \
  --height 1000000000000000000 --grid-span 100000 \
  --max-tasks 12 --max-seconds 90
python3 375/search375.py resume --output-dir pilot
```

- `--max-tasks N`: pause after N additional **validated completed tasks**.
- `--max-attempts N`: pause after N worker attempts, including partial ones.
- `--max-seconds T`: cooperative time budget for this invocation.

Zero disables each execution budget. These are not mathematical search bounds.
The time budget includes planning and validation; a native tile already in
progress may finish after the requested time.

Each task attempts at most 1000 native tiles by default. This provides regular
checkpoint and acceptance opportunities. `--task-max-tiles 0` removes that
per-attempt tile budget, while the assigned ratio band remains finite. Partial
attempts are resumed automatically; they are not credited as full jobs.

## Exact acceptance and accounting

The coordinator and backend verify the cube identity and three-coordinate gcd
using exact integers. The original-equation reconstruction is checked with
exact rational arithmetic. The task and worker identity are checked before
accepting results. Repeated hits and the two signs of `y` cannot inflate the
distinct-triple count.

A planned page is never counted as completed coverage. The coordinator first
collects the actual result, verifies its returned artifacts and hit counts,
and requires complete coverage of that job. It then writes a self-contained
receipt before advancing the search cursor. Receipts contain the assigned
task, checkpoint, binary identity, and all verified cube hits; they form an
ordered hash-linked journal. Resume rebuilds scheduling progress from those
receipts and refuses a mismatched cursor or corrupted history.

If a qualifying hit occurs in valid partial output, the goal may be satisfied
while that task remains pending. The remaining band stays uncredited and is
available if the search is resumed with a larger goal.

## Files and recovery

| File | Meaning |
| --- | --- |
| `state.json` | Authoritative scheduler state, pending job, progress and discoveries |
| `solutions.json` | Exact triples and reconstructed points matching the selected goal |
| `cube_solutions.json` | Every primitive cube triple found, including other charts |
| `jobs/*/page/` | The assigned finite task and page manifest |
| `jobs/*/result/` | Backend output, checkpoint, status and native records |
| `jobs/*/collected/` | Independently checked result and finite-region coverage |
| `jobs/*/receipt.json` | Durable completed-job record |
| `controller.log` | Planning, execution and collection diagnostics |

State and receipts use fsynced atomic replacements. A crash after receipt
creation but before cursor advancement replays the accounting once, without
repeating a completed worker run. Interrupted native work resumes at its
last verified tile checkpoint.

The coordinator has an exclusive campaign lock; each backend runner also has
an exclusive result-directory lock. If the coordinator is killed while its
runner survives, a resumed coordinator waits for that runner instead of
launching an overlapping writer. Execution budgets can pause that wait.

The executable is pinned by SHA256. A changed worker is refused before any
saved result is overwritten. Keep the source commit and dependency/build
record with the campaign; do not mix releases or discard its receipts.

`state` is `found`, `paused`, `running`, or `error`. A normal pause exits zero;
an error exits nonzero. Neither is a claim that an unbounded mathematical
search has been exhausted. The output gives the exact completed bands and
the still-pending work.

## Validation and computational limits

The finite controller tests use the primitive positive control
`(-46)^3+(-67)^3+74^3=7125` at `H=70`, plus target 375 negative controls.
They exercise automatic partial continuation, exact stopping, diagonal
coverage, receipt/state crash recovery, corrupt artifacts, changed binaries,
Ctrl-C/SIGTERM and a killed coordinator with a surviving runner. They do not
claim a new primitive solution of 375.

Arbitrary-precision coordinates and an open-ended scheduler do not guarantee
a practical completion time or the existence of a qualifying solution. Large
shells contain many finite bands. Benchmark the chosen worker and task size;
retain the exact regions and results of every completed job.
