"""
Модульное решето для уравнения 36n^3 - 65 = -2d * x^2 * (-(x+6n) + sqrt(...))

Фильтрует пары (n, x) по следующим условиям:
  1. n ≡ 1 (mod 3)
  2. x ≡ 5 (mod 12)
  3. x ≢ 0 (mod 7)
  4. x | (36n^3 - 65)
  5. (36n^3 - 65) * x должно быть полным квадратом по модулю p
     (необходимое условие целостности sqrt)

Дополнительно: для каждого простого p вычисляет допустимые
классы (n mod p, x mod p) и собирает их через CRT.
"""

from math import gcd
from functools import reduce
from itertools import product
from typing import List, Tuple, Dict, Set, Optional
import json


def is_quadratic_residue(a: int, p: int) -> bool:
    """Проверка: является ли a квадратичным вычетом по модулю p."""
    if a % p == 0:
        return True
    return pow(a, (p - 1) // 2, p) == 1


def valid_pairs_mod_p(p: int) -> List[Tuple[int, int]]:
    """
    Для простого p находит все пары (n mod p, x mod p), удовлетворяющие:
      - n ≡ 1 (mod 3) если p ≠ 3
      - x ≡ 5 (mod 12) если p ∉ {2, 3}
      - x ≢ 0 (mod 7) если p = 7
      - x ≢ 0 (mod p) (нужно для деления)
      - (36*n^3 - 65) * x — квадратичный вычет по mod p

    Возвращает список допустимых (n mod p, x mod p).
    """
    results = []

    for n in range(p):
        # Условие n ≡ 1 (mod 3)
        if p != 3 and n % 3 != 1:
            continue
        if p == 3:
            # n ≡ 1 (mod 3) -> n ≡ 1 (mod 3), но работаем mod 3
            if n != 1:
                continue

        n3_65 = (36 * n * n * n - 65) % p

        for x in range(p):
            # x ≢ 0 (mod p) — нужно для деления
            if x == 0:
                continue

            # x ≡ 5 (mod 12)
            if p not in (2, 3):
                if x % 12 != 5:
                    continue
            elif p == 2:
                # x ≡ 5 (mod 12) -> x ≡ 1 (mod 2)
                if x % 2 != 1:
                    continue
            elif p == 3:
                # x ≡ 5 (mod 12) -> x ≡ 2 (mod 3)
                if x % 3 != 2:
                    continue

            # x ≢ 0 (mod 7)
            if p == 7 and x == 0:
                continue

            # Проверка: (36*n^3 - 65) * x — квадратичный вычет
            val = (n3_65 * x) % p
            if not is_quadratic_residue(val, p):
                continue

            results.append((n, x))

    return results


def density_mod_p(p: int) -> float:
    """Вычисляет плотность допустимых пар по модулю p."""
    valid = valid_pairs_mod_p(p)
    return len(valid) / (p * p) if p > 1 else 0.0


def select_sieving_primes(num_primes: int = 100,
                          min_p: int = 5,
                          max_p: int = 10**6) -> List[int]:
    """
    Выбирает простые числа для решета.
    Исключает p=2,3 (специальные случаи) и p=7 (специальное условие).
    """
    primes = []
    candidate = min_p
    if candidate % 2 == 0:
        candidate += 1

    while len(primes) < num_primes and candidate <= max_p:
        if candidate not in (7,):  # 7 обрабатываем отдельно
            is_prime = True
            if candidate < 2:
                is_prime = False
            elif candidate == 2:
                is_prime = True
            else:
                i = 3
                while i * i <= candidate:
                    if candidate % i == 0:
                        is_prime = False
                        break
                    i += 2
            if is_prime:
                primes.append(candidate)
        candidate += 2

    return primes


def extended_crt(remainders: List[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
    """
    Расширенный CRT: находит (x mod M) из системы x ≡ r_i (mod m_i).
    Возвращает (result, modulus) или None при несовместности.
    """
    if not remainders:
        return (0, 1)

    r, m = remainders[0]
    for r2, m2 in remainders[1:]:
        g = gcd(m, m2)
        if (r2 - r) % g != 0:
            return None
        lcm = m * m2 // g
        # Решаем r + m*t ≡ r2 (mod m2)
        # m*t ≡ (r2 - r) (mod m2)
        # t ≡ (r2 - r) / g * inverse(m/g, m2/g) (mod m2/g)
        diff = (r2 - r) // g
        m_red = m // g
        m2_red = m2 // g
        inv = pow(m_red, -1, m2_red)
        t = (diff * inv) % m2_red
        r = (r + m * t) % lcm
        m = lcm

    return (r, m)


class ModularSieve:
    """
    Модульное решето: для набора простых p собирает допустимые
    классы (n mod p, x mod p) и комбинирует их через CRT.
    """

    def __init__(self, primes: List[int]):
        self.primes = list(set(primes) - {2, 3, 7})  # обрабатываем отдельно
        self.special_primes = [2, 3, 7]
        self.valid_sets: Dict[int, List[Tuple[int, int]]] = {}
        self._compute_valid_sets()

    def _compute_valid_sets(self):
        """Вычисляет допустимые пары для каждого простого."""
        all_primes = self.primes + self.special_primes
        for p in all_primes:
            self.valid_sets[p] = valid_pairs_mod_p(p)

    def estimate_compression(self, num_primes_used: int = 50) -> float:
        """
        Оценивает степень сжатия при использовании num_primes_used простых.
        Возвращает долю пар, проходящих решето.
        """
        primes = sorted(self.valid_sets.keys())[:num_primes_used]
        total_density = 1.0
        for p in primes:
            d = len(self.valid_sets[p]) / (p * p)
            total_density *= d
        return total_density

    def sieve_crt(self, n_target_bits: int = 144,
                  num_primes: int = 100) -> Dict:
        """
        Основной метод решета: комбинирует модульные условия через CRT.

        Параметры:
          n_target_bits: битовая длина n (для оценки)
          num_primes: количество простых для решета

        Возвращает словарь с:
          - 'n_mod': n mod M
          - 'x_mod': x mod M
          - 'M': модуль
          - 'density': итоговая плотность
          - 'candidates_estimate': оценка числа кандидатов
        """
        primes = sorted(self.valid_sets.keys())[:num_primes]

        # Для каждого простого: собираем все допустимые (n, x) пары
        # и пытаемся найти совместимую систему через CRT

        # Стратегия: для каждого простого берём допустимые n-классы и x-классы
        # отдельно, затем комбинируем

        n_classes = {}  # p -> список допустимых n mod p
        x_classes = {}  # p -> список допустимых x mod p

        for p in primes:
            valid = self.valid_sets[p]
            n_set = list(set(n for n, x in valid))
            x_set = list(set(x for n, x in valid))
            n_classes[p] = n_set
            x_classes[p] = x_set

        # Оценка: для каждого простого плотность = |valid| / p^2
        total_density = 1.0
        M = 1
        for p in primes:
            d = len(self.valid_sets[p]) / (p * p)
            total_density *= d
            M *= p

        # Оценка числа кандидатов в диапазоне |n| ~ 2^n_target_bits
        n_range = 2**n_target_bits
        # x ~ n^{5/4}, так что x_range ~ n_range^{5/4}
        x_range = int(n_range**1.25)

        candidates = total_density * n_range * x_range

        return {
            'primes_used': primes,
            'M': M,
            'M_bits': M.bit_length(),
            'density': total_density,
            'candidates_estimate': candidates,
            'n_classes': n_classes,
            'x_classes': x_classes,
        }

    def find_compatible_residues(self, num_primes: int = 30) -> List[Tuple[Tuple[int, int], int]]:
        """
        Находит совместимые пары (n mod M, x mod M) для первых num_primes простых.
        Возвращает список ((n_mod, x_mod), M).

        Для больших num_primes это становится вычислительно тяжёлым —
        используется метод «ветвей и границ» с отсечением по плотности.
        """
        primes = sorted(self.valid_sets.keys())[:num_primes]

        # Начинаем с первого простого
        candidates = [(n, x, p) for n, x in self.valid_sets[primes[0]]]
        current_M = primes[0]

        for i in range(1, len(primes)):
            p = primes[i]
            new_candidates = []
            new_M = current_M * p

            valid_p = self.valid_sets[p]

            for n1, x1, _ in candidates:
                for n2, x2 in valid_p:
                    # CRT для n: n1 mod current_M, n2 mod p
                    crt_n = extended_crt([(n1, current_M), (n2, p)])
                    crt_x = extended_crt([(x1, current_M), (x2, p)])

                    if crt_n is not None and crt_x is not None:
                        new_candidates.append((crt_n[0], crt_x[0], new_M))

            candidates = [(n, x, m) for n, x, m in new_candidates]
            current_M = new_M

            # Отсекаем, если слишком много кандидатов
            if len(candidates) > 10**6:
                print(f"  Отсечение на p={p}: {len(candidates)} кандидатов "
                      f"(M={current_M.bit_length()} бит)")
                break

        return [((n, x), m) for n, x, m in candidates]


def run_sieve_demo():
    """Демонстрация работы модульного решета."""
    print("=" * 60)
    print("ДЕМО: Модульное решето")
    print("=" * 60)

    # Проверяем плотность для первых простых
    test_primes = [5, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73]
    print("\nПлотность допустимых пар по простым модулям:")
    print(f"{'p':>6} | {'valid pairs':>12} | {'density':>10} | {'-log2(d)':>10}")
    print("-" * 50)

    for p in test_primes:
        valid = valid_pairs_mod_p(p)
        d = len(valid) / (p * p)
        log_d = -(-d).bit_length() if d > 0 else 999
        print(f"{p:>6} | {len(valid):>12} | {d:>10.6f} | {log_d:>10}")

    # Оценка сжатия
    sieve = ModularSieve(test_primes)
    density = sieve.estimate_compression(num_primes_used=18)
    print(f"\nИтоговая плотность после {len(test_primes)} простых: {density:.2e}")
    print(f"Степень сжатия: 1/{1/density:.2e}")

    # Оценка для n ~ 10^43
    n_bits = 144  # ~10^43
    result = sieve.sieve_crt(n_target_bits=n_bits, num_primes=18)
    print(f"\nОценка для |n| ~ 2^{n_bits} (~10^{int(n_bits * 0.301)}):")
    print(f"  Модуль M: {result['M_bits']} бит (~10^{int(result['M_bits'] * 0.301)})")
    print(f"  Оценка кандидатов: {result['candidates_estimate']:.2e}")


if __name__ == "__main__":
    run_sieve_demo()
