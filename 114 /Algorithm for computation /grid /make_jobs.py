#!/usr/bin/env python3
"""Work unit generator for the Charity Engine run.

The search is organised in *digit bands*: band D is the set of targets with a D-digit m
(so n = 3m has D or D+1 digits).  The instruction is to exhaust the 10..20 digit bands
first, then 20..30, and so on, so the generator takes a band range and emits work units
that each fit in one to two hours of single core compute time.

Three kinds of work unit are produced.

  A  dsweep    the d-first sweep: an interval of |U| where U = 2dx^2 is the integer
               certificate of d.  Complete: every solution whose certificate lies in the
               interval is found, whatever the size of (m,u).  Because |n| <= |U| is a
               theorem (`DEquation.abs_n_le_abs_U`), band D needs |U| >= 3*10^(D-1);
               conversely a unit that sweeps |U| < 3*10^D cannot produce more than D+1
               digits.  This is the main "search for d" engine.

  C1 xscan     the per-x scan: a block of u = (x-7)/12 together with a window of m.
               Complete in m inside the window, for the listed x only.

  A' dsmooth   the same d-first sweep restricted to B-smooth certificates U, which can be
               enumerated for U of twenty, thirty or more digits.  Not exhaustive, but the
               only sweep type that reaches the high bands; a unit is one shard of a
               (lo, hi, B) box.

  C2 xcurve    the Mordell-Weil phase: a block of u for which the rational points of
               E_x : V^2 = Z^3 - 432x^3(x^3+57) are computed and amplified.  Unbounded in
               m, and hence the only unit type that can realistically reach twenty digits.

Measured throughputs on one modern core (see grid/README.md):

  dsweep   2.4e9 values of |U| per core-hour at |U| ~ 1e9,
           1.6e9 per core-hour at |U| ~ 1e14   (the rate table below interpolates),
  dsmooth  about 7e5 (U,x) pairs per second, i.e. 2.5e9 pairs per core-hour,
  xscan    5.4e11 values of m per core-hour and per x,
  xcurve   a few seconds to a few minutes per x, strongly dependent on the rank.

Usage
-----
    ./make_jobs.py --band-lo 10 --band-hi 20 --hours 1.5 --out jobs/
    ./make_jobs.py --band-lo 20 --band-hi 30 --hours 1.5 --out jobs/ --max-units 200000

Each line of the manifest is a self contained command; grid/run_task.sh executes one line.
"""
import argparse
import math
import os


def dsweep_rate(U):
    """values of |U| processed per core-hour, measured and interpolated"""
    table = [(1e9, 2.4e9), (1e12, 1.9e9), (1e14, 1.6e9), (1e17, 1.2e9)]
    if U <= table[0][0]:
        return table[0][1]
    for (a, ra), (b, rb) in zip(table, table[1:]):
        if U <= b:
            t = (math.log10(U) - math.log10(a)) / (math.log10(b) - math.log10(a))
            return ra + t * (rb - ra)
    return table[-1][1]


XSCAN_RATE = 5.4e11          # values of m per core-hour, per x
DSWEEP_MAX = 10**18          # implementation limit of dsweep (|U| < 1e18)
XSCAN_MAX = 10**19           # implementation limit of xscan (m < 2^64)


def gen_dsweep(band_lo, band_hi, hours, units, start=None):
    """Sweep |U| from 3*10^(band_lo-1) up to 3*10^band_hi."""
    lo = int(3 * 10 ** (band_lo - 1)) if start is None else start
    hi = min(int(3 * 10**band_hi), DSWEEP_MAX)
    out = []
    if lo >= DSWEEP_MAX:
        return out, lo
    while lo < hi and len(out) < units:
        chunk = int(dsweep_rate(lo) * hours)
        chunk = max(chunk, 10**6)
        nxt = min(lo + chunk, hi)
        out.append(("dsweep", lo, nxt))
        lo = nxt
    return out, lo


