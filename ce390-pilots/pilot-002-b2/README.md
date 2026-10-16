# CE390 pilot 002: larger b=2 calibration

This directory contains ONE input task and its matching collector page. It does not submit a job, change the application, or rebuild the image. The input is for the already tested release built from source commit `5055a8fefb59f3c0b2c2ed4902d4df6c6ba3df08`.

## Assigned work

- Exact reduced x/y denominator: 2, with `require_integer_components: true`.
- Same search bounds, signs, n-denominator list, prime sieve and arithmetic precision as the completed 30,000-index b2 pilot.
- Half-open candidate slice: **[1000000, 2000000)**, exactly **1,000,000 indices**.
- Earlier successful pilot: [0, 30000). There is no overlap.
- This is a separated calibration slice. The intervening [30000, 1000000) interval is NOT processed or claimed as covered. The b1 case is also not included.
- Internal wall-time budget: 3600 seconds, with a continuation when unfinished. No estimate of completion time is promised.

The reported 223-second duration for the first CE job and the 1.715269-second interval between its two application-log entries are distinct measurements. Neither should be extrapolated into a reliable whole-campaign estimate from one tiny run.

## Dashboard settings

Batch: `ce390-integer-components-pilot-002-b2`

Instance: `C.2x2` (retain the first pilot's instance class where available). Select an available offer and review its cost before approving submission.

Number of jobs: **1**. Maximum hours per job: **2**.

App (one line):

```text
docker:ce390:5055a8fefb59f3c0b2c2ed4902d4df6c6ba3df08 https://github.com/JAgbanwa/SomethingNew/releases/download/ce390-container-5055a8fefb59f3c0b2c2ed4902d4df6c6ba3df08-38755414832-1/ce390-linux-amd64.tar
```

Command line (one line):

```text
python3 /app/run_xy_task.py --task /local/input/task-000000000001-56177f0462780a47.json --output-dir /local/output
```

Input URL (pinned to the commit that created this file):

```text
https://raw.githubusercontent.com/JAgbanwa/SomethingNew/2eada5e4ffbc6efe8ac66be7646e80aa5d49acad/ce390-pilots/pilot-002-b2/task-000000000001-56177f0462780a47.json
```

Only the task JSON is an input to CE; do not upload the page manifest as another task. Do not edit or overwrite submitted inputs. The input-hosting commit differs from the image-source commit because it adds only calibration data, not new code.

For an uninterrupted complete run, expect `next_index: "2000000"`, `remaining_indices: "0"`, and `output_coverage: {"start":"1000000","stop":"2000000"}` in `status.json`. Two million is the ending cursor, NOT the amount of work in this pilot. `state: "partial"` is a bounded run with work remaining; preserve its continuation and all output batches. A hit is not necessary for a successful pilot. Keep the platform runtime separately from the application elapsed time.

## Reproduce with the unchanged generator

From the computation directory at image-source commit `5055a8fefb59f3c0b2c2ed4902d4df6c6ba3df08`:

```sh
python3 cube_campaign.py --campaign-id ce390-integer-components-pilot-002 \
  --xy-denominator 2 --candidates-per-task 1000000 --page-start 1 \
  --task-count 1 --seconds 3600 --output-dir pilot-002
```

The files are generated under `pilot-002/b2/`. The generator's page start is a TASK ORDINAL, not a candidate offset. This is why the separated slice starts at 1,000,000.

The input was checked using that source's `validate_task` and the collector's `selected_tasks` validator; its task identity, unchanged search/fiber/execution policies, non-overlap and rank/unrank boundary samples were checked. These are configuration checks, NOT results of a new CE run.

Task ID: `56177f0462780a47b6988e19b6873e830ceee0c205f6f61dfb43fcad47a970eb`

Task file SHA256: `5e338654dfa21ba0d64a91f452ef375284651bf4473fd8791986e192be4cb6fd`
