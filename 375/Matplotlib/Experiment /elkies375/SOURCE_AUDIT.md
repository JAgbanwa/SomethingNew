# Attached Elkies package and the current Matplotlib experiments

## Finding

The attachment is the **2007 Elsenhans–Jahnel implementation of Elkies' geometric method**, not a Sander Huisman source file and not a factorization-based solver. Its files identify Andreas-Stephan Elsenhans and Jörg Jahnel as authors, date the documentation 2007-12-03, and use GPL version 2 or later. It is the algorithmic family the user intended.

The existing Matplotlib experiments do not all implement that algorithm:

| Existing file | Actual method | Relationship to attachment |
|---|---|---|
| `375/Matplotlib/Experiment /#1/Script` | Enumerates a finite set of integer `(n,x)` pairs and checks adjacent integer values of `y` | Educational integer-y explorer; no lattice reduction and not all rational y |
| `375/Matplotlib/Experiment /#2 /Script` | Exact 2D Gauss reduction of tangent strips in the integer `(x,t)` lattice for selected fixed n and finite x windows | Genuine slice-wise adaptation of the geometric idea, but not the attached rank-three projective search |
| `375/Matplotlib/Experiment /#3/Script` | Factorization of `N(n)` and finite squarefree/factor-pair enumeration at selected n | Exact and useful, including rational-only y, but a different algorithm |
| `375/Algorithm II/ej_worker.cpp` | Rational tangent enclosures, rank-three LLL, exact lattice enumeration in height/ratio tiles, cubic finite differences/root isolation | Already provides the genuine algorithmic structure needed for the requested improvement |

The headers of #2 and #3 already distinguish their methods accurately. The required improvement is to connect the existing genuine 3D backend to this equation and its visualizations, while retaining the separate rational-only solver.

## What the attachment actually does

The historical program considers positive magnitudes `(a,b,c)` with near-cancellation

`a^3 + b^3 - c^3 = +/-k`.

After normalizing by c, its points lie close to the real curve

`v = (1-u^3)^(1/3)`, where `u=a/c`, `v=b/c`.

It covers the curve with thin tangent parallelograms. A tile imposes three small linear forms on the integer triple `(a,b,c)`:

- a coordinate-height restriction on c;
- a ratio restriction on `a-u0*c`;
- a tangent-strip restriction on `b-A*a-B*c`.

It reduces the resulting rank-three lattice using LLL and enumerates lattice points in a pyramid determined by the tile. Cubic finite differences speed the residual test. The crucial difference from a fixed-n strip search is that the denominator c varies as part of the same lattice problem.

Source pointers in the attachment:

- `elkies_allg.doc`, sections describing `Fliese`, the three linear forms, and LLL (roughly lines 40–125).
- `elkies_allg.c`: `berechne_fliesenformat`, `berechne_drei_linearf`, `lll`, `kleine_vect`, `XY_SCHLEIFE`, and `rechne_intervall`.
- `elkies_allg_init.c`: high-precision initialization and `lll_mpf`.

## Why changing the old numerical constants is insufficient

The historical source has explicit machine-specific assumptions:

- `long int` must be 64 bits.
- `festkomma.h` contains x86-64 assembly instructions such as `mulq` and `addq`.
- Integer lattice coordinates and transformations use signed machine longs.
- The curve arithmetic uses 128-bit fixed point and GMP floating initialization; ordinary LLL and geometric enumeration use doubles.
- Cubic residual screening is performed modulo `2^64`.
- The supplied Makefile assumes a historical Linux static-GMP arrangement under `/usr/lib64`.

The literal integer `10^20` already exceeds signed 64-bit range. Therefore simply raising `SUCHWEITE` cannot safely extend this executable to the requested magnitudes, and its Makefile/assembly are unsuitable as a generic Apple Silicon build.

A modern adapter must perform final cube and original-equation checks with arbitrary-precision integers and exact fractions. Exact acceptance eliminates false positives; certified tile enclosure and inclusive enumeration bounds are separately required to avoid missed candidates. Those are distinct responsibilities.

