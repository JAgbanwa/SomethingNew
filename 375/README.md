# Choosing a search for 375

**Use [`gap-search/`](gap-search/) for the first Charity Engine pilot.** It has a
compiled C++/GMP worker, finite task manifests, restartable runs, exact hit
verification, collection of covered intervals, and sampled reruns. Start with
the local/container pilot in
[`CHARITY_ENGINE_HANDOFF.md`](gap-search/CHARITY_ENGINE_HANDOFF.md); a production
campaign still needs a measured task size and an agreed deployment environment.

For an automatically continuing **local** search, use
[`search375.py`](search375.py) and the [continuing-search guide](CONTINUING_SEARCH.md).
It runs finite EJ jobs, resumes partial attempts, validates returned coverage,
and stops on the selected number of qualifying primitive triples. Its default
interleaved schedule revisits unfinished shells while opening higher ones;
there is no final height bound. It does not submit CE jobs.

The three search paths have different mathematical scopes:

| Path | What it searches | Recommended role |
| --- | --- | --- |
| [`gap-search/`](gap-search/) | Primitive integer representations of `u^3+v^3+w^3=375`, within assigned intervals of the cancellation gap `delta` and an explicit coordinate-to-gap ratio cap | First CE pilot and candidate discovery campaign |
| [`Scripts for large-scale computations/elkies-jahnel/`](Scripts%20for%20large-scale%20computations/elkies-jahnel/) | The complementary Elkies–Elsenhans–Jahnel approach, using lattice enumeration near the cubic curve in assigned cube-height shells and ratio tiles | Height-based coverage, an independent comparison, and a baseline to benchmark before considering a large campaign |
| [`Scripts for large-scale computations/`](Scripts%20for%20large-scale%20computations/) | Reduced slopes `p/q` with only `g=-1,+1`, enumerated by `H=max(abs(p),q)` | Exact statements about this restricted family and cross-checks of its points |

The new Elkies–Jahnel subdirectory does not change the fixed-`g` engine in its
parent directory. It is not a claim that either method is faster on the intended
CE hardware. Compare measured cost and actual mathematical coverage before
moving compute between them.

## Keep the variables straight

The repository writes the original equation as

```text
y^2 = (x+6n+3)^2 + (36n^3+54n^2+27n-58)/x.
```

In the original discussion the integer variable was called `x` and the rational
parameter was called `m`. Their correspondence is:

| Original discussion | Equation notation in this repository |
| --- | --- |
| integer `x` | `n` |
| rational `m` | `x` |
| `m=M/2` | `x=X/2`, so `X=M` |
| `y=Y/2` | `y=Y/2` |

The value `10^14` mentioned in the discussion is an **example search area**.
No fixed lower or upper size cutoff was requested for the original variables.
Do not add `abs(n)>=10^14`, or any other magnitude threshold, to the acceptance
criteria on that basis. Original integer `x` is repository `n`; a separately
requested sign, parity, or size condition would need to use that correspondence.

For an integer cube triple, choose a permutation `(A,B,C)` and reconstruct

```text
n = (A+B+C-3)/6,
x = -(A+B)/2,
y = +(A-B)/2 or -(A-B)/2.
```

For target 375 the first expression is integral. Odd `X=2x` and `Y=2y` give the
half-integer chart from the original request. Integer cube primitivity means
`gcd(A,B,C)=1`; a separate condition such as `gcd(X,Y)=1` must be checked on the
reconstructed point. Cube height `max(abs(A),abs(B),abs(C))` and `abs(n)` are
different quantities. Task ranges determine which region is being examined;
they do not impose an additional magnitude condition on a returned solution.

## Why the fixed-`g` parent engine is not the general search

Its current production contract is exactly `g in {-1,+1}`. The raw diagnostic
solver is not an expansion of that contract. The normal enumerator accepts
slope heights through `200000000`; its reconstruction gives `abs(x)=q/2`, hence
repository `abs(x)<=100000000`. Increasing the number of workers does not remove
either the unit-`g` restriction or the supported height limit.

Historical estimates comparing a general-`g` slope search against the gap search
describe an earlier search scope. They are not measured discovery probabilities
for this fixed-`g` implementation. See each engine's own coverage statement.

## An indefinite campaign still uses finite jobs

The supplied `search375.py` controller keeps issuing and validating finite EJ
work units until its goal is met or execution is paused. The standalone backend
planner only emits a page; its cursor tracks planned work, not verified
execution. Following
[CE's published guidance](https://www.charityengine.com/docs/pages/18677766/Computing%2Bwith%2BCharity%2BEngine),
individual jobs should finish a specified interval and return evidence of which part
completed. The controller then validates outputs, resubmits gaps, and creates
the next units. This preserves an open-ended overall search without sending a
single never-ending process to every device.

The current gap worker has explicit supported arithmetic limits and a finite
ratio cap per task. Merely extending its gap interval with a fixed ratio cap is
not complete coverage of every possible cube triple. Expanding the search
requires a recorded schedule of regions and, eventually, checking the worker's
supported limits. The Elkies–Jahnel backend offers a complementary height-shell
organization; finite completed shells are still required for a coverage claim.

## Before committing a large allocation

Use the handoff guide to establish a clean image build, a reproducible pilot,
task timing on the intended CPU class, exact result verification, and a restart
and retry contract. Pin the source commit, worker hash, and container digest for
each campaign. No job is submitted by generating a campaign manifest or by
running the local pilot.

The currently unsearched frontier for primitive 375 needs an identified source
and a precisely stated region. A planner's `--frontier` value is an assumption,
not a verified exclusion result. Published historical height bounds, recent
gap searches, and illustrative starting regions are not interchangeable.
The repository's probability calculations are heuristic planning aids, not
measured discovery rates or guarantees of a solution.

The Magma implementation can remain an independent reference on licensed
machines. Its [installation guide](https://magma.maths.usyd.edu.au/magma/faq/install)
describes a computer-specific pass file. Deploying Magma itself across CE workers requires a confirmed license
and runtime arrangement; the compiled C++/GMP workers avoid assuming that such an
arrangement already exists.
