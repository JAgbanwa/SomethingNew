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

The Python interface adds independent validation of the native protocol.
The portable Python Booker backend follows the gap/root/square architecture and the
non-cube-free prime-power reasoning also described in this repository's
`375/gap-search/`. It does not import or replace that existing native worker.
The CLI, strict equation verifier, direct-d search and additional tests are new.
The repository's existing files are preserved.

Version 1.1 also adds `bs_worker.cpp`, adapted from
`375/gap-search/src/gap_worker.cpp` at the same repository commit
`857adf3f89831816461641d6d4f7bbf89783304f` (upstream worker version 1.2.0).
It retains the complete prime-power roots, segmented/bucket factorization,
CRT, batched residue sieving and GMP exact reconstruction. The adaptation
adds explicit strict primitive output, wider checked counters, safe native
signal/deadline checkpoints, provenance and a distinct version identifier.
`booker_native.py` independently validates every native record and the
completed-prefix contract. Details are in `BS_NATIVE_METHOD.md`.

`campaign375.py`, its tests, the finite calibration driver and large campaign
manifest are new. They call only the self-contained files in this directory.
No sibling code or prior campaign state is changed. The sample measurements
are bounded local executions, not submissions to an external compute service.

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
