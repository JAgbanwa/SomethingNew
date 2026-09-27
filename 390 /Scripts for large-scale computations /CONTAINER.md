# CE390 container build and deployment

The account owner submits computations through the Charity Engine dashboard,
Remote CLI or API. This repository provides the application and task inputs;
building or testing it does not submit CE jobs or spend CE credits.

## Build and test evidence

The repository workflow
[CE390 container](https://github.com/JAgbanwa/SomethingNew/actions/workflows/ce390-container.yml)
is defined in `.github/workflows/ce390-container.yml`. It runs when the package or
workflow changes on `main`, and can also be started with **Run workflow** in GitHub
Actions. Select a run for the exact source commit you intend to deploy.

The workflow builds a `linux/amd64` Docker image named `ce390:<full-commit-SHA>`.
The Docker build executes the complete Python/C++ regression suite (66 tests at
the time this workflow was introduced). The runtime image contains Python, GMP
and the compiled worker; the compiler and build dependencies remain in the build
stage. Compilation does not request AVX or the build host's native CPU features.

`container_check.py` then checks the built image using Docker, including:

- the supplied pilot and its exact task policy, output files and coverage;
- disabled container networking, one CPU and a 512 MiB memory limit;
- read-only application/input files and a writable `/local/output/` mount;
- execution as a non-root user with a correctly owned output directory;
- the default launch and CE's explicit command line;
- an accelerated computation deadline and continuation into a new output directory;
- SIGTERM handling and error artifacts for invalid input.

These checks exercise the real container and its compiled search worker. Short
deadline tests verify interruption and resumption; they are not hour-long
benchmarks. Inspect the workflow logs and evidence report for the checks that
actually ran and their results. This document describes the acceptance procedure;
its existence is not evidence that a particular workflow run passed.

After all checks succeed, the workflow exports the image with `docker save`,
removes the local tag, reloads the archive with `docker load` and checks that its
image ID equals the tested image ID. It then publishes a GitHub Release with tag
`ce390-container-<full-commit-SHA>-<workflow-run-ID>-<run-attempt>` and these assets:

| Asset | Purpose |
| --- | --- |
| `ce390-linux-amd64.tar` | Uncompressed Docker-save image archive, retaining the image tag |
| `container-evidence.zip` | Container test report and retained evidence |
| `SHA256SUMS` | Checksums of the release assets |

Workflow artifacts also retain build/test evidence. Use the matching run and
release, not an unrelated latest run. Treat released image archives and task URLs
as immutable: never replace their contents while a campaign is running. Keep the
same tested image for all tasks and continuations; continuations also pin the
worker's SHA256 and reject a different binary.

## Download, verify and load the tested image

Open the successful workflow run, note its complete 40-character commit SHA, and
locate the matching tag on the repository's
[Releases page](https://github.com/JAgbanwa/SomethingNew/releases). Download all
three assets from that release into an otherwise empty directory. A rerun has a
different release tag, even when its source commit is unchanged; select the
release associated with the successful run you checked. Do not use a
constructed URL as proof that an asset exists: confirm the release and files are
present first.

In Terminal, change into that directory, then verify the files:

```sh
# macOS
shasum -a 256 -c SHA256SUMS

# Linux alternative
sha256sum -c SHA256SUMS
```

Run the command for your operating system; every listed file must report `OK`.
Next load the archive into a running Docker installation:

```sh
docker load --input ce390-linux-amd64.tar
```

The load output identifies the loaded tag, `ce390:<full-commit-SHA>`. Set a shell
variable to that exact tag, for example
by copying it from the load output:

```sh
CE390_IMAGE='ce390:REPLACE_WITH_THE_ACTUAL_FULL_COMMIT_SHA'
docker image inspect "$CE390_IMAGE" --format '{{.Os}}/{{.Architecture}} {{.Id}}'
```

The platform must be `linux/amd64`. Record the image ID along with the source
commit, archive checksum and workflow run URL. On Apple Silicon, running this
image requires Docker's amd64 emulation; its speed is not representative of CE.

From a checkout of that same commit, change into the directory containing this
document. Run the supplied pilot in fresh input and output directories:

```sh
mkdir -p ce-input ce-output
cp examples/pilot/task-000000000000-13b9502e2c26a4d8.json ce-input/task.json
docker run --rm --platform linux/amd64 --network none --cpus 1 --memory 512m \
  --mount type=bind,src="$(pwd)/ce-input",dst=/local/input,readonly \
  --mount type=bind,src="$(pwd)/ce-output",dst=/local/output \
  "$CE390_IMAGE"
```

Check `ce-output/status.json`: a successful completed pilot has `state: "complete"`
and the assigned interval is fully covered. An empty `hits.jsonl` is a valid search
result, not a deployment failure. Use [CE_OPERATIONS.md](CE_OPERATIONS.md) for
independent collection, verification and continuation handling.

To repeat the container acceptance checks yourself from that package directory,
use a fresh evidence path:

```sh
python3 container_check.py --image "$CE390_IMAGE" --output-dir container-evidence-local
```

## Make the image available to Charity Engine

CE documents two image sources: Docker Hub and a publicly accessible custom image
URL. The registry route is its recommended publication procedure. An account owner
with a Docker Hub repository can publish the already-tested image without
rebuilding it:

```sh
CE390_REMOTE_IMAGE='YOUR_DOCKER_HUB_ACCOUNT/ce390:THE_ACTUAL_FULL_COMMIT_SHA'
docker tag "$CE390_IMAGE" "$CE390_REMOTE_IMAGE"
docker login
docker push "$CE390_REMOTE_IMAGE"
```

Replace both values with the real account and matching source commit. Use a public
repository for CE's documented public-image workflow and preserve the digest from
the push. The CE application field is `docker:` followed by that image name and
tag. Do not put registry or CE credentials in repository files, task JSON, logs or
GitHub Release assets.

For the release archive route, CE documents the custom-image application syntax
`docker:image-name https://public-host/image-file`. With this release's saved
image tag, the corresponding form is:

```text
docker:ce390:<full-commit-SHA> <actual-public-image-archive-URL>
```

Copy the actual download URL for `ce390-linux-amd64.tar` from the release tied to
your successful workflow run. The workflow publishes a standard uncompressed
Docker-save archive and tests reloading it; it does not depend on undocumented
CE compression support. The first CE-hosted pilot must still confirm that CE can
retrieve and import that public release asset.
No authenticated GitHub Actions artifact URL should be supplied as a public image
URL. Do not rebuild the image to work around transport issues: preserve the tested
image and its worker hash.

## Submit one CE pilot

Use the [CE dashboard](https://dashboard.charityengine.com/) or the documented
Remote CLI/API with your own account. Supply:

| Setting | Pilot value |
| --- | --- |
| Application | Accessible image reference from the preceding section |
| Input file | Supplied pilot JSON, staged with the name `task.json` |
| Command line | `/app/run_task.sh --task /local/input/task.json --output-dir /local/output` |
| External allowance | One hour (`--hours 1` in the CLI) |
| Internal computation budget | 3000 seconds in the task JSON |
| Output collection | All files under `/local/output/`, including failure artifacts |

The documented `C.2x2` instance offers two CPU cores and 2 GiB RAM. This package
runs one single-threaded search worker per task; the container acceptance test uses
one CPU and 512 MiB. It does not require a GPU or AVX. Initial CE measurements
determine practical throughput; the local or GitHub runner's speed is not a CE
performance guarantee.

Retrieve the pilot's files and inspect `status.json`. A zero process exit code can
also mean an intentional partial result, in which case submit
`continuation.task.json` as the next `task.json` using the same image. Preserve
earlier outputs and verify contiguous coverage before counting a task complete.

For production, retain 3000-second tasks with `--hours 1`. Use 6000-second tasks
only with `--hours 2` and an agreed two-hour allowance. These leave 10- and
20-minute margins respectively for startup and output handling. Calibrate candidate
counts as described in [CE_OPERATIONS.md](CE_OPERATIONS.md). The account owner
decides how many jobs to submit against available credits.

A passing container workflow establishes reproducible build and local container
behavior. The first CE-hosted pilot separately establishes CE image import,
execution, output retrieval and host performance. Neither test promises a
mathematical solution in the selected search campaign.

## References

- [CE computing, applications and input/output](https://www.charityengine.com/docs/Computing+with+Charity+Engine)
- [CE Docker packaging](https://www.charityengine.com/docs/Packaging+as+a+Docker+container)
- [CE Remote CLI](https://www.charityengine.com/docs/Charity+Engine+Remote+CLI)
- [CE instance types](https://www.charityengine.com/docs/Charity+Engine+Instance+Types)
- [Docker image load](https://docs.docker.com/reference/cli/docker/image/load/)
