# Sources and provenance

This directory is an implementation for JAgbanwa/SomethingNew's original
375 equation, with the agreed `+3` correction in the signed rational parameter.

## Existing repository code

The native lattice mathematics in `ej_worker.cpp` is copied from

```text
375/Scripts for large-scale computations/elkies-jahnel/src/elkies375_worker.cpp
```

at repository commit
`857adf3f89831816461641d6d4f7bbf89783304f` (source blob
`052f359cde85fc1c6c6e88ab67ee5e6fa3afc677`). The native code's only changes are
the provenance header and version label. Its exact rational geometry, LLL,
enumeration and polynomial-root shortcut are retained.

`tests/test_ej_math.py` is adapted from that same commit's
`375/Scripts for large-scale computations/elkies-jahnel/tests/test_math.py`.
Paths and test build locations refer to this self-contained folder.

The new Python interface adds independent validation of the native protocol.
The new Booker backend follows the gap/root/square architecture and the
non-cube-free prime-power reasoning also described in this repository's
`375/gap-search/`. It does not import or replace that existing native worker.
The CLI, strict equation verifier, direct-d search and additional tests are new.
The repository's existing files are preserved.

## Mathematical papers

* Andrew R. Booker, *Cracking the problem with 33*:
  <https://arxiv.org/abs/1903.04284>.
* Andrew R. Booker and Andrew V. Sutherland, *On a question of Mordell*:
  <https://arxiv.org/abs/2007.01209>.
* Noam D. Elkies, *Rational points near curves and small nonzero
  |x^3-y^2| via lattice reduction*:
  <https://arxiv.org/abs/math/0005139>.
* Andreas-Stephan Elsenhans and Jörg Jahnel, *New sums of three cubes*:
  <https://wwwuser.gwdguser.de/~jjahnel/Arbeiten/elk_ants6c.pdf>.
* Booker–Sutherland authors' implementation:
  <https://github.com/AndrewVSutherland/SumsOfThreeCubes>.

The algorithm names identify the mathematical methods. These implementations
are reference adaptations for the stated equation; they are not releases of
the papers' authors' own executables and do not claim equivalent throughput.
