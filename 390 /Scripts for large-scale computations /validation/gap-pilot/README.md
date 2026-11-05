# Gap-search pilot, k = 390 (5 Nov 2026)

Development host, 2 cores, worker 1.0.0, R = 64, through the production pipeline:

```sh
python3 gap_campaign.py --campaign-id ce390-gap-pilot --d-stop 185185187185185186 \
    --task-d-count 1000000000 --us-per-d 0.27 --output-dir pilot
python3 run_gap_task.py --task pilot/tasks/ce390-gap-pilot-0.json --output-dir res/ce390-gap-pilot-0   # and -1
python3 collect_gap.py --page pilot/page.json --results res --output-dir col --require-complete
python3 audit_gap.py --page pilot/page.json --results res --fraction 0.05 --seed 390
```

| Quantity | Value |
| --- | --- |
| Covered | `d` in [185185185185185186, 185185187185185186), `3.847 d <= |z| <= 64 d` |
| `d` values | 2,000,000,000 (gaps: none) |
| Worker time | 0.145 core-hours (0.26 µs per `d`) |
| Audit | 6/6 sampled chunks reproduce exactly |
| Hits | 0 |

So x^3 + y^3 + z^3 = 390 has no solution with |x + y| in that range and
3.847|x+y| <= |z| <= 64|x+y|. (Heuristic expectation for this slice: 2.7e-10.)
The task files are in `examples/gap-pilot/`; `summary.json` is the collector's output.
