/-
# Rational `d` for which `36n³ - 65 = -2d·x²·(-(x+6n) + √((x+6n)² + (36n³-65)/x))`
  has integer solutions `(n, x)`

This file contains

* `SatisfiesEq d n x` : the equation under study;
* `satisfiesEq_of_sq` : the master criterion that turns the search into a search
  for perfect squares:  if `D = x²(x+6n)² + x(36n³-65)` equals `T²` with `T ≥ 0`
  then `d = (-x(x+6n) - T·x/|x|)/(2x²)` solves the equation — and this `d` is
  rational as soon as `n, x, T` are integers;
* `disc_eq_of_satisfiesEq` / `exists_sq_of_satisfiesEq` : the converse, i.e. the
  criterion is *exhaustive* — for integers `n, x` (`x ≠ 0`) a rational `d` exists
  only if `D` is a perfect square.  Hence the search programs in `algorithms/`
  provably miss nothing inside the region they cover;
* exact verification of every solution found by those programs
  (see `RequestProject/Solutions.lean`).
-/
import Mathlib

namespace DSearch

/-- The equation under study, over the reals. -/
def SatisfiesEq (d n x : ℝ) : Prop :=
  36 * n ^ 3 - 65 =
    -2 * d * x ^ 2 * (-(x + 6 * n) + Real.sqrt ((x + 6 * n) ^ 2 + (36 * n ^ 3 - 65) / x))

/-- The discriminant `D = x²(x+6n)² + x(36n³-65)` whose squareness decides everything. -/
def Disc (n x : ℝ) : ℝ := x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 65)

