# Release validation — CE390

## General a/q campaign update — 2026-10-01

The general campaign update removes the implicit `a=1` generator default.
`parameter_space.py` derives its numerator bounds from the integer target box,
counts the enclosure with exact floor sums, and streams candidate indices.
The native C++ search engine and independent mathematical verifier are unchanged.

The complete updated native suite passed **85 tests in 11.072 seconds**.
This includes 11 dedicated parameter-space tests and 8 integration tests added
to the existing 66-test suite. Checks include independently enumerated small
domains, arbitrary-size rank/unrank, page partitions, old task identities,
unsupported proof domains, and deadline/resume across denominator rows.
The collector's synthetic-certificate protocol tests explicitly mock mathematical
verification; those fixtures are not claimed as solutions of the target equation.

The supplied `examples/general-pilot/` task completed all 30,000 indices in
2.980507 seconds in the native environment, spanning 3,996 distinct numerators
and eight denominators. There were 27,979 CF fibers, 2,021 noncoprime skips,
2,473,593 convergents, and zero hits. Independent collection confirmed the exact
selected-page coverage. These are short native measurements, not CE timing
estimates or evidence about the chance of finding a solution.

The Docker acceptance procedure additionally exercises the new general pilot,
real deadline continuations, SIGTERM, and collection, while retaining the
historical pilot as a compatibility check. Consult the successful workflow and
release for the exact source commit for actual Docker results. No CE jobs are
submitted by these checks. The old 49.95-billion-index/approximately-900-hour
estimate applies to the historical selected `a=1` campaign only.

The following sections retain the historical 3.2.0 validation record.

Validation performed on 2026-09-27. This release searches all four sign
combinations with `10^43 <= abs(n) <= 10^45` and
`10^54 <= abs(x) <= 10^55`. The principal square root must be an integer.
Congruences apply to actual signed integers.
No solution in these production regions was found or is claimed.

## Environment and build

The native worker was compiled on Linux x86_64 with GCC 13.3.0, C++17,
`-O3 -Wall -Wextra -Wpedantic`, and GMP 6.3.0. The build completed without
compiler warnings. Python tooling used Python 3.12.14 and its standard library.
Local builds used extracted GMP development headers and static GMP libraries;
the CE Dockerfile obtains the development package through Debian. Source code
does not require CPU-specific instruction flags.

All **66 tests passed in 8.811 seconds** in the final integrated run:
6 campaign, 18 supervisor, 10 collector, 25 verifier, and 7 native worker tests.
The native tests compile and exercise the actual C++ implementation.
See `validation/tests.txt` for the complete transcript.

The user confirmed that all 60 tests of version 3.1.0 passed on the Apple
Silicon Mac in 21.232 seconds using Intel GMP and `clang++ -arch x86_64`.
That result predates this integer-radical default change. The updated 3.2.0
suite was run here on Linux; it must be rerun on the Mac to establish the
new local result. README includes the successful Mac build configuration.

Docker is unavailable in this execution environment, so **the Docker image
was not built or run here**. The supplied Dockerfile runs `make test` before
producing its runtime image. No CE job was submitted. The CE team should
validate the resulting image and measure representative host performance.

## Signed arithmetic validation

Independent mathematical reviews checked the signed cubic reduction,
principal-root reconstruction, signed modular filters, slope coverage,
Legendre bound, exact Newton brackets, interval continued fractions,
stopping rules, signed common-divisor recovery, and exact range exclusions.
The new integer-only denominator filter was independently checked from
`y` integer if and only if `q` divides `abs(x)`. These are mathematical/code
reviews, not machine-checked formal proofs.

The reproducible automated suite includes:

- Seven genuine historical certificates checked against the original unsquared
  equation in explicit rational-radical mode. Their fractional square roots
  make them invalid for the clarified target; default rejection is tested.
- A nonprimitive certificate with `gcd(n,x)=35`, checked by native arithmetic
  helpers and the independent Python verifier.
- Fifty-four native Newton brackets, covering both cubic branches, compared
  with independent exact binary root isolation.
- Fifty auxiliary parameter pairs checked against direct integer-square
  enumeration on all 38,400 signed coordinate pairs with
  `1<=abs(n)<=80`, `1<=abs(x)<=120`, with congruences both enabled and disabled.
  This oracle evaluates the original radical and contains the genuine hit
  `n=-5, x=81`; it does not reuse the cubic or CF implementation.
