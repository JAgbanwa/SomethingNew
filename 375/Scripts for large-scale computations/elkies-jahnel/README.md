# Exact Elkies--Jahnel backend for 375

This is a **separate C++17/GMP implementation of Elkies' geometric method**,
using the adaptive tiles, incremental lattice reduction and enumeration
structure described by Elsenhans and Jahnel. It searches primitive integer
cube representations directly. It does not require Magma and does not impose
the parent directory's `g = +/-1` restriction.

Use [gap-search](../../gap-search/CHARITY_ENGINE_HANDOFF.md) for the first
Charity Engine pilot. This backend provides complementary, exact cube-height
coverage and independent comparisons. It is a new reference implementation,
not the authors' optimized fixed-point code. Complete large height shells
remain expensive; small tests and short benchmarks do not establish a
practical full-shell completion time or a probability of finding a solution.

## What is searched

For a positive noncube target `K` (375 by default), at a sufficiently large
height every representation can be ordered as

```text
(a,b,-c) or (-a,-b,c), 0 < a <= b < c,
a^3 + b^3 - c^3 = +K or -K.
```

A task covers one finite shell/band:

```text
H <= c < 2H,
L <= (5H)*a/c < R,
```

with the global endpoint `R=4H` included. It uses exact integer/rational
comparisons. The proved lower ratio index is

```text
floor(5 * ceil_cuberoot(3H^2 - 3H + 1 - K) / 2).
```

The planner starts every new shell at the tighter, proved upper index

```text
R0 = min(4H, floor_cuberoot(floor(125*(H^3 + K)/2)) + 1).
```

Indeed, `a<=b` implies `2a^3<=c^3+K`. Since `c>=H`, the ratio index
`j=(5H)*a/c` satisfies `j^3<=125*(H^3+K)/2`. The `+1` retains candidates
exactly at an integer cube-root bound because an ordinary task's upper
endpoint is excluded. The existing global endpoint `4H` remains inclusive;
at `H=25,K=375` the boundary representation `(20,20,-25)` is retained.
When `R0<4H`, every omitted index at or above `R0` is proved infeasible.
At large heights the starting ratio is near `2^(-1/3)`, about `0.793700526`,
instead of an empty stretch starting at `0.8`.

Existing tasks and cursors through `4H` remain valid. An explicit
`--right-index` is also retained if it lies in the original valid region.
The tighter default changes which work is scheduled, not the worker's
acceptance rules.

The region proof requires `H>=25`, `125K<=3H^3`, and
`3H^2-3H+1>K`. The worker enforces these conditions. It covers both residual
signs and applies the coordinate gcd test. Heights and indices use arbitrary
precision integers; no fixed bit-width ceiling is imposed.

An individual work unit has a finite endpoint. The **overall planner has no
final height bound**. Each `plan` invocation writes one finite page and a
`next_plan.json` cursor, then exits. Following that cursor assigns the
remaining ratio bands and doubles H once the shell has been fully planned;
each new shell starts at `R0`. This does not mean its computations have
finished. A controller must run the tasks, resume partial work, and collect
their results before claiming coverage. Finite independent jobs support
distributed completion and retries without imposing a final campaign height.

## Mathematical implementation

Let `f(t)=(1-t^3)^(1/3)` on a ratio tile `[left,right]`, with midpoint `r` and
half-width `h`. Exact lower cube-root approximations have denominator
`Q=64H^2`. With `q0<=f(r)`, `qr<=f(right)`, and
`g<=(1-right^3-K/H^3)^(1/3)`, the code forms

```text
s = -r^2/q0^2
curvature = 2*right/qr^5
slope_error = 2*r^2/(Q*q0^3)
perturb = K/(3H^3*g^2)
shift = 1/(2Q) - curvature*h^2/4
E = 1/(2Q) + curvature*h^2/4 + slope_error*h + perturb
beta = q0 - s*r + shift
```

Taylor's theorem and concavity enclose both perturbed curves by
`|b/c-(s*a/c+beta)|<=E`. Thus the map

```text
(a,b,c) -> ((a-r*c)/(2Hh), (b-s*a-beta*c)/(2HE), 2c/H)
```

sends every possible tile solution into the closed squared-radius-3 ball
around `(0,0,3)`. The exact rank-three Gram--Schmidt enumeration includes
its boundary. For `K=+/-3 mod9`, the index-nine sublattice
`a=b=-c mod3` is encoded before reduction. LLL uses exact rational
arithmetic and an integral unimodular transform, reused between tiles.

Short inner intervals use cubic finite differences. Long intervals use an
exact integer polynomial solver: rational/integer bounds isolate derivative
roots, and the remaining monotone intervals are searched by integer binary
search. All roots of both cubic equations are retained; a zero polynomial
falls back to enumeration. No floating-point exclusion, pruning probability,
maximum-result cutoff or truncated integer arithmetic is used.

References:

