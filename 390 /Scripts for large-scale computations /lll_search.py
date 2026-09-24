"""
LLL/BKZ-поиск на решётке ограничений.

Использует алгоритм LLL для поиска малых корней полиномиального
уравнения с учётом модульных ограничений и асимптотики.

Основная идея (метод Копперсмита, адаптированный):
  1. Параметризуем x = C * n^{5/4} + delta (delta — малая поправка)
  2. Подставляем в y^2 = [x(x+6n)]^2 + (36n^3-65)*x
  3. Строим решётку из полиномиальных соотношений
  4. LLL-редукция находит короткий вектор = (delta, y)
"""

import numpy as np
from typing import List, Tuple, Dict, Optional
from math import gcd, isqrt, log2, ceil


def gram_schmidt(basis: np.ndarray) -> np.ndarray:
    """Грам-Шмидт ортогонализация."""
    n = basis.shape[0]
    orthogonal = basis.copy().astype(float)
    mu = np.zeros((n, n))

    for i in range(n):
        for j in range(i):
            if np.dot(orthogonal[j], orthogonal[j]) > 0:
                mu[i, j] = np.dot(basis[i], orthogonal[j]) / np.dot(orthogonal[j], orthogonal[j])
            orthogonal[i] = orthogonal[i] - mu[i, j] * orthogonal[j]

    return orthogonal


def lll_reduce(basis: np.ndarray, delta: float = 0.75) -> np.ndarray:
    """
    LLL-редукция решётки.
    basis: строки — векторы решётки
    Возвращает LLL-редуцированный базис.
    """
    B = basis.copy().astype(float)
    n = B.shape[0]

    def gs_inner(B):
        n = B.shape[0]
        Bstar = B.copy().astype(float)
        mu = np.zeros((n, n))
        for i in range(n):
            for j in range(i):
                norm = np.dot(Bstar[j], Bstar[j])
                if norm > 0:
                    mu[i, j] = np.dot(B[i], Bstar[j]) / norm
                Bstar[i] = Bstar[i] - mu[i, j] * Bstar[j]
        return Bstar, mu

    Bstar, mu = gs_inner(B)
    k = 1

    while k < n:
        for j in range(k - 1, -1, -1):
            if abs(mu[k, j]) > 0.5:
                q = round(mu[k, j])
                B[k] = B[k] - q * B[j]
                Bstar, mu = gs_inner(B)

        norm_k = np.dot(Bstar[k], Bstar[k])
        norm_km1 = np.dot(Bstar[k-1], Bstar[k-1])

        if norm_k >= (delta - mu[k, k-1]**2) * norm_km1 and norm_k > 0:
            k += 1
        else:
            B[[k, k-1]] = B[[k-1, k]]
            Bstar, mu = gs_inner(B)
            k = max(k - 1, 1)

    return B


def build_coppersmith_lattice(poly_coeffs: List[int],
                               modulus: int,
                               bound: int,
                               degree: int = 3,
                               m: int = 4) -> np.ndarray:
    """
    Строит решётку для метода Копперсмита.

    Для полинома f(x) = sum a_i * x^i и модуля N:
    строим решётку из сдвигов x^j * f(x)^k * N^{m-k}
    с границей |x| < X = bound.

    Параметры:
      poly_coeffs: коэффициенты [a_0, a_1, ..., a_d]
      modulus: модуль N
      bound: граница X для корня
      degree: степень полинома
      m: параметр решётки (количество «уровней»)
    """
    # Размер решётки
    dim = degree * m + 1

    # Строим матрицу решётки
    # Строки соответствуют полиномам: x^j * f(x)^k * N^{m-k}
    # Столбцы соответствуют коэффициентам при x^i, масштабированным X^i

    lattice = np.zeros((dim, dim), dtype=object)

    # Для простоты: используем целочисленную решётку
    # Полином f(x) = a_0 + a_1*x + ... + a_d*x^d
    # Сдвиги: f(x), x*f(x), ..., x^{m-1}*f(x), f(x)^2, ...
    # Умноженные на N^{m-1}, N^{m-2}, ...

    # Простая версия: мономиальные сдвиги
    X = bound

    row = 0
    for k in range(m):
        for j in range(degree):
            if row >= dim:
                break
            # Полином: x^j * f(x) * N^{m-k-1}
            # Коэффициенты: a_i * N^{m-k-1} при x^{i+j}
            for i in range(degree + 1):
                col = i + j
                if col < dim:
                    val = poly_coeffs[i] * (modulus ** (m - k - 1)) * (X ** col)
                    lattice[row, col] = int(val)
            row += 1

    # Дополнительные строки: x^j * N^m (мономиальные)
    for j in range(dim - row):
        if row + j < dim:
            col = j + degree  # сдвиг
            if col < dim:
                lattice[row + j, col] = int(modulus ** m * X ** col)

    # Преобразуем в float для LLL
    lattice_float = np.array(lattice, dtype=float)
    return lattice_float


