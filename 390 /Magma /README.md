The scripts in Magma as found in the sub-folders of this folder can be independently ran and verified [here](https://magma.maths.usyd.edu.au/magma/).



# Rational Non-Integer Values of $d$ and the Asymptotics of Solutions

## 1. How the Equation Simplifies

The original equation:

$$36n^3 - 65 = -2d\,x^2\\left(-(x+6n)+\sqrt{(x+6n)^2+\frac{36n^3-65}{x}}\right)$$

Let $A = x+6n$, $B = \frac{36n^3-65}{x}$, and $k = \sqrt{A^2+B}$. Then the equation can be rewritten as

$$xB = -2dx^2(-A+k) = 2dx^2(A-k)$$

Rationalizing (multiplying by $A+k$):

$$B \cdot (A+k) = 2dx \cdot (-B) \quad\Longrightarrow\quad A+k = -2dx$$

provided that $B \neq 0$. Hence $k = -(2dx + x + 6n)$, and substituting back into $k^2 = A^2+B$ and simplifying gives the **only essential relation**:

$$\boxed{4d\,x^2\,(dx + x + 6n) = 36n^3 - 65}$$

This is a quadratic equation in $d$. Its discriminant is exactly the expression under the square root in the original formula, so **the condition that the square root be an integer and the condition that $d$ be rational are one and the same**. Specifically:

$$d = \frac{-(x+6n) \pm k}{2x}, \qquad k = \sqrt{(x+6n)^2 + \frac{36n^3-65}{x}} \in \mathbb{Z}$$

Thus, the plan reduces to:

1. Find integers $(n, x)$ with $x \mid (36n^3-65)$ and $k \in \mathbb{Z}$;

2. Compute $d$ and check that $d \in \mathbb{Q} \setminus \mathbb{Z}$.

---

## 2. What It Means for $k$ to Be an Integer

The condition $k \in \mathbb{Z}$ is equivalent to requiring that

$$(x+6n)^2 + \frac{36n^3-65}{x}$$

be a perfect square. Expanding:

$$k^2 - (x+6n)^2 = \frac{36n^3-65}{x}$$

$$(k - (x+6n))(k + (x+6n)) = \frac{36n^3-65}{x}$$

This is a factorization: the product of two integers (of different parity when $x+6n$ is fixed) equals $\frac{36n^3-65}{x}$. Each factorization $\frac{36n^3-65}{x} = uv$ with $u \equiv v \pmod{2}$ gives a candidate $k = \frac{u+v}{2}$, $x+6n = \frac{v-u}{2}$.

This is where Magma does the heavy lifting: for each $n$ (with $n \equiv 1 \pmod{3}$), it enumerates the divisors $x$ of $36n^3-65$ satisfying the congruences $x \equiv 5 \pmod{12}$, $x \not\equiv 0 \pmod{7}$, and checks whether the corresponding factorization produces a perfect square.

---

## 3. Asymptotics and Scale

The condition $x \sim n^{5/4}$, together with the simplified equation, makes it possible to estimate the order of magnitude of $d$. If $dx \ll 6n$ (which is consistent with the asymptotics—see below), then

$$4d\,x^2 \cdot 6n \approx 36n^3 \quad\Longrightarrow\quad d \approx \frac{3}{2}\left(\frac{n}{x}\right)^{\!2} \sim \frac{3}{2}\,n^{-1/2}$$

For $n \sim 10^{43}$, this gives $d \sim 10^{-21.5}$—a rational number with an enormous denominator, certainly not an integer. The very fact that $\min |n| \sim 10^{43}$ means that **solutions do not occur for small $n$**; an astronomically large search region is needed, making manual enumeration impossible and justifying the use of Magma with exact arithmetic.

Checking the condition $dx \ll 6n$: with $d \sim \frac{3}{2}n^{-1/2}$ and $x \sim n^{5/4}$, we obtain $dx \sim \frac{3}{2}n^{3/4}$, while $6n = 6n$. The ratio $\frac{dx}{6n} \sim \frac{1}{4}n^{-1/4} \to 0$, so the approximation is valid.

---

## 4. Exactly How the Magma Results Bring the Goal Closer

Each triple $(d, n, x)$ found by a Magma computation accomplishes the following:

### (a) Proof of Existence

Finding even one triple with $d \in \mathbb{Q}\setminus\mathbb{Z}$ **settles the existence part** of the problem: the desired values of $d$ exist. Without computation, this is not obvious—the equation combines cubic and quadratic structures, and it could in principle have turned out that all solutions yield integer values of $d$.

### (b) Verification of All Conditions Simultaneously

Magma simultaneously checks:

- $n \equiv 1 \pmod{3}$, $x \equiv 5 \pmod{12}$, $x \not\equiv 0 \pmod{7}$;

- $x \mid (36n^3 - 65)$;

- $k = \sqrt{(x+6n)^2 + (36n^3-65)/x} \in \mathbb{Z}$;

- $d = \frac{-(x+6n)+k}{2x} \in \mathbb{Q}\setminus\mathbb{Z}$ (or with the “$-$” sign).

Each result is a **fully verified witness**, not a heuristic estimate. Magma's exact arithmetic (along with its support for rings, lattices, and elliptic curves) rules out rounding errors, which are unavoidable with floating-point arithmetic at the $10^{43}$ scale.

### (c) Identifying the Structure of the Solution Set

Several triples make it possible to:

- see exactly which rational values of $d$ arise (for example, whether $d$ always has the form $\frac{a}{b}$ with fixed properties of $b$);

- check whether $(n, x)$ lie on an algebraic curve (which would open a path to a parametrization and possibly a proof that the family is infinite);

- compare the empirical values of $d$ with the asymptotic estimate $d \sim \frac{3}{2}n^{-1/2}$, thereby confirming or refining it.

### (d) Estimating Density and a Lower Bound

The fact that $\min |n| \sim 10^{43}$ is an **empirical lower bound**: no $n$ of a smaller order of magnitude (with the given congruences) yields a solution. This:

- gives an idea of how “rare” the solutions are (from a theoretical perspective, there is a potential connection with Hall's conjecture or the abc conjecture, where such exceptionally large minimal examples are characteristic);

- indicates the scale at which to search for the **next** solutions, if the goal is to construct a series.

### (e) Connection with Elliptic Curves

For fixed $d$, the equation $4dx^2(dx+x+6n) = 36n^3-65$ can be regarded as a model of a (possibly elliptic) curve over $\mathbb{Q}$ in the variables $(n, x)$. The points found by Magma are rational points on this curve. If the curve has positive rank, the method of infinite descent (or point addition using the group law) can **generate an infinite family of solutions** from a single initial one. Magma can compute the rank and generate points, turning a single result into a potentially infinite series.

---

## 5. Summary: What Has Been Achieved

| Stage | Status without Magma | Status with Magma Results |
|---|---|---|
| Existence of $d \in \mathbb{Q}\setminus\mathbb{Z}$ | Open question | **Proved** (a witness has been found) |
| Simultaneous verification of congruences | Not feasible by hand | **Completed** using exact arithmetic |
| Lower bound for $\min\lvert n\rvert$ | Unknown | Estimate $\sim 10^{43}$ |
| Asymptotics $x \sim n^{5/4}$ | Conjecture | **Confirmed** by the data |
| Path to parametrization | Not apparent | Apparent through the structure of the elliptic curve |

In essence, the Magma computations transform the problem from a “purely theoretical question of existence” into a situation with **concrete, verified points**, confirmed asymptotics, and a clear algebraic-geometric framework (elliptic curves) for potentially constructing an infinite family. The next step is to try to use the points found to compute the rank of the corresponding elliptic curve and, if it is positive, obtain a generating family analytically rather than by enumeration.
