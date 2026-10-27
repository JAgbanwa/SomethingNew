# CE390 task examples

## Current d-first half-integer search

Generate new tasks with `d_campaign.py` from the current tested revision.
Production searches rational `d`, integer `n=1 (mod 3)`, odd half-integer
`x=X/2`, and odd positive half-integer principal radical `y=Y/2`.
It uses height shells and an explicit `g` bound, with no `n,x` rectangle.

A small production pilot is:

```sh
python3 d_campaign.py --campaign-id ce390-dfirst-pilot \
  --h-start 1 --h-stop 121 --g-max-digits 100 \
  --output-dir dfirst-pilot
```

The strengthened filter admits 517 fractions in these shells. This count is a
regression check, not a success probability. A full default plan is generated
without `--h-stop`, using the 1,800-hour project ceiling, 1,600 estimated work
hours, and the measured rate supplied with `--us-per-pair`.

Use `run_d_campaign.py` for local serial execution under the durable project
ledger. A direct single-task run or distributed CE submission needs separate
central resource accounting. The project's 1,800 hours include its retries and
pilots; the additional 200 hours are reserved for other projects. See
[../README.md](../README.md) and [../CE_OPERATIONS.md](../CE_OPERATIONS.md).

## Historical fixtures

The existing example directories preserve earlier algorithms, task identities,
and reproduction evidence. They are not inputs for the new default entrypoint.

| Directories | Historical scope |
| --- | --- |
| `general-pilot/`, `general/` | Integer-coordinate rectangle and q-major auxiliary slopes |
| `variable-aq-pilot/` | Interleaved rational-coordinate slopes with integer cube components |
| `integer-components-pilot/` | Earlier q-major integer-component tasks |
| `xy-pilot/`, `xy-diagnostic/` | Broader equal-denominator rational-coordinate tests |
| `pilot/`, `50min/`, `60min/`, `100min/` | Earlier selected-numerator integer-coordinate fixtures |

These historical files retain their original bytes. Explicit historical runners
remain available for validation; do not stage one of these tasks as a d-first
task or silently reinterpret its completed coverage. Different historical modes
can overlap, so their counts must not be added as disjoint new coverage.

`../validation/dfirst/` also retains recorded d-first results from the earlier
filter, including the seven `k=6` known-answer certificates. Preserve their
original counts, hashes, and timing attribution; use newly generated tasks to
calibrate the current worker.
