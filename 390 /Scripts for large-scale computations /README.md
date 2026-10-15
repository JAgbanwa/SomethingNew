# CE390: exact searches for the corrected rational target

The corrected target is rational d satisfying

```
36*n^3-65 = -2*d*x^2*(y-(x+6*n)),
y = sqrt((x+6*n)^2+(36*n^3-65)/x), y >= 0,
den(n) in {1,2,3,6}, den(x)=den(y)=b>=1.
```

Denominators are measured in lowest terms. The denominator of n need not equal
b, and b is not limited to 1,2,3,6. This replaces the earlier n/x denominator
proposal in PR #3, not the historical integer task semantics.

Read [XY_DENOMINATORS.md](XY_DENOMINATORS.md) for the derivation, completeness
conditions, safe prime sieve, denominator policies and detailed commands.
The full historical integer-search README is retained verbatim as
[INTEGER_COORDINATES.md](INTEGER_COORDINATES.md). Existing integer tasks,
programs and the default container entrypoint keep their original behavior.

## Corrected search tools

`xy_campaign.py` generates pages; `run_xy_task.py` runs restartable tasks using
`bin/xy_cf_worker`; `collect_xy.py` checks returned coverage and certificates;
`verify_xy.py` independently verifies the original equation with exact rationals.
The generator defaults to all four n denominators, all signs, no extra residue
restrictions and the original huge n,x magnitude bounds. Each campaign chooses
one exact x/y denominator b. Finite tasks do not exhaust all b or all slopes.

```
make -j2
make test
python3 xy_campaign.py --campaign-id ce390-xy-b84-pilot --xy-denominator 84 \
  --candidates-per-task 30000 --task-count 1 --seconds 3600 --output-dir xy-tasks
python3 run_xy_task.py --task xy-tasks/task-000000000000-*.json --output-dir xy-output
```

84 is an example denominator, not a prediction about where a solution occurs.
`examples/xy-pilot` uses the production magnitude bounds; `examples/xy-diagnostic`
is a small nonempty correctness check, not a production-range solution.

## Charity Engine

A new tested image containing these tools is required for corrected tasks:

```
python3 /app/run_xy_task.py --task /local/input/task.json --output-dir /local/output
```

Use the existing operational guidance in [CE_OPERATIONS.md](CE_OPERATIONS.md)
for output retrieval and external time allowances, but use the xy runner,
collector and verifier for the new schema. A 3,600-second internal budget needs
a two-hour external allowance. Read status.json; exit zero can mean partial.
No scripts submit jobs, publish an image, or spend CE credits automatically.
Fractional certificates are not automatically integer cube solutions for 390.
