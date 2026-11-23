# Large search regions, completed samples, and resumption

The initial bounds of 500 for cube coordinates and 50 for rational height were
validation examples. They were too small to present as a discovery campaign.
The large configuration now provides explicit finite regions, a compiled
Booker backend, and source-pinned resumable tasks. The original equation and
the requested oddness, positive radical and coprimality tests remain exact.

## 1. The committed large plan

[`campaigns/large.json`](campaigns/large.json) contains arithmetic descriptions
of these regions, with **no optional `d`, rational-height, or `n` filter**:

| Method | Planned mathematical region |
| --- | --- |
| Native Booker--Sutherland | Integer `1 <= D <= 1,000,000,000,000`; `floor(3847D/1000) <= abs(w) <= 1024D`; `D=abs(u+v)` and `(u+v)w<0` |
| Exact Elkies--Elsenhans--Jahnel | All proved ratio bands in shells starting at `10^15`, `2*10^15`, `4*10^15`, `8*10^15`; thus `10^15 <= max(abs(u),abs(v),abs(w)) < 16,000,000,000,000,000` |

The triples satisfy `u^3+v^3+w^3=375`. Every possible original-equation chart
is checked, including the signs of the rational parameter and of `x` and `n`.
The Booker cap `abs(w)/D <= 1024` excludes larger ratios. Its region is not a
complete cube box or an unrestricted smallest-coordinate search. The EJ plan
does not certify the region below `10^15`.

These starting scales are choices, not asserted unsearched frontiers. Creating
a plan performs no mathematical search. In particular, a whole large EJ shell
is prohibitively expensive on one machine with the current exact reference
implementation; see the measured costs in [EJ_SCALING.md](EJ_SCALING.md).

### Rational d and original coordinates

Uppercase `D` is the **integer gap** used for modular arithmetic. Your corrected
signed rational parameter is

\[
d=-\frac{y+x+6n+3}{2x}=\frac{a+c}{b+c}.
\]

There is no rational-height-50 restriction on the native searches. If
`d=p/q` is reduced with `q>0`, any cube box of height `B` implies

\[
\max(|p|,q)\le2B,\qquad q\text{ odd},\qquad
|x|,y\le B-\tfrac12.
\]

For the EJ plan, the largest allowed integer cube height is
`15,999,999,999,999,999`. Thus the plan permits reduced rational heights up
to the outer bound **31,999,999,999,999,998**. The corresponding coarse
integer-n bounds are

\[
-8\cdot10^{15}\le n\le8\cdot10^{15}-1,
\]

with the necessary residue condition `n == 2 (mod 3)` still enforced by the
equation. These are outer bounds on accepted charts, not an assertion that
every `d` or `n` in those intervals occurs or has been searched independently.

The native Booker plan has a different, sharper n bound. Since the pair sum
and `w` have opposite signs and `abs(w)>D`,

\[
|u+v+w|=|w|-D\le(1024-1)10^{12},\qquad
n=(u+v+w-3)/6.
\]

Consequently its charts have

\[
-170{,}500{,}000{,}000{,}000\le n
\le170{,}499{,}999{,}999{,}999.
\]

A conservative exact outer bound on rational height in that region is
**19,943,113,620,805,657**. To check it, put `M=10^12`, `R=1024` and

\[
r_0=\left\lfloor\sqrt{\left\lfloor
\frac{4R^3M^2+1500}{3}\right\rfloor}\right\rfloor,
\quad U=\left\lfloor\frac{M+r_0}{2}\right\rfloor.
\]

The exact discriminant bounds give `abs(u),abs(v)<=U`, while
`abs(w)<=RM`. Every pair sum has magnitude at most `max(M,U+RM)`, which is
the stated rational-height bound. Cancellation during reduction can make the
actual denominator and numerator much smaller.

Neither finite native region covers every point for a bounded `n` or every
point for a bounded rational `d`. The separate direct-`d` command remains
available when that is the desired ordering. Simply raising both its height
and n limits is costly: its work grows quadratically with rational height
and linearly with the number of eligible n values, while it continues to
solve for **all** integer scales `m`.

## 2. What was actually completed

The following target-375 native Booker runs completed on 23 November 2026.
Every interval uses ratio cap 1024 and the exact sign/ratio region above.
Times include starting Python and the validated native worker. They are
single local observations, not averaged benchmark scores or runtime promises.

| Inclusive integer-D interval | D values processed | Seconds | Accepted original-equation solutions |
| --- | ---: | ---: | ---: |
| `1` through `1,048,576` | 1,048,576 | 0.228 | 0 |
| `1,000,000,000` through `1,001,048,575` | 1,048,576 | 0.247 | 0 |
| `999,998,951,425` through `1,000,000,000,000` | 1,048,576 | 0.235 | 0 |
| `1` through `100,000,000` | **100,000,000** | **15.388** | **0** |

The 100-million-gap run accounted for **4,052,713,299 progression candidates**
and **123,547 exact checks** after sieving. It returned a validated complete
terminal record. The smaller low interval overlaps this run and must not be
counted as additional coverage. Together, the three disjoint completed
intervals contain **102,097,152 integer gaps**, all with the stated ratio cap.
They do not establish global nonexistence or completion of the trillion-gap plan.

