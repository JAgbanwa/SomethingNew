# Current d-first pilot

`task.json` covers rational heights `1 <= H < 121` for `m=65`, with odd
half-integer coordinates and `|g| <= 10^100`. The strengthened modulo-4 filter
leaves **517** admissible fractions. There are no coordinate rectangle bounds.
The task's soft deadline is 120 seconds; this is a short correctness check,
not a representative campaign throughput estimate or an expected solution.

From the computation directory, run it through the persistent budget controller:

```sh
python3 run_d_campaign.py --page examples/dfirst-pilot/page.json --output-dir pilot-results
python3 collect_d.py --page examples/dfirst-pilot/page.json --results-dir pilot-results --output-dir pilot-collected
python3 verify_d.py pilot-collected/hits.jsonl --m 65
```

The single-task container input is this folder's `task.json`. A direct container
invocation does not use the central controller's ledger; charge it to the same
project allowance externally. A separate pilot ledger does not grant another
1,800 hours. The 200 hours reserved for other projects remain unavailable here.

