# CE390: rational-d search with an 1,800-core-hour project limit

**Current target:** find a rational `d` and an integer `n = 1 (mod 3)` such that

```text
x = X/2,  X odd,
y = sqrt((x+6n)^2 + (36n^3-65)/x) = Y/2,  Y odd and Y > 0,
36n^3 - 65 = -2*d*x^2*(y - (x+6n)).
```

Both signs of `n` and `X` are searched. All accepted values use exact arithmetic.
There are no prescribed lower or upper coordinate ranges for `n` or `x` in
this workflow. The old large coordinate rectangles are historical fixtures.

The project allowance is **1,800 aggregate core-hours**. The other **200 hours
are reserved for other projects** and are never available to this campaign.
The default plan allocates an estimated 1,600 hours of search within the 1,800-hour
ceiling, leaving 200 hours of project headroom. Headroom, retries, calibration,
and continuations must all fit inside 1,800; they do not borrow the other projects'
200 hours.

## Search scope

The engine enumerates reduced fractions `d = p/q`, `q > 0`, in increasing height
`H(d) = max(abs(p), q)`. Each fraction gives the exact Thue equation

```text
72*n^3 - 12*p*q*n*g^2 + p*q*(p+q)*g^3 = 130,
x = -q*g/2,
Y = (2*p+q)*g - 12*n.
```

It retains `q*g` odd and `Y > 0`. The reconstructed integer cube components
`A = -x+y`, `B = -x-y`, `C = 2*x+6*n` satisfy `A^3+B^3+C^3 = 390`.
That identity implies `n = 1 (mod 3)`; the production verifier also checks it
explicitly. The mathematical reduction and congruence proof are in
[D_FIRST.md](D_FIRST.md).

The fast solver's default coverage is **`1 <= abs(g) <= 10^100`**. Therefore
`abs(x) <= q*10^100/2` for each tested fraction. Removing the coordinate
rectangle does not remove this limit or the finite rational-height range.
Completed coverage means the assigned heights and the recorded `g` bound;
it does not establish global nonexistence or promise a discovery within the
budget. `tools/certify_d.gp` can instead certify individual fractions with
PARI's unconditional, unbounded Thue solver.

## Stronger modulo-4 exclusion

For odd `m` (including production `m=65`), the half-integer target requires

```text
p*(p+q) = 2 (mod 4).
```

This follows directly from the Thue equation modulo 4, since `q` and `g`
are odd. If `p` is odd, it requires `p = q (mod 4)`; if `p` is even, it
requires `p = 2 (mod 4)`. It is applied before expensive solving in the native
worker, independent Python filter, and PARI certification helper. Signed
numerators use mathematical nonnegative residues. Even-`m` validation modes
do not inherit the odd-`m` exclusion.

