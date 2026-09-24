"""
Главная программа для поиска решений уравнения:

  36n^3 - 65 = -2d * x^2 * (-(x+6n) + sqrt((x+6n)^2 + (36n^3-65)/x))

Стратегия:
  1. Параметризация d вблизи -1 (или 0)
  2. Модульное решето для сужения (n, x) mod M
  3. Факторизационный поиск для малых n
  4. 3-спуск на CM-кривой для генерации кандидатов
  5. Мордель-Вейлевское решето для сужения кандидатов
  6. LLL-поиск для крупных n
  7. Верификация найденных решений

Использование:
  python main.py --mode demo          # демонстрация всех модулей
  python main.py --mode sieve         # только модульное решето
  python main.py --mode factor        # только факторизационный поиск
  python main.py --mode search-small   # поиск малых решений
  python main.py --mode search-large  # настройка для больших n
  python main.py --mode verify n x d_num d_den  # верификация
"""

import sys
import argparse
from typing import List, Tuple


def run_demo():
    """Запуск демонстрации всех модулей."""
    print("=" * 70)
    print("ПОЛНАЯ ДЕМОНСТРАЦИЯ АЛГОРИТМОВ ПОИСКА РЕШЕНИЙ")
    print("=" * 70)
    print()

    # 1. Модульное решето
    print("\n" + "=" * 70)
    print("ЭТАП 1: Модульное решето")
    print("=" * 70)
    from modular_sieve import run_sieve_demo
    run_sieve_demo()

    # 2. Параметризация
    print("\n" + "=" * 70)
    print("ЭТАП 2: Параметризация d")
    print("=" * 70)
    from thue_param import run_parametrization_demo
    run_parametrization_demo()

    # 3. Факторизационный поиск
    print("\n" + "=" * 70)
    print("ЭТАП 3: Факторизационный поиск")
    print("=" * 70)
    from factorization_search import run_factorization_demo
    run_factorization_demo()

    # 4. CM-спуск
    print("\n" + "=" * 70)
    print("ЭТАП 4: 3-спуск на CM-кривой")
    print("=" * 70)
    from cm_descent import run_cm_descent_demo
    run_cm_descent_demo()

    # 5. LLL-поиск
    print("\n" + "=" * 70)
    print("ЭТАП 5: LLL-поиск")
    print("=" * 70)
    from lll_search import run_lll_demo
    run_lll_demo()

    # 6. Верификация
    print("\n" + "=" * 70)
    print("ЭТАП 6: Верификация")
    print("=" * 70)
    from verify import run_verify_demo
    run_verify_demo()

    print("\n" + "=" * 70)
    print("ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")
    print("=" * 70)


def run_sieve_only():
    """Только модульное решето."""
    from modular_sieve import ModularSieve, valid_pairs_mod_p, select_sieving_primes

    print("Модульное решето: анализ плотности и сжатия")
    print()

    primes = select_sieving_primes(num_primes=50, min_p=5, max_p=10000)
    sieve = ModularSieve(primes)

    print(f"Простых: {len(primes)}")
    for p in primes[:20]:
        d = len(sieve.valid_sets[p]) / (p * p)
        print(f"  p={p:>6}: {len(sieve.valid_sets[p]):>4} валидных пар, "
              f"плотность={d:.6f}")

    # Оценка сжатия
    for n_primes in [10, 20, 30, 50]:
        density = sieve.estimate_compression(n_primes)
        print(f"\n{n_primes} простых: плотность={density:.2e}, "
              f"сжатие=1/{1/density:.2e}")


def run_factor_only():
    """Только факторизационный поиск."""
    from factorization_search import search_with_modular_prefilter, verify_solution

    print("Факторизационный поиск малых решений")
    print()

    for n in range(-100, 101):
        sols = search_with_modular_prefilter(n, x_max=10**6)
        if sols:
            for s in sols:
                d = s['d']
                ok = verify_solution(s['n'], s['x'], d[0], d[1])
                print(f"  n={s['n']}, x={s['x']}, d={d[0]}/{d[1]}={s['d_float']:.8f}, "
                      f"root={s['root']}, valid={'✓' if ok else '✗'}")


def run_search_small():
    """Поиск малых решений (n до 10^6)."""
    from factorization_search import search_with_modular_prefilter, verify_solution
    from modular_sieve import ModularSieve, valid_pairs_mod_p

    print("Поиск малых решений (|n| ≤ 10^6)")
    print()

    # Сначала: модульный предфильтр
    sieve_primes = [5, 11, 13, 17, 19, 23, 29, 31, 37, 41]
    sieve = ModularSieve(sieve_primes)

    solutions_found = 0

    for n in range(-10**6, 10**6 + 1):
        if n == 0:
            continue
        if n % 3 != 1:
            continue

        sols = search_with_modular_prefilter(n, x_max=10**6,
                                             sieve_mods=sieve_primes)
        if sols:
            for s in sols:
                d = s['d']
                ok = verify_solution(s['n'], s['x'], d[0], d[1])
                if ok:
                    solutions_found += 1
                    print(f"  ✓ n={s['n']}, x={s['x']}, "
                          f"d={d[0]}/{d[1]}={s['d_float']:.10f}, "
                          f"root={s['root']}")

                    # Запись в файл
                    with open('solutions_found.txt', 'a') as f:
                        f.write(f"{s['n']}\t{s['x']}\t{d[0]}\t{d[1]}\t"
                                f"{s['root']}\t{s['y']}\n")

        if n % 100000 == 0 and n != 0:
            print(f"  ... проверено до n={n}, найдено {solutions_found}")

    print(f"\nВсего найдено решений: {solutions_found}")