def gen_xscan(band_lo, hours, units, u_start=0, u_count=64):
    """Cover the bottom decade of the band for u_count values of u.

    If one value of x needs less than the target time for the whole decade, several
    consecutive x are packed into the same work unit; otherwise the decade is split into
    windows of m, one unit each."""
    m0 = 10 ** (band_lo - 1)
    m1 = 10**band_lo
    win = int(XSCAN_RATE * hours)
    width = m1 - m0
    out = []
    if width <= win:
        per = max(1, win // width)
        u = u_start
        while u < u_start + u_count and len(out) < units:
            out.append(("xscan", u, min(u + per, u_start + u_count), m0, m1))
            u += per
    else:
        for u in range(u_start, u_start + u_count):
            a = m0
            while a < m1 and len(out) < units:
                b = min(a + win, m1)
                out.append(("xscan", u, u + 1, a, b))
                a = b
            if len(out) >= units:
                break
    return out


def gen_dsmooth(band_lo, band_hi, units, B=60, shards_per_box=None):
    """Shards of the box [3*10^(band_lo-1), 3*10^band_hi) of B-smooth certificates."""
    lo = int(3 * 10 ** (band_lo - 1))
    hi = int(3 * 10**band_hi)
    n = units if shards_per_box is None else shards_per_box
    return [("dsmooth", lo, hi, B, i, n) for i in range(n)]


def gen_xcurve(u_start, units, block=64):
    return [("xcurve", u_start + i * block, u_start + (i + 1) * block) for i in range(units)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--band-lo", type=int, default=10, help="first digit count of m")
    ap.add_argument("--band-hi", type=int, default=20, help="last digit count of m")
    ap.add_argument("--hours", type=float, default=1.5, help="target core-hours per work unit")
    ap.add_argument("--max-units", type=int, default=20000)
    ap.add_argument("--xscan-x", type=int, default=64, help="how many values of x for the C1 units")
    ap.add_argument("--xcurve-units", type=int, default=2000)
    ap.add_argument("--dsmooth-units", type=int, default=1000)
    ap.add_argument("--dsmooth-B", type=int, default=60)
    ap.add_argument("--out", default="jobs")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    name = os.path.join(args.out, "band%02d_%02d.manifest" % (args.band_lo, args.band_hi))
    units = []
    a, _ = gen_dsweep(args.band_lo, args.band_hi, args.hours, args.max_units)
    units += a
    if not a:
        print("note: the d-first sweep cannot reach band %d (|n| <= |U| and |U| < 1e18)" % args.band_lo)
    if 10 ** args.band_lo <= XSCAN_MAX:
        units += gen_xscan(args.band_lo, args.hours, args.max_units // 4, u_count=args.xscan_x)
    else:
        print("note: the per-x scan cannot reach band %d (m must fit in 64 bits);"
              " use the xcurve units only" % args.band_lo)
    units += gen_dsmooth(args.band_lo, args.band_hi, args.dsmooth_units, args.dsmooth_B)
    units += gen_xcurve(0, args.xcurve_units)

    with open(name, "w") as f:
        for i, wu in enumerate(units):
            if wu[0] == "dsweep":
                f.write("%06d dsweep --ulo %d --uhi %d\n" % (i, wu[1], wu[2]))
            elif wu[0] == "xscan":
                f.write("%06d xscan --u0 %d --u1 %d --m0 %d --m1 %d\n" % (i, wu[1], wu[2], wu[3], wu[4]))
            elif wu[0] == "dsmooth":
                f.write("%06d dsmooth --lo %d --hi %d --B %d --shard %d --shards %d\n"
                        % (i, wu[1], wu[2], wu[3], wu[4], wu[5]))
            else:
                f.write("%06d xcurve --u0 %d --u1 %d\n" % (i, wu[1], wu[2]))
    print("wrote %s with %d work units (~%.1f core-hours each)" % (name, len(units), args.hours))
    nd = [u for u in units if u[0] == "dsweep"]
    if nd:
        print("  %6d dsweep units  (|U| from %.3g to %.3g, reaching %d digit m)"
              % (len(nd), nd[0][1], nd[-1][2], len(str(nd[-1][2] // 3))))
    print("  %6d xscan units" % sum(1 for u in units if u[0] == "xscan"))
    print("  %6d dsmooth units (B = %d, |U| up to %.3g)"
          % (sum(1 for u in units if u[0] == "dsmooth"), args.dsmooth_B, 3 * 10**args.band_hi))
    print("  %6d xcurve units" % sum(1 for u in units if u[0] == "xcurve"))


if __name__ == "__main__":
    main()
