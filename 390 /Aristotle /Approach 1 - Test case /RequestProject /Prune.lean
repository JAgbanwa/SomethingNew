/-
# The pruning theorem behind the fastest search engine

For a solution `(n, x)` put `A = x(x+6n)`, `T = √D`, `m = T - A`.  Then
`m² = x·(K - 2(x+6n)m)` with `K = 36n³ - 65`, so `x | m²`.  Consequently, for
every prime `p` that does *not* divide `K`, the exponent of `p` in `x` is EVEN
(`even_padicValInt_of_not_dvd`).  Since `K = 36n³-65` is always odd and always
`≡ 1 (mod 3)`, the exponents of `2` and of `3` in `x` are always even
(`even_padicValInt_two`, `even_padicValInt_three`): values such as
`x = ±2, ±3, ±6, ±8, ±12, …` are impossible.

Equivalently: the squarefree kernel `s` of `x` must divide `36n³ - 65`, which
confines `n` to the roots of a cubic congruence modulo `s` — the prune that
makes the engine `algorithms/engine_sqfree.c` ~`s` times faster than a scan.
-/
import Mathlib
import RequestProject.DSearch

namespace DSearch

/-- The auxiliary integer `m = T - x(x+6n)` satisfies `m² = x·(K - 2(x+6n)m)`;
in particular `x ∣ m²`. -/
theorem m_sq_eq (n x T : ℤ)
    (hT : T ^ 2 = x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 65)) :
    (T - x * (x + 6 * n)) ^ 2
      = x * ((36 * n ^ 3 - 65) - 2 * (x + 6 * n) * (T - x * (x + 6 * n))) := by
  linear_combination hT

/-- `36n³ - 65` is odd. -/
theorem two_not_dvd (n : ℤ) : ¬ ((2 : ℤ) ∣ 36 * n ^ 3 - 65) := by
  rintro ⟨c, hc⟩
  set y := n ^ 3 with hy
  omega

/-- `36n³ - 65` is never divisible by `3`. -/
theorem three_not_dvd (n : ℤ) : ¬ ((3 : ℤ) ∣ 36 * n ^ 3 - 65) := by
  rintro ⟨c, hc⟩
  set y := n ^ 3 with hy
  omega

/-- **Pruning theorem.** If `D = x²(x+6n)² + x(36n³-65)` is a perfect square `T²`
and the prime `p` does not divide `36n³-65`, then `p` occurs to an even power in `x`. -/
theorem even_padicValInt_of_not_dvd (p : ℕ) [hp : Fact p.Prime] (n x T : ℤ) (hx : x ≠ 0)
    (hT : T ^ 2 = x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 65))
    (hpK : ¬ ((p : ℤ) ∣ 36 * n ^ 3 - 65)) :
    Even (padicValInt p x) := by
  have hprime : Prime (p : ℤ) := Nat.prime_iff_prime_int.mp hp.out
  set m : ℤ := T - x * (x + 6 * n) with hm_def
  set u : ℤ := (36 * n ^ 3 - 65) - 2 * (x + 6 * n) * m with hu_def
  have hm2 : m ^ 2 = x * u := m_sq_eq n x T hT
  have hK0 : (36 * n ^ 3 - 65) ≠ 0 := by
    intro h0; exact hpK (h0 ▸ dvd_zero _)
  have hm0 : m ≠ 0 := by
    intro h0
    rw [h0] at hm2
    have hxu : x * u = 0 := by simpa using hm2.symm
    rcases mul_eq_zero.mp hxu with h | h
    · exact hx h
    · rw [hu_def, h0] at h; simp at h; exact hK0 (by linarith [h])
  have hu0 : u ≠ 0 := by
    intro h0
    rw [h0, mul_zero] at hm2
    exact hm0 (pow_eq_zero_iff (n := 2) (by norm_num) |>.mp hm2)
  by_cases hpx : (p : ℤ) ∣ x
  · have hpm : (p : ℤ) ∣ m := hprime.dvd_of_dvd_pow (hm2 ▸ hpx.mul_right u)
    have hpu : ¬ (p : ℤ) ∣ u := by
      intro h
      apply hpK
      have hsum : 36 * n ^ 3 - 65 = u + 2 * (x + 6 * n) * m := by rw [hu_def]; ring
      rw [hsum]
      exact dvd_add h (Dvd.dvd.mul_left hpm _)
    have h1 : padicValInt p (m ^ 2) = padicValInt p x + padicValInt p u := by
      rw [hm2, padicValInt.mul hx hu0]
    have h2 : padicValInt p (m ^ 2) = 2 * padicValInt p m := by
      rw [sq, padicValInt.mul hm0 hm0]; ring
    have h3 : padicValInt p u = 0 := padicValInt.eq_zero_of_not_dvd hpu
    exact ⟨padicValInt p m, by omega⟩
  · rw [padicValInt.eq_zero_of_not_dvd hpx]
    exact ⟨0, rfl⟩

/-- The exponent of `2` in `x` is even for every solution: `x = ±2, ±8, ±18, …` are impossible. -/
theorem even_padicValInt_two (n x T : ℤ) (hx : x ≠ 0)
    (hT : T ^ 2 = x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 65)) :
    Even (padicValInt 2 x) :=
  haveI : Fact (Nat.Prime 2) := ⟨Nat.prime_two⟩
  even_padicValInt_of_not_dvd 2 n x T hx hT (two_not_dvd n)

/-- The exponent of `3` in `x` is even for every solution: `x = ±3, ±12, ±27, …` are impossible. -/
theorem even_padicValInt_three (n x T : ℤ) (hx : x ≠ 0)
    (hT : T ^ 2 = x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 65)) :
    Even (padicValInt 3 x) :=
  haveI : Fact (Nat.Prime 3) := ⟨Nat.prime_three⟩
  even_padicValInt_of_not_dvd 3 n x T hx hT (three_not_dvd n)

end DSearch
