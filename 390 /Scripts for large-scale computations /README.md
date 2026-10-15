# CE390: exact search with integer cube components

The final target is rational d satisfying

```
36*n^3-65 = -2*d*x^2*(y-(x+6*n)),
y = sqrt((x+6*n)^2+(36*n^3-65)/x), y >= 0,
den(n) in {1,2,3,6}, den(x)=den(y)>=1,
-x+y in Z, -x-y in Z, 2*x+6*n in Z.
```

BOTH signs are required simultaneously. Denominators mean lowest terms.
These conditions force the equal x/y denominators to be **1 or 2**, and give

```
(-x+y)^3 + (-x-y)^3 + (2*x+6*n)^3 = 390.
```

The integer cube sum also forces **n itself to be integral**, by modulo 9 and
parity. This is a consequence of the full conditions, not a heuristic exclusion;
generated tasks still explicitly permit n denominators 1,2,3,6. Read
[INTEGER_COMPONENTS.md](INTEGER_COMPONENTS.md) for the proofs and exact scope.
Every accepted hit independently verifies all three integers and their cube sum,
in addition to the original unsquared equation and nonnegative square root.

## Generate and run both denominator cases

```sh
make -j2
make test
python3 cube_campaign.py --campaign-id ce390-integer-components-pilot \
  --candidates-per-task 30000 --task-count 1 --seconds 3600 --output-dir cube-tasks
python3 run_xy_task.py --task cube-tasks/b1/task-000000000000-*.json --output-dir cube-results/b1
python3 run_xy_task.py --task cube-tasks/b2/task-000000000000-*.json --output-dir cube-results/b2
python3 collect_xy.py --page cube-tasks/b1/page-000000000000.json \
  --page cube-tasks/b2/page-000000000000.json --results-dir cube-results --output-dir cube-collected
```

This writes TWO pilot tasks, one per exact x/y denominator. Defaults retain
10^43<=|n|<=10^45 and 10^54<=|x|<=10^55 as rational VALUE bounds, all signs,
and all rational d, without additional congruence restrictions. No jobs are
submitted. Both input tasks are supplied in `examples/integer-components-pilot/`.
The two denominator cases are exhaustive for the new condition; the two finite
slope prefixes are NOT exhaustive for the n,x region. No target hit is claimed.

The new task field `require_integer_components: true` is bound to task identity.
The runner forwards it to the native worker and requires acknowledgement even
for empty hit lists. Certificates include exact decimal strings `cube_plus`,
`cube_minus`, `cube_third` and `cube_sum` (390). The collector and verifier
recompute these fields. Checkpoints pin the worker and relevant Python sources.

## Compatibility and deployment

[INTEGER_COORDINATES.md](INTEGER_COORDINATES.md) describes the historical integer
programs; [XY_DENOMINATORS.md](XY_DENOMINATORS.md) describes the broader PR4
x/y-rational mode before the final three integrality conditions. Those existing
tasks, indices, and the default entrypoint keep their meanings. The old examples
with b=6 and b=84 are NOT final-target pilots. PR3's equal-n/x proposal is also
not this target. `xy_campaign.py` remains a broader tool; explicitly add
`--require-integer-components` with b=1 or b=2 to select one final-target case.

For Charity Engine a NEW tested image is needed. Stage one task per job as
`task.json` and explicitly run

```
python3 /app/run_xy_task.py --task /local/input/task.json --output-dir /local/output
```

A 3,600-second internal budget needs a two-hour external allowance. Read the
returned status.json and collect all outputs; exit zero can mean partial.
Source changes do not alter existing images or submitted reservations. Do not
clear continuation hash pins to force a task onto a different implementation.
