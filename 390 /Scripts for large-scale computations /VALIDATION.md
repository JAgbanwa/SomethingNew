# Release validation — CE390 3.1.0

Validation performed on 2026-09-27. This release searches all four sign
combinations with `10^43 <= abs(n) <= 10^45` and
`10^54 <= abs(x) <= 10^55`. Congruences apply to actual signed integers.
No solution in these production regions was found or is claimed.

## Environment and build

The native worker was compiled on Linux x86_64 with GCC 13.3.0, C++17,
`-O3 -Wall -Wextra -Wpedantic`, and GMP 6.3.0. The build completed without
compiler warnings. Python tooling used Python 3.12.14 and its standard library.
Local builds used extracted GMP development headers and static GMP libraries;
the CE Dockerfile obtains the development package through Debian. Source code
does not require CPU-specific instruction flags.

All **60 tests passed in 7.716 seconds** in the final integrated run:
5 campaign, 16 supervisor, 10 collector, 23 verifier, and 6 native worker tests.
The native tests compile and exercise the actual C++ implementation.
See `validation/tests.txt` for the complete transcript.

The previous 3.0.0 suite passed all 44 tests on the user's Apple Silicon Mac
using Intel GMP and `clang++ -arch x86_64`. That result predates this signed
extension. The 3.1.0 tests were run here on Linux; they must be rerun on the
Mac to establish the updated local result. README includes the working Mac
build configuration from the earlier verification.

Docker is unavailable in this execution environment, so **the Docker image
was not built or run here**. The supplied Dockerfile runs `make test` before
producing its runtime image. No CE job was submitted. The CE team should
validate the resulting image and measure representative host performance.

## Signed arithmetic validation

Independent mathematical reviews checked the signed cubic reduction,
principal-root reconstruction, signed modular filters, slope coverage,
Legendre bound, exact Newton brackets, interval continued fractions,
stopping rules, signed common-divisor recovery, and exact range exclusions.
These are mathematical/code reviews, not machine-checked formal proofs.

The reproducible automated suite includes:

- Seven genuine historical certificates checked against the original unsquared
  equation. They are regression fixtures outside the production regions.
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
  each under `all`, `pp`, `pn`, `np`, and `nn` sign policies. These include
  `(-5,81)` and `(166,-2500)`. Even parameter denominators are allowed only
  in the explicitly relaxed regression mode; production enforces parity.
- Signed production-sized near-square rejections and signed congruence
  tests, including cases whose absolute values have different residues.
- Adaptive precision agreement, explicit precision-cap failure, invalid-input
  recovery, wrong-root-branch rejection, altered certificates, zero denominators,
  magnitude boundaries, and auxiliary-parameter metadata verification.

A separate independent audit enumerated 720,000 signed pairs with
`1<=abs(n)<=120`, `1<=abs(x)<=1500` and compared 1,500 worker responses
across sign and congruence policies. It then enumerated 3,600,000 signed pairs
with `1<=abs(n)<=300`, `1<=abs(x)<=3000` and compared 750 worker responses
including even-parameter relaxed fixtures. All result sets agreed. These
separate audit observations supplement the reproducible included test suite.

There is no genuine production-region fixture or same-sign hit fixture.
Empty same-sign searches and passing tests are not evidence of existence,
or proof of coverage outside the stated per-parameter mathematical guarantee.

## Task lifecycle and pilot

Tests cover page partitioning, deterministic identities, sign-policy identity,
rejection of version-1 tasks, mismatched worker parameterizations and sign
policies, deadlines, signal interruption, unchanged cursors on failure,
cross-host continuations, retained coverage, binary pinning, corruption and
missing records, and collection with missing prefixes. Returned coverage is
checked independently of whether any hits were found.

A fresh native signed pilot wrote all outputs below
`/local/output/ce390-signed-validation/`, keeping this validation run isolated
from earlier outputs. CE deployment still defaults to `/local/output/`.
The pilot completed 30,000 candidate indices: 20,000 CF fibers and 10,000
necessary congruence exclusions, examining 347,558 convergents. It returned
zero hits and completed in approximately 1.61 seconds on this host.
The collector certified completion of the selected page; the independent
verifier confirmed that the collected file contained zero certificates.
The exact task and status are `validation/pilot_task.json` and
`validation/pilot_status.json`. They use the new version-2 task contract.

## Performance observations

`validation/benchmark.json` records fresh native persistent-worker measurements
with the all-sign policy: 20,000 small-numerator fibers in approximately
0.72 seconds, and 1,324 fibers with 71-digit numerators and 82-digit
denominators in approximately 0.10 seconds. These measurements include
process and JSON output costs but exclude supervisor overhead.

These are short local observations, not CE throughput guarantees or
one-hour stability measurements. Counts for 50-minute or 100-minute tasks
must be recalibrated on representative CE machines. The watchdog and
continuation contract handle an assigned count exceeding the time budget.

## Delivery and scope

The release archive and replacement GitHub folder contain identical source,
examples, documentation, tests and validation evidence. `SHA256SUMS` hashes
every delivered file except itself. Compiled binaries and local dependencies
are excluded. Generate new tasks for 3.1.0; do not reuse 3.0.0 tasks or
checkpoints under the changed mathematical parameterization.

Completeness is established for each successfully processed auxiliary slope
in the requested signs and bounds. A finite pilot does not exhaust all slopes
in these regions. No supplied asymptotic heuristic is treated as a theorem,
and no probability or deadline for finding a solution is asserted.
