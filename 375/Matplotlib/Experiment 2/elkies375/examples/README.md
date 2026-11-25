# Recorded validation runs

These files come from actual execution of the package. They are not manually
constructed search results. Commands below run from the `elkies375` directory.

| Run | Search scope | Observed result | Completion meaning |
|---|---|---|---|
| [demo](demo/README.md) | All integer cube lifts, `1 <= n <= 5` | Two canonical nonprimitive cube triples; 11 native tiles | Complete integer-cube target in this small n interval |
| [large-pilot](large-pilot/README.md) | Primitive cube lifts, `10^17 <= n <= 10^20`, one width-1000 ratio task in each of 43 height shells | 551 native tiles, 12,571 lattice points covered, no exact hits | Only 43 assigned tasks complete; the full interval search is unfinished |
| [rational-control](rational-control/README.md) | All rational y, integer x, fixed `n = 13` | `x = -144`, `|y| = 695/756`, nonintegral cube lift | Complete fixed-n factor-pair search |

The full mathematical/backend/campaign/plot suite passed **53 tests**. Its
output is preserved in [test-run.log](test-run.log). The tests include exact
small brute-force comparisons, boundary cases, rational-only separation,
worker failure and malformed output, checkpoint integrity and resume, large
integer task paging and truthful visual coverage.

The search counters are deterministic for the recorded scopes/settings;
elapsed times, execution timestamps, platform strings and compiled binary
hashes are environment-dependent. The recorded runs used Linux. The macOS
compiler configuration is supported but was not executed on a Mac here.

The records store UTC execution times. This documentation was prepared on
25 November 2026 in the user's Europe/Amsterdam timezone.
