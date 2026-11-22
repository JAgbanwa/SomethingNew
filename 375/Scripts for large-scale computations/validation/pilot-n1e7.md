# Local pilot: k = 375, all n with |n| < 10^7

Run on 22 Nov 2026 on the development host (shared two-core cloud VM, one core
per task), worker version 1.0.0, through the production pipeline:

```sh
python3 make_campaign.py --campaign-id ce375-local-pilot --n-start -10000000 --n-stop 10000000 \
  --us-per-n 120 --task-hours 0.12 --output-dir camp
python3 run_task.py --task camp/tasks/ce375-local-pilot-0.json --output-dir res/ce375-local-pilot-0
python3 run_task.py --task camp/tasks/ce375-local-pilot-1.json --output-dir res/ce375-local-pilot-1
python3 collect.py --results res --page camp/page.json --output-dir col
```

| Quantity | Value |
| --- | --- |
| `n` range / processed `n` (`n = 2 mod 3`) | `[-10^7, 10^7)` / 6,666,667 |
| Divisors of `N(n)` tested | 214,306,182 (645,796,700 candidate `x`, both forms and signs) |
| Exact GMP square tests | 11,964,703 |
| `n` not fully factored | **0** |
| Coverage / gaps | `[-10^7, 10^7)` / none |
| Elapsed | 407 s + 395 s = 802 s (120 us per processed `n`, both tasks in parallel) |
| **Points** | **3**, all non-primitive |
| **Desired (primitive) points** | **0** |

| form | `n` | `x` | `y` | cubes | `gcd` point / cubes |
| --- | ---: | ---: | ---: | --- | --- |
| integer | 2 | -5 | 0 | 5, 5, 5 | 1 / 5 |
| integer | 2 | -20 | 0 | 20, 20, -25 | 2 / 5 |
| half | 2 | 5/2 | ±45/2 | 20, -25, 20 | 5 / 5 |

So, with every factorisation proved (`|N(n)| < 3.317e24` throughout this
range): **there is no rational point of either form with `|n| < 10^7` other
than these three, whatever the size of `x` and `y`, and none of them is
primitive.** Files: `pilot-n1e7-summary.json`, `pilot-n1e7-hits.jsonl`,
`pilot-n1e7-points.txt`; task files in `examples/pilot/`.
