/-
# Correctness of the complete search engine (`algorithms/engine_full.py`)

Every solution has `x = s t²` with `s` squarefree and (pruning theorem)
`s | K = 36n³ - 65`.  Writing `K = s K'`, the theorem below shows that the
discriminant
      `D = x²(x+6n)² + x K`
is a perfect square **iff** the much smaller quantity
      `E = t²(x+6n)² + K'`
is a perfect square.  Since `E = G²` is equivalent to the factorisation
`K' = (G - W)(G + W)` with `W = t(s t² + 6n)`, this reduces the search for `x`
to enumerating the factorisations of `K'` — which is exactly what the complete
engine does, and why it needs no bound on `|x|`.
-/
import Mathlib
import RequestProject.DSearch

namespace DSearch

/-- A rational whose square is an integer is an integer. -/
theorem exists_int_sq_of_rat_sq (q : ℚ) (m : ℤ) (h : q ^ 2 = (m : ℚ)) :
    ∃ y : ℤ, y ^ 2 = m := by
  have hcast : ((q : ℝ)) ^ 2 = (m : ℝ) := by exact_mod_cast h
  have hint : ∃ y : ℤ, q = (y : ℚ) := by
    by_contra hcon
    push_neg at hcon
    have hirr : Irrational (q : ℝ) :=
      irrational_nrt_of_notint_nrt 2 m (by exact_mod_cast hcast)
        (by rintro ⟨y, hy⟩; exact hcon y (by exact_mod_cast hy)) (by norm_num)
    exact hirr ⟨q, rfl⟩
  obtain ⟨y, hy⟩ := hint
  exact ⟨y, by exact_mod_cast hy ▸ h⟩

/-- **Correctness of the complete engine.**  For `x = s t²` and `K = s K'`, the
discriminant `D` is a perfect square iff `E = t²(x+6n)² + K'` is. -/
theorem disc_sq_iff_reduced (n s t K' : ℤ) (hs : s ≠ 0) (ht : t ≠ 0)
    (hK : 36 * n ^ 3 - 65 = s * K') :
    (∃ T : ℤ, T ^ 2 =
        (s * t ^ 2) ^ 2 * (s * t ^ 2 + 6 * n) ^ 2 + (s * t ^ 2) * (36 * n ^ 3 - 65))
      ↔ (∃ G : ℤ, G ^ 2 = t ^ 2 * (s * t ^ 2 + 6 * n) ^ 2 + K') := by
  have hfactor :
      (s * t ^ 2) ^ 2 * (s * t ^ 2 + 6 * n) ^ 2 + (s * t ^ 2) * (36 * n ^ 3 - 65)
        = (s * t) ^ 2 * (t ^ 2 * (s * t ^ 2 + 6 * n) ^ 2 + K') := by
    rw [hK]; ring
  constructor
  · rintro ⟨T, hT⟩
    have hT' : T ^ 2 = (s * t) ^ 2 * (t ^ 2 * (s * t ^ 2 + 6 * n) ^ 2 + K') := by
      rw [hT]; exact hfactor
    have hdvd : (s * t) ^ 2 ∣ T ^ 2 := ⟨_, hT'⟩
    have hdvd' : (s * t) ∣ T := (Int.pow_dvd_pow_iff two_ne_zero).mp hdvd
    obtain ⟨G, hG⟩ := hdvd'
    refine ⟨G, ?_⟩
    have hst : (s * t) ≠ 0 := mul_ne_zero hs ht
    have : (s * t) ^ 2 * G ^ 2 = (s * t) ^ 2 * (t ^ 2 * (s * t ^ 2 + 6 * n) ^ 2 + K') := by
      rw [← hT']; rw [hG]; ring
    exact mul_left_cancel₀ (pow_ne_zero 2 hst) this
  · rintro ⟨G, hG⟩
    refine ⟨|s * t * G|, ?_⟩
    rw [sq_abs, hfactor, ← hG]
    ring

end DSearch
