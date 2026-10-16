# Variable a and q during the search

The common x/y denominator b=2 remains fixed for the half-integer case. The
auxiliary numerator a and denominator q are BOTH variables, not presumed
solution values. The equation, coordinate bounds, signs, and all three integer
component checks are unchanged.

## New task ordering

New cube_campaign.py tasks default to --parameter-order interleaved, with mode
n-sixths-xy-interleaved-aq-v1. They generate pairs throughout the full derived
enclosure during the run instead of finishing a long a=1-only initial section.
There is no fixed a=1, a=2, selected numerator list, or additional small numerator
ceiling. The first eight dispatched a,q pairs are printed in run.log so actual
behavior is visible.

The ordering is a scheduling convention, NOT evidence that a particular pair
contains a solution. Repeated a or q can still occur; no value is held fixed as
an assumed location of the desired solution. This is not a discovery guarantee.

## Exact set-preserving permutation

Let C be the finite number of pairs in the existing derived enclosure, before
necessary filters. The old rank-to-pair map is unchanged. Visit its ranks in the
following recursively defined order:

    P_1 = [0]
    P_C = [2*r for r in P_ceil(C/2)] + [2*r+1 for r in P_floor(C/2)]

The two pieces partition exactly the even and odd ranks below C. Induction
proves that every old rank occurs exactly once: nothing is omitted or duplicated.
The code computes the mapping and its inverse with O(log C) integer operations
and no C-sized array. Example: C=8 gives 0,4,2,6,1,5,3,7. This distributes finite
prefixes across the same enclosure; it does not add a mathematical restriction.
The base rank-to-(a,q) operation also costs time, so this random-access traversal
is slower than the old sequential iterator. Old pilot rates do not apply.

## Necessary half-integer parity

For b=2 let x=X/2, y=Y/2 with X,Y odd and k=6*n integral. Then

    a/q = |Y-|X|+2*k*sign(X)| / |X|.

The numerator is even and denominator odd. Reduction removes only an odd common
factor, so reduced a is even and q is odd. This excludes odd a; it does NOT fix
any even value or assert that all even values yield solutions. Python and C++
now apply this necessary filter before continued-fraction work, after the
existing filters. The exclusion belongs to denominator_excluded and retains
its index and the common checkpoint path. Other b values are unchanged.

## Compatibility and scope

The new mode is hashed into task identity. Historical q-major tasks retain their
old IDs and index-to-pair maps; they are NOT silently rewritten. In particular,
the former a=1-only b2 pilots remain historical deployment tests, not suitable
calibration of the surviving target fibers. Unknown modes fail closed. The new
collector inverts the correct mode when validating returned hit indices.
Implementation and worker hash protections remain. Changing modes cannot reuse
an old checkpoint; do not clear pins to force a continuation onto new code.

Within one mode, disjoint slices mean disjoint work. Across different modes,
indices are not interchangeable and visited pairs may overlap. Keep old and new
campaigns separate; do not add their index counts as if they were one contiguous
search. The collector rejects conflicting fiber definitions under one campaign
ID and reports different campaigns separately.

A task runs until its assigned slice completes or its time limit is reached,
saving a continuation when necessary. It does not freeze on a numerator when no
hit is found. It also cannot promise to run forever until a solution is found.
The finite sampled slices are NOT exhaustive searches of the whole n,x region.
The original bounds and continued-fraction completeness argument still require
independent review; this traversal change is not proof of discovery feasibility.

## Build, generate, and inspect

    make -j2
    make test
    python3 cube_campaign.py --campaign-id ce390-variable-aq-pilot \
      --xy-denominator 2 --parameter-order interleaved \
      --candidates-per-task 256 --task-count 1 --seconds 3600 \
      --output-dir variable-aq-tasks
    python3 run_xy_task.py --task variable-aq-tasks/b2/task-000000000000-*.json \
      --output-dir variable-aq-results
    python3 collect_xy.py --page variable-aq-tasks/b2/page-000000000000.json \
      --results-dir variable-aq-results --output-dir variable-aq-collected

256 is a validation budget, not a bound on a or q. The task generates pairs
dynamically. examples/variable-aq-pilot contains this task and an exact preview
of its first 256 pairs' diversity and filter counts. Sample pairs are diagnostic
output, NOT a fixed list in the task definition. Omit --xy-denominator 2 to
generate separate tasks for both b=1 and b=2. The broad xy_campaign.py default
stays q-major for compatibility; its --parameter-order interleaved selects the
new mode explicitly. cube_campaign.py --parameter-order q-major reproduces the
historical order.

A newly built image is required. For one task staged as task.json, use:

    python3 /app/run_xy_task.py --task /local/input/task.json --output-dir /local/output

No existing CE reservation/image changes. No job is submitted by these scripts.
