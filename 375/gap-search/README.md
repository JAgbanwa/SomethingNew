# CE375 primitive gap search: finding primitive representations of 375

**Goal.** Rational `x, y` with `n` an integer on

```text
y² = (x + 6n + 3)² + (36n³ + 54n² + 27n − 58)/x,     36n³ + 54n² + 27n − 58 = ((6n+3)³ − 375)/6,
```

accepting primitive integers `(n, x)` with `y` an integer, or `x = X/2`, `y = Y/2` with `X, Y` odd
and `gcd(X, Y) = 1`. With `A = −x + y`, `B = −x − y`, `C = 2x + 6n + 3`, the equation is exactly
`A³ + B³ + C³ = 375`, so the accepted points are the points of *primitive* representations
`375 = a³ + b³ + c³`, `gcd(a, b, c) = 1` (one representation gives up to three points, in either
chart). This folder searches for those representations; `to_points375.py` turns each one into its
points `(n, x, ±y)` with the same flags as the d-first folder (`primitive_point`,
`primitive_cubes`, `desired`) and checks every point exactly on the equation.

## 1. Why this folder exists

The engine in [`../Scripts for large-scale computations/`](../Scripts%20for%20large-scale%20computations/)
reaches each point through the slope `(A+C)/(A+B)` of its representation, enumerated by height `H`. A representation of size `M` only appears at
height about `M/g`, with `g = gcd(A+B, A+C)`, so it is reached only if `g ≥ M/H`. Nothing forces
`g` to be large, and under the Booker–Sutherland model the d-first yield on 1,800 core-hours
(`H ≈ 1.5·10⁶`) is `E/ρ ≈ 5·10⁻⁹` for a frontier of `10¹⁵`. The search here enumerates where
solutions are expected instead, `δ = |a+b|` and the cube roots of 375 modulo `δ`
(Booker–Sutherland), restricted to `δ` that can carry a primitive solution, and starts at the
frontier of what has already been searched. Measured plans give `E/ρ ≈ 0.4–2.7` on the same
1,800 hours (section 4), about **10⁸ times** the d-first figure.

That engine stays useful for exact statements about points whose slope has small height; it is not
the tool for finding a representation.

## 2. Mathematics

Write a solution with `|a| ≥ |b| > |c|`, `δ = |a+b|`, `z = |c|`. Booker–Sutherland: `δ < α z`
(`α = 2^(1/3) − 1`), `z³ ≡ ±375 (mod δ)`, and `Δ = (4(z³ − K)/δ − δ²)/3 = (a−b)²`. Since
`375 ≡ 6 (mod 9)`, all of `a, b, c ≡ 2 (mod 3)`, exactly as for 114, so the sign and residue
rules of the 114 engine apply unchanged.

**Lemma (primitive δ).** Let `p ≠ 3` be a prime with `p³ | k` and `p ≡ 2 (mod 3)` (for 375: `p = 5`).
If `gcd(a, b, c) = 1`, then `v_p(δ) = 0` or `v_p(δ) ≥ 3`.

*Proof.* If `p ∤ c`, then `a³ + b³ = k − c³ ≢ 0 (mod p)`, so `p ∤ a + b`. If `p | c`, then `p ∤ a`
(otherwise `p | b³ = k − a³ − c³`, and `p | gcd`), likewise `p ∤ b`, so `a ≡ −b (mod p)` gives
`a² − ab + b² ≡ 3b² ≢ 0 (mod p)`. Hence `v_p(a+b) = v_p(a³+b³) = v_p(k − c³) ≥ min(v_p(k), 3) = 3`. ∎

So for 375 every `δ` with `5 ∥ δ` or `25 ∥ δ` is skipped (`--primitive`), 19.2 % of the `δ` prime
to 3. Every `δ` with `5 ∤ δ` can only carry primitive solutions; for `125 | δ`, the worker tags each
hit with `primitive = [gcd(x, y, z) = 1]`.

