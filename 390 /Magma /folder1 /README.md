### English

# Magma Script: Rational Non-Integer `d` for the Equation

## Algebraic Core

After rationalization, the original equation reduces to a quadratic in `d`:

```
4*x^3*d^2 + (4*x^3 + 24*n*x^2)*d - (36*n^3 - 65) = 0
```

For `d` to be rational, the discriminant must be a perfect square, which is equivalent to:

```
y^2 = x^4 + 12*n*x^3 + 36*n^2*x^2 + (36*n^3 - 65)*x
```

This is a **quartic with a rational point** `(0, 0)`, so for each fixed `n`, it is an elliptic curve. The transformation `X = 1/x`, `Y = y/x^2` gives a Weierstrass form, and a shift and scaling give the short Weierstrass form:

```
V^2 = W^3 - 780*n*W + (-3*(12*n^3 - 65)^2 + 16900)
```

## Script Structure

| Phase | Method | Purpose |
|------|-------|------------|
| 1 | Brute force `(n, x)` | Small solutions subject to congruence restrictions |
| 1b | Near-square (`t = y - x*(x + 6*n)`) | Parameterization: `2*t*x^2 + (12*t*n - A)*x + t^2 = 0` |
| 1c | Unrestricted | Reference: found `(n, x) = (-5, 81)`, `d = -5/1458` |
| 2 | `MordellWeilGroup` | For specific values of `n`: rank, generators, multiples |
| 3 | Generic fiber `E/Q(t)` | Elliptic surface — the key to large values of `n` |
| 4 | CRT analysis | Sieving over primes `p` for valid pairs `(n mod p, x mod p)` |
| 5 | Group law | Multiples of the known point `P0` at `n = -5` |
| 6 | Strategy for `10^43` | The height grows as `k^2 * h(P)`; `k ~ sqrt(99/h)` is needed |

## Why `n ~ 10^43`

The only solution found without congruence restrictions is `(n, x) = (-5, 81)`, with `x ≡ 9 (mod 12)` (which does not satisfy the requirement `x ≡ 5`). This means that solutions satisfying the required congruence conditions occur only for very large `|n|` — as multiples of sections on the elliptic surface, whose height grows quadratically with the multiplier. The script sets up precisely this mechanism: `MordellWeilGroup` for the generic fiber → generation of sections → sieving mod 84 → specialization and verification.


### Russian

# Magma Script: Rational Non-Integer `d` for the Equation

## Алгебраическое ядро

Исходное уравнение после рационализации сводится к квадратному относительно `d`:

```
4*x^3*d^2 + (4*x^3 + 24*n*x^2)*d - (36*n^3 - 65) = 0
```

Условие рациональности `d` — дискриминант должен быть полным квадратом, что эквивалентно:

```
y^2 = x^4 + 12*n*x^3 + 36*n^2*x^2 + (36*n^3 - 65)*x
```

Это **квартика с рациональной точкой** `(0, 0)`, значит, для каждого фиксированного `n` это эллиптическая кривая. Преобразование `X = 1/x`, `Y = y/x^2` даёт форму Вейерштрасса, а сдвиг и масштабирование — короткую форму:

```
V^2 = W^3 - 780*n*W + (-3*(12*n^3 - 65)^2 + 16900)
```

## Структура скрипта

| Фаза | Метод | Назначение |
|------|-------|------------|
| 1 | Brute force `(n, x)` | Малые решения с модульными ограничениями |
| 1b | Near-square (`t = y - x*(x + 6*n)`) | Параметризация: `2*t*x^2 + (12*t*n - A)*x + t^2 = 0` |
| 1c | Без ограничений | Референс: найдено `(n, x) = (-5, 81)`, `d = -5/1458` |
| 2 | `MordellWeilGroup` | Для конкретных `n`: ранг, генераторы, кратные |
| 3 | Generic fiber `E/Q(t)` | Эллиптическая поверхность — ключ к большим `n` |
| 4 | CRT-анализ | Ситовanie по простым `p` для валидных пар `(n mod p, x mod p)` |
| 5 | Group law | Кратные известной точки `P0` при `n = -5` |
| 6 | Стратегия для `10^43` | Высота растёт как `k^2 * h(P)`, нужно `k ~ sqrt(99/h)` |

## Почему `n ~ 10^43`

Единственное найденное решение без модульных ограничений — `(n, x) = (-5, 81)` с `x ≡ 9 (mod 12)` (не удовлетворяет требованию `x ≡ 5`). Это означает, что решения с правильными модульными условиями возникают только при очень больших `|n|` — как кратные секций на эллиптической поверхности, высота которых растёт квадратично с номером кратного. Скрипт настраивает именно этот механизм: `MordellWeilGroup` для generic fiber → генерация секций → ситование mod 84 → специализация и проверка.
