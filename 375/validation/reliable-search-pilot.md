# Measured validation of the reliable 375 search

**Date:** 2026-11-23. **Result:** both finite local pilots completed their stated
work without finding a primitive representation of 375. The continuing EJ
pilot paused, resumed, and finished six exact bands. No Charity Engine job was
submitted. No full large height shell or global height exclusion is claimed.

The accompanying [JSON record](reliable-search-pilot.json) contains exact
counters, every completed EJ band, source hashes, binary hashes, and evidence
file digests. These measurements used changes on top of commit
`857adf3f89831816461641d6d4f7bbf89783304f`; they do not describe that base commit alone.

## Gap pilot: complete finite region and full rerun audit

The gap worker covered **27,300,000** integer gap values in
`[100000000000000, 100000027300000)`, with
`floor(3847*d/1000) <= abs(z) <= 65536*d`. The planner used `frontier=0`.
One 50,000-value calibration task was followed by 109 tasks of 250,000 values.

| Recorded quantity | Result |
| --- | ---: |
| Completed tasks / audited chunks | 110 / 110 |
| Candidate counter | 71,174,059,987 |
| Exact checks | 2,173,909 |
| Hits / primitive hits | 0 / 0 |
| Search wall / child CPU seconds | 37.279 / 34.412 |
| Full audit wall / child CPU seconds | 30.109 / 30.026 |
| Sum of measured command wall seconds | 67.661 |
| Collector gaps / errors | 0 / 0 |

Every completed chunk was rerun with the pinned native worker. All **110/110**
matched in counters and exact solution identities. This checks reproducibility
with the same implementation; it is not a second search algorithm. The
candidate counter measures algorithmic candidate positions, not solutions.
The finite ratio cap remains part of the coverage statement.

## Continuing EJ pilot: six exact bands, with resume

The controller began at cube height `H=1000000000000000000`, using the
interleaved level sequence `0,1,0,2,1,0`, task width 100,000 ratio indices,
`tile-scale=11/2`, and at most 1,000 completed tiles per worker attempt.
It required primitive cube triples in the half chart, with no extra
point-gcd requirement. The start height selected work; it imposed no magnitude
acceptance predicate on the original equation's variables.

For each row, coverage is `H <= c < 2H` and `L <= (5H)*a/c < R`, with
`0 < a <= b < c` and `a^3+b^3-c^3 = +375` or `-375`.

| Job | H | L, included | R, excluded | Tiles | Lattice points covered |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1000000000000000000 | 3968502629920398687 | 3968502629920498687 | 6,250 | 157,225 |
| 1 | 2000000000000000000 | 7937005259840897374 | 7937005259840997374 | 6,250 | 156,906 |
| 2 | 1000000000000000000 | 3968502629920298687 | 3968502629920398687 | 6,250 | 156,188 |
| 3 | 4000000000000000000 | 15874010519681894748 | 15874010519681994748 | 6,250 | 156,423 |
| 4 | 2000000000000000000 | 7937005259840797374 | 7937005259840897374 | 6,250 | 156,817 |
| 5 | 1000000000000000000 | 3968502629920198687 | 3968502629920298687 | 6,250 | 156,675 |

| Invocation | Wall seconds | Child CPU seconds | Cumulative completed tasks | Stop reason |
| --- | ---: | ---: | ---: | --- |
| Start | 90.100 | 89.444 | 4 | 90-second cooperative execution budget |
| Resume | 35.201 | 35.027 | 6 | Two additional completed tasks |
| Total | 125.301 | 124.470 | 6 | Paused |

The final totals are **37,500 credited tiles**, **940,234 covered lattice
points**, **zero primitive cube hits**, and **zero qualifying original-point
hits**. All six bands passed collection, with no gaps or errors inside those
bands. **No job remained pending after resume.**

At the first pause, job 4 was pending. The initial timing includes that partial
work, while the initial credited totals (25,000 tiles; 626,742 lattice points)
include only the four completed jobs. The resume finished job 4 and then job 5.
`lattice_points` includes intervals covered algebraically by the exact cubic
solver; it is not a count of individual cube evaluations.

Wall time uses `time.monotonic`; child CPU uses the change in
`RUSAGE_CHILDREN` user plus system time, including the controller, runners and
native workers. Startup, planning and collection contribute where applicable.
The local Python version was 3.12.14. These figures do not forecast full-shell
completion or discovery probability, and the two pilots cover different
mathematical regions, so their timings are not a like-for-like speed ranking.

## Tested build identities

| Worker | SHA-256 |
| --- | --- |
| Gap | `b86593f81f702a23b09f17f54ca0613956671aa10338bec9b270efdd10645485` |
| EJ | `d481d0221138a2818d55105166bf05331f25d64c17adc68d35459f7f5bd2af06` |

The JSON contains the tested controller/backend/source file hashes as well.
Recorded gap hashes were unchanged at finish; recorded EJ start hashes still
matched after resume. Compiler or platform changes can produce a different
binary hash, so pin the binary actually deployed.

## Reproduce from the repository root

Use fresh output directories. These are finite validation commands; elapsed
time and the location of a budgeted pause depend on the machine.

```sh
make -C "375/Scripts for large-scale computations/elkies-jahnel"
python3 375/search375.py start --output-dir validation-runs/ej \
  --height 1000000000000000000 --grid-span 100000 \
  --task-max-tiles 1000 --solutions 1 --max-tasks 12 --max-seconds 90
python3 375/search375.py resume --output-dir validation-runs/ej \
  --max-tasks 2 --max-seconds 60
```

To force the same six completed bands independently of timing, use
`--max-tasks 4 --max-seconds 0` for the start and `--max-tasks 2 --max-seconds 0`
for resume. That selects the same bands while allowing each invocation to
finish its chosen task count.

The gap reproduction below preserves the original two-part partition and
reruns every chunk. The function and paths are local to the subshell.

```sh
(
  set -eu
  cd 375/gap-search
  make
  pilot_sha=$(sha256sum bin/gap_worker | cut -d ' ' -f 1)
  run_gap_page() {
    pilot_name=$1
    pilot_start=$2
    pilot_stop=$3
    pilot_chunk=$4
    pilot_dir="../../validation-runs/gap/$pilot_name"
    python3 gap_campaign.py --campaign-id "ce375-large-$pilot_name" \
      --k 375 --d-start "$pilot_start" --d-stop "$pilot_stop" \
      --ratio-max 65536 --task-d-count "$pilot_chunk" --frontier 0 \
      --output-dir "$pilot_dir/campaign"
    for task in "$pilot_dir"/campaign/tasks/*.json; do
      task_id=$(basename "$task" .json)
      python3 run_gap_task.py --task "$task" \
        --output-dir "$pilot_dir/results/$task_id" --worker bin/gap_worker \
        --chunk "$pilot_chunk" --expected-worker-sha256 "$pilot_sha"
    done
    python3 collect_gap.py --page "$pilot_dir/campaign/page.json" \
      --results "$pilot_dir/results" --output-dir "$pilot_dir/collected" \
      --require-complete --expected-worker-sha256 "$pilot_sha"
    python3 audit_gap.py --page "$pilot_dir/campaign/page.json" \
      --results "$pilot_dir/results" --worker bin/gap_worker \
      --fraction 1 --seed 375 --expected-worker-sha256 "$pilot_sha"
  }
  run_gap_page sample 100000000000000 100000000050000 50000
  run_gap_page pilot 100000000050000 100000027300000 250000
)
```
