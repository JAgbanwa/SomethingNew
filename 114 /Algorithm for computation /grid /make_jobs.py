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

Half chart (x = X/2, X odd) and integral radicals
-------------------------------------------------
    ./make_jobs.py --chart half ...          the same plan in the half chart: dsweep/dsmooth
                                             with --half --rational-sqrt, xscan --half,
                                             xcurve --half
    ./make_jobs.py --target integral --n-lo 1.667e18 --n-hi 1.667e19 --x-max 1e6 --out jobs/
                                             xroots units (both charts) that exhaust every
                                             solution with an INTEGRAL radical, i.e. every
                                             114 = A^3+B^3+C^3, with |X| < x-max and
                                             n-lo <= |n| < n-hi (both signs of n and X)

For the integral target the default n range starts where the Booker-Sutherland searches stop
for small |X|: they cover every triple with min(|A|,|B|,|C|) <= 10^17 and every triple with a
pair sum |A+B| <= 1.85e17 and third cube |C| <= 10^19; in the coordinates of the equation
|A+B| = |X| (half chart) or 2|x| (integer chart) and C = X + 6n resp. 2x + 6n, so for small
|X| the uncovered region begins at |n| = 10^19/6 = 1.667e18 (see HALF_INTEGER.md §5).
The xroots cost model below was measured on one core of the machine used for this session;
run one pilot unit on the grid hardware and rescale (each output ends with secs=...).
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


# xroots: seconds ~ KAPPA * W * ln(X1/X0)  +  PI * (number of progressions),
# progressions ~ NU * (X1 - X0) * min(1, W / (486 X0)); measured at n ~ 2e18 (one core).
XR_KAPPA = {"half": 7.5e-11, "int": 7e-12}
XR_PI = {"half": 3e-6, "int": 4e-7}
XR_NU = {"half": 7.6, "int": 17.9}


def xroots_seconds(chart, x0, x1, w):
    x0 = max(x0, 1)
    prog = XR_NU[chart] * (x1 - x0) * min(1.0, w / (486.0 * x0))
    return XR_KAPPA[chart] * w * math.log(x1 / x0) + XR_PI[chart] * prog


