# CE390 3.2.0 — exact continued-fraction search

Research compute package for the equation

```
36*n^3 - 65 = -2*d*x^2 * (sqrt((x+6*n)^2 + (36*n^3-65)/x) - (x+6*n))
```

**Target:** integers `10^43 <= abs(n) <= 10^45`,
`10^54 <= abs(x) <= 10^55`, with `n % 3 == 1`, `x % 12 == 5`,
`x % 7 != 0`; rational `d`. Bounds are inclusive and all large
numbers are decimal integer strings. The principal square root must be a
**nonnegative integer**. **All four sign combinations are searched by default:** `(+,+)`,
`(+,-)`, `(-,+)`, and `(-,-)`. Congruences apply to the signed integers;
for example, a negative `x` must still satisfy `x % 12 == 5`.
Outputs are written to **`/local/output/`**.

This release implements a targeted research search. It does **not** claim
that a solution exists in this rectangle, that the stated asymptotic scale is
a proven lower bound, or that a finite sample of rational parameters exhausts
the rectangle. No target solution is bundled or claimed.

## What is actually searched

Write `N=abs(n)`, `X=abs(x)`, `tau=sign(n*x)` and let `y` be the
principal square root. Every target solution has a unique reduced slope

```
a/q = abs(y/X - 1 + 6*n/x),     0 < a < q,
a and q odd, gcd(a,q) = 1.
```

For each explicitly assigned `(a,q)`, the native GMP engine considers
both `tau=+1` and `tau=-1` and solves

```
H_tau(N,X) = 36*q^2*N^3 + 12*q*(2*q+tau*a)*N*X^2
             - a*(2*q+tau*a)*X^3
           = sign(n)*65*q^2.
```

It computes certified continued-fraction convergents of the unique positive
root of each `H_tau(z,1)=0`, reconstructs the possible common divisor of
`(n,x)` by an exact perfect-cube test, and recovers both signs from the
polynomial residual. It computes `d=-(y+x+6*n)/(2*x)` and verifies every
candidate in the original equation.
It neither loops across the integer rectangle nor factors its 130-digit
values of `36*n^3-65`. All mathematical accept/reject decisions use arbitrary
precision integers. Timing measurements alone use floating point.

**Coverage guarantee:** a successfully completed fiber covers every target
solution with that auxiliary slope `a/q`, in the requested sign combinations
and magnitude bounds; a successfully completed task covers its assigned
fibers. A fiber does not fix `d` when `x<0`. A partial task does not certify
its unfinished fiber.
The proof, scope of the small-bound test fallback, and derivation are in
[MATHEMATICS.md](MATHEMATICS.md).

The worker, campaign generator, and independent verifier require an
**integer square root by default**, matching the clarified target.
With default options, each generated task explicitly records
`require_integer_sqrt: true`.
This condition gives integer cubes summing to 390. The exact check uses
integer/rational arithmetic, with no rounding tolerance.

`--allow-rational-sqrt` explicitly enables the broader exploratory mode.
Its fractional-radical hits are not solutions to the requested integer-radical
problem. Historical fractional-radical regression fixtures use this mode
only to test the underlying arithmetic and the rejection filter.

## Build and validate

A C++17 compiler, GNU make, GMP development libraries, and Python 3.10+ are
required. The Python tooling uses only the standard library. On a Debian or
Ubuntu build host, install `g++ make libgmp-dev python3`, then run:

```bash
make
python3 -m unittest discover -s tests -v
```

On your Apple Silicon Mac with **Intel GMP already installed under
`/usr/local`**, use:

```bash
export PATH="$(brew --prefix python@3.12)/libexec/bin:$PATH"
export CXX="clang++ -arch x86_64"
export CXXFLAGS="-O3 -std=c++17 -Wall -Wextra -Wpedantic"
export CPPFLAGS="-I$(brew --prefix gmp)/include"
export LDFLAGS="-L$(brew --prefix gmp)/lib"
export LDLIBS="-lgmpxx -lgmp"
make clean && make &&
"$(brew --prefix python@3.12)/bin/python3.12" -m unittest discover -s tests -v
```