The existing `ej_worker.cpp` implements these improvements with GMP integer/rational arithmetic, exact unimodular LLL transformations, rational tangent enclosures, and exact translated-ball enumeration. It is a suitable base and makes no claim to reproduce the historical optimized program's speed.

One historical CLI detail also matters if documenting the attachment: its `main` parses the first argument as the start and the second as the interval **length**, then adds them. The informal usage prose calls the second value an endpoint; the code governs actual behavior.

## Exact bridge to the user's equation

Let

`S=6n+3`, `T=S+x`, `N=(S^3-375)/6`, and `t=y*T`.

Then

`(A,B,C)=(-x-t,-x+t,S+2x)`

satisfies

`A^3+B^3+C^3 = 375 - 6*[x*(t^2-T^2)-N]`.

Conversely, from a signed integer triple `(A,B,C)` with cube sum 375, choose any pair A,B with the same parity and set

- `n=(A+B+C-3)/6`;
- `x=-(A+B)/2`;
- `t=(B-A)/2`;
- `y=t/(6n+3+x)`.

An implementation must check n and x integrality, the requested n interval, the excluded poles `x=0` and `6n+3+x=0`, the exact original equation, and primitive gcd. It must consider **all parity-compatible choices of the distinguished coordinate C**, then deduplicate equivalent `+/-y` pairs. Taking only the first native ordering can miss valid integer-x parameterizations.

For cube sum 375, cubes modulo 9 force every signed cube coordinate to be `-1 mod3`. The coordinate sum is also odd, so it is `3 mod6`. At least two of three integer coordinates have the same parity. Thus the pullback is natural and covers every primitive integer cube triple admitted by the native coordinate region, subject to the equation's explicit domain and the selected n interval.

The adapter must not reuse Algorithm II's unrelated additional odd/coprime X,Y and principal-square-root requirements. Those belong to another parameterization. Reuse the validated `iter_shell` cube stream, then apply this equation's own verifier.

## Rational-only points remain a different target

Integer native cube triples correspond to integer t and rational y. They do **not** exhaust all rational y with integer n,x: t can itself be nonintegral.

The general exact rational test is

`r^2 = x^2*(S+x)^2+x*N`, with `|y|=r/|x*(S+x)|`.

For example, the existing rational-only control `n=13,x=-144,|y|=695/756` has nonintegral t. An integer-cube backend should not report having searched or excluded that class of points.

The resulting architecture keeps separate targets:

1. A genuine 3D Elkies/EJ mode for primitive/integer cube lifts, with equation-specific rational-y pullback and exact green/orange markers.
2. The existing all-x factor-pair mode for all rational y at selected n, with its independent complete/partial slice records.

Combining their visualizations must preserve their different coverage meanings.

## Height and n are different bounds

The native height is `c=max(|A|,|B|,|C|)`. The equation's parameter instead satisfies `A+B+C=6n+3`. A searched height shell or a ratio band is not a searched full n interval, and drawing a real curve for an n value is not evidence of any exact arithmetic coverage for that slice.

For positive n, a finite all-hit height envelope can be derived without factoring N. At height at least 25, the relevant canonical sign form is `(a,b,-c)` with `0<a<=b<c` and `S=a+b-c>0`; the separate canonical-sign proof in `EJ_METHOD.md` accounts for the other sign patterns at smaller height. Put `u=c-a` and `v=c-b`. The cube residues force `u=v=2 mod3`, so both are at least 2. The exact identity is

`S^3-375 = 3*u*v*(2*S+u+v)`.

Since `u*v >= 2*(u+v-2)` and `c=S+u+v`, this implies

`(c-1)^2 <= (S+1)^2 + (S^3-375)/6`.

Therefore the integer upper bound used in `region.py` is

`c <= 1 + isqrt((S+1)^2 + (S^3-375)//6)`,

rounded down to `c=1 mod3`. This is sharper than the weaker height envelope that only used a positive gap `c-b>=1`. Evaluate it at `S=6*n_max+3` to enclose the whole requested positive n interval.

For the lower bound, `u,v>=2` first gives `c>=S+4`. The implemented planner sharpens this using

`(S+c)^3 <= 4*(c^3+375)`,

