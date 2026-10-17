# Integer n and reduced x/y denominator 2: bounded CE390 search

**This task searches for a qualifying a/q; it is NOT known to contain one.** No discovery or success probability is promised. The full equation and all three integrality conditions are retained, not relaxed to manufacture an easy demonstration. A valid hit would provide three integer cubes summing to 390.

## Target and scope

- `n_denominators: [1]`: n must be an integer.
- `xy_denominator: "2"`: x=X/2 and y=Y/2, both in lowest terms, with X,Y odd and Y positive.
- y is the original principal square root; rational d and the original unsquared equation are checked.
- `require_integer_components: true`: -x+y, -x-y, 2*x+6*n must all be integers, with exact cube sum 390.
- Both a and q vary in `n-sixths-xy-interleaved-aq-v1`; neither is fixed or chosen as a known successful parameter.
- Original magnitude bounds: 10^43 <= |n| <= 10^45; 10^54 <= |x| <= 10^55. All signs, no additional coordinate congruences, all rational d eligible.
- ONE task covers **[10000,20000)**: 10,000 candidate indices. This does not overlap the preceding interleaved [0,256) pilot; [256,10000) remains unassigned here. There is no mathematical reason to favor this finite slice as a solution location.
- Internal limit 3,600 seconds; external CE allowance two hours. Neither is a discovery-time estimate. Continuations preserve unfinished work; this job does not run indefinitely until it finds a solution.

This task uses the unchanged interleaved implementation at source commit `1d82c1a841120ca9a496428967f7bd5a9ed54f04`. Its Python and worker pins match the retained CI status and the native SHA256 reported by the user's successful 256-index CE run. Do not remove pins to force another executable or implementation.

## Dashboard

Batch name: `ce390-n-integer-b2-search-001-b2`.
Use the same `C.2x2` instance class as the successful pilot where available. Select an available offer and review its price. Number of jobs: **1**. Maximum hours per job: **2**.

App, one line:

```text
docker:ce390:1d82c1a841120ca9a496428967f7bd5a9ed54f04 https://github.com/JAgbanwa/SomethingNew/releases/download/ce390-container-1d82c1a841120ca9a496428967f7bd5a9ed54f04-38901247314-1/ce390-linux-amd64.tar
```

Command line:

```text
python3 /app/run_xy_task.py --task /local/input/task-000000000001-d13df5856519a9b6.json --output-dir /local/output
```

Single input URL:

```text
https://raw.githubusercontent.com/JAgbanwa/SomethingNew/cf58dea722869378c42d3847f28fdffe5624744b/ce390-pilots/n-integer-b2-search-001/task-000000000001-d13df5856519a9b6.json
```

Do not submit the page manifest or a source ZIP as another input. Do not use the historical `run_task.sh` command. Input-hosting commits differ from the image-source commit because they add task data only.

## How a solution is returned

`Dispatch candidate` means trial parameters, not a solution. A hit is written to `hits.jsonl` after exact checks, with a,q,n,x,y,d and the integer cube components. The log then says `Certified hit`. For this task the certificate must have `n_den: "1"`, `x_den: "2"`, `y_den: "2"`, and `cube_sum: "390"`. The search may complete with no hits; that is not a claim about other slices or the entire coordinate region.

A full uninterrupted run ends at candidate 20000 with zero remaining and output coverage [10000,20000). Save all outputs from every invocation, including continuations. Verify results with the matching task and `verify_xy.py`; collect coverage with `collect_xy.py` and the included page. The two denominator cases and different parameter orderings must not be conflated.

## Configuration validation

The task and page passed the pinned source's validators. All 90 source-manifest hashes matched, and the manifest's Git blob matched the pinned GitHub source. All 10,000 scheduled pairs have distinct a values and distinct q values. The existing preliminary filters leave 1,090 pairs, also with distinct numerators and denominators. Passing necessary filters does NOT prove existence of a solution. This preview performs no native search of the new task.

A local native-policy smoke check on old indices 3 and 13 (outside this assignment) confirmed n_denominators=[1], b=2 and integer-component enforcement. The complete new assignment was not run locally or on CE in preparing these files. No new 217-test-suite run is being claimed; the application is unchanged.

Reproduce with the existing generator:

```sh
python3 cube_campaign.py --campaign-id ce390-n-integer-b2-search-001 \
  --xy-denominator 2 --parameter-order interleaved --n-denominators 1 \
  --candidates-per-task 10000 --page-start 1 --task-count 1 --seconds 3600 \
  --output-dir generated
```

Then add the supplied expected-worker and implementation hash fields. Those runtime pins do not alter task identity. The standalone setup kit contains a script that reproduces the exact pinned input and verifies it.

Task ID: `d13df5856519a9b65cbba5325b9dd1b370198f937fe495fb379a9bbf22c361eb`.
Input SHA256: `9ff875c2600c5ef5bc660488967804a7cf620fc3c4a2c0eca56efb6add67f116`.

Only task data and instructions were added on this branch. No application source, main-branch file, published image, or CE reservation was changed.