Intel executables on Apple Silicon require Rosetta. With native ARM GMP
under `/opt/homebrew`, use `export CXX=clang++` instead. The configuration
above passed all 60 tests of version 3.1.0 on the user's Mac in 21.232 seconds.
The updated 3.2.0 suite must be rerun there. Local tests do not submit CE jobs.

See [VALIDATION.md](VALIDATION.md) for the checks actually run for this
release and the limits of that validation. `Dockerfile` supplies the same
build environment for Charity Engine. Native builds and container builds
are different validation claims; consult the release record before dispatch.

## Run independent jobs

Use [CE_OPERATIONS.md](CE_OPERATIONS.md) for exact job creation, command
lines, calibration, resumption, and collection. Each task uses one worker
process and one CPU core. Give every task an isolated `/local/output/`.
Choose its finite fiber count from measured throughput on representative
Charity Engine CPUs. Newly generated tasks default to a 3,600-second (one-hour)
soft search budget. Use a two-hour CE allowance (`--hours 2`) to leave time for
startup and output handling. Existing task JSON files retain their own budgets.

Each task records its input and exact coverage, checkpoints the next
uncompleted fiber, and writes a continuation when the soft deadline interrupts
it. Retrieve **all** output files, including empty hit files, completion
status, and continuations. An empty hits file by itself is not evidence of
complete coverage. A replay may repeat arithmetic; it must not advance the
coverage cursor past an incomplete fiber.

The campaign generator is paged: it writes only the requested job page.
Starting another numerator range or increasing parameter bounds creates a
new campaign; it must not silently redefine old task identities. No script
submits paid jobs or sends messages automatically.

`examples/pilot/` contains one small calibration task with its original
3,000-second budget. `examples/50min/`, `examples/60min/`, and `examples/100min/`
contain example first pages with those soft budgets;
their fixed counts are starting points to recalibrate, not promised durations.
Only the included page is assigned, not every task in its broader parameter
interval. Do not submit the overlapping example campaigns together.

The one-hour example changes the execution budget and campaign name only; it
retains the historical `a=1` selection and is not a general `a/q` campaign.
A longer task budget does not establish broader mathematical coverage or enforce
an aggregate 2,000 CPU-hour limit. See the one-hour instructions in
[CE_OPERATIONS.md](CE_OPERATIONS.md) before generating new task pages.

After retrieving pilot results into a directory such as `returned/`, run:

```bash
python3 collector.py --page examples/pilot/page-000000000000.json \
  --results-dir returned --output-dir collected
python3 verify.py collected/hits.jsonl
```

The collector validates task identities, checks certificates, merges returned
coverage intervals, and reports gaps. It exits 0 for complete selected-page
coverage, 2 for valid partial returns, and 1 for invalid data. An empty result
file is normal. To collect multiple pages, repeat `--page`.

## Choosing rational parameters

The supplied bounds imply approximately

```
12*10^-12 < a/q < 12*10^-9 + 37*10^-27 < 1.
```

For the integer-radical target, additionally `q` divides `abs(x)` and hence
`q <= 10^55`. The worker rejects larger denominators and candidates whose
`abs(x)` is not divisible by `q`. These necessary conditions preserve every
integer-radical target solution. Small numerators are a search preference, not a
completeness theorem or an evidence-based prediction of where a solution is.
You can search large decimal parameters; avoid describing a
small-numerator pilot as a comprehensive campaign. First benchmark a small
representative page, then agree a finite campaign and CPU budget with the
Charity Engine team. The files support such campaigns without asserting a
known practical route to a first solution.

**Upgrade from 3.1.0:** regenerate production tasks using the new defaults.
The integer-radical policy is part of task identity. Old version-2 tasks
without this flag retain their original rational-radical meaning; they are
not silently reinterpreted. Existing continuations are pinned to their
original binary and must not be reused with the new binary.

