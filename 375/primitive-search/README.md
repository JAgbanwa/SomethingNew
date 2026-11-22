# Search for a primitive representation of 375

The target is an integer triple satisfying

\[
x^3+y^3+z^3=375,\qquad \gcd(x,y,z)=1.
\]

**No primitive 375 solution has been found by this work.** This package supplies a tested worker, a measured local search model, a completed local pilot, bounded Charity Engine submission tools, and precise collection of the regions actually searched. No Charity Engine job has been submitted.

This is a standalone adaptation of this repository's `114 /Algorithm for computation /gap-search` worker at commit `052a0e2672f96c97fd5bebfdac7c9ad4830eafbb`. Its pair-sum method follows the Booker–Sutherland approach. Existing 114 and 390 campaigns are separate projects with their own budgets.

## Why 375, and what counts as progress?

375 already has representations such as `5^3 + 5^3 + 5^3`. Multiplying a solution for 3 by 5 produces another such representation. The intended discovery is the first **primitive** representation, if still unknown when found. Every returned hit is checked independently with Python integers, including its gcd, exact cube sum, pair sum and search bounds.

As checked on 22 November 2026, the [Nakao primitive-solution table](https://www.kaynet.or.jp/~kay/misc/aa3-1000.html#375) still marks primitive 375 as unknown. [Huisman's published search](https://arxiv.org/abs/1604.07746) covers coordinate heights through `10^15`. A [14 November 2026 search announcement](https://community.openai.com/t/ai-helps-locate-undiscovered-solution-to-sum-of-three-cubes/1416364) describes ongoing work between heights `10^15` and `10^16`, including 375. An announcement is not a completed coverage certificate. The default here starts strictly above `10^16` to complement that stated range; this does not establish that no one else has searched there.

A successful new primitive triple would resolve a specific outstanding computational case. A run with no hit establishes absence only in the exact recorded bands, subject to validation and hardware audits. It would not prove that primitive 375 is impossible or establish a complete new coordinate-height bound.

## What changed in the worker

- `--primitive-only` rejects every nonprimitive hit exactly. For 375 it also skips pair sums with 5-adic valuation 1 or 2, and prunes impossible lifts when `125` divides the pair sum.
- Singular cube roots modulo prime powers are enumerated completely. The old brute-force size cap is removed, which matters because `375 = 3*5^3`.
- `--height-min H` requires `max(abs(x),abs(y),abs(z)) > H`. A conservative exact block-level cutoff avoids enumerating candidates below that height. Final hits receive an exact height check.
- The lower `z` bound uses 128-bit arithmetic. GMP handles exact cube, square and gcd calculations.
- Deadlines are checked after every 65,536-value sieve block. Checkpoints flush after approximately 30 seconds, the requested count, a deadline, or completion. A native deadline can overrun by one block. The bundle runtime also applies a wall-clock watchdog.
- Checkpoints bind the worker binary and all coverage-affecting task parameters. Collectors validate registered intervals and report partial work as partial.

See [MATH.md](MATH.md) for the pruning arguments and the probability model. These changes are an engineering adaptation, not a claimed new general algorithm or theorem.

## Build and run the supplied pilot

Dependencies: C++17 compiler, GMP development headers, Python 3.11 or later, and NumPy for the inherited regression tests. On Debian/Ubuntu:

```bash
sudo apt-get install g++ make libgmp-dev python3 python3-numpy
make
make test
```

The supplied pilot searches 100 million pair-sum values in two concurrent tasks:

```bash
python3 run_ce_bundle.py \
  --manifest examples/pilot/bundle.json \
  --copy-index 0 \
  --output-dir results/pilot

python3 collect_gap.py \
  --page examples/pilot/page.json \
  --results results/pilot \
  --output-dir results/pilot-collected \
  --require-complete

python3 audit_gap.py \
  --page examples/pilot/page.json \
  --results results/pilot \
  --fraction .02 --min-chunks 1 --seed 375
```

The pilot's exact region has `d = abs(x+y)` in `[1000000000000, 1000100000000)`, `abs(z) <= 32768*d`, the worker's canonical lower bound, and strict coordinate height above `10^16`. It is a functional pilot, not a meaningful fraction of the production campaign. The example's two-minute task deadline may return partial work on a slower host; the collector will expose the gap.

Recorded local result: 100,000,000 `d` values covered, 112,221,288,971 candidate progression entries, 3,215,147 exact checks, zero hits and zero gaps. One independently rerun chunk, covering 16,777,216 `d` values, matched every deterministic counter. See `validation/pilot-collected/summary.json`, `validation/pilot-audit.txt` and the original returned files under `validation/pilot-results/`.

## Calibrate before choosing a large campaign

Run the bounded calibration on representative target hardware:

```bash
python3 benchmark375.py \
  --height-min 10000000000000000 \
  --output calibration.json \
  --budget-seconds 180 --sample-seconds 3 --repeats 2
```

Only add `--measurement-environment charity-engine` when that command actually runs on a CE host. A `--quick` run is an integration check and cannot supply a planning fit. The benchmark saves returned worker records and independently verifies any hits, including when a later sample fails.

The recorded local fit from 24 samples is

\[
\text{nanoseconds per }d
\simeq 254.725+0.0138716\max(0,R-r_{\min}(d)).
\]

The median absolute relative error was 2.19%, with a maximum of 7.65%. Two additional low-`d`, high-`R` samples were about 4% slower than this fit. This is local-host evidence, not a measurement of CE performance. See `validation/local-benchmark.json` and `validation/extreme-benchmark.json`.

## A reviewable 2,000-core-hour allocation

This plan interprets the allowance as **core-hours**. One hour on a two-core instance reserves two core-hours.

| Allocation | Core-hours |
|---|---:|
| Up to 900 two-core instances, at most one hour each | 1,800 |
| Remaining allowance for calibration, audits and follow-up | 200 |
| Total | 2,000 |

The proposed tasks each have a 42-minute modeled runtime and a 45-minute worker deadline. Per-band rounding and the instance allowance leave about 1,231.8 modeled productive core-hours. Setup, output transfer, scheduling differences, partial work and retries are not treated as productive search time.

Generate the measured-host proposal:

```bash
python3 band_campaign.py \
  --campaign-id ce375-primitive \
  --output-dir campaigns/production \
  --core-hours 1250 \
  --height-min 10000000000000000 \
  --benchmark-json validation/local-benchmark.json \
  --task-hours .70 --deadline-seconds 2700 --max-tasks 1800

python3 pack_ce.py \
  --campaign campaigns/production/campaign.json \
  --output campaigns/production/bundle.json \
  --max-core-hours 1800
```

Use a new output directory each time. Replace the benchmark file with CE measurements before bulk submission. The planner budgets the actual constant-ratio bands and reduces its productive-hour target when task rounding would exceed the task cap.

The recorded proposal has 74 bands, 1,799 tasks paired into 900 instances, and pair sums from `10^6` through `12,089,131,427,541` exclusive. Its ratios vary by band. The density heuristic gives expected count `0.0240044`; additionally modeling counts as Poisson gives about **2.37%** probability of at least one hit. These are assumptions, not confidence intervals or a guarantee.

For comparison, using the same timing coefficients with a `10^15` floor gives roughly **5.84%** under the same probability model. That alternative has not been separately calibrated and overlaps the announced ongoing search. Determine available coverage before spending the budget there. The chosen `10^16` floor prioritizes complementing that search.

`validation/production-plan.json` records the proposal. Its band page references are generated by the command above; the generated campaign and its 1,799 task files are not checked into Git.

## Docker and Charity Engine

Build and check the complete image:

```bash
docker build --platform linux/amd64 --tag primitive375:local .
python3 container_check.py --image primitive375:local --output-dir container-check
```

The Docker build runs the full suite. The integration harness checks source and binary identities, both entrypoint modes, actual concurrent tasks, exact collection and recovery of a known primitive solution for 600. Test containers run without network access. The repository's `CE375 primitive search` workflow performs these checks and exports the tested image as a GitHub Actions artifact.

CE must be able to retrieve the image from a supported registry or an HTTPS `docker save` archive. The workflow artifact is a build deliverable; it is not itself a public CE image URL. After loading and publishing the tested image, supply its real versioned name and, when needed, its archive URL.

Stage and inspect a pilot without making any external call:

```bash
python3 ce_submit.py \
  --manifest examples/pilot/bundle.json \
  --image docker:YOUR_PUBLISHED_IMAGE:VERSION \
  --ce-cli /absolute/path/to/ce-cli \
  --workdir ce-state/pilot \
  --max-core-hours 2
```

For an archive, add `--image-tar-url https://YOUR_HOST/primitive375-image.tar`. After configuring `CE_AUTH_TOKEN` locally, use the same command with `--submit`. Use the same command and work directory with `--retrieve` to collect results. Do not place a token in a task, bundle, repository or chat message.

The launcher splits copies into batches of at most 500 and reserves each full allocation before calling the official CLI. It preserves ambiguous submissions as charged reservations and refuses automatic resubmission. Retrieval requires the original nonempty CLI checkpoint. Retain the work directory. The ledger applies to this exact plan and cannot account for jobs started elsewhere; subtract any earlier CE allocations before setting a new cap.

The pilot is charged against the 200-hour reserve, not added beyond the 2,000-hour total. Run and retrieve a CE pilot before bulk work. There are no CE credentials or live CE jobs embedded in this package.

## Collect, audit, and report

For a band campaign:

```bash
python3 collect_campaign.py \
  --campaign campaigns/production/campaign.json \
  --results ce-state/production \
  --output-dir results/production-collected \
  --require-complete
```

This reports the union of the actual bands, each with its own ratio, height floor and gaps. Run `audit_gap.py` on the returned chunks for each band page to sample hardware correctness. A sampled audit is evidence about returned work, not a formal proof of complete enumeration.

For a partial task, preserve its outputs and use `continuation.task.json` for further work. Reusing the same output directory is permitted only with the same worker binary and compatible checkpoint. A fresh directory can hold a continuation with a rebuilt worker; collect both directories to retain their respective coverage. Further CE allocations require remaining budget and a separately accounted plan.

If a hit appears, preserve the original output, source/image hashes and task manifest; recheck the cube identity and gcd independently; and compare with the current literature before asserting priority.

## References

- Booker and Sutherland, [On a question of Mordell](https://arxiv.org/abs/2007.01209), PNAS 118 (2021), e2022377118.
- Huisman, [Newer sums of three cubes](https://arxiv.org/abs/1604.07746), 2016.
- [Nakao's primitive solutions table](https://www.kaynet.or.jp/~kay/misc/aa3-1000.html#375), checked 22 November 2026.
- [Recent search announcement and primitive 192 triple](https://community.openai.com/t/ai-helps-locate-undiscovered-solution-to-sum-of-three-cubes/1416364), 14 November 2026. Its other claims should be checked individually; for example, a primitive 600 solution already occurs in the older tables and is used here as a positive control.
- Charity Engine [Remote CLI](https://www.charityengine.com/docs/pages/18677786/Charity%2BEngine%2BRemote%2BCLI) and [Docker packaging](https://www.charityengine.com/docs/pages/153354261/Packaging%2Bas%2Ba%2BDocker%2Bcontainer).
