# Local pilot: k = 375, heights 1 <= H < 4000

Run on 22 Nov 2026 on the development host (shared two-core cloud VM, one core
per task), worker version 1.0.0, with the production pipeline:

```sh
python3 make_campaign.py --campaign-id ce375-local-pilot --h-stop 4000 --task-hours 0.05 --output-dir pilot
python3 run_task.py --task pilot/tasks/ce375-local-pilot-0.json --output-dir pilot-res/ce375-local-pilot-0
python3 run_task.py --task pilot/tasks/ce375-local-pilot-1.json --output-dir pilot-res/ce375-local-pilot-1
python3 collect.py --results pilot-res --page pilot/page.json --output-dir pilot-col
```

| Quantity | Value |
| --- | --- |
| Raw pairs `(p, q)` | 31,988,001 |
| Admissible `d` solved | 1,226,189 (3.83 %) |
| Convergents tested | 239,050,626 |
| Precision refinements / exact roots | 0 / 0 |
| `g` bound | `1 <= abs(g) <= 10^100` |
| Coverage / gaps | `[1, 4000)` / none |
| Elapsed | 148.5 s + 84.8 s = 233 s (7.3 us/pair, both tasks in parallel) |
| Thue solutions / other branch | 4 / 1 |
| **Hits** | **3** (integer chart 2, half chart 1) |
| **Desired (primitive) hits** | **0** |

The three hits are all non-primitive (cube components share the factor 5):

| `d` | chart | `n` | `x` | `s` | cubes | `gcd` point / cubes |
| --- | --- | --- | --- | --- | --- | --- |
| `1` | integer | 2 | -5 | 0 | 5, 5, 5 | 1 / 5 |
| `-1/8` | integer | 2 | -20 | 0 | 20, 20, -25 | 2 / 5 |
| `-8` | half | 2 | 5/2 | 45/2 | 20, -25, 20 | 5 / 5 |

So no rational `d` with height below 4000 has a **primitive** point, in either
chart, with `|g| <= 10^100` (i.e. `|x| <= q * 10^100 / 2`). For the three
`d` above, `tools/certify_d.gp` (PARI `thue()`, unconditional, no bound on
`g`) confirms these are their only points.

Files: task files in `examples/pilot/`, collector output in
`pilot-h4000-summary.json`, `pilot-h4000-hits.jsonl` and
`pilot-h4000-d_values.txt`.
