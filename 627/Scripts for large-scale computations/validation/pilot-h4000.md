# Local pilot: k = 627, heights 1 <= H < 4000

Run on 30 Oct 2026 on the development host (shared cloud VM, one core per task),
worker version 1.0.0, with the production pipeline:

```sh
python3 make_campaign.py --campaign-id ce627-local-pilot --h-stop 4000 --task-hours 0.05 --output-dir pilot
python3 run_task.py --task pilot/tasks/ce627-local-pilot-0.json --output-dir pilot-res/ce627-local-pilot-0
python3 run_task.py --task pilot/tasks/ce627-local-pilot-1.json --output-dir pilot-res/ce627-local-pilot-1
python3 collect.py --results pilot-res --page pilot/page.json --output-dir pilot-col
```

| Quantity | Value |
| --- | --- |
| Raw pairs `(p, q)` | 31,988,001 |
| Admissible `d` solved | 820,834 (2.57 %) |
| Convergents tested | 160,024,865 |
| Precision refinements / exact roots | 0 / 0 |
| `g` bound | `1 <= abs(g) <= 10^100` |
| Coverage / gaps | `[1, 4000)` / none |
| Elapsed | 132.4 s + 66.9 s = 199 s (6.2 us/pair) |
| **Hits** | **0** (integer chart 0, half chart 0) |

So no rational `d` with height below 4000 has a point, in either chart,
with `|g| <= 10^100` (i.e. `|x| <= q * 10^100 / 2`). The task files are in
`examples/pilot/`; `pilot-h4000-summary.json` is the collector's output.
