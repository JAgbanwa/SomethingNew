# Charity Engine handoff: primitive 375 gap search

This is the recommended **pilot package** for the search
`u^3+v^3+w^3=375`, with `gcd(u,v,w)=1`. This guide prepares a concrete build,
local validation run, and deployment contract. The complementary Elkies–Jahnel backend lives in
[`../Scripts for large-scale computations/elkies-jahnel/`](../Scripts%20for%20large-scale%20computations/elkies-jahnel/).
Benchmark that backend before choosing it for a large allocation.

Run the commands below from `375/gap-search/`. They build, plan, execute, and
validate local work. Publishing an image and submitting CE jobs are separate
steps.

## 1. Search contract and notation

The worker's `x,y,z` are **cube coordinates**. The original equation uses
repository variables `(n,x,y)`, where repository `n` was called `x` in the
original discussion and repository `x` was called `m`.

Each task fixes:

- target `k=375` and `primitive=true`;
- a half-open cancellation-gap interval `[d_start,d_stop)`;
- `ratio_max`, limiting the smallest coordinate magnitude relative to the gap;
- a task identifier and application deadline.

`to_points375.py` converts verified cube triples back to equation points. The
discussion's `10^14` is an example search area, not a requested lower or upper
cutoff. Accept qualifying points at any magnitude encountered in the assigned
regions; do not add an `abs(n)>=10^14` filter. Keep odd-numerator, sign, and
point-gcd conditions explicit. The planner's cube-coordinate frontier is a
separate heuristic assumption, not a solution-acceptance threshold.

Each completed task supports a statement only about its specified gap/ratio
region and filters. `--frontier` changes the planner's heuristic estimate; it
does not cause the worker to discard or skip candidates below that frontier.
The planner's frontier expression drops the signed constant 375 and is an
asymptotic approximation. Every worker hit is checked with the actual target.

## 2. Published CE interface and what needs agreement

