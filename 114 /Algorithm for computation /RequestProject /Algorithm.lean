import RequestProject.Main

/-!
# Correctness of the search algorithms

This file contains the mathematics that the large-scale (grid) search programs in `grid/` rely
on.  Everything is stated for the equation

```
36 n³ - 19 = -2 d x² (-(x + 6n) + √((x+6n)² + (36n³-19)/x))      (`DEquation.Sat d n x`)
```

studied in `RequestProject/Main.lean`, and in particular for the *integral certificate*
`U = 2 d x²`, which (`DEquation.sat_iff_exists_U`) is always an integer and satisfies

```
U² + 2 U x (x + 6n) = x (36 n³ - 19).                                        (★)
```

The results below are exactly the facts the search programs use.

* `sat_iff_dSweep` — the **d-first sweep** (Algorithm A).  A pair `(n, x)` solves the equation
  for the rational `d` iff the integer `U = 2dx²` divides-condition `U² = c·x` holds for an
  integer `c` and `n` is a root of the cubic `36 n³ - 12 U n = c + 2 U x + 19`.  So one can
  enumerate `U` (i.e. enumerate candidate `d`), then `x ∣ U²`, and *solve* for `n` by a cube
  root, instead of enumerating `n` and `x`.
* `sat_U_dvd`, `sat_abs_x_le_U_sq` — for each `U` only the divisors of `U²` have to be tried.
* `sat_abs_n_le_abs_U` — `|n| ≤ |U|`: this calibrates the sweep, a `D`-digit `n` requires a
  `D`-digit (or larger) `U`.
* `sat_U_mod_twelve` — the congruence filter for the family `n = 3m`, `x = 12u + 7` asked for
  by the user: `U ≡ 5` or `11 (mod 12)`, so 10 of every 12 values of `U` can be skipped.
* `mordell_of_sat`, `sat_of_mordell_point` — the **per-`x` elliptic curve** view (Algorithm C):
  for fixed `x` the solutions are the integral points of the Mordell curve
  `V² = Z³ - 432 x³ (x³ + 57)` with `Z = 12x(3n + x)`, `V = 36 x Y`.  This is the only one of
  the three views that is not bounded in `n`, and is what a large-digit search must use.
-/

namespace DEquation

open scoped Classical

/-! ### The divisibility structure of the certificate `U` -/

/-- From `(★)`, `x` divides `U²`. -/
theorem sat_U_dvd {U n x : ℤ}
    (h : U ^ 2 + 2 * U * x * (x + 6 * n) = x * (36 * n ^ 3 - 19)) :
    x ∣ U ^ 2 :=
  ⟨36 * n ^ 3 - 19 - 2 * U * (x + 6 * n), by linarith [h]⟩

/-- A certificate is never zero: `U = 0` would force `36n³ = 19`. -/
theorem sat_U_ne_zero {U n x : ℤ} (hx : x ≠ 0)
    (h : U ^ 2 + 2 * U * x * (x + 6 * n) = x * (36 * n ^ 3 - 19)) :
    U ≠ 0 := by
  rintro rfl
  have : x * (36 * n ^ 3 - 19) = 0 := by linarith [h]
  rcases mul_eq_zero.1 this with h' | h'
  · exact hx h'
  · exact int_cubic_ne_zero n (by linarith)

/-- Hence `|x| ≤ U²`: for a given `U` only the (finitely many) divisors of `U²` can occur. -/
theorem sat_abs_x_le_U_sq {U n x : ℤ} (hx : x ≠ 0)
    (h : U ^ 2 + 2 * U * x * (x + 6 * n) = x * (36 * n ^ 3 - 19)) :
    |x| ≤ U ^ 2 := by
  have hU : U ≠ 0 := sat_U_ne_zero hx h
  have hdvd : x ∣ U ^ 2 := sat_U_dvd h
  exact Int.le_of_dvd (lt_of_le_of_ne (sq_nonneg U) (Ne.symm (pow_ne_zero 2 hU)))
    ((abs_dvd _ _).mpr hdvd)

/-! ### Algorithm A: the d-first sweep -/

