# Final target: all three cube components are integers

This extends the broader equal-x/y-denominator search from PR #4. BOTH signs of
`-x +/- y` must be integral at the SAME solution, as must `2*x+6*n`.
The earlier equal-n/x proposal (PR #3) is not the requested target.

## Target and exact deductions

Find rational d satisfying

```
36*n^3-65 = -2*d*x^2*(y-(x+6*n)),
y = sqrt((x+6*n)^2+(36*n^3-65)/x), y >= 0,
den(n) in {1,2,3,6}, den(x)=den(y)>=1,
A=-x+y in Z, B=-x-y in Z, C=2*x+6*n in Z.
```

Denominators are positive and in lowest terms. The original rational VALUE
bounds remain 10^43<=|n|<=10^45 and 10^54<=|x|<=10^55. All signs of n,x and all
rational d are eligible by default, without additional residue restrictions.
The principal root y is nonnegative. It is NOT required to be an integer.

### Only two x/y denominator cases are possible

Adding and subtracting A and B gives

```
2*x = -(A+B),     2*y = A-B.
```

These are integers with matching parity. Thus x,y are either BOTH integers
(reduced denominator b=1), or BOTH noninteger half-integers (b=2). No b>2 can
satisfy the simultaneous conditions. Conversely, either of these two cases,
together with 6*n integral, makes A,B,C integral. The implementation still
checks all three rational expressions explicitly.

This is a proven reduction, not an arbitrary denominator cutoff. The coordinate
denominator b is different from the auxiliary slope denominator q; q is not
restricted to 1 or 2.

### The integer cube sum, and why n must actually be integral

Direct algebra, even without integrality assumptions, gives

```
A^3+B^3+C^3-390 = -6*x*(y^2-(x+6*n)^2-(36*n^3-65)/x).
```

The radical identity therefore gives A^3+B^3+C^3=390. Once the three components
are integers, this is an integer sum-of-three-cubes certificate, not merely a
solution of a broader rational equation.

There is a further exact consequence. Cubes modulo 9 belong to {-1,0,1} and
390 is 3 modulo 9, so each of the three cubes must be 1 modulo 9. Consequently
A=B=C=1 modulo 3, making A+B+C divisible by 3. Also t^3=t modulo 2: the even
cube sum makes A+B+C even. Thus

```
n=(A+B+C)/6 is an integer.
```

Reduced n denominators 2,3,6 cannot produce a hit satisfying ALL the conditions.
This follows from the equation and integrality, not a new assumed restriction.
Generated tasks retain the requested list [1,2,3,6]; both independent Python and
native verification check the derived n-integrality invariant after checking
the original equation and integer components.

None of these deductions establishes existence of a solution in the requested
large rectangle. No full-target solution is bundled or claimed.

## Search implementation and compatibility

The existing xy continued-fraction engine is reused, not replaced by a brute-
force scan of the coordinate rectangle. Its scaled variables k=6*n, X=b*x,
exact slope enclosure, CF completeness threshold and exact fallback are
unchanged. Read XY_DENOMINATORS.md for the derivation of that broader engine.
Its old examples with b=6 and b=84 are NOT examples of the present final target.

The 733-prime sieve remains safe, including for half-integer y. The equal reduced
denominators give q|X and gcd(X,b)=1. Clearing the radical equation gives

```
6*X*(Y^2-(X+b*k)^2)=b^3*(k^3-390),   Y=b*y, k=6*n.
```

Thus X divides k^3-390. Every p|q requires k^3=390 modulo p; for p>3 these are
the same prime obstructions as 36*t^3=65 via k=6*t. No unproved extension to
arbitrary rational radicals is used. The 20,000 cutoff limits the sieve primes,
not the magnitude of n,x,q.

The task's new immutable search field is

```
"require_integer_components": true
```

True requires b=1 or 2. Nonboolean values are rejected. Missing/false preserves
the earlier broad x/y search. This field is included in task hashing; old task
IDs and candidate ranks are unchanged, and old validators reject the new field
rather than silently weakening its conditions.

`cube_campaign.py` selects BOTH b=1 and b=2 by default and writes separate pages
with distinct campaign IDs. `xy_campaign.py` remains the historical broader tool;
add `--require-integer-components` with `--xy-denominator 1` or `2` for one final-
target case. `--task-count` is PER denominator in the new wrapper.

`run_xy_task.py` forwards the native flag and requires a matching boolean in
every worker reply, EVEN WHEN THE HIT LIST IS EMPTY. `xy_cf_worker` version 1.1.0
checks integrality and the exact cube sum before accepting/serializing a hit.
`xy_common.py` independently verifies the original principal radical, original
unsquared equation, d, bounds and reduced denominators, then recomputes the
integer triple and checks its cube sum. `verify_xy.py` and `collect_xy.py` use
that verifier. Supplied cube fields are checked rather than trusted.

A final-target certificate includes canonical decimal strings
`cube_plus`, `cube_minus`, `cube_third`, `cube_sum`, with `cube_sum` equal to
`"390"`, in addition to its exact rational n,x,y,d and gap fields.

Old integer tools/default container entrypoint and broad-rational task files
retain their meanings. Checkpoints still pin both the native worker and Python
source. Use the same exact image for a task and every continuation; do not clear
hash pins to force an old continuation onto a different implementation.

## Build and generate the two pilot tasks

From the package directory:

```sh
make -j2
make test
python3 cube_campaign.py --campaign-id ce390-integer-components-pilot \
  --candidates-per-task 30000 --task-count 1 --seconds 3600 \
  --output-dir cube-tasks
```

This writes TWO tasks: b1/ and b2/, each with 30,000 candidate indices, the original
large bounds, all four n-denominator options, all signs and no extra congruences.
It does not submit jobs. `components-page-000000000000.json` records exactly the
pages written. The same tasks are supplied in `examples/integer-components-pilot/`.

`--xy-denominator 1` or `2` deliberately selects only that case and the plan
reports `both_xy_denominators_selected: false`. Optional congruence flags impose
additional restrictions; they are not needed for this full corrected target.
`--noninteger-d` optionally excludes integer d, otherwise all rational d qualify.

Run the two tasks in separate fresh output directories:

```sh
python3 run_xy_task.py --task cube-tasks/b1/task-000000000000-*.json --output-dir cube-results/b1
python3 run_xy_task.py --task cube-tasks/b2/task-000000000000-*.json --output-dir cube-results/b2
python3 collect_xy.py \
  --page cube-tasks/b1/page-000000000000.json \
  --page cube-tasks/b2/page-000000000000.json \
  --results-dir cube-results --output-dir cube-collected
python3 verify_xy.py cube-results/b1/hits.jsonl --task cube-tasks/b1/task-000000000000-*.json
python3 verify_xy.py cube-results/b2/hits.jsonl --task cube-tasks/b2/task-000000000000-*.json
```

Each verifier uses its matching task. Do not verify a combined b1/b2 hit file
against just one task. Preserve all new-host continuation outputs so collection
can reconstruct actual coverage. A zero process exit may mean partial execution;
inspect status.json and retain continuation.task.json whenever work remains.

The two denominator cases are exhaustive, but two FINITE SLOPE PREFIXES are not
an exhaustive search of the n,x region. No existence or success probability is
attached to these prefixes.

## Charity Engine deployment

A NEW tested image containing this revision is required. Source changes do not
alter an already-published image or a submitted reservation. Stage each selected
task separately as task.json and explicitly use

```
python3 /app/run_xy_task.py --task /local/input/task.json --output-dir /local/output
```

Use separate jobs/output directories, with a two-hour external allowance for
the 3,600-second internal budget. Do not modify existing running jobs merely to
adopt the new target. No script submits jobs, merges code or publishes releases.

## Validation scope

Synthetic structural inputs test only integrality, NOT the original equation.
For example n=2,x=1/2,y=3/2 makes the three components integers, but does not
satisfy the 390 radical and must not pass the final verifier.

The genuine OLD broad-rational fixture n=-65,x=5785/6,y=3391/6,d=-3418/5785 has
-x+y=-399 integral, but -x-y=-4588/3 nonintegral. It remains a regression fixture
for the historical mode and is explicitly rejected by the new target.

Tests cover the denominator/parity theorem, cube identity, modulo proof for n,
Python/C++ structural agreement, independent original-equation small oracles,
rejection of broad fixtures, task IDs, worker acknowledgements, deadline and
continuation behavior, source/binary pins, collection and Docker packaging.
CI also runs both new finite pilots in the built container. Refer to actual
logs for test outcomes; this document alone is not evidence of a successful run.
