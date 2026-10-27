# Validation of the modulo-4 filter and 1,800-hour campaign

Executed on 27 October 2026. This record belongs to worker **1.1.0** and the
new budget controller. Earlier records under `validation/dfirst/` retain their
original version, counts, and hashes.

## Regression suite

`tests.txt` records **249 passing tests** in 44.674 seconds. The complete suite
includes the earlier integer and rational-coordinate regressions, 19 targeted
native/filter tests, and 13 budget/controller tests.

The mathematical checks include exhaustive local cubic residues modulo 4,
signed numerator examples, independently computed admissibility counts,
preservation of all seven known `k=6` answers, native/Python agreement for odd,
even, and negative diagnostic constants, brute-force comparisons, and planted
large continued-fraction solutions. Production `m=65` explicitly verifies
`n = 1 (mod 3)`; generic test targets do not inherit that production assertion.

The controller checks include exact planning boundaries, immutable task hashes,
exclusive ledger locking, errors and continuations charged as new attempts,
restart without resetting usage, no launch when a reservation will not fit,
retention of unresolved crash reservations, one-CPU affinity, and termination
of a genuinely hung worker grandchild.

## Actual native campaign pilot

`current-pilot.json` records the new production pilot through height 120:

- 28,920 raw pairs and **517 admissible fractions**, with no hits.
- Completed coverage `[1,121)` at `|g| <= 10^100`.
- Independent collection and exact hit verification completed.
- The budget controller recorded one settled attempt.
- Re-running the same page and results directory launched no further attempt
  and preserved the charged time.

The former filter admitted 789 fractions at this height. The independent
regression verifies that precisely 272 are removed by `p(p+q) = 2 (mod 4)`.
The empty production pilot is a coverage check, not a proof of nonexistence
outside its recorded bounds or a prediction of future discovery.

## Same-host timing samples

`benchmark.json` compares the unchanged baseline worker 1.0.0 with worker 1.1.0
using the same compiler optimization, GMP dependencies, and one-CPU affinity.
Both use `m=65`, `G=10^100` and identical raw shell ranges.

| Heights | Baseline seconds | New seconds | Baseline admissible | New admissible |
| --- | ---: | ---: | ---: | ---: |
| 1–1,000 | 9.762334 | 5.399138 | 44,281 | 29,633 |
| 100,000–100,004 | 8.630058 | 3.854018 | 37,795 | 22,695 |

These short samples were not repeated and ran on a shared host. They show an
observed improvement for these runs; they do not establish a production rate
or guarantee a campaign finish time. The planning default remains 4.5
microseconds per raw pair until the actual execution hosts are calibrated.

## Scope of this evidence

No large or paid campaign was launched. Local native compilation used GMP
development files extracted into the workspace, with include/library paths
supplied to the compiler. Docker and PARI were not run in this local
environment. The pull-request workflow independently builds the Docker image,
runs the suite, and checks the new default container entrypoints and known
answers; its outcome must be read from that workflow's own evidence.

