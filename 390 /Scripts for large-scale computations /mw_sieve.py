"""
Мордель-Вейлевское решето (Mordell-Weil Sieve).

Идея: для эллиптической кривой E, ассоциированной с задачей,
использовать локальную информацию (E(F_p)) для сужения
глобальных кандидатов.

Для нашей задачи: при фиксированном x уравнение
  y^2 = [x(x+6n)]^2 + (36n^3 - 65) * x
преобразуется к эллиптической кривой с j=0 (CM на Z[omega]).

Кривая в координатах (N, Y):
  Y^2 = N^3 + k
где N = 36*x*(3n + x), Y = 34992*x^2*y, k = -(x^3 + 195)/108

Стратегия Mordell-Weil Sieve:
  1. Найти (хотя бы частично) группу Mordell-Weil E(Q)
  2. Для каждого простого p вычислить E(F_p) и образ E(Q) -> E(F_p)
  3. Найти подмножество E(F_p), удовлетворяющее модульным условиям
  4. Комбинировать через CRT/решётку
"""

from typing import List, Tuple, Dict, Set, Optional
from math import gcd, isqrt
from functools import reduce
from itertools import product as iter_product


def elliptic_curve_points_mod_p(a: int, b: int, p: int) -> List[Tuple[int, int]]:
    """
    Вычисляет все точки эллиптической кривой Y^2 = N^3 + a*N + b над F_p.
    (В нашей формулировке: Y^2 = N^3 + k, так что a=0, b=k)
    """
    points = []
    # Точка на бесконечности обозначается как None
    points.append(None)

    for N in range(p):
        rhs = (N * N * N + a * N + b) % p
        if rhs == 0:
            points.append((N, 0))
        else:
            # Проверка квадратичного вычета
            if pow(rhs, (p - 1) // 2, p) == 1:
                # Находим квадратный корень по mod p
                Y = sqrt_mod_p(rhs, p)
                if Y is not None:
                    points.append((N, Y))
                    points.append((N, p - Y))

    return points


def sqrt_mod_p(a: int, p: int) -> Optional[int]:
    """Находит квадратный корень из a по модулю p (Tonelli-Shanks)."""
    if a == 0:
        return 0
    if p == 2:
        return a % 2

    # Проверка: квадратичный вычет?
    if pow(a, (p - 1) // 2, p) != 1:
        return None

    # p ≡ 3 (mod 4)
    if p % 4 == 3:
        return pow(a, (p + 1) // 4, p)

    # Tonelli-Shanks
    Q = p - 1
    S = 0
    while Q % 2 == 0:
        Q //= 2
        S += 1

    # Находим квадратичный невычет z
    z = 2
    while pow(z, (p - 1) // 2, p) != p - 1:
        z += 1

    M = S
    c = pow(z, Q, p)
    t = pow(a, Q, p)
    R = pow(a, (Q + 1) // 2, p)

    while True:
        if t == 1:
            return R
        # Находим наименьший i: t^{2^i} = 1
        i = 1
        temp = (t * t) % p
        while temp != 1:
            temp = (temp * temp) % p
            i += 1
        b = pow(c, 1 << (M - i - 1), p)
        M = i
        c = (b * b) % p
        t = (t * c) % p
        R = (R * b) % p


def point_add_mod_p(P: Optional[Tuple[int, int]],
                    Q_pt: Optional[Tuple[int, int]],
                    a_coeff: int, p: int) -> Optional[Tuple[int, int]]:
    """Сложение точек на Y^2 = X^3 + a_coeff*X + b над F_p."""
    if P is None:
        return Q_pt
    if Q_pt is None:
        return P

    x1, y1 = P
    x2, y2 = Q_pt

    if x1 == x2:
        if y1 == 0 or y1 == p - y1 and y1 != y2:
            return None  # точка на бесконечности
        # P = Q: касательная
        lam = (3 * x1 * x1 + a_coeff) * pow(2 * y1, -1, p) % p
    else:
        lam = (y2 - y1) * pow(x2 - x1, -1, p) % p

    x3 = (lam * lam - x1 - x2) % p
    y3 = (lam * (x1 - x3) - y1) % p
    return (x3, y3)


def point_mul_mod_p(k: int, P: Optional[Tuple[int, int]],
                    a_coeff: int, p: int) -> Optional[Tuple[int, int]]:
    """Умножение точки на скаляр (double-and-add)."""
    if k == 0 or P is None:
        return None
    if k < 0:
        if P is None:
            return None
        return point_mul_mod_p(-k, (P[0], (-P[1]) % p), a_coeff, p)

    result = None
    addend = P
    while k > 0:
        if k & 1:
            result = point_add_mod_p(result, addend, a_coeff, p)
        addend = point_add_mod_p(addend, addend, a_coeff, p)
        k >>= 1
    return result


def curve_order_mod_p(a: int, b: int, p: int) -> int:
    """Вычисляет порядок E(F_p) для Y^2 = X^3 + aX + b."""
    count = 1  # точка на бесконечности
    for x in range(p):
        rhs = (x**3 + a * x + b) % p
        if rhs == 0:
            count += 1
        elif pow(rhs, (p - 1) // 2, p) == 1:
            count += 2
    return count


class MordellWeilSieve:
    """
    Мордель-Вейлевское решето.

    Для кривой Y^2 = N^3 + k (j=0, a=0) и набора простых p:
      1. Вычисляет E(F_p) и его структуру
      2. Для каждого p находит допустимые классы (N mod p, Y mod p)
         с учётом модульных условий на (n, x)
      3. Комбинирует через CRT
    """

    def __init__(self, k: int, x_val: int):
        """
        Параметры:
          k: параметр кривой Y^2 = N^3 + k
          x_val: значение x (для связи N с n)
        """
        self.k = k
        self.x = x_val
        self.a_coeff = 0  # для j=0: Y^2 = X^3 + k

    def N_from_n(self, n: int) -> int:
        """N = 36 * x * (3n + x)"""
        return 36 * self.x * (3 * n + self.x)

    def n_from_N(self, N: int) -> Optional[int]:
        """Обратное преобразование: n = (N/(36x) - x) / 3"""
        denom = 36 * self.x
        if N % denom != 0:
            return None
        val = N // denom
        val -= self.x
        if val % 3 != 0:
            return None
        return val // 3

    def compute_valid_classes(self, p: int) -> Dict:
        """
        Для простого p находит допустимые классы (N mod p, Y mod p),
        удовлетворяющие:
          - N ≡ 36*x*(3n+x) (mod p) для n ≡ 1 (mod 3)
          - x ≡ 5 (mod 12), x ≢ 0 (mod 7)
          - Y^2 ≡ N^3 + k (mod p)
        """
        k_mod = self.k % p
        x_mod = self.x % p

        valid_n_classes = set()
        if p == 3:
            valid_n_classes = {1}
        else:
            for n in range(p):
                if n % 3 == 1:
                    valid_n_classes.add(n)

        valid_points = []
        n_to_N_map = {}
        for n_class in valid_n_classes:
            N_class = (36 * x_mod * (3 * n_class + x_mod)) % p
            n_to_N_map[N_class] = n_class

        for N_class in n_to_N_map:
            rhs = (N_class**3 + k_mod) % p
            if rhs == 0:
                valid_points.append((N_class, 0, n_to_N_map[N_class]))
            elif pow(rhs, (p - 1) // 2, p) == 1:
                Y = sqrt_mod_p(rhs, p)
                if Y is not None:
                    valid_points.append((N_class, Y, n_to_N_map[N_class]))
                    if Y != 0:
                        valid_points.append((N_class, (p - Y) % p, n_to_N_map[N_class]))

        return {
            'p': p,
            'curve_order': curve_order_mod_p(0, k_mod, p),
            'valid_points': valid_points,
            'n_classes': list(valid_n_classes),
        }


def run_mw_sieve_demo():
    """Демонстрация Мордель-Вейлевского решета."""
    print("=" * 60)
    print("ДЕМО: Мордель-Вейлевское решето")
    print("=" * 60)

    # Для демонстрации используем малое x
    # k = -(x^3 + 195) / 108
    # Нужно, чтобы k было целым (или работаем с масштабированной кривой)

    test_x_values = [5, 17, 29]  # x ≡ 5 (mod 12)

    for x in test_x_values:
        print(f"\n--- x = {x} ---")
        # k = -(x^3 + 195) / 108
        num = -(x**3 + 195)
        if num % 108 != 0:
            # Масштабируем: работаем с Y'^2 = N^3 + k_num
            # где k_num = -(x^3 + 195), и проверяем делимость отдельно
            print(f"  k не целое для x={x}: -(x^3+195)={num}, не делится на 108")
            # Используем масштабированную версию
            k_scaled = num
            sieve = MordellWeilSieve(k_scaled, x)
            # Для масштабированной кривой: Y'^2 = 108*N^3 + k_scaled*108
            # Это не стандартная форма, пропускаем
            continue

        k = num // 108
        print(f"  k = {k}")

        sieve = MordellWeilSieve(k, x)

        # Проверяем для нескольких простых
        test_primes = [5, 7, 11, 13, 17, 19, 23, 29, 31]
        print(f"  {'p':>6} | {'|E(F_p)|':>10} | {'valid pts':>10} | {'density':>10}")
        print("  " + "-" * 45)

        for p in test_primes:
            if p == 7 and x % 7 == 0:
                continue
            result = sieve.compute_valid_classes(p)
            density = len(result['valid_points']) / result['curve_order'] if result['curve_order'] > 0 else 0
            print(f"  {p:>6} | {result['curve_order']:>10} | {len(result['valid_points']):>10} | {density:>10.6f}")


if __name__ == "__main__":
    run_mw_sieve_demo()
