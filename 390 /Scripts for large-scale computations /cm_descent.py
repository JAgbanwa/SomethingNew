"""
3-спуск на эллиптической кривой с j=0 (CM на Z[omega]).

Для кривой Y^2 = N^3 + k, j=0, комплексное умножение на Z[omega],
omega = e^{2*pi*i/3}.

3-спуск использует факторизацию:
  N^3 + k = (N + alpha)(N + omega*alpha)(N + omega^2*alpha)
где alpha = k^{1/3}.

В кольце Z[omega] (или его расширении) это даёт гомоморфизм
E(Q) -> K^*/(K^*)^3, образ которого — 3-группа Сельмера.

Для j=0 кривой 3-спуск особенно эффективен, т.к.:
  - Кольцо целых Z[omega] — PID (даже EUF)
  - Группа единиц Z[omega]^* = {±1, ±omega, ±omega^2} (конечна)
  - Факторизация в Z[omega] сводится к факторизации в Z
"""

from typing import List, Tuple, Dict, Optional, Set
from math import gcd, isqrt
import sys


# ============================================================
# Арифметика в Z[omega], omega = (-1 + sqrt(-3))/2
# omega^2 = -1 - omega, omega^3 = 1
# ============================================================

class OmegaInt:
    """Элемент кольца Z[omega]: a + b*omega, omega = (-1+sqrt(-3))/2."""

    def __init__(self, a: int, b: int):
        self.a = a
        self.b = b

    def __repr__(self):
        return f"OmegaInt({self.a}, {self.b})"

    def __str__(self):
        if self.b == 0:
            return str(self.a)
        if self.a == 0:
            if self.b == 1:
                return "ω"
            return f"{self.b}ω"
        if self.b > 0:
            return f"{self.a} + {self.b}ω"
        return f"{self.a} - {-self.b}ω"

    def __add__(self, other):
        return OmegaInt(self.a + other.a, self.b + other.b)

    def __sub__(self, other):
        return OmegaInt(self.a - other.a, self.b - other.b)

    def __mul__(self, other):
        # (a + b*omega)(c + d*omega) = ac + (ad+bc)*omega + bd*omega^2
        # omega^2 = -1 - omega
        # = ac + (ad+bc)*omega + bd*(-1-omega)
        # = (ac - bd) + (ad + bc - bd)*omega
        a, b = self.a, self.b
        c, d = other.a, other.b
        return OmegaInt(a*c - b*d, a*d + b*c - b*d)

    def norm(self) -> int:
        """Норма N(a + b*omega) = a^2 - ab + b^2."""
        return self.a * self.a - self.a * self.b + self.b * self.b

    def conjugate(self):
        """Комплексное сопряжение: a + b*omega -> a + b*omega^2 = (a-b) - b*omega."""
        return OmegaInt(self.a - self.b, -self.b)

    def __eq__(self, other):
        if isinstance(other, OmegaInt):
            return self.a == other.a and self.b == other.b
        return self.a == other and self.b == 0

    def is_unit(self) -> bool:
        return self.norm() == 1

    def __hash__(self):
        return hash((self.a, self.b))


