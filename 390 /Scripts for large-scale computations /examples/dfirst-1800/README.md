# 1,800-hour project plan preview

`plan-preview.json` is the output of `d_campaign.py --plan-only` using the
production defaults. It is a summary for review, not a task or an executable
page manifest. No search was launched to generate it.

The defaults give:

- Project ceiling: **1,800 aggregate core-hours**.
- Estimated work allowance: **1,600 hours**, leaving project headroom within the ceiling.
- Separate reserve for other projects: **200 hours outside this project**.
- Planning rate: **4.5 microseconds per raw pair**; recalibrate on the actual hosts.
- Rational heights: **1 through 799,999**, inclusive.
- Scope per rational parameter: **1 <= |g| <= 10^100**; no n,x rectangle.
- Generated task count: **1,901**; each task and its continuations retain exact coverage.

Generate the actual page and tasks in a new directory:

```sh
python3 d_campaign.py --campaign-id ce390-dfirst-1800 --output-dir dfirst-tasks
```

Run and resume with `run_d_campaign.py`, reusing one results directory and its
budget ledger. The controller counts errors, retries, and continuations. A
partial run must not be reported as full height coverage. Independently
submitted provider jobs require separate central accounting within the same
1,800-hour allowance.