**Roots modulo `p^e` for `p | k`.** With `k = p^v u`, `p ∤ u`: for `e ≤ v` the roots of `z³ ≡ k` are
the multiples of `p^⌈e/3⌉`; for `e > v` they need `3 | v`, and then `z = p^(v/3) z'` with
`z'³ ≡ u (mod p^(e−v))` (cube roots and Hensel lifting as for other primes), `z'` free modulo
`p^(e−v/3)`. For 375 this gives 25 roots modulo `5^e` for every `e ≥ 3`. The worker builds these
directly, for any `e` (the inherited brute force refused `5^11 | δ`).

## 3. The frontier and the yield model

For 114, Booker and Sutherland's runs excluded every `δ` up to `10¹⁹/54`. Their algorithm is
stated for cube-free `k`, so 375 may not have been in those runs. The public bound that does
cover all `k < 1000`, primitive solutions of 375 included, is Elsenhans–Jahnel's Elkies-type search
with `max(|a|, |b|, |c|) ≤ 10¹⁴` (Huisman later reached `10¹⁵`). The planner takes this
**frontier** `N` as a parameter (`--frontier`, default `10¹⁴`) and counts only solutions beyond it:
the largest coordinate is `(δ + √Δ)/2`, so a solution lies beyond `N` exactly when

```text
z³ > δ (3 (2N − δ)² + δ²) / 4.
```

Integrating the Booker–Sutherland density `ρ/(2√α) δ^(−1/2) z^(−3/2)` over `δ/α < z ≤ Rδ` above that
curve gives the expected number of primitive solutions `E` in a campaign, as a multiple of `ρ`.
The frontier moves the best region to *small* `δ` with a *large* ratio `R`, where each `δ` is cheap
and carries a lot of heuristic weight.

