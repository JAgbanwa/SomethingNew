"""
Параметризация d = -1 - p/q и построение уравнения Туэ.

Исходное уравнение (после преобразования):
  36n^3 - 24d * n * x^2 - 4d(1+d) * x^3 = 65

При d = -1 - p/q:
  36n^3 + 24(1 + p/q) * n * x^2 - 4(-1-p/q)(-p/q) * x^3 = 65
  36n^3 + 24(q+p)/q * n * x^2 - 4p(q+p)/q^2 * x^3 = 65

Умножаем на q^2:
  36q^2 * n^3 + 24q(q+p) * n * x^2 - 4p(q+p) * x^3 = 65q^2

Аналогично при d = p/q (корень вблизи 0):
  36q^2 * n^3 - 24pq * n * x^2 - 4p(q+p) * x^3 = 65q^2
"""

from typing import List, Tuple, Dict, Optional
from math import gcd
import json


def parametrize_d_near_minus_one(p: int, q: int) -> Dict:
    """
    Параметризация d = -1 - p/q.

    Возвращает:
      - d: значение d
      - coefficients: коэффициенты формы Туэ
      - rhs: правая часть
      - polynomial: ассоциированный кубический полином
    """
    d_num = -(p + q)
    d_den = q
    g = gcd(abs(d_num), d_den)
    d_num //= g
    d_den //= g

    # Форма Туэ: 36q^2 * n^3 + 24q(q+p) * n * x^2 - 4p(q+p) * x^3 = 65q^2
    A = 36 * q * q           # коэффициент при n^3
    B = 0                     # коэффициент при n^2 * x (нет в нашем случае)
    C = 24 * q * (q + p)      # коэффициент при n * x^2
    D = -4 * p * (q + p)      # коэффициент при x^3
    rhs = 65 * q * q

    # Ассоциированный полином: A*t^3 + C*t - D = 0 (полагая x = t*n)
    # Точнее: 36q^2 * t^3 + 24q(q+p) * t - 4p(q+p) = 0
    poly_coeffs = [A, 0, C, -(-D)]  # [t^3, t^2, t, const] — приводим к виду A*t^3 + 0*t^2 + C*t + (-D) = 0
    # Но D = -4p(q+p), так что -D = 4p(q+p)
    poly_coeffs = [A, 0, C, 4 * p * (q + p)]

    return {
        'd': (d_num, d_den),
        'd_float': d_num / d_den,
        'coefficients': {'A': A, 'B': B, 'C': C, 'D': D},
        'rhs': rhs,
        'polynomial': poly_coeffs,  # A*t^3 + C*t + 4p(q+p) = 0
        'p': p,
        'q': q,
    }


def parametrize_d_near_zero(p: int, q: int) -> Dict:
    """
    Параметризация d = p/q (корень вблизи 0).

    Форма Туэ: 36q^2 * n^3 - 24pq * n * x^2 - 4p(q+p) * x^3 = 65q^2
    """
    A = 36 * q * q
    C = -24 * p * q
    D = -4 * p * (q + p)
    rhs = 65 * q * q

    poly_coeffs = [A, 0, C, -D]  # A*t^3 + C*t + (-D) = 0

    return {
        'd': (p, q),
        'd_float': p / q,
        'coefficients': {'A': A, 'B': 0, 'C': C, 'D': D},
        'rhs': rhs,
        'polynomial': poly_coeffs,
        'p': p,
        'q': q,
    }


