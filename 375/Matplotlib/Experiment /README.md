# Matplotlib experiments for the 375 equation

The equation studied here is

$$
y^2=1+\frac{36n^3+54n^2+27n-58}{x(6n+3+x)^2},
\qquad n,x\in\mathbb Z,
$$

with `x != 0` and `x != -(6n+3)`. The broader target is an exact integer
cube lift with cube sum 375 and coordinate gcd 1.

## Use the actual projective Elkies method

The current entry point is **[elkies375/elkies375_lab.py](elkies375/elkies375_lab.py)**.
Download the whole `elkies375` directory: the entry point uses its adjacent
Python modules and GMP C++ worker.

Start with the [installation and run instructions](elkies375/README.md).
The package connects a rank-three tangent-tile / LLL / lattice-enumeration
backend to this equation, applies an integer n interval through the
cube-coordinate sum, verifies every point exactly, and records resumable
height/ratio coverage. It also retains a separately named factor-pair engine
for rational-y points whose cube lift is nonintegral.

The [source audit](elkies375/SOURCE_AUDIT.md) compares this implementation with
the user-supplied `Elkies_allg.tar`. The [adaptation proof](elkies375/METHOD.md)
derives the change of variables, modular conditions and finite height bounds.
The [native method proof](elkies375/EJ_METHOD.md) describes the lattice enclosure
and exact enumeration.

## Historical experiments

| Folder | Algorithm originally used | Relationship to the attached algorithm |
|---|---|---|
| [#1](%231/README.md) | Direct integer-y candidates at selected integer n,x | A finite direct scan, without a projective 3D lattice |
| [#2](%232%20/README.md) | Fixed-n tangent strips and a rank-two lattice | A useful local adaptation, but a different search space |
| [#3](%233/README.md) | Exact factor pairs at selected n, with global real-curve geometry | Covers rational-only y at completed n slices; does not use projective 3D LLL |
| [elkies375](elkies375/README.md) | Projective tangent tiles, rank-three LLL, exact lattice enumeration | Implements the defining geometric method and maps its hits to this equation |

The original images and reported historical results remain attached to their
actual algorithms. An attractive curve or a dense set of display slices is
not evidence that every integer n in its displayed interval was searched.

Each historical `Script` accepts an explicit `--engine elkies` route to the
new sibling package. With that option omitted, its existing options and
behavior are preserved.

The repository folder is now spelled **`Matplotlib`**. `Experiment ` retains
its existing trailing space, and `#2 ` also has a trailing space; quote paths
when using a shell.
