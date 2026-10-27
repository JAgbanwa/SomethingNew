# CE390 operations: d-first search and project accounting

The current search uses `d_campaign.py`, `run_d_task.py`, `collect_d.py`, and
`verify_d.py`. It seeks rational `d`, integer `n = 1 (mod 3)`, and
`x=X/2`, `y=Y/2` with odd `X,Y` and positive `Y`. It has no prescribed
coordinate rectangle. The fast solver's finite scope is the assigned rational
height shells and `1<=abs(g)<=10^g_max_digits`; the default exponent is 100.
See [D_FIRST.md](D_FIRST.md) for the proof and exact acceptance conditions.

## 1. Project limit and units

The allowance for **this project is 1,800 aggregate core-hours**. An additional
**200 hours are reserved for other projects**, outside that limit. No retry,
continuation, calibration run, or faster-host extrapolation permits using those
other-project hours.

The default plan estimates 1,600 search hours, leaving 200 hours of headroom
inside this project's ceiling. Planned workload is an estimate. Actual resource
accounting decides when launches must stop.

For local serial execution on Linux, use the durable campaign controller. It
requires CPU-affinity support and pins the runner and worker to one available CPU:

```sh
python3 d_campaign.py --campaign-id ce390-dfirst-1800 \
  --budget-core-hours 1800 --planned-core-hours 1600 \
  --us-per-pair 4.5 --g-max-digits 100 --output-dir dfirst-tasks
python3 run_d_campaign.py --page dfirst-tasks/page.json \
  --output-dir dfirst-results --max-attempts 1
```

`--max-attempts 1` limits that invocation to one charged pilot attempt. Continue
with the same page and results directory, omitting `--max-attempts`, when ready.
The controller does not contact or submit work to Charity Engine.

Its `budget.json` reserves the full possible duration of each serial one-worker
attempt, including shutdown allowance, before launching it. After the process
has terminated, it settles elapsed time and releases unused reservation.
Continuations and retries count as new attempts; errors also consume time.
If the remaining allowance cannot cover a full attempt, no new attempt starts.
A crash leaves its full reservation held against the allowance and automatic restart refuses to proceed
until that attempt is reconciled. Never reset or delete a ledger to replenish
an exhausted budget. A second output directory is a separate ledger and does
not expand the authorized project allowance.

This accounting treats one worker invocation as one core times elapsed wall
time. It is not an account-wide CE billing meter. Direct `run_d_task.py`
invocations, remote jobs, other result directories, and manually launched
processes are outside its enforcement.

### External CE jobs require central resource accounting

Before submitting each remote attempt, reserve its full possible provider
allocation against the remaining **1,800-hour project allowance**. Keep one
central record of job ID, task/continuation ID, allocated cores, external time
allowance, status, and actual billed or allocated usage. Pending jobs retain
their reservation. Settle it only from returned provider evidence; reserve
retries and continuations separately. Do not submit a job whose maximum charge
would exceed the remainder.

Confirm what CE means by its quoted hours and charges. For example, two allocated
cores for two hours can consume four core-hours even when this package has one
search thread. A two-hour host reservation and a one-hour internal search budget
are different quantities. Use the provider's actual accounting for a strict
external-service limit. The local page's cost estimate and local controller
cannot cap independently submitted remote jobs.

## 2. Current task and container command

Build or select the tested container from the exact source revision containing
the strengthened filter and d-first entrypoint. See [CONTAINER.md](CONTAINER.md).
Stage **one individual task** as `/local/input/task.json`; do not stage `page.json`
as a task. The command is:

```text
python3 /app/run_d_task.py --task /local/input/task.json --output-dir /local/output
```

The current container chooses this command when no arguments are supplied.
Argument-only invocation also selects the d-first runner; an explicit command
continues to work. The old `run_task.sh` is only for explicitly historical
integer-coordinate tasks and does not interpret d-first task files.

All retrievable results belong under `/local/output/`. The task schema is
`ce390-dfirst-task-v1`, and `search.parameterization` is
`dfirst-thue-height-shells-v1`. Production has `m="65"`, `chart="half"`, and
`g_max_digits=100`. Task scopes contain height shells, not `n_min`, `n_max`,
`x_min`, or `x_max`.

The internal task budget defaults to 3,600 seconds. The task runner stops starting
new shells before its soft deadline and has a separate termination allowance.
Historically a two-hour external CE allowance has been used to leave startup and
output time. Confirm the current host's external limits; never equate the
internal budget with its total resource charge.

