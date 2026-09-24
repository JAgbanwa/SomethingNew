"""
Верификация найденных решений.

Полная проверка пары (n, x, d) в исходном уравнении:

  36n^3 - 65 = -2d * x^2 * (-(x+6n) + sqrt((x+6n)^2 + (36n^3-65)/x))

Проверяет:
  1. n, x — целые числа
  2. x ≠ 0
  3. x | (36n^3 - 65) (для целостности подкоренного выражения)
  4. (36n^3 - 65) / x — целое
  5. (x+6n)^2 + (36n^3-65)/x ≥ 0 (вещественность)
  6. sqrt(...) — целое
  7. Исходное уравнение выполняется
  8. Модульные условия: n ≡ 1 (mod 3), x ≡ 5 (mod 12), x ≢ 0 (mod 7)
"""

from fractions import Fraction
from math import isqrt
from typing import Tuple, Dict, Optional
import json


def verify_full(n: int, x: int, d_num: int, d_den: int,
                check_modular: bool = True) -> Dict:
    """
    Полная верификация решения.

    Параметры:
      n: целое значение n
      x: целое значение x
      d_num: числитель d
      d_den: знаменатель d
      check_modular: проверять ли модульные условия

    Возвращает словарь с результатами всех проверок.
    """
    result = {
        'n': n,
        'x': x,
        'd': f"{d_num}/{d_den}",
        'd_value': Fraction(d_num, d_den),
        'checks': {},
        'valid': True,
        'errors': [],
    }

    # 1. Целостность
    if not isinstance(n, int) or not isinstance(x, int):
        result['checks']['integers'] = False
        result['errors'].append('n и x должны быть целыми')
        result['valid'] = False
        return result
    result['checks']['integers'] = True

    # 2. x ≠ 0
    if x == 0:
        result['checks']['x_nonzero'] = False
        result['errors'].append('x не должно быть равно 0')
        result['valid'] = False
        return result
    result['checks']['x_nonzero'] = True

    # 3. Модульные условия
    if check_modular:
        mod_n = (n % 3 == 1)
        mod_x = (x % 12 == 5)
        mod_x7 = (x % 7 != 0)
        result['checks']['n_mod_3'] = mod_n
        result['checks']['x_mod_12'] = mod_x
        result['checks']['x_not_mod_7'] = mod_x7
        if not mod_n:
            result['errors'].append(f'n ≡ {n % 3} (mod 3), должно быть 1')
            result['valid'] = False
        if not mod_x:
            result['errors'].append(f'x ≡ {x % 12} (mod 12), должно быть 5')
            result['valid'] = False
        if not mod_x7:
            result['errors'].append(f'x ≡ 0 (mod 7), не должно быть')
            result['valid'] = False

    # 4. x | (36n^3 - 65)
    val = 36 * n**3 - 65
    if val % x != 0:
        result['checks']['x_divides'] = False
        result['errors'].append(f'x не делит (36n^3 - 65) = {val}')
        result['valid'] = False
        return result
    result['checks']['x_divides'] = True

    # 5. Подкоренное выражение
    A = x + 6 * n
    fraction_part = val // x  # целое по предыдущей проверке
    radicand = A * A + fraction_part

    result['checks']['radicand'] = radicand

    if radicand < 0:
        result['checks']['nonneg'] = False
        result['errors'].append(f'Подкоренное выражение отрицательно: {radicand}')
        result['valid'] = False
        return result
    result['checks']['nonneg'] = True

    # 6. sqrt — целое
    if radicand == 0:
        S = 0
        result['checks']['sqrt_integer'] = True
    else:
        S = isqrt(radicand)
        if S * S != radicand:
            result['checks']['sqrt_integer'] = False
            result['errors'].append(f'sqrt({radicand}) не целое (ближайший квадрат: {S}^2 = {S*S})')
            result['valid'] = False
            return result
        result['checks']['sqrt_integer'] = True

    result['S'] = S

    # 7. Проверка исходного уравнения
    d = Fraction(d_num, d_den)
    lhs = Fraction(36 * n**3 - 65)
    inner = -(x + 6 * n) + S
    rhs = -2 * d * x * x * inner

    result['checks']['equation'] = (lhs == rhs)
    if lhs != rhs:
        result['errors'].append(
            f'Уравнение не выполняется: LHS={lhs}, RHS={rhs}'
        )
        result['valid'] = False

    # 8. Дополнительная информация
    w = x * (x + 6 * n)
    y = S
    result['info'] = {
        'A': A,
        'S': S,
        'w': w,
        'radicand': radicand,
        'y_minus_w': y - w,
        'y_plus_w': y + w,
        'd_from_y_w': f"{y - w}/{2 * x * x}",
        'd_from_neg_y_w': f"{-(y + w)}/{2 * x * x}",
    }

    return result


def verify_batch(solutions: List[Tuple[int, int, int, int]]) -> List[Dict]:
    """Пакетная верификация решений."""
    results = []
    for n, x, d_num, d_den in solutions:
        r = verify_full(n, x, d_num, d_den)
        results.append(r)
    return results


def format_result(result: Dict, verbose: bool = False) -> str:
    """Форматирование результата верификации."""
    lines = []
    status = "✓ ВАЛИДНО" if result['valid'] else "✗ НЕВАЛИДНО"
    lines.append(f"  Решение (n={result['n']}, x={result['x']}, d={result['d']}): {status}")

    if result['errors']:
        for err in result['errors']:
            lines.append(f"    ✗ {err}")

    if verbose and result['valid']:
        info = result.get('info', {})
        lines.append(f"    S = {info.get('S', '?')}")
        lines.append(f"    w = x(x+6n) = {info.get('w', '?')}")
        lines.append(f"    y - w = {info.get('y_minus_w', '?')}")
        lines.append(f"    y + w = {info.get('y_plus_w', '?')}")

    return "\n".join(lines)


# Тип для аннотации
from typing import List


def run_verify_demo():
    """Демонстрация верификации."""
    print("=" * 60)
    print("ДЕМО: Верификация решений")
    print("=" * 60)

    # Тест с заведомо валидным решением (если найдём)
    print("\n1. Проверка валидного решения:")

    # Тривиальный случай: n=1, пробуем разные x
    for n in [1, -1, 4, -4, 7, -7]:
        for x in range(-100, 101):
            if x == 0 or x % 12 != 5 or x % 7 == 0:
                continue
            val = 36 * n**3 - 65
            if val % x != 0:
                continue
            A = x + 6 * n
            radicand = A * A + val // x
            if radicand < 0:
                continue
            S = isqrt(radicand)
            if S * S == radicand:
                # Нашли кандидат: вычисляем d
                w = x * (x + 6 * n)
                # d = (y - w) / (2x^2)
                d_num = S - w
                d_den = 2 * x * x
                from math import gcd
                g = gcd(abs(d_num), abs(d_den))
                d_num //= g
                d_den //= g

                result = verify_full(n, x, d_num, d_den)
                print(f"\n{format_result(result, verbose=True)}")

    # Тест с невалидным решением
    print("\n2. Проверка невалидного решения:")
    result = verify_full(10, 17, 1, 3)  # случайные значения
    print(format_result(result, verbose=True))

    print("\n3. Проверка тривиального d=0:")
    # d=0: 36n^3 - 65 = 0 -> n = (65/36)^{1/3} — не целое
    result = verify_full(1, 5, 0, 1)
    print(format_result(result, verbose=True))


if __name__ == "__main__":
    run_verify_demo()