/-- With `c = U²/x`, equation `(★)` becomes a **cubic in `n` alone**. -/
theorem cubic_in_n {U n x c : ℤ} (hx : x ≠ 0) (hc : U ^ 2 = c * x)
    (h : U ^ 2 + 2 * U * x * (x + 6 * n) = x * (36 * n ^ 3 - 19)) :
    36 * n ^ 3 - 12 * U * n = c + 2 * U * x + 19 := by
  have hmul : x * (36 * n ^ 3 - 12 * U * n) = x * (c + 2 * U * x + 19) := by
    rw [hc] at h; ring_nf; ring_nf at h; linarith [h]
  exact mul_left_cancel₀ hx hmul

/-- Conversely the cubic together with `U² = c·x` gives back `(★)`. -/
theorem eq_of_cubic_in_n {U n x c : ℤ} (hc : U ^ 2 = c * x)
    (h : 36 * n ^ 3 - 12 * U * n = c + 2 * U * x + 19) :
    U ^ 2 + 2 * U * x * (x + 6 * n) = x * (36 * n ^ 3 - 19) := by
  have := congrArg (fun z : ℤ => x * z) h
  simp only at this
  rw [hc]
  nlinarith [this]

/-- **Correctness of the d-first sweep (Algorithm A).**

`Sat d n x` holds iff there are integers `U` (the certificate `2dx²`) and `c` with

* `U² = c·x`  (so `x` runs through the divisors of `U²`),
* `36 n³ - 12 U n = c + 2 U x + 19`  (a cubic in `n`, solved by a cube root), and
* the branch condition `(U + x(x+6n))·x ≤ 0`.

Enumerating `U` and `x ∣ U²` and solving the cubic therefore finds *every* solution whose
certificate `U` lies in the swept range, and produces no spurious ones. -/
theorem sat_iff_dSweep {d : ℚ} {n x : ℤ} (hx : x ≠ 0) :
    Sat d n x ↔ ∃ U c : ℤ, (U : ℚ) = 2 * d * (x : ℚ) ^ 2 ∧ U ^ 2 = c * x ∧
      36 * n ^ 3 - 12 * U * n = c + 2 * U * x + 19 ∧ (U + x * (x + 6 * n)) * x ≤ 0 := by
  rw [sat_iff_exists_U hx]
  constructor
  · rintro ⟨U, hU, heq, hsign⟩
    obtain ⟨c, hc⟩ := sat_U_dvd heq
    refine ⟨U, c, hU, by rw [hc]; ring, ?_, hsign⟩
    exact cubic_in_n hx (by rw [hc]; ring) heq
  · rintro ⟨U, c, hU, hc, hcub, hsign⟩
    exact ⟨U, hU, eq_of_cubic_in_n hc hcub, hsign⟩