- [Elsenhans--Jahnel, New sums of three cubes](https://wwwuser.gwdguser.de/~jjahnel/Arbeiten/elk_ants6c.pdf).
- [Author-linked implementation](https://wwwuser.gwdguser.de/~jjahnel/Arbeiten/Software/Elkies_allg.tar.gz).

This source implements the mathematics independently; it is not a copy of
the historical implementation. The rational enclosure and long-interval
polynomial shortcut are adaptations for an exact fixed-target search.

## Build and validate

Requires C++17, GMP development headers/libraries, GNU Make and Python 3.9+
on Linux/POSIX (the runner uses `fcntl.flock` for exclusive result ownership).

```sh
make
make test
```

Tests include independent exhaustive small shells, primitive positive and
negative controls, ratio and height boundaries, width invariance, tile-boundary
continuation, the known huge nonprimitive 375 example, height `10^40`, and
polynomial roots beyond 50 digits. The tighter planner bound is checked
against exhaustive small shells, an exact interior cube-root boundary, the
inclusive global endpoint, and advancement to later shells. Pipeline tests
exercise nonempty results,
separate continuations, missing terminal records, changed binaries, invalid
hits and mixed-version collection.

The large 375 example is a regression fixture with gcd 5. It is never counted
as a newly discovered primitive representation.

## Plan a bounded pilot, then keep extending

For illustration, start a short page at cube height `10^14`:

```sh
python3 ej375.py plan --campaign-id ce375-ej-pilot --height 100000000000000 \
  --grid-span 1000 --page-size 2 --output-dir pilot
```

The height is a selectable starting region, not a required solution magnitude
or a final search limit. No fixed lower or upper size cutoff was requested.
This cursor visits that shell and then higher shells; regions below the chosen
start need their own planned coverage if they are to be included. Starting
elsewhere changes the assigned work, not the solution-acceptance criteria.
The first task begins at the proved feasible upper edge described above.
Being in that region permits solutions; it does not guarantee a hit.

`grid-span` is the integer ratio-index width of each task, not a coordinate
bound or a promised runtime. Calibrate it on the intended worker hardware.
`tile-scale` changes the subdivision and performance, not the covered region.

Run each task using the names in `pilot/page.json`:

```sh
for task in pilot/tasks/*.json; do
  id=$(basename "$task" .json)
  python3 ej375.py run --task "$task" --output-dir "results/pilot/$id"
done
python3 ej375.py collect --page pilot/page.json --results results/pilot \
  --output-dir collected --require-complete
```

Generate the next page from the saved planning cursor, and repeat as long as
desired. There is no terminal shell in the cursor:

```sh
python3 ej375.py plan --cursor pilot/next_plan.json --output-dir next-page
```

Keep a separate result root for each page, such as `results/pilot` and
`results/next-page`. The collector rejects unrelated tasks instead of silently
mixing pages. Retain each page manifest and its collection summary.

Optional `--max-tiles` and `--deadline-seconds` cause explicit partial results,
not a claim that the full assigned band is complete. Signals finish the
current tile. Checkpoints normally cover batches of 100 completed tiles
(`--checkpoint-every`); a hard interruption can require replaying the
uncheckpointed batch. A final terminal record always commits the remaining
completed tiles.

## Resume and collect

Run the same task again in the same output directory to resume. A changed
task or binary is refused. Alternatively run `continuation.task.json` in a
new directory and retain **all** partial and continuation result directories.
The collector verifies their parent task, exact intervals and binary hashes;
receiving only a final continuation cannot fill an earlier missing interval.
Each runner holds `runner.lock` exclusively for its result directory. A second
runner fails before modifying task, status, checkpoint or hit files, including
when a controller has died but its original worker runner is still alive.

Pin `--worker-sha256` during planning, and/or supply
`--expected-worker-sha256` to collection. A page cannot mix binaries.
`status.json` distinguishes `complete`, `partial` and `error`. An unexpected
exit, malformed terminal record, wrong scope or invalid hit is an error.
Rejected result directories contribute no accepted coverage.
Successful complete/partial results must include `hits.jsonl`, including an
empty file when no hit was found. Its number of unique verified triples must
match the saved status count. Missing or truncated hit artifacts contribute
no coverage, and a rerun refuses to overwrite a successful status whose
saved artifacts fail these checks. Running/error states remain resumable
under the normal crash-replay rules.

Collection writes exact verified hits and a coverage/gap summary. Counts of
`lattice_points` include intervals covered algebraically by the cubic solver;
they are not counts of individual cube evaluations. Arbitrary task repartition
changes the tile geometry and therefore may change these counts. Compare hits
and region coverage across different partitions; counters are additive when
resuming at the actual saved tile boundary.

`ce375-ej-*` schemas are deliberately incompatible with both `ce375-gap-*`
and the parent fixed-g schemas. Never merge these coverage claims by merely
matching their target constant.

## Original equation and notation

For a reported cube triple `(u,v,w)`,

```text
n = (u+v+w-3)/6
M = -v-w, Y = w-v
m = M/2, y = Y/2.
```

Here `n` is the original conversation's integer `x`; the parent directory's
rational `x` is the conversation's `m`. Each hit contains exact original-point
mappings for both charts and the available signs of `y`. The integer point-gcd
is `gcd(n,m,y)`; the half-chart test is `gcd(M,Y)`. These point conditions are
reported separately from coordinate-gcd primitivity.

The native campaign searches all primitive cube representations in its region,
including all-odd cube triples. Odd `M,Y` correspond to the half chart. The
discussion's `10^14` was an example search area. It supplies no lower or upper
acceptance threshold for `n`, `m`, `y`, or the cube coordinates. The converter
reports qualifying points at every magnitude found in the assigned region;
there is no `|n|>=10^14` acceptance filter or derived mandatory starting height.

## Container contract

The Dockerfile builds/tests this backend independently. Its default command is

```text
python3 /app/ej375.py run --task /local/input/task.json --output-dir /local/output
```

This provides a container interface for comparison pilots; it is not a claim
of an already accepted Charity Engine application. Build and test the image
on the agreed architecture, pin its digest, benchmark job size, and confirm
partial-output/retry behavior before a remote allocation. No job is submitted
by the planner or runner.