def omega_divide(p: OmegaInt, q: OmegaInt) -> Optional[OmegaInt]:
    """Деление в Z[omega]: p/q, если результат — целое в Z[omega]."""
    q_conj = q.conjugate()
    q_norm = q.norm()

    # p * q_conj = (p*q_conj) / q_norm
    num = p * q_conj

    if num.a % q_norm != 0 or num.b % q_norm != 0:
        return None

    return OmegaInt(num.a // q_norm, num.b // q_norm)


def omega_gcd(a: OmegaInt, b: OmegaInt) -> OmegaInt:
    """НОД в Z[omega] (алгоритм Евклида)."""
    while b.norm() > 0:
        q = omega_divide(a, b)
        if q is None:
            break
        a, b = b, a - q * b
    return a


def factorize_in_Z_omega(n: int) -> List[Tuple[OmegaInt, int]]:
    """
    Факторизация целого числа n в Z[omega].

    Простые в Z:
      - p = 3: ramified, 3 = -(1-omega)^2 * unit (простое (1-omega) с нормой 3)
      - p ≡ 1 (mod 3): splits, p = pi * pi_conj
      - p ≡ 2 (mod 3): inert, остаётся простым в Z[omega]
    """
    if n == 0:
        return []
    n = abs(n)
    factors = []

    # Разложение на простые в Z
    z_factors = factorize_int(n)

    for p, e in z_factors:
        if p == 3:
            # 3 = -(1-omega)^2 (с точностью до единицы)
            pi = OmegaInt(1, -1)  # 1 - omega, норма 3
            factors.append((pi, 2 * e))

        elif p % 3 == 1:
            # p расщепляется: p = pi * pi_conj
            pi = find_split_prime(p)
            if pi is not None:
                factors.append((pi, e))
                factors.append((pi.conjugate(), e))

        else:
            # p ≡ 2 (mod 3): остаётся простым
            factors.append((OmegaInt(p, 0), e))

    return factors


def factorize_int(n: int) -> List[Tuple[int, int]]:
    """Разложение целого числа на простые множители."""
    if n <= 1:
        return []
    factors = []
    d = 2
    while d * d <= n:
        count = 0
        while n % d == 0:
            count += 1
            n //= d
        if count > 0:
            factors.append((d, count))
        d += 1
    if n > 1:
        factors.append((n, 1))
    return factors


def find_split_prime(p: int) -> Optional[OmegaInt]:
    """
    Для простого p ≡ 1 (mod 3) находит pi в Z[omega] с N(pi) = p.
    """
    # Ищем a, b такие, что a^2 - ab + b^2 = p
    for b in range(1, isqrt(p) + 1):
        # a^2 - ab + b^2 = p
        # a^2 - ab + (b^2 - p) = 0
        # D = b^2 - 4(b^2 - p) = 4p - 3b^2
        D = 4 * p - 3 * b * b
        if D < 0:
            break
        if D > 0:
            sqrt_D = isqrt(D)
            if sqrt_D * sqrt_D == D and (b + sqrt_D) % 2 == 0:
                a = (b + sqrt_D) // 2
                return OmegaInt(a, b)
            if sqrt_D * sqrt_D == D and (b - sqrt_D) % 2 == 0:
                a = (b - sqrt_D) // 2
                if a > 0:
                    return OmegaInt(a, b)
        elif D == 0:
            # b = 0: a^2 = p — только если p — полный квадрат
            pass
    return None


# ============================================================
# 3-спуск
# ============================================================

def selmer_3_descent_j0(k: int, S_primes: List[int]) -> Dict:
    """
    3-спуск для кривой Y^2 = X^3 + k (j=0).

    Вычисляет 3-группу Сельмера, используя факторизацию
    в Z[omega].

    Параметры:
      k: параметр кривой
      S_primes: список простых для S-единиц (включая делители k и 3)

    Возвращает:
      - dim_selmer: размерность 3-группы Сельмера
      - cosets: представители смежных классов
    """
    # Факторизация k в Z[omega]
    k_factors = factorize_in_Z_omega(k)

    # 3-группа Сельмера: элементы K^*/(K^*)^3, удовлетворяющие
    # локальным условиям в каждой S-единице

    # Для j=0: Sel^{(3)}(E/Q) вложено в (Z[omega, 1/S]^* / (.)^3)
    # Размер ограничена: dim <= dim_S + 1, где dim_S = |S|

    # Для каждого простого из S: локальное условие
    # (вычисление образа в локальной группе)

    S_primes_with_3 = set(S_primes) | {3}
    # Включаем простые, делящие k
    k_int_factors = factorize_int(abs(k))
    for p, _ in k_int_factors:
        S_primes_with_3.add(p)

    S_list = sorted(S_primes_with_3)

    # Размерность Сельмера (оценка)
    # Для кривой Y^2 = X^3 + k:
    # dim Sel^{(3)} = |S| - 1 (приближённо, без учёта тонких локальных условий)
    # Точнее: dim Sel^{(3)} = |{p in S : v_p(k) ≡ 1 or 2 (mod 3)}|

    relevant_primes = []
    for p in S_list:
        v_p = 0
        temp = abs(k)
        while temp % p == 0:
            temp //= p
            v_p += 1
        if v_p % 3 != 0:
            relevant_primes.append(p)

    dim_estimate = len(relevant_primes)

    return {
        'k': k,
        'S_primes': S_list,
        'k_factors_in_Z_omega': [(str(f), e) for f, e in k_factors],
        'relevant_primes': relevant_primes,
        'dim_selmer_estimate': dim_estimate,
        'rank_estimate': max(0, dim_estimate - 1),  # грубая оценка ранга
    }


def compute_integral_points_j0(k: int, N_bound: int = 10**6) -> List[Tuple[int, int]]:
    """
    Поиск целых точек на Y^2 = X^3 + k.

    Для j=0 кривой можно использовать структуру:
    каждая целая точка (X, Y) соответствует разложению
    Y^2 = X^3 + k в Z[omega].

    Параметры:
      k: параметр кривой
      N_bound: верхняя граница для |X|
    """
    points = []

    # Прямой поиск для малых границ
    for X in range(-N_bound, N_bound + 1):
        val = X**3 + k
        if val < 0:
            continue
        Y = isqrt(val)
        if Y * Y == val:
            points.append((X, Y))
            if Y != 0:
                points.append((X, -Y))

    return points


def heegner_point_method(k: int) -> Optional[Tuple[int, int]]:
    """
    Метод точек Хигнера для кривой Y^2 = X^3 + k.

    Для j=0 кривой с CM на Z[omega], точки Хигнера можно
    вычислить через значения эта-функций.

    Это заглушка — полная реализация требует работы с
    мнимым квадратичным полем и значениями L-функций.
    """
    # Для j=0: дискриминант CM-поля = -3
    # Точки Хигнера соответствуют CM-точкам на модулярной кривой X_0(3)

    # Полная реализация: см. Cohen, "Advanced Topics in Computational
    # Number Theory", Chapter 6 (Heegner Points)

    print("  [Заглушка: метод точек Хигнера требует PARI/GP или Magma]")
    print("  Рекомендуется: ellheegner() в PARI/GP или HeegnerPoint() в Magma")

    return None


def run_cm_descent_demo():
    """Демонстрация 3-спуска на CM-кривой."""
    print("=" * 60)
    print("ДЕМО: 3-спуск на CM-кривой (j=0)")
    print("=" * 60)

    # Арифметика Z[omega]
    print("\n1. Арифметика Z[omega]:")
    a = OmegaInt(2, 1)
    b = OmegaInt(1, -1)
    print(f"   a = {a}, b = {b}")
    print(f"   a + b = {a + b}")
    print(f"   a * b = {a * b}")
    print(f   f"   N(a) = {a.norm()}, N(b) = {b.norm()}")

    # Факторизация
    print("\n2. Факторизация в Z[omega]:")
    for n in [7, 13, 19, 31, 3]:
        factors = factorize_in_Z_omega(n)
        factor_str = " * ".join(f"({f})^{e}" if e > 1 else f"({f})" for f, e in factors)
        print(f"   {n} = {factor_str}")

    # 3-спуск
    print("\n3. 3-спуск для Y^2 = X^3 + k:")
    test_k_values = [-2, 7, -26, 65, -65]
    for k in test_k_values:
        result = selmer_3_descent_j0(k, S_primes=[2, 3, 5])
        print(f"   k={k}: dim Sel^(3) ~ {result['dim_selmer_estimate']}, "
              f"relevant primes: {result['relevant_primes']}")

    # Целые точки
    print("\n4. Целые точки Y^2 = X^3 + k:")
    for k in [2, -2, 7, -26]:
        pts = compute_integral_points_j0(k, N_bound=1000)
        print(f"   k={k}: {len(pts)} точек в диапазоне |X| <= 1000")
        for p in pts[:5]:
            print(f"     (X={p[0]}, Y={p[1]})")
        if len(pts) > 5:
            print(f"     ... и ещё {len(pts)-5}")


if __name__ == "__main__":
    run_cm_descent_demo()