def search_small_root_coppersmith(poly_coeffs: List[int],
                                   modulus: int,
                                   bound: int,
                                   degree: int = 3,
                                   m: int = 4) -> List[int]:
    """
    Поиск малых корней полинома по модулю методом Копперсмита.

    Возвращает список найденных корней x таких, что
    f(x) ≡ 0 (mod modulus) и |x| < bound.
    """
    # Строим решётку
    L = build_coppersmith_lattice(poly_coeffs, modulus, bound, degree, m)

    # LLL-редукция
    L_reduced = lll_reduce(L)

    # Первый (короткий) вектор даёт полином с малыми коэффициентами
    # g(x) = sum c_i * x^i, где c_i = L_reduced[0, i] / X^i

    # Извлекаем коэффициенты
    X = bound
    coeffs = []
    for i in range(L_reduced.shape[1]):
        if X ** i > 0:
            c = round(L_reduced[0, i] / (X ** i))
            coeffs.append(c)
        else:
            coeffs.append(0)

    # Ищем целые корни полинома g(x)
    roots = find_integer_roots(coeffs, bound)

    # Проверяем, какие корни удовлетворяют исходному уравнению
    valid_roots = []
    for r in roots:
        val = sum(c * r**i for i, c in enumerate(poly_coeffs))
        if val % modulus == 0:
            valid_roots.append(r)

    return valid_roots


def find_integer_roots(coeffs: List[int], bound: int) -> List[int]:
    """Поиск целых корней полинома с заданными коэффициентами."""
    # Используем рациональный корневой теорема + перебор
    if not coeffs or all(c == 0 for c in coeffs):
        return []

    # Нормализуем
    c0 = coeffs[0]
    if c0 == 0:
        # x=0 — корень, делим на x
        return [0] + find_integer_roots(coeffs[1:], bound)

    # Делители свободного члена
    divisors_c0 = []
    abs_c0 = abs(c0)
    i = 1
    while i * i <= abs_c0:
        if abs_c0 % i == 0:
            divisors_c0.extend([i, -i])
            if i != abs_c0 // i:
                divisors_c0.extend([abs_c0 // i, -(abs_c0 // i)])
        i += 1

    roots = []
    for d in divisors_c0:
        if abs(d) > bound:
            continue
        val = sum(c * d**i for i, c in enumerate(coeffs))
        if val == 0:
            roots.append(d)

    return roots


def build_constraint_lattice(n_mod: int, x_mod: int,
                              M: int, n_bits: int = 144) -> np.ndarray:
    """
    Строит решётку ограничений из модульных условий.

    Параметры:
      n_mod: n mod M
      x_mod: x mod M
      M: модуль
      n_bits: ожидаемая битовая длина n

    Решётка кодирует:
      n = n_mod + M * k1
      x = x_mod + M * k2
      с оценкой |k1| ~ 2^n_bits / M
      и x ~ n^{5/4}
    """
    # Масштабирование: веса для n и x
    # n ~ 2^n_bits, x ~ n^{5/4} ~ 2^{5n_bits/4}
    n_scale = 2 ** n_bits
    x_scale = int(2 ** (5 * n_bits / 4))

    # Решётка:
    # [M, 0, 0]
    # [n_mod, n_scale, 0]
    # [x_mod, 0, x_scale]

    # Вектор (k1, k2, 1) отображается в (n, x, 1)
    # через матрицу преобразования

    L = np.array([
        [M, 0, 0],
        [n_mod, n_scale, 0],
        [x_mod, 0, x_scale],
    ], dtype=float)

    return L


def lattice_search(n_mod: int, x_mod: int, M: int,
                    n_bits: int = 144) -> List[Tuple[int, int]]:
    """
    LLL-поиск кандидатов (n, x) из модульных остатков.

    Возвращает список пар (n, x), потенциально удовлетворяющих
    размерным ограничениям.
    """
    L = build_constraint_lattice(n_mod, x_mod, M, n_bits)
    L_reduced = lll_reduce(L)

    # Короткие векторы в редуцированной решётке соответствуют
    # малым (k1, k2) -> кандидатам (n, x)
    candidates = []

    for i in range(L_reduced.shape[0]):
        vec = L_reduced[i]
        # Восстанавливаем k1, k2
        # vec ≈ (n, x, 1) * scale
        # n = n_mod + M * k1, x = x_mod + M * k2

        # Из короткого вектора извлекаем приблизительные n и x
        # (зависит от конкретной параметризации решётки)
        n_approx = round(vec[0])
        x_approx = round(vec[1])

        # Проверяем модульные условия
        if n_approx % M == n_mod % M and x_approx % M == x_mod % M:
            candidates.append((n_approx, x_approx))

    return candidates


def run_lll_demo():
    """Демонстрация LLL-поиска."""
    print("=" * 60)
    print("ДЕМО: LLL-поиск на решётке ограничений")
    print("=" * 60)

    # Демонстрация: поиск малых корней
    # f(x) = x^3 + 2x^2 + 3x + 4 (mod 100)
    # Ищем корень |x| < 5
    print("\n1. Тест Coppersmith: f(x) = x^3 + 2x^2 + 3x + 4 (mod 100)")
    poly = [4, 3, 2, 1]  # [a0, a1, a2, a3]
    roots = search_small_root_coppersmith(poly, 100, 5, degree=3, m=2)
    print(f"   Найденные корни: {roots}")
    for r in roots:
        val = sum(c * r**i for i, c in enumerate(poly))
        print(f"   f({r}) = {val}, mod 100 = {val % 100}")

    # Демонстрация: решётка ограничений
    print("\n2. Тест решётки ограничений:")
    n_mod = 1  # n ≡ 1 (mod 3)
    x_mod = 5  # x ≡ 5 (mod 12)
    M = 3 * 12  # = 36 (НОК для базовых условий)

    # Для малых n_bits (демонстрация)
    L = build_constraint_lattice(n_mod, x_mod, M, n_bits=20)
    print(f"   Матрица решётки (n_bits=20):")
    print(f"   {L}")
    L_red = lll_reduce(L)
    print(f"   LLL-редуцированная:")
    print(f"   {L_red}")


if __name__ == "__main__":
    run_lll_demo()
