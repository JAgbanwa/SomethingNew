# CE390 task examples

Use `general-pilot/` for new calibration and `general/` for initial general
search pages. Neither contains a selected numerator list. Every allowed
numerator for each assigned denominator is derived from the integer bounds.

- `general-pilot/`: one 30,000-index task in an explicit denominator window
  around 10^12. It exercises many numerators; the window is a performance
  sample, not a prediction of where a solution lies. Only its included page
  is assigned, even though its manifest describes additional possible tasks.
- `general/`: ten initial 50,000,000-index tasks in the full derived parameter
  enclosure. The count is a chunk-size example to calibrate. Each task has a
  3600-second soft budget and may return a continuation. The enormous total
  in the manifest is an implicit mathematical domain, not a funded campaign.

The ordering is by increasing denominator, then increasing numerator. Early
rows may have only a=1 because the exact bounds exclude other numerators there;
later rows automatically introduce 5, 7, 11, and further admissible numerators.
No numerator is assumed to be successful. No finite completed prefix establishes
that the full integer rectangle has been searched.

`pilot/`, `50min/`, `60min/`, and `100min/` are **historical a=1 fixtures**.
Their original bytes remain available to verify old results and regression
evidence. They are superseded for the requested general search. Do not mistake
their old 49.95-billion-index total for the size of the new general campaign.

All these parameter domains can overlap. Track exact completed coverage before
submitting further work. The scripts do not submit CE jobs or enforce the
campaign-wide 2,000 CPU-hour allowance. Submit 3600-second tasks with CE
`--hours 2` to leave startup and output time.