**Upgrade from 3.0.0:** regenerate tasks using the new generator. The
`ce390-task-v2` schema records magnitude bounds and a sign policy, and uses
the new auxiliary-slope parameterization. Old tasks and checkpoints are
rejected rather than silently given broader coverage. Earlier positive-only
test and pilot results do not establish completion of the signed campaign.

A production result certificate contains exact `n`, `x`, rational `d`, and
an integer square root (`y_den: "1"`, `sqrt_integer: true`).
Independently recheck returned hits using `verify.py` before
reporting any mathematical discovery. Keep the task and its status alongside
the hits to distinguish discovery verification from coverage accounting.

## Files and provenance

- `src/cf_worker.cpp`: native exact search engine.
- `campaign.py`, `run_task.py`, `run_task.sh`: bounded independent tasks.
- `verify.py`: independent exact result verification.
- `collector.py`: validate returned certificates and detect gaps in a job page.
- `tests/`: differential, arithmetic, and task-lifecycle tests.
- `MATHEMATICS.md`: derivation and completeness proof per fiber.
- `CE_OPERATIONS.md`: Charity Engine handoff instructions.
- `VALIDATION.md`, `validation/`: release evidence.
- `SHA256SUMS`: hashes of delivered source and evidence files.

This is a replacement of the former demonstration package, not a claim to
implement a CM descent, Mordell–Weil sieve, or Coppersmith method. The
continued-fraction algorithm is derived in this release. The integer-radical
connection to sums of three cubes is contextualized by Booker and Sutherland,
[On a question of Mordell](https://arxiv.org/abs/2007.01209); their full
algorithm is not implemented here. Charity Engine I/O and task conventions
were checked against its [computing documentation](https://www.charityengine.com/docs/Computing%2Bwith%2BCharity%2BEngine)
on 2026-09-26.

## Step-by-step Terminal verification on macOS (v3.2.0)

These steps use the Intel GMP/Homebrew configuration on an Apple Silicon Mac
described above. GMP and Homebrew Python 3.12 must already be installed;
Intel executables require Rosetta.

1. Download the supplied `ce390-3.2.0.zip` archive and extract it in **Downloads**.
   The extracted folder should be named `ce390-3.2.0`.

2. Open Terminal and enter:

   ```bash
   cd "$HOME/Downloads/ce390-3.2.0"
   ```

   If using a GitHub checkout instead of the supplied archive, change into
   the directory containing this README and the Makefile before continuing.

3. Once inside that folder, paste the entire block below:

   ```bash
   export PATH="$(brew --prefix python@3.12)/libexec/bin:$PATH"
   export CXX="clang++ -arch x86_64"
   export CXXFLAGS="-O3 -std=c++17 -Wall -Wextra -Wpedantic"
   export CPPFLAGS="-I$(brew --prefix gmp)/include"
   export LDFLAGS="-L$(brew --prefix gmp)/lib"
   export LDLIBS="-lgmpxx -lgmp"

   make clean && make &&
   "$(brew --prefix python@3.12)/bin/python3.12" -m unittest discover -s tests -v
   ```

4. A successful run should end with:

   ```text
   Ran 66 tests in ...s

   OK
   ```

   The elapsed time will vary. The final `OK` confirms that all 66 tests
   passed; the line reporting the number of tests alone does not establish
   success. If an error appears, retain the final 30 lines of output for
   diagnosis.

This runs local verification only; it does not submit Charity Engine jobs
or start the large-scale search. The v3.2.0 production defaults require an
integer principal square root.

## Container build and Charity Engine deployment

See [CONTAINER.md](CONTAINER.md) for the automated Docker build, real-container
pilot and continuation checks, downloadable image and evidence, and self-service
CE submission settings. The workflow builds Linux amd64 and runs the regression
suite before testing the container. Select a successful run for the exact commit
and use its matching image for every task and continuation.

The first CE-hosted pilot separately checks CE image import and output retrieval.
Local native test results and Docker test results are distinct validation records.