`ρ` (Heath-Brown's constant for primitive solutions of 375) is **not** computed here: Booker and
Sutherland tabulate it only for cube-free `k`, and the local factor at 5 changes. All yields below
are therefore stated as `E/ρ`; for scale, `ρ₁₁₄ = 0.058`.

## 4. Measured plans for 1,800 core-hours

Calibration (`gap_campaign.py --calibrate`, k = 375, `--primitive`, development host, one core):

| ratio_max | µs per δ at δ = 10¹⁰ | µs per δ at δ = 10¹² |
| ---: | ---: | ---: |
| 1024 | 0.211 | 0.221 |
| 2048 | 0.245 | 0.238 |
| 4096 | 0.271 | 0.289 |
| 8192 | 0.385 | 0.367 |
| 16384 | 0.463 | 0.553 |
| 32768 | 0.700 | 0.690 |
| 65536 | 1.206 | 1.186 |

Best plans (`gap_campaign.py --optimize`, 1,800 core-hours), against the d-first engine on the same
hours and the same model:

| frontier N | best plan | **E/ρ, this engine** | E/ρ, d-first (H ≈ 1.5·10⁶) |
| --- | --- | ---: | ---: |
| 10¹⁴ | δ from 5.6·10⁸ to 2.4·10¹³, R = 4096 | **2.66** | ~5·10⁻⁸ |
| 10¹⁵ | δ from 5.6·10⁹ to 2.4·10¹³, R = 4096 | **1.07** | ~5·10⁻⁹ |
| 10¹⁶ | δ from 5.6·10⁹ to 1.4·10¹³, R = 16384 | **0.39** | ~5·10⁻¹⁰ |

If `ρ` for primitive 375 is near `ρ₁₁₄`, the 10¹⁵ row is about a 1 in 16 chance; compare 1 in
151,000 for 114 on the same hours. **Two things must be confirmed before launch**, because the
estimate rests on them:

1. **The frontier.** Ask Booker or Sutherland (or Charity Engine) whether any search beyond the
   Elkies-type bounds has covered primitive solutions of 375. A higher frontier lowers `E/ρ` as in
   the table; a search that already covered this `(δ, z)` region would make the campaign redundant.
2. **`ρ` for primitive 375**, from Heath-Brown's local densities with the factor at 5 for primitive
   solutions.

## 5. Running

```sh
make && make test                                    # 31 tests, about 2.5 minutes
python3 gap_campaign.py --calibrate --calibration-d 1e10 --save-calibration calib.json   # on the grid's CPU
python3 gap_campaign.py --optimize calib.json --core-hours 1800 --frontier <confirmed N>
python3 gap_campaign.py --campaign-id ce375-gap --core-hours 1800 --d-start <D0> --ratio-max <R> \
    --us-per-d <measured> --frontier <N> --output-dir ce375-gap-tasks
# each task (Charity Engine: the container's default command on /local/input/task.json)
python3 run_gap_task.py --task ce375-gap-tasks/tasks/ce375-gap-0000.json --output-dir results/ce375-gap-0000
# afterwards
python3 collect_gap.py --page ce375-gap-tasks/page.json --results results --output-dir collected --require-complete
python3 audit_gap.py   --page ce375-gap-tasks/page.json --results results --fraction 0.02
python3 to_points375.py collected/hits.jsonl              # points and d in both charts, DESIRED flagged
```

Tasks are primitive by default (`"primitive": true`); the runner, collector and auditor all check
it. Checkpointing, continuations, coverage gaps and the 2 % audit are those of the 114 pipeline.

## 6. Validation (`make test`, 31 tests)

* **Inherited engine tests (16):** the record solutions of 33, 42, 3, 165, 579, 795, 906; a brute
  force for every `k ≡ ±3 (mod 9)` up to 100; filter verdicts against exact arithmetic (including
  `z ≥ 2⁶⁴`); factorizations and roots at production size; plan / run / interrupt / resume /
  collect; coverage accounting and the audit.
* **Cube-factor and primitive tests (15):**
  * roots modulo every `δ < 2500` against brute force for `k = 24, 375, 1875, 3000, 7125, −375`, and
    root counts at `δ ≈ 10¹³` divisible by `5^e`, `e` up to 17;
  * the lemma checked on every primitive solution with coordinates up to 600 for those `k`;
  * a brute force over coordinates up to 1500 for `k = 24, 48, 375, 750, 1875, 3000, 6000, 7125`:
    without `--primitive` the worker finds exactly the solutions in its region with correct
    `primitive` flags; with it, exactly the primitive ones;
  * `--no-filter` gives identical hits; `5 × (the k = 3 record)` is found and tagged non-primitive
    without `--primitive` and skipped with it; cube-free `k` are unaffected; `k = 3·7³` is refused
    (`7 ≡ 1 mod 3`, where the lemma does not hold);
  * counters are identical however a range is split (the audit's precondition);
  * the converter agrees with the d-first folder's `common375.py` on points, `d` and flags;
  * the yield model reduces to the closed form without a frontier and places the frontier exactly;
  * an end-to-end campaign at `k = 7125 = 57·5³` finds its primitive solution `(−67)³ + (−46)³ + 74³`,
    collects it as PRIMITIVE, audits cleanly and converts it to two desired half-chart points.

**Pilot at k = 375** (worker 1.2.0, 22 Nov 2026, through plan / run / collect / audit):
`δ ∈ [5623413252, 7623413252)`, `R = 4096`, `--primitive`, two tasks in parallel on the two-core
development host.

| Quantity | Value |
| --- | --- |
| `δ` values | 2,000,000,000 (gaps: none) |
| skipped: `3 \| δ` / primitivity lemma / no cube root | 666,666,667 / 256,000,000 / 700,605,724 |
| `δ` processed, cube roots | 376,727,609, 953,402,561 |
| candidates `z` | 325,122,046,498 (163 per `δ`) |
| exact GMP checks | 9,953,920 |
| worker time | 0.154 core-hours (0.28 µs per `δ`) |
| audit (5 %) | 6 / 6 chunks reproduce exactly |
| representations of 375 | 0 |

Heuristic weight of the pilot region: `E/ρ = 1.06·10⁻⁴` (frontier `10¹⁵`). The first audit of an
earlier build caught a split-dependent accounting difference (the primitivity skip was read from
sieve factor lists); it was fixed, and a regression test now requires identical counters however a
range is split.

## 7. What a completed run proves

That 375 has no primitive representation with `δ = |a+b|` in the covered range and
`3.847 δ ≤ |c| ≤ R δ`, and hence no accepted point `(n, x, ±y)` of either chart arising from one. The odds in
section 4 are heuristic, and conditional on the frontier and on `ρ`.