def estimate_q_for_n(n_magnitude: int, root: str = 'near_minus_one') -> Dict:
    """
    Оценивает параметры q для заданного порядка n.

    Для корня d ≈ -1: q ~ C * n^{1/4} (C — константа из асимптотики x ~ C*n^{5/4})
    Для корня d ≈ 0:  q ~ (9/C^3) * n^{3/4}

    Параметры:
      n_magnitude: порядок n (например, 10^43)
      root: 'near_minus_one' или 'near_zero'
    """
    # Оценка C: из x ~ n^{5/4} и условий задачи
    # C ~ x / n^{5/4}; при n ~ 10^43, x ~ 10^53 (при C ~ 10^53/10^{53.75} ~ 10^{-0.75} ~ 0.18)
    # Точнее: x ~ n^{5/4} означает C ~ 1, q ~ n^{1/4}

    n_log10 = len(str(n_magnitude)) - 1 if isinstance(n_magnitude, int) else int(n_magnitude)

    if root == 'near_minus_one':
        # q ~ n^{1/4}, p — малое (1..20)
        q_estimate = 10 ** (n_log10 / 4)
        p_range = list(range(1, 21))
        d_estimate = -1 - 1 / q_estimate  # для p=1
    else:
        # q ~ n^{3/4}
        q_estimate = 10 ** (3 * n_log10 / 4)
        p_range = list(range(1, 10))
        d_estimate = 1 / q_estimate

    return {
        'q_estimate': int(q_estimate),
        'q_bits': int(q_estimate).bit_length(),
        'p_range': p_range,
        'd_estimate': d_estimate,
        'root': root,
    }


def generate_parithue_command(p: int, q: int, root: str = 'near_minus_one') -> str:
    """
    Генерирует команду для PARI/GP thue() для решения уравнения Туэ.

    Форма: A*n^3 + C*n*x^2 + D*x^3 = rhs
    PARI/GP требует полином от двух переменных.
    """
    if root == 'near_minus_one':
        params = parametrize_d_near_minus_one(p, q)
    else:
        params = parametrize_d_near_zero(p, q)

    A = params['coefficients']['A']
    C = params['coefficients']['C']
    D = params['coefficients']['D']
    rhs = params['rhs']

    # PARI/GP: thue(Thue([A,0,C,D], rhs))
    # Полином: A*X^3 + C*X*Y^2 + D*Y^3
    return f"thue(thueinit({A}*X^3 + {C}*X*Y^2 + {D}*Y^3), {rhs})"


def generate_magma_command(p: int, q: int, root: str = 'near_minus_one') -> str:
    """
    Генерирует команду для Magma Thue().
    """
    if root == 'near_minus_one':
        params = parametrize_d_near_minus_one(p, q)
    else:
        params = parametrize_d_near_zero(p, q)

    A = params['coefficients']['A']
    C = params['coefficients']['C']
    D = params['coefficients']['D']
    rhs = params['rhs']

    return f"Thue({A}*n^3 + {C}*n*x^2 + {D}*x^3, {rhs});"


def run_parametrization_demo():
    """Демонстрация параметризации."""
    print("=" * 60)
    print("ДЕМО: Параметризация d")
    print("=" * 60)

    # Оценка для n ~ 10^43
    n_mag = 10**43
    for root in ['near_minus_one', 'near_zero']:
        est = estimate_q_for_n(n_mag, root)
        print(f"\nКорень {root}:")
        print(f"  Оценка q: ~10^{int(est['q_bits'] * 0.301)} ({est['q_bits']} бит)")
        print(f"  Диапазон p: {est['p_range']}")
        print(f"  Оценка d: {est['d_estimate']:.6e}")

        # Пример для p=1, q=100 (демонстрационный)
        if root == 'near_minus_one':
            params = parametrize_d_near_minus_one(1, 100)
        else:
            params = parametrize_d_near_zero(1, 100)

        print(f"  Пример (p=1, q=100):")
        print(f"    d = {params['d'][0]}/{params['d'][1]} = {params['d_float']:.6f}")
        print(f"    Коэффициенты: A={params['coefficients']['A']}, "
              f"C={params['coefficients']['C']}, D={params['coefficients']['D']}")
        print(f"    RHS = {params['rhs']}")

        # PARI/GP команда
        gp_cmd = generate_parithue_command(1, 100, root)
        print(f"    PARI/GP: {gp_cmd[:80]}...")

        # Magma команда
        magma_cmd = generate_magma_command(1, 100, root)
        print(f"    Magma:   {magma_cmd[:80]}...")


if __name__ == "__main__":
    run_parametrization_demo()
