# CE390: variable-a/q search with integer cube components

**Current target:** an exact-arithmetic, parameterized search for integer triples
whose cubes sum to 390, using rational auxiliary coordinates and rational `d`.
**Neither `a=1` nor `a=2` is fixed.** New `cube_campaign.py` tasks vary both `a`
and `q` through the interleaved ordering described below.

Documentation checked against implementation commit
[`1d82c1a841120ca9a496428967f7bd5a9ed54f04`](https://github.com/JAgbanwa/SomethingNew/commit/1d82c1a841120ca9a496428967f7bd5a9ed54f04)
on 16 October 2026. Native `xy_cf_worker` version: **1.1.1**.
The historical integer search is a separate interface, not the default example
for this corrected target.

> This is a research computation, not a claim of a solution, a formally verified
> search algorithm, or a demonstrated improvement over established methods.
> A finite task covers only its assigned parameter indices. Successful execution
> does not prove the absence of missed cases in the mathematical reduction.

## 0. d-first engine for the half-integer target (recommended)

[D_FIRST.md](D_FIRST.md) adds a second engine, `bin/dthue_worker`, that
**enumerates rational `d` directly** for the half-integer target
(`x = X/2`, `y = Y/2`, `X, Y` odd). For `d = p/q` in lowest terms, such points
are exactly the integer solutions `(n, g)` of one Thue equation

```text
72 n^3 - 12 p q n g^2 + p q (p+q) g^3 = 130,   q g odd,   (2p+q) g > 12 n,
```

with `x = -q g/2` and `y = ((2p+q) g - 12 n)/2`. Each `d` is solved completely
for `1 <= |g| <= 10^100`, which covers the 10^43–10^45 / 10^53–10^55
rectangle for that `d`. The worker visits `d` in order of height
`max(|p|, q)`, so a finished campaign proves a cumulative statement of the
form "no such point for any `d` of height at most H".

Proved filters on `p` and `q` remove about 98 % of pairs. One core handles
about 4,700 admissible `d` per second, so all `d` up to height about 950,000
cost about 2,000 core-hours. The k = 6 version of the same code recovers all of
its known half-integer points, and its Thue solutions agree with PARI's
unconditional `thue()` on 1,934 equations. For k = 390, every `d` up to
height 20,000 (14,168,321 admissible values) has been checked with no point
found, and every `d` up to height 120 has been certified with no bound
(`validation/dfirst/`). The rectangle search below is unchanged.

```sh
python3 d_campaign.py --campaign-id ce390-dfirst-001 --h-start 1 --h-stop 300001 --output-dir dfirst-tasks
python3 run_d_task.py --task dfirst-tasks/task-000000-*.json --output-dir out/t0     # CE: /app/run_d_task.py
python3 collect_d.py --page dfirst-tasks/page.json --results-dir out --output-dir collected
```

## 1. Mathematical objective and notation

Find rational `n,x,y,d`, with `x != 0`, satisfying

```text
36*n^3 - 65 = -2*d*x^2*(y - (x+6*n)),
y = sqrt((x+6*n)^2 + (36*n^3-65)/x),   y >= 0,
den(n) in {1,2,3,6},   den(x) = den(y) = b >= 1,
A = -x+y in Z,   B = -x-y in Z,   C = 2*x+6*n in Z.
```

Here `den` means the positive denominator **after reduction to lowest terms**.
Both signs of `-x +/- y` must be integral at the same solution. The letters
`A,B,C` denote the integer cube components; they are not the auxiliary `x,y`.
The radical identity gives

```text
A^3 + B^3 + C^3 - 390
  = -6*x*(y^2 - (x+6*n)^2 - (36*n^3-65)/x) = 0.
```

Adding and subtracting `A,B` gives `2*x=-(A+B)` and `2*y=A-B`, with matching
parities. Thus there are exactly two coordinate-denominator cases:

| Case | Coordinates | Common reduced denominator |
| --- | --- | --- |
| Integer | `x,y` are integers; `y >= 0` | `b=1` |
| Half-integer | `x=X/2`, `y=Y/2`, with `X,Y` odd and `Y>0` | `b=2` |

Moreover, cubes modulo 9 force `A=B=C=1 mod 3`, and parity forces `A+B+C` even.
Therefore `n=(A+B+C)/6` is integral. This is a consequence of the full target,
not an assumed exclusion. Tasks still explicitly allow `n` denominators
`[1,2,3,6]`; the verifier checks the derived integrality of accepted `n`.
See [INTEGER_COMPONENTS.md](INTEGER_COMPONENTS.md) for the derivation.

The code searches coordinates through auxiliary slopes and recovers

```text
d = -(y+x+6*n)/(2*x).
```

It does not separately enumerate a fixed list of rational `d` values. Both
integer and noninteger rational `d` are eligible unless `--noninteger-d` is
explicitly selected. All final candidates are checked against the original
unsquared equation, not just a transformed polynomial.

### Coordinate ranges are bounds on values, not unscaled numerators

| Quantity | Default scope |
| --- | --- |
| `n` | `10^43 <= abs(n) <= 10^45`, inclusive |
| `x` | `10^54 <= abs(x) <= 10^55`, inclusive |
| Signs | All four sign combinations of `n,x` (`--signs all`) |
| `y` | The nonnegative radical determined by `n,x`; no independent `y_min/y_max` |
| Additional coordinate congruences | None by default (`--congruence-policy none`) |

These are **selected research bounds**, not proved lower bounds for all possible
solutions to the integer 390 problem. No heuristic relation such as
`x ~ n^(5/4)` is imposed as an extra filter.

For scaling, write signed `k=6*n`, `X=b*x`, `Y=b*y`. The implementation uses
`6*10^43 <= abs(k) <= 6*10^45` and
`b*10^54 <= abs(X) <= b*10^55`. In the half-integer case, `X` is odd, so its
actual possible magnitudes run from `2*10^54+1` to `2*10^55-1`. Dividing by 2
returns the original coordinate-value interval. `Y` is reconstructed from the
radical and checked for oddness via its reduced denominator; it is not given
an independent search interval or assumed equal to `X`.

Custom magnitude endpoints must be positive integer strings. The current fast
enclosure requires `n_min>=2`, `x_min>6*n_max`, and a derived slope upper bound
below 2. Unsupported rectangles are rejected, not reported as completed empty
searches. See [XY_DENOMINATORS.md](XY_DENOMINATORS.md).

## 2. Both a and q vary during the search

The reduced auxiliary slope is

```text
a/q = abs(y/abs(x) - 1 + 6*n/x),   a,q>0, gcd(a,q)=1.
```

The full parameter enclosure is derived from the coordinate bounds. It includes
all integer numerators within its derived interval for each denominator, with
`q <= b*x_max`. There is no preferred numerator list, chosen solution-producing
`a` or `q`, or additional small-numerator ceiling.

`aq_traversal.py` provides the new mode **`n-sixths-xy-interleaved-aq-v1`**. It is
an exactly invertible permutation of the older increasing-q ranks, so it
changes the visitation order, not the enclosed set. A running task generates
pairs across that enclosure rather than exhausting a long initial `a=1` region.
Repeated numerators or denominators are still possible: neither parameter is
held fixed as an assumed location of a solution. This scheduling convention is
not evidence that a chosen pair contains a solution or that discovery becomes
more likely. The first eight pairs actually sent to the worker are logged.

The worker applies the continued-fraction search and exact exceptional-case
fallback described in [XY_DENOMINATORS.md](XY_DENOMINATORS.md), then verifies
reconstructed coordinates. The traversal does not brute-force the coordinate
rectangle. It continues after empty fibers or hits until the assigned slice
ends or the job is interrupted; it does not automatically run indefinitely
until a solution is found.

### Proven exclusions are not fixed parameter choices

For `b=2`, `X,Y` are odd and `k=6*n` is integral. Hence

```text
a/q = abs(Y-abs(X)+2*k*sign(X))/abs(X)
```

has an even reduced numerator and odd denominator. Both supervisor and worker
reject incompatible parity before continued-fraction work. **This does not
select `a=2`; eligible even numerators remain variable.**

The 733-prime obstruction sieve below 20,000 remains in use under the equal-x/y
proof: `q` divides `abs(X)`, and `X` divides `k^3-390`. For primes greater than 3,
`k^3=390 mod p` is equivalent via `k=6*t` to `36*t^3=65 mod p`. The cutoff limits
sieve primes, not `n,x,a,q`. All index exclusions retain normal checkpoint
advancement. Details and compatibility rules are in
[VARIABLE_AQ.md](VARIABLE_AQ.md).

### Use the correct interface and task mode

| Interface/input | Behavior |
| --- | --- |
| `cube_campaign.py` | Final integer-component target; interleaved by default; both `b=1,2` unless one is selected |
| `xy_campaign.py` | Broader historical interface; still q-major by default; needs **both** `--require-integer-components` and `--parameter-order interleaved` for this target/order |
| `campaign.py` / `run_task.py` / `run_task.sh` | Historical integer-coordinate search; not the new task interface |
| `examples/variable-aq-pilot/b2/` | Current 256-index interleaved validation task |
| `examples/integer-components-pilot/` | Historical 30,000-index q-major tasks; not silently converted |
| `examples/xy-pilot/`, `examples/xy-diagnostic/` | Broader rational targets without the final integer-component requirement |

The earlier b2 deployment pilots selected only `a=1`, which is incompatible
with the proven b2 parity. They tested execution, not representative target
fibers. Do not reuse those slices or their timing estimates as calibration for
the new mode. Interleaved unranking adds overhead and visits different-sized
parameters; measure this implementation separately.

## 3. Build and run a current small pilot

Run commands **from this computation directory**, with Python 3.10+, GNU Make,
a C++17 compiler and GMP development headers/libraries installed. Python tools
use the standard library; the native workers use GMP. On Debian/Ubuntu the
build dependencies are `python3`, `make`, `g++`, and `libgmp-dev`. A Docker build
installs its own dependencies.

```sh
sha256sum --check SHA256SUMS
make -j2
make test
```

On macOS, the checksum equivalent is `shasum -a 256 -c SHA256SUMS`. Use a compiler
and GMP installation for the same architecture; do not copy historical Intel
flags into a native ARM build without checking them.

Use fresh directories. This generates **one b2 task**, with 256 indices as a
small validation workload, not a bound on either `a` or `q`:

```sh
python3 cube_campaign.py --campaign-id ce390-variable-aq-pilot \
  --xy-denominator 2 --parameter-order interleaved \
  --candidates-per-task 256 --task-count 1 --seconds 3600 \
  --output-dir variable-aq-tasks
python3 run_xy_task.py \
  --task variable-aq-tasks/b2/task-000000000000-*.json \
  --output-dir variable-aq-results
python3 collect_xy.py \
  --page variable-aq-tasks/b2/page-000000000000.json \
  --results-dir variable-aq-results --output-dir variable-aq-collected
python3 verify_xy.py variable-aq-collected/hits.jsonl \
  --task variable-aq-tasks/b2/task-000000000000-*.json
```

The same task is supplied at
[`examples/variable-aq-pilot/b2/task-000000000000-ab2c4ea54bf6ebf3.json`](examples/variable-aq-pilot/b2/task-000000000000-ab2c4ea54bf6ebf3.json).
Before submission, check `fibers.mode` is `n-sixths-xy-interleaved-aq-v1`,
`search.require_integer_components` is `true`, and `search.xy_denominator`
is the intended case. A different image alone cannot change an old task's mode.

### Generate separate jobs for both denominator cases

Omitting `--xy-denominator 2` generates **two tasks**, one per denominator:

```sh
python3 cube_campaign.py --campaign-id ce390-variable-aq-both \
  --parameter-order interleaved --candidates-per-task 256 \
  --task-count 1 --seconds 3600 --output-dir variable-aq-both
python3 run_xy_task.py --task variable-aq-both/b1/task-000000000000-*.json \
  --output-dir variable-aq-both-results/b1
python3 run_xy_task.py --task variable-aq-both/b2/task-000000000000-*.json \
  --output-dir variable-aq-both-results/b2
python3 collect_xy.py --page variable-aq-both/b1/page-000000000000.json \
  --page variable-aq-both/b2/page-000000000000.json \
  --results-dir variable-aq-both-results --output-dir variable-aq-both-collected
```

`--task-count` is **per denominator**. `--page-start` is a zero-based **task
ordinal**, not a coordinate, slope denominator, or candidate offset. For the
next page, keep the campaign, mode, bounds and task size fixed and use
`--page-start 1`; the manifest reports the next ordinal. Changing task size or
mathematical scope requires a separate campaign definition and explicit coverage
accounting. No generator submits jobs or allocates the manifest's total workload.

## 4. Outputs, checkpoints, and coverage

All retrievable files belong under `/local/output` on a CE host (or the chosen
local output directory). Preserve the entire returned directory for each
invocation, including failures and continuations.

| File | Meaning |
| --- | --- |
| `task.json` | Exact task and immutable mathematical policy used |
| `status.json` | Application state, actual elapsed time, covered intervals and counters |
| `run.log` | Progress plus up to the first eight dispatched `a,q` pairs per invocation |
| `hits.jsonl` | Exact rational certificates and recomputed integer cube components; may be empty |
| `checkpoint.json` | Next unfinished index and implementation/worker pins |
| `continuation.task.json` | Present when work remains; next-host input using the same implementation |
| `worker.stderr.log`, error JSON files | Worker or startup failure information, when produced |

A final-target certificate contains `n_num/n_den`, `x_num/x_den`, `y_num/y_den`,
`d_num/d_den`, and exact `cube_plus`, `cube_minus`, `cube_third`, `cube_sum` strings.
The verifier recomputes the radical, original equation, reduced denominators,
three integer components and their sum of cubes, which must equal 390. Verifying
an empty hit file alone says nothing about coverage.

`state: complete` certifies completion of the assigned suffix, not necessarily
possession of output from every preceding host. `state: partial` requires a
continuation; exit zero can represent this intentional boundary. Errors must
not be counted as completed fibers. Collect all preceding output batches with
the matching page manifests; the collector reports gaps and overlaps.

An index denotes a parameter pair, **not one coordinate pair**. Its accounted
category is one of `search_fibers_completed`, `non_coprime_skipped`,
`denominator_excluded`, `congruence_excluded`, or `bounds_excluded`.
`q_sieve_excluded` is a subset of `congruence_excluded`, not an additional total.
`denominator_excluded` also includes the b2 parity filter. `fibers_completed`
counts worker replies, not all processed indices.

The mode is part of task identity. Old and new indices are not interchangeable;
cross-mode samples may visit overlapping pairs. Keep their campaigns separate
and do not add their counts as though they were one contiguous traversal.
Continuations pin the worker and relevant Python source, including
`aq_traversal.py`; do not remove pins to force a resume under another version.

**Selecting both b cases covers all possible denominators, not all slopes or the
entire coordinate rectangle.** The raw b2 enclosure has about `4.536e101` indexed
pairs before filtering. Completing a small fraction of it is not an exhaustive
search or a bound on the time needed to discover a solution. Interleaving does
not shrink that set or establish a practical whole-domain search. Independent
review of the reduction, completeness argument and workload is still important.

## 5. Charity Engine: use the current runner, input, and image together

The checked interleaved implementation has a published Linux amd64 image at the
[release for source commit `1d82c1a...`](https://github.com/JAgbanwa/SomethingNew/releases/tag/ce390-container-1d82c1a841120ca9a496428967f7bd5a9ed54f04-38901247314-1),
with `ce390-linux-amd64.tar`, `container-evidence.zip`, and release `SHA256SUMS`.
This is a pinned known build, not a promise that every future `latest` release
has the same scope. Source and image checksums are separate manifests.

For that image, the CE **App** field is this single line:

```text
docker:ce390:1d82c1a841120ca9a496428967f7bd5a9ed54f04 https://github.com/JAgbanwa/SomethingNew/releases/download/ce390-container-1d82c1a841120ca9a496428967f7bd5a9ed54f04-38901247314-1/ce390-linux-amd64.tar
```

Stage one new-mode input as `task.json`, then set the in-container command to:

```text
python3 /app/run_xy_task.py --task /local/input/task.json --output-dir /local/output
```

When CE retains the input URL's long filename, use that exact basename after
`/local/input/` instead. Do not submit a page manifest as the task. Verify the
public input URL and keep submitted contents immutable. These paths and the
custom-image syntax follow [CE's input/output and application documentation](https://www.charityengine.com/docs/Computing%2Bwith%2BCharity%2BEngine).

**Do not use the historical `run_task.sh` command or `examples/general-pilot`
merely because an automatically generated release note or older deployment
page names them.** The container's no-argument entrypoint is intentionally still
the historical runner. The corrected target requires the explicit xy command.
For a local image build, use `docker build --platform linux/amd64 -t ce390-local .`;
record the tested image and use it consistently for a task and its continuations.

The internal budget defaults to 3,600 seconds; allow two external hours for
startup and returning outputs. With a one-hour external allowance, generate a
separate 3,000-second task instead. These are per-invocation budgets, not an
aggregate campaign cap or a guarantee of results within two hours of submission.
Keep platform elapsed time separate from application elapsed time. Source changes
do not alter previously submitted images or reservations. Review the offer and
cost before each CE submission; none is made by the search scripts.

## 6. Validation record and documentation map

For the variable-a/q implementation, [PR #6](https://github.com/JAgbanwa/SomethingNew/pull/6)
has successful [regression checks](https://github.com/JAgbanwa/SomethingNew/actions/runs/38898512469)
and a [dedicated variable-a/q container run](https://github.com/JAgbanwa/SomethingNew/actions/runs/38898512427).
The suite contains **217 tests**. In that run, the 256-index b2 task scheduled
256 distinct `a` and 256 distinct `q`; 31 pairs survived the preliminary filters.
The worker completed those searches and the collector checked the returned
coverage. No target solution was reported. The supplied
[preview](examples/variable-aq-pilot/preview.json) is diagnostic evidence, not a
preselected list governing the search.

The [main-branch image workflow](https://github.com/JAgbanwa/SomethingNew/actions/runs/38901247314)
also passed. Its container acceptance checks and the dedicated variable-a/q run
are distinct evidence. Inspect the exact run's logs and artifacts rather than
treating a document, an empty output, or a successful exit as proof of mathematical
completeness. Historical counts and benchmarks in `VALIDATION.md` and
`validation/` are version-specific, not the current traversal's performance.

| Document | Scope |
| --- | --- |
| [D_FIRST.md](D_FIRST.md) | d-first half-integer engine: Thue reduction, proofs, filters, validation, throughput |
| [VARIABLE_AQ.md](VARIABLE_AQ.md) | Current ordering, parity proof and index compatibility |
| [INTEGER_COMPONENTS.md](INTEGER_COMPONENTS.md) | Final target's integrality and cube identity; its old q-major examples are historical |
| [XY_DENOMINATORS.md](XY_DENOMINATORS.md) | Broader equal-x/y engine, enclosure and continued-fraction derivation |
| [INTEGER_COORDINATES.md](INTEGER_COORDINATES.md), [MATHEMATICS.md](MATHEMATICS.md), [Q_SIEVE.md](Q_SIEVE.md) | Historical integer interface and its mathematical assumptions |
| [CE_OPERATIONS.md](CE_OPERATIONS.md), [CONTAINER.md](CONTAINER.md) | Shared operational background; historical commands/pilot paths must not replace the current xy instructions above |

Neither the earlier equal-n/x proposal nor an unqualified rational radical is
this final target. Do not silently apply historical integer-only congruences to
fractions. Optional congruence policies and restricted q windows narrow the
search and must be stated explicitly. Current code, immutable task definitions
and the appropriate mode-specific proof take precedence over historical examples.