Through height 120, this strengthens the historical admissible count from
789 to **517**, excluding 272 extra fractions without excluding any of the
seven recorded `k=6` known-answer certificates. Candidate-count savings alone
are not a runtime estimate. Short, same-host
native comparisons of versions 1.0.0 and 1.1.0 also found lower elapsed time
with the new filter; see [the recorded samples](validation/dfirst-v1.1/benchmark.json).
Those unrepeated shared-host samples do not establish production throughput.
The default planning rate remains a conservative 4.5 microseconds per raw pair.
See [D_FIRST.md, section 3](D_FIRST.md#3-which-d-need-to-be-tried-proved-filters).

## Build and generate the budgeted campaign

Run from this directory with Python 3.10+, a C++17 compiler, GNU Make, and GMP
headers/libraries (`libgmp-dev` on Debian/Ubuntu):

```sh
sha256sum --check SHA256SUMS
make -j2
make test
# Preview the default scope and budget without writing task files.
python3 d_campaign.py --campaign-id ce390-dfirst-1800 \
  --output-dir dfirst-tasks --plan-only
# Materialize the same explicit budget profile.
python3 d_campaign.py \
  --campaign-id ce390-dfirst-1800 \
  --budget-core-hours 1800 \
  --planned-core-hours 1600 \
  --us-per-pair 4.5 \
  --g-max-digits 100 \
  --output-dir dfirst-tasks
```

Without `--h-stop`, the generator derives the largest height fitting the
estimated-work allocation. At 4.5 microseconds per raw pair and 1,600 planned
hours, that is **`H <= 799999`**, or the half-open range `[1, 800000)`.
This default plan writes 1,901 task files and estimates 1599.997 search hours.
The exact pair count is `2*H^2 + H`; `H=800000` would cost 1600.001 estimated
hours. This is a scheduling estimate, not a promised runtime. A different
measured rate changes the derived height. Explicit `--h-stop` remains available
for smaller pilots or deliberately selected ranges.

Generation writes tasks and `page.json`; it does not start computation or submit
Charity Engine jobs. A generation command alone does not enforce runtime usage.

## Run with the project ledger

The serial controller requires Linux CPU-affinity support and pins each runner
and its worker to one available CPU. It enforces the page's project ceiling
across its launches:

```sh
python3 run_d_campaign.py \
  --page dfirst-tasks/page.json \
  --output-dir dfirst-results \
  --max-attempts 1
```

This runs at most one attempt as a pilot. Inspect its returned status and timing,
then continue the same campaign and ledger:

```sh
python3 run_d_campaign.py \
  --page dfirst-tasks/page.json \
  --output-dir dfirst-results
python3 collect_d.py \
  --page dfirst-tasks/page.json \
  --results-dir dfirst-results \
  --output-dir dfirst-collected
python3 verify_d.py dfirst-collected/hits.jsonl --m 65
```

The controller keeps `budget.json` in the results directory, reserves the full
possible attempt allowance before launch, and charges elapsed time after the
process has terminated. Continuations and retries are new charged attempts.
Its lock excludes a second controller on the same results directory. An
unresolved crash reservation remains held against the allowance and blocks automatic restart until
reconciled; it is never silently refunded. Keep the original page and results
directory together. Creating another results directory is another ledger, not
permission to spend another 1,800 hours. Changing the immutable page requires
a new plan whose budget is no greater than the project allowance left after
all earlier work; preserve the old ledger as part of that accounting.

The ledger accounts a serial one-worker invocation as one core times elapsed
wall time, including its shutdown allowance. Direct invocations of
`run_d_task.py` and independent distributed CE submissions bypass this local
controller. Their actual resource or provider charges must be reserved and
reconciled centrally within the same project allowance; see
[CE_OPERATIONS.md](CE_OPERATIONS.md). A provider's two-hour reservation is not
necessarily one search core-hour.

## Container and task entrypoint

Use a rebuilt, tested image from this source. With a d-first task staged as
`/local/input/task.json`, the default container command and the explicit CE
command both run:

```text
python3 /app/run_d_task.py --task /local/input/task.json --output-dir /local/output
```

The input must be an individual d-first task, not `page.json`. The container's
argument-only invocation also selects `run_d_task.py`. Explicit historical
commands remain available to reproduce old task definitions.

For build, pilot, release, and output-handling instructions use
[CONTAINER.md](CONTAINER.md) and [CE_OPERATIONS.md](CE_OPERATIONS.md).
A source change does not update an already-published image or a submitted job.

## Evidence and documentation

The committed `validation/dfirst/` results are historical measurements for the
prior filter: heights through 20,000 yielded no point at `G=10^100`, and the
PARI records certified heights through 120 without a `g` bound. Their original
counts and hashes are retained. Do not relabel them as runs of the strengthened
filter. Use current test output and a newly measured pilot for this version.

| Document | Purpose |
| --- | --- |
| [D_FIRST.md](D_FIRST.md) | Exact reduction, filters, solver scope, historical evidence, budget formula |
| [CE_OPERATIONS.md](CE_OPERATIONS.md) | Project accounting, external tasks, continuations, exact coverage |
| [CONTAINER.md](CONTAINER.md) | Build, validate, select, and deploy the matching container |
| [examples/README.md](examples/README.md) | Generate current d-first pilots; identify historical examples |
| [HISTORICAL_RECTANGLE_SEARCH.md](HISTORICAL_RECTANGLE_SEARCH.md) | Archived coordinate-rectangle README |
| [HISTORICAL_CE_OPERATIONS.md](HISTORICAL_CE_OPERATIONS.md) | Archived rectangle campaign operations |
| [HISTORICAL_CONTAINER.md](HISTORICAL_CONTAINER.md) | Archived rectangle container guide |

The `campaign.py`, `xy_campaign.py`, and `cube_campaign.py` interfaces and their
fixtures are retained for explicit historical use. They are not the production
entrypoint or budget plan for this half-integer d-first campaign.