The current
[CE computing guide](https://www.charityengine.com/docs/pages/18677766/Computing%2Bwith%2BCharity%2BEngine)
recommends independent, self-contained jobs with distinct ranges and a predefined
iteration count calibrated to approximately one hour on an ordinary CPU. For
uneven work, it recommends shorter jobs. An indefinite overall campaign should
therefore be a controller issuing finite jobs, validating returned coverage, and
issuing further jobs.

The
[Docker packaging guide](https://www.charityengine.com/docs/pages/153354261/Packaging%2Bas%2Ba%2BDocker%2Bcontainer)
specifies Docker images for user-provided applications. This package uses a
Debian slim runtime, Python, and GMP. Its entry point reads
`/local/input/task.json` and writes results to `/local/output`. Use a versioned,
immutable task URL and image reference: CE may cache inputs by URL.

The public
[Remote CLI documentation](https://www.charityengine.com/docs/pages/18677786/Charity%2BEngine%2BRemote%2BCLI)
describes `--hours` as an execution cap, with a one-hour default. Its
`--checkpoint` option tracks job submissions and retrieval across CLI restarts.
It does **not** document saving application memory or guaranteeing that a lost
host's `/local/output` is recoverable. The application's checkpoint and the CE
CLI's checkpoint serve different purposes.

Before remote deployment, agree the architecture, resource class, execution
cap, termination grace period, handling of partial outputs, retry policy, and
result-retention period with CE. Do not infer guaranteed redundant validation or
durable remote checkpoints from the public interface. The
[instance documentation](https://www.charityengine.com/docs/pages/108921118/Charity%2BEngine%2BInstance%2BTypes)
describes heterogeneous CPU models; avoid host-specific compiler optimizations
unless the agreed worker class supports them.

The
[quick-start guide](https://www.charityengine.com/docs/pages/108920973/Quick-Start%2BGuide%2Bfor%2BComputing)
explains obtaining an account/key and testing on one's own participating device.
No account request, contact, image publication, or remote submission is performed
by the local instructions here.

## 3. Freeze and build the candidate release

Record the exact source commit and any uncommitted changes before a pilot. A
release used for a campaign should have an immutable source identifier. Build
on the agreed architecture; the default Makefile does not request `-march=native`.

```sh
git rev-parse HEAD
git status --short
make
make test
sha256sum bin/gap_worker
docker build -t ce375-gap:pilot .
docker image inspect ce375-gap:pilot --format '{{.Id}}'
```

Keep the compiler version, dependency versions, test output, worker SHA-256,
and image identifier in the release record. Pin base-image and published-image
digests for the actual deployment; a moving image tag is insufficient provenance.
The worker built inside the image can differ from the host-built worker, so
record its hash separately and use that hash for the container campaign.

The image build runs its included tests. The cross-folder converter comparison
requires the sibling fixed-`g` source tree and may be skipped in the isolated
image context; retain the full checkout's test result as well. A passing local
build alone does not establish remote platform compatibility.

## 4. Reproducible local smoke pilot

This deliberately small pilot creates **two finite tasks**, each covering
500,000 gap values, at target 375 in primitive mode. It exercises the pipeline;
it is not an approximately one-hour production calibration or a discovery-rate
measurement. `--frontier 0` avoids assuming a prior exclusion region for this
test. The planner's default time estimate is not a measured result.

```sh
ce375_worker_sha256=$(sha256sum bin/gap_worker | cut -d ' ' -f 1)

python3 gap_campaign.py \
  --campaign-id ce375-smoke \
  --d-start 10000000000 --d-stop 10001000000 \
  --ratio-max 4096 --task-d-count 500000 \
  --deadline-seconds 0 --frontier 0 \
  --output-dir ce375-smoke

python3 run_gap_task.py \
  --task ce375-smoke/tasks/ce375-smoke-0.json \
  --output-dir results/ce375-smoke-0 \
  --expected-worker-sha256 "$ce375_worker_sha256"
python3 run_gap_task.py \
  --task ce375-smoke/tasks/ce375-smoke-1.json \
  --output-dir results/ce375-smoke-1 \
  --expected-worker-sha256 "$ce375_worker_sha256"

python3 collect_gap.py \
  --page ce375-smoke/page.json --results results \
  --output-dir collected-smoke --require-complete \
  --expected-worker-sha256 "$ce375_worker_sha256"
python3 audit_gap.py \
  --page ce375-smoke/page.json --results results \
  --fraction 1 --seed 375 \
  --expected-worker-sha256 "$ce375_worker_sha256"
```

Success means both task statuses say `complete`, returned coverage is exactly
`[10000000000,10001000000)`, the collector reports no gaps or errors, and every
pilot chunk agrees in counters and exact solution identities on rerun. A nonzero number of mathematical hits is not a
success criterion for an infrastructure test. If there are hits, convert them:

```sh
python3 to_points375.py collected-smoke/hits.jsonl
```

An empty hit file is normal when the saved-hit counters are zero, but the file
must still be returned. A missing file is an integrity error. Do not invoke the
converter on an empty hit file as if it were an error. The repository's known-answer tests separately exercise
candidate discovery, exact checking, and primitivity classification.

## 5. Test the container contract locally

Use a fresh output directory for the container test. Stage a task under the
expected name and mount it read-only:

```sh
ce375_image_worker_sha256=$(docker run --rm ce375-gap:pilot sha256sum /app/bin/gap_worker | cut -d ' ' -f 1)
mkdir -p ce-input container-results/ce375-smoke-0
cp ce375-smoke/tasks/ce375-smoke-0.json ce-input/task.json
docker run --rm \
  --mount "type=bind,src=$(pwd)/ce-input,dst=/local/input,readonly" \
  --mount "type=bind,src=$(pwd)/container-results/ce375-smoke-0,dst=/local/output" \
  ce375-gap:pilot --expected-worker-sha256 "$ce375_image_worker_sha256"
```

Repeat with task 1 and a different output directory, then run the collector and
auditor against `container-results`. Do not mix host and container outputs in a
single collection unless their worker hashes agree. Pass the image's expected
worker hash to both collector and auditor. The auditor must execute the exact
binary used by the tasks. If the host-built binary differs, run the audit inside
the same image on trusted local hardware:

```sh
docker run --rm \
  --mount "type=bind,src=$(pwd),dst=/pilot,readonly" \
  ce375-gap:pilot python3 /app/audit_gap.py \
  --page /pilot/ce375-smoke/page.json --results /pilot/container-results \
  --fraction 1 --seed 375 \
  --expected-worker-sha256 "$ce375_image_worker_sha256"
```

Store each returned job's
files together in its own directory; identical output filenames are expected
across jobs.

## 6. Outputs, interruptions, and coverage

The runner writes:

| File | Meaning |
| --- | --- |
| `task.json` | Assigned task parameters |
| `status.json` | `running`, `partial`, `complete`, or `error`, with progress and worker identity |
| `checkpoint.json` | Completed gap interval and accumulated counters |
| `chunks.jsonl` | Per-chunk deterministic counters and worker hashes for reruns; return even when empty |
| `hits.jsonl` | Exactly verified candidate triples and worker hashes; return even when empty |
| `run.log`, `worker.stderr.log` | Execution and diagnostic logs |
| `continuation.task.json` | Remaining interval after a deliberately partial run, when needed |

The application writes checkpoints only for completed chunks. A restart with
the same task, binary, and retained output directory resumes from that cursor.
Atomic local writes protect against torn local checkpoints; they do not create
remote storage durability. If outputs are lost, reissue the uncredited interval.

Use `--expected-worker-sha256` in the runner, collector and auditor to pin the binary.
The runner refuses a changed-binary resume before modifying its output
directory. The collector rejects mixed worker hashes or a mismatch with the
expected hash, exits with an error, and accepts no coverage from that collection.
Normal completion requires a matching worker terminal record and a successful
process exit; reaching the endpoint without that record is an error. Deliberate
partial runs and genuine interruptions remain resumable.

The collector and auditor require the task, status and both JSONL logs together;
a checkpoint is also required to claim committed progress. They reject missing
or truncated logs, absent per-record hashes, and counts that disagree with the
saved unique hit identities. Nothing from an invalid directory is credited.
The checkpoint hit counters describe only its durable interval. A hit saved
from an unfinished next chunk can legitimately make `status.hits` larger than
the checkpoint hit count; it remains available and is deduplicated on resume.
A stale `running` status may lag a valid checkpoint, but cannot claim progress
or counters beyond it.

Interrupted final chunks can leave old rows in the append-only chunk log.
Validation reconstructs the latest contiguous partition of the durable prefix
and reconciles its counters with the checkpoint, so replayed rows do not count
twice. Audits sample only that committed partition. Every sampled interval must
match both its rerun counters and the exact ordered `(x, y, z)` identities; a
different valid triple with the same hit count does not pass. A rerun also needs
a matching start, complete terminal record and successful process exit.

For planned deadlines, leave time before CE's hard cap for a chunk to finish,
the runner to close its files, and the platform to return outputs. Determine the
margin from measured chunk times and CE's termination behavior. A `partial`
status can have exit code zero by design; a zero exit code alone is not proof
that the assigned interval is complete.

Return partial results to the collector and schedule their continuation tasks
in fresh output directories, or resume with the retained original directory.
Do not credit an interval merely because a job was submitted or its deadline
elapsed. The controller must retain the page manifest, validate returned
coverage, and reissue uncovered intervals. Rerunning the same region after a
lost result is acceptable; silently skipping it is not.

## 7. Calibrate before choosing a production campaign

Measure the intended worker build on the agreed CPU class and near the planned
gap sizes:

```sh
python3 gap_campaign.py --calibrate --calibration-d 1e10 \
  --save-calibration calibration.json
```

The optimizer can then explore a specified budget and a **documented assumed
frontier**:

```sh
python3 gap_campaign.py --optimize calibration.json \
  --core-hours <budget> --frontier <documented_assumption>
```

The placeholders above must be replaced with actual decisions. Use the measured
`--us-per-d`, chosen gap interval, and ratio to generate a production page. Size
individual tasks from measurements, allowing for setup time and slower hosts;
the planner's processing estimate does not replace an end-to-end timing.

Keep an explicit distinction between a published cube-height exclusion, any
later gap-region exclusions, and an illustrative starting region. The
currently unsearched primitive-375 frontier has not been established by these
instructions. Heuristic expected counts and Poisson-style probabilities assume
a distribution model; they are not measured chances or guarantees.

## 8. What to send for a CE pilot

Provide the source revision and build instructions; the agreed image reference
and digest; the worker hash; a page manifest and task JSON files; the exact
container command and resource requirements; local pilot results; and the
collector, verifier, and audit instructions. Include a short statement of the
covered mathematical region and the interruption/continuation contract.

Use an independent exact check for every returned solution. Sampled chunk reruns
help detect faulty execution but are not a complete certificate of all negative
results. Record the sampling seed, selected chunks, binary version, and outcomes.

Confirm permission to distribute and execute the project code and include
dependency notices with the release. This guide does not choose or add a new
repository license. GMP's terms are documented in its
[copying conditions](https://gmplib.org/manual/Copying).
Magma requires a computer-specific installation/license arrangement according
to its [installation guide](https://magma.maths.usyd.edu.au/magma/faq/install) and
[ordering information](https://magma.maths.usyd.edu.au/magma/ordering). Do not
include Magma in the volunteer-worker image without a confirmed arrangement.

After a successful local and CE pilot, the same controller can keep generating
further finite regions. Extending only `d_stop` with one fixed `ratio_max` is a
search of that region family, not complete coverage of every cube triple; any
broader schedule must be explicit and respect the worker's supported limits.