def gen_xroots(chart, x_max, n_lo, n_hi, hours, epochs=100):
    """Tile {1 <= |X| < x_max} x {n_lo <= |n| < n_hi} (both signs of n) into units of about
    `hours` core-hours.  The n range is cut into `epochs` consecutive slices; inside a slice
    every decade of |X| (split further when one decade alone is too long) gets windows of n
    of the width that fits the time budget.  Units are listed slice by slice, so running a
    prefix of the manifest exhausts a complete region { all |X| < x_max } x { slices done }."""
    target = hours * 3600.0
    bands = []
    a = 1
    while a < x_max:
        b = min(a * 10, x_max)
        bands.append((a, b))
        a = b
    pieces = []
    for a, b in bands:
        # split the band until its fixed (per-progression) cost uses at most half the budget
        ps = [(a, b)]
        while max(XR_PI[chart] * XR_NU[chart] * (q - p) for p, q in ps) > target / 2 and len(ps) < 10**6:
            ps = [h for p, q in ps for h in ((p, (p + q) // 2), ((p + q) // 2, q)) if h[0] < h[1]]
        pieces += ps
    width = []
    for p, q in pieces:
        fixed = XR_PI[chart] * XR_NU[chart] * (q - p)
        per_w = XR_KAPPA[chart] * math.log(q / p)
        width.append(int(max((target - fixed) / per_w, 1e6)) if per_w > 0 else n_hi - n_lo)
    out = []
    total = 0.0
    step = -(-(n_hi - n_lo) // epochs)
    for e in range(epochs):
        e0, e1 = n_lo + e * step, min(n_lo + (e + 1) * step, n_hi)
        if e0 >= e1:
            break
        for (p, q), w in zip(pieces, width):
            for sign in (1, -1):
                lo = e0
                while lo < e1:
                    hi = min(lo + w, e1)
                    total += xroots_seconds(chart, p, q, hi - lo)
                    out.append((e, ("xroots", chart, p, q, lo, hi) if sign > 0
                                else ("xroots", chart, p, q, -hi, -lo)))
                    lo = hi
    return out, total / 3600.0


def fmt_unit(i, wu):
    kind = wu[0]
    if kind == "dsweep":
        return "%06d dsweep --ulo %d --uhi %d%s" % (i, wu[1], wu[2], wu[3])
    if kind == "xscan":
        return "%06d xscan --u0 %d --u1 %d --m0 %d --m1 %d%s" % (i, wu[1], wu[2], wu[3], wu[4], wu[5])
    if kind == "dsmooth":
        return "%06d dsmooth --lo %d --hi %d --B %d --shard %d --shards %d%s" % (i, wu[1], wu[2], wu[3], wu[4], wu[5], wu[6])
    if kind == "xcurve":
        return "%06d xcurve --u0 %d --u1 %d%s" % (i, wu[1], wu[2], wu[3])
    if kind == "xroots":
        return "%06d xroots%s --X0 %d --X1 %d --n0 %d --n1 %d" % (
            i, " --half" if wu[1] == "half" else "", wu[2], wu[3], wu[4], wu[5])
    raise ValueError(kind)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["rational", "integral"], default="rational",
                    help="rational: Aristotle's plan (any rational radical); integral: the radical "
                         "is integral (y integer, or y = Y/2 with Y odd), i.e. 114 = A^3+B^3+C^3")
    ap.add_argument("--chart", choices=["int", "half", "both"], default=None,
                    help="integer chart (x integer), half chart (x = X/2, X odd) or both; default: "
                         "int for --target rational, both for --target integral")
    ap.add_argument("--band-lo", type=int, default=10, help="first digit count of m")
    ap.add_argument("--band-hi", type=int, default=20, help="last digit count of m")
    ap.add_argument("--hours", type=float, default=1.5, help="target core-hours per work unit")
    ap.add_argument("--max-units", type=int, default=20000)
    ap.add_argument("--xscan-x", type=int, default=64, help="how many values of x for the C1 units")
    ap.add_argument("--signs", choices=["pos", "all"], default="all",
                    help="xscan: x > 0 and n >= 0 only (the original plan), or all four sign combinations")
    ap.add_argument("--xcurve-units", type=int, default=2000)
    ap.add_argument("--dsmooth-units", type=int, default=1000)
    ap.add_argument("--dsmooth-B", type=int, default=60)
    ap.add_argument("--x-max", type=float, default=1e6, help="integral target: |X| < x-max")
    ap.add_argument("--n-lo", type=float, default=1.667e18, help="integral target: n-lo <= |n|")
    ap.add_argument("--n-hi", type=float, default=1.667e19, help="integral target: |n| < n-hi")
    ap.add_argument("--epochs", type=int, default=1000, help="integral target: slices of the n range")
    ap.add_argument("--out", default="jobs")
    args = ap.parse_args()
    chart = args.chart or ("both" if args.target == "integral" else "int")
    charts = ["int", "half"] if chart == "both" else [chart]

    os.makedirs(args.out, exist_ok=True)
    units = []
    if args.target == "integral":
        name = os.path.join(args.out, "integral_%s.manifest" % chart)
        est = 0.0
        per_chart = []
        for ch in charts:
            u, hrs = gen_xroots(ch, int(args.x_max), int(args.n_lo), int(args.n_hi), args.hours,
                                args.epochs)
            per_chart.append(u)
            est += hrs
            print("  %-4s chart: %d xroots units in total, about %.3g core-hours for the whole region"
                  % (ch, len(u), hrs))
        # merge the charts epoch by epoch (a stable sort keeps each chart's order inside an epoch)
        merged = [w for e, w in sorted((ew for lst in per_chart for ew in lst), key=lambda ew: ew[0])]
        units = merged[:args.max_units]
        with open(name, "w") as f:
            for i, wu in enumerate(units):
                f.write(fmt_unit(i, wu) + "\n")
        print("wrote %s with %d work units (whole region: about %.3g core-hours%s)"
              % (name, len(units), est,
                 "; truncated at --max-units, a prefix of the n range" if len(merged) > len(units) else ""))
        return

    name = os.path.join(args.out, "band%02d_%02d%s.manifest"
                        % (args.band_lo, args.band_hi, "" if chart == "int" else "_" + chart))
    for ch in charts:
        half = ch == "half"
        a, _ = gen_dsweep(args.band_lo, args.band_hi, args.hours, args.max_units)
        units += [w + ((" --half --rational-sqrt" if half else ""),) for w in a]
        if not a:
            print("note: the d-first sweep cannot reach band %d (|n| <= |G| and |G| < 1e18)" % args.band_lo)
        if 10 ** args.band_lo <= XSCAN_MAX:
            xs = gen_xscan(args.band_lo, args.hours, args.max_units // 4, u_count=args.xscan_x)
            sgn = [""] if args.signs == "pos" else ["", " --xneg", " --nneg", " --xneg --nneg"]
            for w in xs:
                for sg in sgn:
                    units.append(w + ((" --half" if half else "") + sg,))
        else:
            print("note: the per-x scan cannot reach band %d (m must fit in 64 bits);"
                  " use the xcurve units only" % args.band_lo)
        units += [w + ((" --half --rational-sqrt" if half else ""),)
                  for w in gen_dsmooth(args.band_lo, args.band_hi, args.dsmooth_units, args.dsmooth_B)]
        units += [w + ((" --half" if half else ""),) for w in gen_xcurve(0, args.xcurve_units)]

    with open(name, "w") as f:
        for i, wu in enumerate(units):
            f.write(fmt_unit(i, wu) + "\n")
    print("wrote %s with %d work units (~%.1f core-hours each)" % (name, len(units), args.hours))
    nd = [u for u in units if u[0] == "dsweep"]
    if nd:
        print("  %6d dsweep units  (|G| from %.3g to %.3g, reaching %d digit m)"
              % (len(nd), nd[0][1], nd[-1][2], len(str(nd[-1][2] // 3))))
    print("  %6d xscan units" % sum(1 for u in units if u[0] == "xscan"))
    print("  %6d dsmooth units (B = %d, |G| up to %.3g)"
          % (sum(1 for u in units if u[0] == "dsmooth"), args.dsmooth_B, 3 * 10**args.band_hi))
    print("  %6d xcurve units" % sum(1 for u in units if u[0] == "xcurve"))


if __name__ == "__main__":
    main()