def run_search_large_setup():
    """Настройка поиска для больших n (~10^43)."""
    from thue_param import estimate_q_for_n, parametrize_d_near_minus_one
    from modular_sieve import ModularSieve, select_sieving_primes
    from cm_descent import selmer_3_descent_j0

    print("=" * 70)
    print("НАСТРОЙКА ПОИСКА ДЛЯ КРУПНЫХ n (~10^43)")
    print("=" * 70)

    # 1. Оценка параметров d
    n_mag = 10**43
    est = estimate_q_for_n(n_mag, 'near_minus_one')
    print(f"\n1. Параметризация d ≈ -1:")
    print(f"   q ~ {est['q_estimate']} (~10^{int(est['q_bits'] * 0.301)})")
    print(f"   p диапазон: {est['p_range']}")
    print(f"   d ~ {est['d_estimate']:.6e}")

    # 2. Выбор простых для решета
    print(f"\n2. Выбор простых для решета:")
    sieve_primes = select_sieving_primes(num_primes=200, min_p=5, max_p=10**6)
    print(f"   Выбрано {len(sieve_primes)} простых (до {sieve_primes[-1]})")

    sieve = ModularSieve(sieve_primes[:100])
    density = sieve.estimate_compression(100)
    print(f"   Плотность после 100 простых: {density:.2e}")
    print(f"   Сжатие: 1/{1/density:.2e}")

    # Оценка кандидатов
    n_range = 2 * 10**43
    x_range = int(n_range**1.25)
    candidates = density * n_range * x_range
    print(f"   Оценка кандидатов: {candidates:.2e}")

    # 3. Параметризация для конкретных (p, q)
    print(f"\n3. Примеры форм Туэ:")
    for p in [1, 2, 3, 6, 12]:
        q = est['q_estimate']
        params = parametrize_d_near_minus_one(p, q)
        c = params['coefficients']
        print(f"   p={p}, q={q}:  {c['A']}*n^3 + {c['C']}*n*x^2 + {c['D']}*x^3 = {params['rhs']}")
        print(f"     d = {params['d'][0]}/{params['d'][1]} = {params['d_float']:.10e}")

    # 4. 3-спуск
    print(f"\n4. 3-спуск на CM-кривой:")
    # Для демонстрации берём малое x
    for x_test in [5, 17, 29, 41, 53]:
        k_num = -(x_test**3 + 195)
        if k_num % 108 == 0:
            k = k_num // 108
            result = selmer_3_descent_j0(k, S_primes=[2, 3, 5, 7])
            print(f"   x={x_test}: k={k}, dim Sel^(3) ~ {result['dim_selmer_estimate']}, "
                  f"relevant: {result['relevant_primes']}")

    # 5. Инструкции для внешних систем
    print(f"\n5. Команды для внешних систем:")
    from thue_param import generate_parithue_command, generate_magma_command

    for p in [1, 6]:
        q = 1000  # демонстрационный q
        gp = generate_parithue_command(p, q, 'near_minus_one')
        magma = generate_magma_command(p, q, 'near_minus_one')
        print(f"\n   PARI/GP (p={p}, q={q}):")
        print(f"     {gp[:120]}")
        print(f"\n   Magma (p={p}, q={q}):")
        print(f"     {magma[:120]}")

    print(f"\n6. Рекомендации:")
    print(f"   - Начать с корня d ≈ -1 (q ~ 10^11)")
    print(f"   - Использовать PARI/GP thue() для точного решения")
    print(f"   - Модульное решето: ~200 простых, M ~ 10^1000")
    print(f"   - 3-спуск: реализовать в Magma (HeegnerPoint, RankBounds)")
    print(f"   - LLL: использовать fplll для BKZ с block_size=40")
    print(f"   - Параллелизация: per-q (каждый q — независимая задача)")


def run_verify(n: int, x: int, d_num: int, d_den: int):
    """Верификация конкретного решения."""
    from verify import verify_full, format_result
    result = verify_full(n, x, d_num, d_den)
    print(format_result(result, verbose=True))
    return result['valid']


def main():
    parser = argparse.ArgumentParser(
        description='Поиск решений диофантова уравнения 36n^3 - 65 = -2d*x^2*(...)'
    )
    parser.add_argument('--mode', type=str, default='demo',
                        choices=['demo', 'sieve', 'factor', 'search-small',
                                 'search-large', 'verify'],
                        help='Режим работы')
    parser.add_argument('args', nargs='*', help='Дополнительные аргументы')

    args = parser.parse_args()

    if args.mode == 'demo':
        run_demo()
    elif args.mode == 'sieve':
        run_sieve_only()
    elif args.mode == 'factor':
        run_factor_only()
    elif args.mode == 'search-small':
        run_search_small()
    elif args.mode == 'search-large':
        run_search_large_setup()
    elif args.mode == 'verify':
        if len(args.args) < 4:
            print("Использование: python main.py --mode verify n x d_num d_den")
            sys.exit(1)
        run_verify(int(args.args[0]), int(args.args[1]),
                   int(args.args[2]), int(args.args[3]))


if __name__ == "__main__":
    main()
