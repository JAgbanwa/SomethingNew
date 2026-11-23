# Local handoff smoke pilot

This record accompanies [handoff-smoke.json](handoff-smoke.json) and the
[Charity Engine handoff](../CHARITY_ENGINE_HANDOFF.md). It is a finite local
pipeline validation, not a remote CE run or a newly discovered solution.

The exact recipe in the handoff was executed with target 375, primitive mode,
two tasks of 500,000 gaps, `ratio_max=4096`, and `frontier=0`:

```text
[10000000000,10000500000)
[10000500000,10001000000)
```

Both tasks completed. Collection reported exactly 1,000,000 gap values covered,
no gaps, no errors, and no representations of 375. All 2 returned chunks were
rerun by `audit_gap.py --fraction 1 --seed 375`; both counter records matched.
The collector counted 161,427,900 modular candidate values and 4,911 exact GMP
checks. These are different stages of the same finite search, not distinct
solutions or an exhaustive coordinate-height bound.

The JSON record stores the compiler, architecture, executable hash and relevant
source-file hashes. The short run rounds to zero in the worker's coarse elapsed
timer; **no production throughput or core-hour estimate is inferred from it**.
Use the calibration commands on the agreed execution hardware to size CE jobs.

Separately, the native gap test suite passed all 50 tests, including a nonempty
known-answer pipeline, exact arithmetic, interruption/resume, provenance,
terminal-record validation and independent collection checks. Docker was not
available in the local workspace; the added GitHub workflow performs actual
image builds and mounted-input/output positive-control runs.