The exact commands, scopes, start/end records, counters, source and binary
fingerprints are preserved in [large_bs_bench.json](large_bs_bench.json).
Reproduce the bounded calibration, saving a new report, with

```sh
python3 benchmark_booker.py --output my-booker-calibration.json
```

The script supplies a 30-second native budget and a 45-second process-group
limit for each sample. A native budget is checked only after a completed
chunk. Any timeout or failed process is denied a completion claim.

For EJ, eighteen completed measurements exercised **six distinct 1000-index
bands** at heights `10^15` and `10^16`, each repeated at three tile scales.
All reported zero hits. At default scale, middle and upper bands took about
0.125--0.190 seconds. Repetitions test scaling; they do not multiply coverage.
Exact endpoints and records are in [large_ej_bench.json](large_ej_bench.json).

The algorithmic scopes differ, so these measurements are not a like-for-like
speed contest. EJ's full ratio range at height `H` is approximately `4H`
index units. The observed local throughput makes full large shells extremely
expensive with this implementation. Conversely, linearly extending the
100-million-gap Booker timing to one trillion gaps gives roughly **43 core
hours before task-launch overhead or changes in arithmetic cost**. That is
only arithmetic extrapolation from one sample; it is not a measured campaign
duration, resource reservation, or guarantee of parallel speedup.

No remote compute was submitted, and these bounded calibration processes have
finished. The large campaign remains a plan until its individual tasks run.

## 3. Run and resume

Build both native workers:

```sh
make build
```

The committed plan is pinned to its mathematical source files and the campaign
runner. Use it with the corresponding commit. If you intentionally change the
code or want different bounds, create a **new** plan and a new state directory:

```sh
python3 campaign375.py plan --output campaigns/my-large.json
```

Every bound is configurable: `--bs-start`, `--bs-stop` (exclusive),
`--bs-width`, `--ratio-max`, `--ej-height`, `--ej-stop` (exclusive), and
`--ej-width`. `ej-stop/ej-height` must be a power of two so the declared shells
meet exactly. `--engine booker` or `--engine elkies` creates a one-method plan.

For example, execute up to ten Booker tasks and inspect their certified status:

```sh
python3 campaign375.py run --plan campaigns/large.json \
  --state-dir runs/large --engine booker --max-tasks 10
python3 campaign375.py status --plan campaigns/large.json --state-dir runs/large
```

One logical Booker task contains at most **1,048,576 D values**. The full plan
has **953,675 Booker tasks**. Task 0 starts at `D=1`; task 953674 is the final
interval ending at `D=10^12`. To inspect or run that final interval directly:

```sh
python3 campaign375.py task --plan campaigns/large.json --task-id 953674
python3 campaign375.py run --plan campaigns/large.json \
  --state-dir runs/large --task-id 953674
```

An attempt stops only after completed native chunks/tiles. Defaults are
`--bs-seconds 30` and `--ej-max-tiles 1000`. A partial attempt writes immutable
output plus an atomic checkpoint and returns **exit 3**. Repeating the same
command resumes the exact unsearched portion. Exit 0 means the requested
invocation finished its selected tasks, not that the entire campaign is done;
the status field `entire_campaign_complete` is the campaign-level statement.

To request the whole Booker partition in one foreground invocation, use
`--engine booker --max-tasks 953675`. This is a long computation; use the
measured calibration and your available resources to schedule it. A partial
budget stop can still require repeating the command.

For process-level parallelism, choose a worker count and give each process a
different index. For example, run this with each `I` from 0 through 7 in
separate processes on a machine with the resources for eight workers:

```sh
python3 campaign375.py run --plan campaigns/large.json \
  --state-dir runs/large --engine booker \
  --workers 8 --worker-index I --max-tasks 100
```

Replace `I` with a decimal index. Task IDs are assigned by their residue
modulo `workers`; source and scope are identical across workers. A POSIX lock
prevents concurrent attempts on the same task even if assignments overlap.
All processes must use a shared state directory on a filesystem supporting
POSIX advisory locks. The runner does not submit a cluster, cloud, or paid job.

The full EJ partition has **599,996,716,272** logical width-100000 bands.
These are computed lazily from five small family records across the combined
plan, not written as separate files. This count is a candid description of the
work, not an affordability claim. For selected EJ work use `--engine elkies`,
an explicit task ID, or the existing `elkies-shell` command with exact bounds.

## 4. What a checkpoint proves

Before advancing any boundary the runner requires matching source hashes,
the exact assigned scope, the strict equation conditions, the expected child
exit status, one complete start/end stream, and exact revalidation of every
reported solution. It retains the SHA-256 fingerprint of each immutable
attempt. `status` reaudits those files and the chain of continuation boundaries.

Booker covers a prefix and continues at `D_next`. EJ covers a suffix while
walking downward and continues with the same lower ratio index and
`index_stop=next_index`. The runner retains that direction. A crash, malformed
output, altered source, corrupted file, missing terminal record, or failed
process cannot mark a region complete. If an interruption happens before a
checkpoint is committed, repeating work is allowed; skipping unproved work is
not. Unreferenced attempt files supply no certified coverage.

Only a source-consistent, gap-free union of completed task records can make
`entire_campaign_complete` true. Neither a planned task nor a partial one
counts as a completed task.