## 3. Calibrate before extending the plan

Generate a small, explicit height range if a short pilot is desired:

```sh
python3 d_campaign.py --campaign-id ce390-dfirst-pilot \
  --h-start 100000 --h-stop 100005 \
  --budget-core-hours 1800 --planned-core-hours 1600 \
  --seconds 3600 --target-seconds 3000 --output-dir dfirst-pilot
```

This assigns five shells at moderate height; it is a timing sample, not evidence
that a solution is more likely there. A separate pilot's actual resource usage
still belongs to the same 1,800-hour project total. If it is run outside the
main controller, account for it centrally before allocating the remaining
allowance; creating a pilot page is not a second project budget. When generating
the later production page, set `--budget-core-hours` to at most `1800` minus
all previously consumed project core-hours. Preserve the earlier ledger or
provider records. Never modify a page already bound to a running controller
ledger to change its height range or replenish its allowance.

Measure `1e6 * elapsed_seconds / counters.pairs` from completed attempt statuses
for microseconds per raw parameter pair, and include host overhead and charges
in the allocation model. Sample representative heights and use the updated
worker. The old committed timings and admissible counts predate the stronger
modulo-4 filter. Fewer solver candidates do not by themselves establish a
proportional wall-time saving.

With rate `u` microseconds per pair, the estimate through height `H` is
`(2*H*H+H)*u/3.6e9` core-hours. At `u=4.5`, the default 1,600-hour work target
covers heights through 799,999. Explicit height limits are exclusive at the
stop endpoint. Plan and execute in stages rather than treating the estimate as
a promise that every assigned height will fit before the cap.

## 4. Outputs and continuations

Preserve every output directory, including incomplete and failed attempts.

| File | Meaning |
| --- | --- |
| `task.json` | The exact task supplied to this invocation |
| `status.json` | State, completed shells, counters, elapsed time, code/worker pins |
| `checkpoint.json` | Next unfinished shell and the output's coverage start |
| `hits.jsonl` | Exact certificates verified against the original equation |
| `run.log` | Progress, hits, and completion or failure reason |
| `worker.stderr.log` | Native worker diagnostics |
| `continuation.task.json` | Same mathematical task, resuming at the next unfinished shell |

The campaign controller additionally owns its durable budget ledger and separate
attempt directories. Do not combine unrelated campaign ledgers or count a
continuation as free work.

A successful process exit may describe an intentional partial result. Check
`state`, `next_h`, and `remaining_shells` in `status.json`. Submit the returned
continuation only with the same tested worker and implementation. Do not remove
hash pins to force an old continuation to use this new filter version.

Completed shells are checkpoints. A worker failure or unresolved precision limit
must not be reclassified as an empty completed shell. Retain all earlier outputs
when moving a continuation to another host.

## 5. Collect and verify the actual coverage

```sh
python3 collect_d.py --page dfirst-tasks/page.json \
  --results-dir dfirst-results --output-dir dfirst-collected
python3 verify_d.py dfirst-collected/hits.jsonl --m 65
```

The collector unions returned height intervals, reports gaps, and independently
verifies each hit. An empty hit file is a valid outcome; verifying an empty file
alone says nothing about coverage. A budget-exhausted campaign may have gaps or
unfinished tasks, which remain part of its report.

For a completed interval `[a,b)`, the finite statement is that each reduced
`d=p/q` with `a<=max(abs(p),q)<b` has no qualifying point with
`1<=abs(g)<=10^100` other than the listed verified hits. The local exclusions
prove impossibility for the rejected fractions. No finite interval certifies
all rational parameters, arbitrary `g`, or the earlier coordinate rectangle.

A valid production hit has integer `n=1 (mod 3)`, odd `X,Y`, positive `Y`, and
satisfies both the exact radical identity and the original unsquared equation.
The verifier also recomputes integer cube components with sum 390. No
floating-point tolerance is used for acceptance.

## Historical operations and external references

The previous rectangle-specific guide is preserved in
[HISTORICAL_CE_OPERATIONS.md](HISTORICAL_CE_OPERATIONS.md). Its parameters,
entrypoints, resource estimates, and published image links do not define the
current campaign.

- [CE computing and input/output](https://www.charityengine.com/docs/Computing+with+Charity+Engine)
- [CE Remote CLI](https://www.charityengine.com/docs/Charity+Engine+Remote+CLI)
- [CE instance types](https://www.charityengine.com/docs/Charity+Engine+Instance+Types)
