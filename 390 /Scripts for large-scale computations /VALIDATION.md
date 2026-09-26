# Release validation — CE390 3.0.0

This record describes validation performed on 2026-09-26. No solution in the
requested production rectangle was found or is claimed.

## Environment and build

The native worker was compiled on Linux x86_64 with GCC 13.3.0, C++17,
`-O3 -Wall -Wextra -Wpedantic`, and GMP 6.3.0. The build completed without
warnings. Python tooling was run with Python 3.12.14 using its standard library.
The local build used extracted GMP development headers and static GMP
libraries; normal CE container builds obtain the development package through
the Dockerfile. The source does not use CPU-specific instruction flags.

The supplied Dockerfile builds and runs `make test` before producing its
runtime image. Docker is unavailable in this execution environment, so **the
Docker image was not built or run here**. No job was submitted to the Charity
Engine service. Its actual image, runtime and heterogeneous host performance
must be validated by the CE team before a broad dispatch.

## Arithmetic validation

Two independent mathematical reviews checked the cubic reduction,
principal-root condition, required congruences, Legendre bound, exact Newton
bracketing, interval continued fractions, stopping rules, common-divisor
recovery, and range exclusions. These are reviews of the stated mathematical
argument; they are not a machine-checked formal proof.

The automated suite includes:

- Seven genuine historical equation certificates, with rational square roots,
  checked directly against the original unsquared equation. These fixtures
  are outside the production rectangle and are not new target solutions.
- A nonprimitive historical certificate with `gcd(n,x)=35`, checked in both
  the native arithmetic helper and the independent Python verifier.
- Forty-eight native Newton brackets compared with independent exact binary
  root isolation.
- Seventy fixed rational-parameter fibers in two congruence modes, compared
  against exhaustive integer-polynomial enumeration on `1<=n<=80`,
  `1<=x<=120`. The oracle performs 1,344,000 pair iterations before residue
  skips. These small positive boxes contain no applicable solutions.
- Adaptive precision compared with higher initial precision, explicit
  precision-cap failure, invalid-input recovery, wrong-branch rejection,
  altered certificates, zero denominators, and production-sized near squares.

A separate review compared 1,303 fibers with direct rational-square
enumeration for positive `n,x<=450`; the result sets agreed and were empty.
There is **no genuine positive production-region hit fixture**. Testing empty
searches is not presented as evidence that a solution exists or as proof of
search completeness outside the proved per-fiber scope.

## Task lifecycle validation

The suite checks page partitioning, deterministic identities, deadline and
signal interruption, unchanged cursors on worker failure, cross-host
continuations, retained local coverage, binary pinning, protocol policy flags,
corrupted or missing result records, and collection with missing prefixes.
Returned coverage is checked independently of whether any hits were found.
All **44 tests passed**. See `validation/tests.txt` for the final complete test transcript.

A native end-to-end pilot used the **default** `/local/input/task.json` and
`/local/output/` paths. It completed 30,000 candidate indices: 10,000 relevant
CF fibers and 20,000 necessary congruence exclusions, with 173,782 convergents
examined. It returned zero hits. The collector certified completion of that
selected page, and the independent verifier confirmed that the collected
file contained zero certificates. The exact task and status are retained as
`validation/pilot_task.json` and `validation/pilot_status.json`.

## Performance observations

`validation/benchmark.json` records native persistent-worker measurements:
20,000 relevant small-numerator fibers in approximately 1.00 seconds
(about 20,000 per second), and 1,193 relevant fibers with 71-digit numerator
and 82-digit denominator parameters in approximately 0.091 seconds
(about 13,100 per second). These timings include process and JSON output
costs but exclude supervisor overhead. The end-to-end pilot completed in
approximately 0.70 seconds on this host.

These are short, local observations, not CE throughput guarantees or
one-hour stability measurements. Counts for 50-minute or 100-minute tasks
must be recalibrated on representative CE machines. The watchdog and explicit
continuation contract handle a task whose assigned count exceeds its budget.

## Delivery and scope

The release archive and replacement GitHub folder contain the same source,
examples, mathematical documentation, tests, and validation evidence.
`SHA256SUMS` hashes every delivered file except itself. Compiled binaries,
local dependency packages, and temporary build/test files are not delivered.

Completeness is proved for each successfully processed rational-parameter
fiber in its requested bounds. No finite pilot certifies the entire rectangle,
no asymptotic statement supplied with the request is treated as a theorem,
and no probability or deadline for finding a solution is asserted.