- Four genuine mixed-sign fixtures recovered through the actual worker,
  in explicit rational-radical mode under `all`, `pp`, `pn`, `np`, and `nn`
  sign policies. These include
  `(-5,81)` and `(166,-2500)`. Even parameter denominators are allowed only
  in the explicitly relaxed regression mode; production enforces parity.
- Signed production-sized near-square rejections and signed congruence
  tests, including cases whose absolute values have different residues.
- Default API, CLI, and native-worker rejection of a genuine fractional
  radical, with explicit opt-out acceptance; default-generated tasks record
  the integer policy, and legacy tasks retain their original meaning.
- Adaptive precision agreement, explicit precision-cap failure, invalid-input
  recovery, wrong-root-branch rejection, altered certificates, zero denominators,
  magnitude boundaries, and auxiliary-parameter metadata verification.

For version 3.1.0, a separate independent audit enumerated 720,000 signed pairs with
`1<=abs(n)<=120`, `1<=abs(x)<=1500` and compared 1,500 worker responses
across sign and congruence policies. It then enumerated 3,600,000 signed pairs
with `1<=abs(n)<=300`, `1<=abs(x)<=3000` and compared 750 worker responses
including even-parameter relaxed fixtures. All result sets agreed. These
historical audit observations supplement the reproducible included test suite;
they are not fresh benchmarks of the new integer-only defaults.

There is no genuine production-region fixture or integer-radical acceptance
fixture. Historical fractional-radical examples are not desired solutions.
Empty same-sign searches and passing tests are not evidence of existence,
or proof of coverage outside the stated per-parameter mathematical guarantee.

## Task lifecycle and pilot

Tests cover page partitioning, deterministic identities, sign-policy identity,
rejection of version-1 tasks, mismatched worker parameterizations and sign
policies, deadlines, signal interruption, unchanged cursors on failure,
cross-host continuations, retained coverage, binary pinning, corruption and
missing records, and collection with missing prefixes. Returned coverage is
checked independently of whether any hits were found.

A fresh native integer-radical signed pilot wrote all outputs below
`/local/output/ce390-integer-validation/`, keeping this validation run isolated
from earlier outputs. CE deployment still defaults to `/local/output/`.
The pilot completed 30,000 candidate indices: 20,000 CF fibers and 10,000
necessary congruence exclusions, examining 347,558 convergents. It returned
zero hits and completed in approximately 1.68 seconds on this host.
The collector certified completion of the selected page; the independent
verifier confirmed that the collected file contained zero certificates.
The exact task and status are `validation/pilot_task.json` and
`validation/pilot_status.json`. They use the version-2 task contract with `require_integer_sqrt: true`.

## Performance observations

`validation/benchmark.json` records fresh native persistent-worker measurements
with the all-sign, integer-radical policy: 20,000 small-numerator fibers in
approximately 0.74 seconds, and 1,332 fibers with 44-digit numerators and
55-digit denominators in approximately 0.11 seconds. Integer-radical searches
exclude denominators above `10^55`, so the old 82-digit-denominator benchmark
would no longer measure the production CF workload. These measurements include
process and JSON output costs but exclude supervisor overhead.

These are short local observations, not CE throughput guarantees or
one-hour stability measurements. Counts for 50-minute or 100-minute tasks
must be recalibrated on representative CE machines. The watchdog and
continuation contract handle an assigned count exceeding the time budget.

## Delivery and scope

The release archive and replacement GitHub folder contain identical source,
examples, documentation, tests and validation evidence. `SHA256SUMS` hashes
every delivered file except itself. Compiled binaries and local dependencies
are excluded. Generate new production tasks for 3.2.0 so that the integer
policy is explicit. Older version-2 tasks without the integer flag retain
their broader rational-radical meaning. Binary-pinned continuations cannot
be reused with the updated worker.

Completeness is established for each successfully processed auxiliary slope
in the requested signs and bounds with the recorded radical policy. A finite pilot does not exhaust all slopes
in these regions. No supplied asymptotic heuristic is treated as a theorem,
and no probability or deadline for finding a solution is asserted.
