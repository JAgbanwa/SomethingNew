# CE390 container: d-first half-integer target

Use a container built from the exact source revision containing the current
modulo-4 filter, integer `n=1 (mod 3)` checks, and d-first entrypoint.
The production target and 1,800-core-hour project plan are in
[README.md](README.md). The other 200 hours remain reserved for other projects.

Building, testing, or downloading the image does not submit CE jobs. A container's
per-task deadline does not enforce an account-wide budget; follow
[CE_OPERATIONS.md](CE_OPERATIONS.md) for central resource accounting.

## Build and validate

From this computation directory on a Docker host:

```sh
sha256sum --check SHA256SUMS
docker build --platform linux/amd64 --tag ce390-dfirst-local .
python3 container_check.py --image ce390-dfirst-local --output-dir container-evidence-local
```

The multi-stage Docker build installs GMP and a C++17 compiler, builds the native
workers, and runs the regression suite. The runtime contains the compiled
workers, Python, and GMP. It does not require a compiler or network access for
searching. A build made under emulation is not a representative CE benchmark.

The repository's [container workflow](https://github.com/JAgbanwa/SomethingNew/actions/workflows/ce390-container.yml)
builds a Linux amd64 image named `ce390:<source-commit>`, runs its acceptance
checks, exports and reloads the same image, and publishes a release only after
successful checks. Inspect the actual workflow evidence for the source revision
you intend to use. This guide is not evidence that any particular run passed.

The matching release contains:

| Asset | Purpose |
| --- | --- |
| `ce390-linux-amd64.tar` | Uncompressed Docker-save image archive |
| `container-evidence.zip` | Build and container acceptance evidence |
| `SHA256SUMS` | Release asset checksums |

Select the successful run for the intended source commit and its corresponding
release tag. Confirm that its assets exist. Do not use an old image merely
because it has `dthue_worker`: it may lack the new exclusion, verifier assertion,
or default command. Preserve the tested image ID, source SHA, archive checksum,
and worker hash for the campaign and its continuations.

## Load a released image

Download the three assets from the matching
[GitHub Release](https://github.com/JAgbanwa/SomethingNew/releases), then run:

```sh
sha256sum --check SHA256SUMS
docker load --input ce390-linux-amd64.tar
```

On macOS, use `shasum -a 256 -c SHA256SUMS`. Record the exact loaded image tag.
The intended external platform is Linux amd64. A source edit does not update
previously published images, staged tasks, or jobs already submitted.

## Stage and run a current pilot

Generate a short d-first task page using the code from the same revision:

```sh
python3 d_campaign.py --campaign-id ce390-container-dfirst-pilot \
  --h-start 1 --h-stop 121 --output-dir container-pilot-tasks
mkdir -p ce-input ce-output
cp container-pilot-tasks/task-000000-*.json ce-input/task.json
```

Set `CE390_IMAGE` to the exact tested image tag. This local example uses the
rebuilt tag from above:

```sh
CE390_IMAGE=ce390-dfirst-local
docker run --rm --platform linux/amd64 --network none --cpus 1 --memory 512m \
  --mount type=bind,src="$(pwd)/ce-input",dst=/local/input,readonly \
  --mount type=bind,src="$(pwd)/ce-output",dst=/local/output \
  "$CE390_IMAGE"
```

The current default entrypoint runs:

```text
python3 /app/run_d_task.py --task /local/input/task.json --output-dir /local/output
```

Supplying only runner arguments selects that same runner. An explicit command,
including the command above, remains supported. The old `/app/run_task.sh`
requires an explicitly historical task and is not the production default.

Inspect `ce-output/status.json` and retain every output file. An empty
`hits.jsonl` can be a correctly completed pilot. For the supplied half-open
height range `[1,121)`, the strengthened production filter should admit 517
fractions, including all cases left possible by its necessary local conditions.
That count is a useful smoke check, not a proof that the entire solver is correct.

Collect the pilot and verify all returned certificates:

```sh
python3 collect_d.py --page container-pilot-tasks/page.json \
  --results-dir ce-output --output-dir ce-collected
python3 verify_d.py ce-collected/hits.jsonl --m 65
```

This direct container run bypasses `run_d_campaign.py`'s local ledger. Account
its actual usage within the same project allowance if it uses project resources.

## Charity Engine settings

Use a publicly accessible tested image archive or the intended published image
reference. For the custom-image route, the application field has the form:

```text
docker:ce390:<actual-source-commit> <actual-public-image-archive-URL>
```

Copy the actual archive URL from the matching successful release. Do not use an
authenticated Actions-artifact URL as a public CE input. Confirm the provider's
current import and resource settings with a pilot before scaling up.

| Setting | Current value |
| --- | --- |
| Input | One d-first task, staged as `/local/input/task.json` |
| Command | `python3 /app/run_d_task.py --task /local/input/task.json --output-dir /local/output` |
| Task parameterization | `dfirst-thue-height-shells-v1` |
| Production target | `m=65`, `chart=half`, `g_max_digits=100` |
| Coordinate ranges | No `n,x` rectangle |
| Internal task budget | 3,600 seconds by default |
| External allowance | Historically two hours for a 3,600-second task; confirm actual provider limits and charges |
| Output | Every file under `/local/output/`, including failure and continuation records |

Reserve the full possible provider allocation for every submitted attempt before
launch. All remote jobs, continuations, retries, and startup/output charges must
fit within the project's **1,800-hour** allowance under the relevant accounting
unit. The separate 200-hour reserve is unavailable to this project. The local
serial controller cannot enforce the charges of independently submitted CE jobs.

Use the same tested image for a task and all its continuations. A continuation
pins the worker and Python implementation; do not discard those pins to move an
old task to the new filter. A successful local container workflow establishes
build and runtime behavior; the first CE-hosted pilot separately establishes
image import, scheduling, output retrieval, and real-host throughput.

The previous coordinate-rectangle container guide is preserved in
[HISTORICAL_CONTAINER.md](HISTORICAL_CONTAINER.md).

## References

- [CE computing and input/output](https://www.charityengine.com/docs/Computing+with+Charity+Engine)
- [CE Docker packaging](https://www.charityengine.com/docs/Packaging+as+a+Docker+container)
- [Docker image load](https://docs.docker.com/reference/cli/docker/image/load/)