/-- **Master criterion.** If `D = T²` with `T ≥ 0`, then the explicit value
`d = (-x(x+6n) - T·x/|x|)/(2x²)` satisfies the equation. -/
theorem satisfiesEq_of_sq (n x T d : ℝ) (hx : x ≠ 0) (hT : 0 ≤ T)
    (hD : T ^ 2 = Disc n x)
    (hd : 2 * x ^ 2 * d = -(x * (x + 6 * n)) - T * x / |x|) :
    SatisfiesEq d n x := by
  have hax : |x| ≠ 0 := abs_ne_zero.mpr hx
  have hax2 : |x| ^ 2 = x ^ 2 := sq_abs x
  have hD' : T ^ 2 = x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 65) := hD
  have hroot : Real.sqrt ((x + 6 * n) ^ 2 + (36 * n ^ 3 - 65) / x) = T / |x| := by
    have h1 : (x + 6 * n) ^ 2 + (36 * n ^ 3 - 65) / x = (T / |x|) ^ 2 := by
      rw [div_pow, hax2, hD']
      field_simp
    rw [h1, Real.sqrt_sq (by positivity)]
  unfold SatisfiesEq
  rw [hroot]
  have hxx : -2 * d * x ^ 2 = -(2 * x ^ 2 * d) := by ring
  rw [hxx, hd]
  rcases lt_or_gt_of_ne hx with hneg | hpos
  · rw [abs_of_neg hneg]
    field_simp
    nlinarith [hD']
  · rw [abs_of_pos hpos]
    field_simp
    nlinarith [hD']

/-- **Converse.** Any real `d` solving the equation (with a nonnegative radicand and
`36n³ ≠ 65`) forces `D` to be the square of `2dx² + x(x+6n)`. -/
theorem disc_eq_of_satisfiesEq (n x d : ℝ) (hx : x ≠ 0) (hK : 36 * n ^ 3 - 65 ≠ 0)
    (hrad : 0 ≤ (x + 6 * n) ^ 2 + (36 * n ^ 3 - 65) / x)
    (h : SatisfiesEq d n x) :
    Disc n x = (2 * d * x ^ 2 + x * (x + 6 * n)) ^ 2 := by
  set r := Real.sqrt ((x + 6 * n) ^ 2 + (36 * n ^ 3 - 65) / x) with hrdef
  have hr2 : r ^ 2 = (x + 6 * n) ^ 2 + (36 * n ^ 3 - 65) / x := Real.sq_sqrt hrad
  have hxr : x * (r ^ 2 - (x + 6 * n) ^ 2) = 36 * n ^ 3 - 65 := by
    rw [hr2]; field_simp; ring
  have h1 : 2 * d * x ^ 2 * ((x + 6 * n) - r) = 36 * n ^ 3 - 65 := by
    unfold SatisfiesEq at h; linarith [h]
  have hne : (x + 6 * n) - r ≠ 0 := by
    intro h0
    apply hK
    rw [← h1, h0]; ring
  have hfac : ((x + 6 * n) - r) * (2 * d * x ^ 2 + x * (r + (x + 6 * n))) = 0 := by
    linear_combination h1 - hxr
  have h2 : 2 * d * x ^ 2 + x * (r + (x + 6 * n)) = 0 :=
    (mul_eq_zero.mp hfac).resolve_left hne
  have h3 : x * (2 * d * x + (r + (x + 6 * n))) = 0 := by linear_combination h2
  have hlin : 2 * d * x + (r + (x + 6 * n)) = 0 := by
    rcases mul_eq_zero.mp h3 with h4 | h4
    · exact absurd h4 hx
    · exact h4
  have hDisc : Disc n x = x ^ 2 * r ^ 2 := by
    unfold Disc; rw [hr2]; field_simp
  have hxrr : x * r = -(2 * d * x ^ 2 + x * (x + 6 * n)) := by linear_combination x * hlin
  rw [hDisc, show x ^ 2 * r ^ 2 = (x * r) ^ 2 by ring, hxrr]
  ring

/-- **Exhaustiveness over the integers.** If `n, x` are integers with `x ≠ 0` and some
*rational* `d` solves the equation (with nonnegative radicand), then
`D = x²(x+6n)² + x(36n³-65)` is the square of an integer.  This is exactly the
predicate the search programs test, so they provably miss no solution. -/
theorem exists_sq_of_satisfiesEq (n x : ℤ) (d : ℚ) (hx : x ≠ 0)
    (hrad : 0 ≤ ((x : ℝ) + 6 * (n : ℝ)) ^ 2 + (36 * (n : ℝ) ^ 3 - 65) / (x : ℝ))
    (h : SatisfiesEq (d : ℝ) (n : ℝ) (x : ℝ)) :
    ∃ T : ℤ, 0 ≤ T ∧ T ^ 2 = x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 65) := by
  have hxR : (x : ℝ) ≠ 0 := Int.cast_ne_zero.mpr hx
  have hK : 36 * (n : ℝ) ^ 3 - 65 ≠ 0 := by
    intro h0
    have hz : (36 * n ^ 3 - 65 : ℤ) = 0 := by exact_mod_cast h0
    have h36 : (36 : ℤ) ∣ 65 := ⟨n ^ 3, by linarith⟩
    norm_num at h36
  have hmain := disc_eq_of_satisfiesEq (n : ℝ) (x : ℝ) (d : ℝ) hxR hK hrad h
  set q : ℚ := 2 * d * (x : ℚ) ^ 2 + (x : ℚ) * ((x : ℚ) + 6 * (n : ℚ)) with hq
  set Dz : ℤ := x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 65) with hDz
  have hqR : ((q : ℚ) : ℝ) = 2 * (d : ℝ) * (x : ℝ) ^ 2 + (x : ℝ) * ((x : ℝ) + 6 * (n : ℝ)) := by
    rw [hq]; push_cast; ring
  have hcast : (q : ℝ) ^ 2 = (Dz : ℝ) := by
    rw [hqR, ← hmain, hDz]; unfold Disc; push_cast; ring
  have hqQ : q ^ 2 = (Dz : ℚ) := by exact_mod_cast hcast
  have hint : ∃ y : ℤ, q = (y : ℚ) := by
    by_contra hcon
    push_neg at hcon
    have hirr : Irrational (q : ℝ) :=
      irrational_nrt_of_notint_nrt 2 Dz (by exact_mod_cast hcast)
        (by rintro ⟨y, hy⟩; exact hcon y (by exact_mod_cast hy)) (by norm_num)
    exact hirr ⟨q, rfl⟩
  obtain ⟨y, hy⟩ := hint
  refine ⟨|y|, abs_nonneg _, ?_⟩
  have hyq : (y : ℚ) ^ 2 = (Dz : ℚ) := by rw [← hy]; exact hqQ
  have hyz : y ^ 2 = Dz := by exact_mod_cast hyq
  rw [sq_abs, hyz]

end DSearch