/-- **Range calibration for the sweep:** `|n| ≤ |U|`.  A solution with a `D`-digit `n` has a
certificate `U` with at least `D` digits, so sweeping `|U| ≤ T` covers exactly the solutions
with `|U| ≤ T` and can only produce `|n| ≤ T`. -/
theorem abs_n_le_abs_U {U n x : ℤ} (hx : x ≠ 0)
    (h : U ^ 2 + 2 * U * x * (x + 6 * n) = x * (36 * n ^ 3 - 19)) :
    |n| ≤ |U| := by
  have aux : ∀ a b : ℤ, 1 ≤ b → b + 1 ≤ a → 36 * a ^ 3 - 12 * a * b ≤ 2 * b ^ 3 + b ^ 2 + 19 →
      False := by
    intro a b hb hab hle
    have ha2 : 2 ≤ a := by omega
    have hba : b ≤ a - 1 := by omega
    have hb0 : (0 : ℤ) ≤ b := by omega
    have hb3 : b ^ 3 ≤ (a - 1) ^ 3 := pow_le_pow_left₀ hb0 hba 3
    have hb2 : b ^ 2 ≤ (a - 1) ^ 2 := pow_le_pow_left₀ hb0 hba 2
    have hab' : 12 * a * b ≤ 12 * a * (a - 1) := by nlinarith
    nlinarith [ha2, sq_nonneg (a - 2), mul_nonneg (by omega : (0:ℤ) ≤ a - 2) (sq_nonneg a)]
  obtain ⟨c, hc⟩ := sat_U_dvd h
  have hxU : |x| ≤ U ^ 2 := sat_abs_x_le_U_sq hx h
  have hcub : 36 * n ^ 3 - 12 * U * n = c + 2 * U * x + 19 :=
    cubic_in_n hx (by rw [hc]; ring) h
  -- `|c| ≤ U²`
  have hx1 : 1 ≤ |x| := Int.one_le_abs (by exact_mod_cast hx)
  have hcx : |c| * |x| = U ^ 2 := by
    rw [← abs_mul, mul_comm, ← hc, abs_of_nonneg (sq_nonneg U)]
  have hcabs : |c| ≤ U ^ 2 := by nlinarith [abs_nonneg c, hcx]
  by_contra hcon
  push_neg at hcon
  have h1 : |U| + 1 ≤ |n| := hcon
  have hU : U ≠ 0 := sat_U_ne_zero hx h
  have hU1 : 1 ≤ |U| := Int.one_le_abs (by exact_mod_cast hU)
  have habs : |c + 2 * U * x + 19| ≤ |c| + 2 * (|U| * |x|) + 19 := by
    have t1 := abs_add_le (c + 2 * U * x) (19 : ℤ)
    have t2 := abs_add_le c (2 * U * x)
    have t3 : |2 * U * x| = 2 * (|U| * |x|) := by rw [abs_mul, abs_mul]; norm_num [mul_assoc]
    have t4 : |(19 : ℤ)| = 19 := by norm_num
    linarith
  have hlow : 36 * |n| ^ 3 - 12 * (|U| * |n|) ≤ |36 * n ^ 3 - 12 * U * n| := by
    have h1' := abs_sub_abs_le_abs_sub (36 * n ^ 3) (12 * U * n)
    have h2' : |36 * n ^ 3| = 36 * |n| ^ 3 := by rw [abs_mul, abs_pow]; norm_num
    have h3' : |12 * U * n| = 12 * (|U| * |n|) := by rw [abs_mul, abs_mul]; norm_num [mul_assoc]
    linarith
  rw [hcub] at hlow
  have hUx : |U| * |x| ≤ |U| * U ^ 2 := mul_le_mul_of_nonneg_left hxU (abs_nonneg U)
  have hUsq : U ^ 2 = |U| ^ 2 := (sq_abs U).symm
  have hUcube : |U| * U ^ 2 = |U| ^ 3 := by rw [hUsq]; ring
  refine aux |n| |U| hU1 h1 ?_
  have : 36 * |n| ^ 3 - 12 * (|U| * |n|) ≤ |U| ^ 2 + 2 * |U| ^ 3 + 19 := by
    calc 36 * |n| ^ 3 - 12 * (|U| * |n|) ≤ |c + 2 * U * x + 19| := hlow
      _ ≤ |c| + 2 * (|U| * |x|) + 19 := habs
      _ ≤ U ^ 2 + 2 * (|U| * U ^ 2) + 19 := by linarith
      _ = |U| ^ 2 + 2 * |U| ^ 3 + 19 := by rw [hUsq] at hUcube ⊢; linarith [hUcube]
  linarith [this]