which follows from `a^3+b^3 >= (a+b)^3/4`. Its left side minus right side decreases for `c>=S`; an exact integer bisection finds the first possible c, then rounds upward to `c=1 mod3`. Evaluate it at the requested minimum S. For `n=2`, this correctly starts the canonical mixed-sign region at `c=25`.

For the interval `10^17 <= n <= 10^20`, the resulting upper height is approximately `6*10^30`, not `10^20`. An n bound is a bound on the coordinate sum and does not impose the same bound on the largest coordinate. The derived finite envelope is a **search plan**, not a claim that such a search can be completed on a laptop. Small heights below 25 are checked separately when relevant. At those heights `|A+B+C|<=72`, so they cannot contribute to the requested very large positive n interval.

The planner also intersects each height shell with outward-rounded ratio bounds from the requested sum interval. This narrows the plan without assuming that a sampled n curve represents a completed search. Native work is paged lazily; even a complete list of planned bands would not be evidence that those bands were searched.

The necessary integer-cube modular conditions are:

`n mod27 in {2,5,14,20,23}`, `x mod3=1`, `t mod3=0`.

These conditions concern integer cube lifts, not rational-only points. They can reject mapped candidates or help plan admissible slices, but do not make an enormous remaining interval computationally complete.

## Required coverage and tests

Native coverage records should retain exact height shell, ratio index interval, completed tile boundary, source/version, primitive-selection flag, and terminal status. An interrupted worker, output error, missing EOF/end record, or tile budget must not become completed coverage. The existing strict Python interface already provides most of this behavior.

A useful coverage plot has height/ratio axes and distinguishes finished tile regions from assigned but unfinished regions. The equation plot can separately show selected n-slice geometry and verified mapped points. A green star is justified only by the exact original equation, integer cube coordinates, cube sum 375, and gcd 1.

Focused controls should include:

- Native `K=375,H=25` with nonprimitive hits enabled, recovering `(20,20,-25)` and its valid `(n,x,y)=(2,-20,0)` pullback.
- The small-height `(5,5,5)` control, demonstrating why the height-25 backend alone cannot certify every n=2 point.
- The rational-only n=13 control in the separate factor-pair mode.
- All parity-compatible coordinate choices, duplicate coordinates, both signs of y, and exact pole handling.
- Existing small-shell brute-force comparisons for the 3D backend, including targets with known primitive hits.
- Completed-tile resume and strict rejection of missing or malformed terminal output.
- A bounded large-integer run proving arithmetic and visualization stability without calling its n interval exhaustive.

## New implementation and visualization contract

The `elkies375` directory supplies the modern 3D path: `region.py` proves and plans the native region, `ej_worker.cpp` performs the integer-lattice search, `ej_backend.py` checks its output protocol, `equation.py` independently verifies the rational-y pullback, and `campaign.py` records resumable work. This is a modern exact implementation of the attached algorithmic structure, not a verbatim port or a claim to reproduce the historical program's speed.

`plotting.py` reads those saved records without launching another search. It draws three distinct views:

- A selected exact integer n, both signs of its real y branches, and independently rechecked exact points. An optional exact integer-x check can identify rational-only points, but changes no native coverage record.
- Every requested geometry sample, plus every hit n, in a 3D view. These are explicitly labeled real geometry rather than independently searched full n slices. Geometry samples are not silently capped at 1,000 or rounded through machine floats.
- The native height/ratio plan and completed ratio intervals, with an exact integer-offset zoom for saved tasks. A tiny completed band does not color a whole height shell as complete. A failed continuation does not advance coverage; any previously validated completed prefix remains visible.

One canonical cube triple can produce several equation parameterizations. The figures therefore distinguish mapped cube triples from `(n,x,|y|)` representation counts. Green stars require a recomputed zero original-equation residual, integral cube coordinates, exact cube sum 375, and gcd 1. Orange circles mark exact nonprimitive cube lifts. Purple diamonds are exact rational-only points from an explicitly labeled manual check. There are no invented approximate-candidate dots.

A static PNG has finite resolution. The native worker ranges over all integer coordinates inside completed tiles, while the equation curves remain a finite visual sampling. Arbitrary n and x can be entered exactly in the interactive viewer; this one-point facility is not a global all-rational-y search.