/-- `|n| ≤ |U|`, phrased for a solution of the original equation. -/
theorem sat_abs_n_le_abs_U {d : ℚ} {n x U : ℤ} (h : Sat d n x)
    (hU : (U : ℚ) = 2 * d * (x : ℚ) ^ 2) : |n| ≤ |U| := by
  have hx : x ≠ 0 := sat_x_ne_zero h
  rw [sat_iff_exists_U hx] at h
  obtain ⟨U', hU', heq, _⟩ := h
  have : U = U' := by
    have : ((U : ℚ)) = ((U' : ℚ)) := by rw [hU, hU']
    exact_mod_cast this
  subst this
  exact abs_n_le_abs_U hx heq

/-! ### The congruence filter for the family `n = 3m`, `x = 12u + 7` -/

/-- **Sieve for the requested family.**  As soon as `x = 12u + 7` (the hypothesis `n = 3m`
is not needed), the certificate `U = 2dx²` satisfies `U ≡ 5` or `U ≡ 11 (mod 12)`.  In
particular `U` is coprime to `6`, so the sweep may skip 10 out of every 12 values of `U`,
and every divisor of `U²` is coprime to `6` as `x` must be. -/
theorem U_mod_twelve {U n u : ℤ}
    (h : U ^ 2 + 2 * U * (12 * u + 7) * ((12 * u + 7) + 6 * n)
      = (12 * u + 7) * (36 * n ^ 3 - 19)) :
    U % 12 = 5 ∨ U % 12 = 11 := by
  have key : ∀ a b c : ZMod 12,
      a ^ 2 + 2 * a * (12 * b + 7) * ((12 * b + 7) + 6 * c)
        = (12 * b + 7) * (36 * c ^ 3 - 19) → a = 5 ∨ a = 11 := by decide
  have hcast : ((U : ZMod 12)) = 5 ∨ ((U : ZMod 12)) = 11 := by
    refine key (U : ZMod 12) (u : ZMod 12) (n : ZMod 12) ?_
    have := congrArg (fun z : ℤ => ((z : ZMod 12))) h
    push_cast at this
    convert this using 2
  have h5 : ((5 : ℤ) : ZMod 12) = 5 := by norm_num
  have h11 : ((11 : ℤ) : ZMod 12) = 11 := by norm_num
  rcases hcast with hc | hc
  · left
    have : U ≡ 5 [ZMOD 12] := by
      rw [Int.ModEq]
      have := (ZMod.intCast_eq_intCast_iff U 5 12).1 (by rw [hc, h5])
      simpa [Int.ModEq] using this
    simpa [Int.ModEq] using this
  · right
    have : U ≡ 11 [ZMOD 12] := by
      rw [Int.ModEq]
      have := (ZMod.intCast_eq_intCast_iff U 11 12).1 (by rw [hc, h11])
      simpa [Int.ModEq] using this
    simpa [Int.ModEq] using this

/-- The same filter stated for a solution of the original equation.  Only `x ≡ 7 (mod 12)`
is needed; the extra hypothesis `n = 3m` of the requested family costs nothing and gains
nothing here, so the sweep can afford to accept every `n`. -/
theorem sat_U_mod_twelve {d : ℚ} {n u U : ℤ} (h : Sat d n (12 * u + 7))
    (hU : (U : ℚ) = 2 * d * ((12 * u + 7 : ℤ) : ℚ) ^ 2) :
    U % 12 = 5 ∨ U % 12 = 11 := by
  have hx : (12 * u + 7 : ℤ) ≠ 0 := by omega
  rw [sat_iff_exists_U hx] at h
  obtain ⟨U', hU', heq, _⟩ := h
  have : U = U' := by
    have : ((U : ℚ)) = ((U' : ℚ)) := by rw [hU, hU']
    exact_mod_cast this
  subst this
  exact U_mod_twelve heq

/-! ### Algorithm C: the per-`x` Mordell curve -/

/-- **The elliptic curve view.**  Writing `Y² = x²(x+6n)² + x(36n³-19)` (the perfect square
condition of `exists_d_iff`), the point `Z = 12x(3n+x)`, `V = 36xY` lies on the Mordell curve
`V² = Z³ - 432 x³ (x³ + 57)`.  For fixed `x` the solutions of the original equation are thus
among the integral points of one Mordell curve, and — unlike the sweeps over `n` or over `U` —
this view puts no bound on `n`. -/
theorem mordell_of_sat {n x Y : ℤ}
    (h : Y ^ 2 = x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 19)) :
    (36 * x * Y) ^ 2 = (12 * x * (3 * n + x)) ^ 3 - 432 * x ^ 3 * (x ^ 3 + 57) := by
  linear_combination (1296 * x ^ 2) * h

/-- The converse: an integral point of the Mordell curve whose `Z`-coordinate is of the shape
`12x(3n+x)` and whose `V`-coordinate is divisible by `36x` gives back the perfect square
condition, hence (via `sat_of_U`) a value of `d`. -/
theorem sat_of_mordell_point {n x Y : ℤ} (hx : x ≠ 0)
    (h : (36 * x * Y) ^ 2 = (12 * x * (3 * n + x)) ^ 3 - 432 * x ^ 3 * (x ^ 3 + 57)) :
    Y ^ 2 = x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 19) := by
  have hx2 : (1296 : ℤ) * x ^ 2 ≠ 0 := by positivity
  refine mul_left_cancel₀ hx2 ?_
  linear_combination h

/-- Packaging Algorithm C: a Mordell point with the right shape yields an explicit `d`. -/
theorem sat_of_mordell {n x Y : ℤ} (hx : x ≠ 0)
    (h : (36 * x * Y) ^ 2 = (12 * x * (3 * n + x)) ^ 3 - 432 * x ^ 3 * (x ^ 3 + 57))
    (hsign : Y * x ≤ 0) :
    Sat (((Y - x * (x + 6 * n) : ℤ) : ℚ) / (2 * (x : ℚ) ^ 2)) n x := by
  have hY := sat_of_mordell_point hx h
  refine sat_of_U hx (by nlinarith [hY]) (by simpa using hsign)

end DEquation
