"""Matplotlib geometry, exact-point inspection, and genuine EJ coverage.

The real curves are display-only. Native coverage is a separate height/ratio
region; a curve drawn at n never means that every integer x at n was searched.
Large integers remain exact until their final bounded drawing coordinates.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
import json
import math
from pathlib import Path

from equation import check_point, integer, rational_point_at

BLUE = "#357fba"
PALE = "#dce7f0"
AMBER = "#d99b2b"
GREEN = "#07812d"
ORANGE = "#e87b12"
PURPLE = "#7b35c9"
GREY = "#c5ccd3"
RED = "#b64c49"
INK = "#213549"


def compact(value: Fraction | int) -> float:
    """Bound a rational coordinate before any conversion to float."""
    q = Fraction(value)
    sign = -1.0 if q < 0 else 1.0
    q = abs(q)
    if q > 1:
        return sign * (1.0 - 2.0 / math.pi * math.atan(float(1 / q)))
    return sign * 2.0 / math.pi * math.atan(float(q))


def geometry_values(low: int, high: int, count: int) -> list[int]:
    """Exact integer-rounded logarithmic anchors; never silently thin samples."""
    low, high, count = integer(low), integer(high), integer(count)
    if low > high or count < 1:
        raise ValueError("need an ordered n interval and positive geometry_slices")
    count = min(count, high-low+1)
    if count == 1:
        return [low]
    if low <= 0 or high-low+1 == count:
        return sorted({low+(high-low)*i//(count-1) for i in range(count)})
    exponent = count-1
    found = []
    with localcontext() as context:
        context.prec = max(80, len(str(abs(high)))+40)
        log_low, log_high = Decimal(low).ln(), Decimal(high).ln()
        for i in range(count):
            if i == 0:
                result = low
            elif i == exponent:
                result = high
            else:
                result = int(((log_low*(exponent-i)+log_high*i)/exponent).exp())
                target = low**(exponent-i)*high**i
                while result**exponent > target:
                    result -= 1
                while (result+1)**exponent <= target:
                    result += 1
            found.append(result)
    # Small intervals can have repeated rounded logarithmic anchors. Fill with
    # exact linear anchors and then unused integers to honor the requested count.
    values = set(found)
    values.update(low+(high-low)*i//exponent for i in range(count) if len(values) < count)
    if len(values) < count:
        value = low
        while len(values) < count:
            values.add(value)
            value += 1
    return sorted(values)


def _bisect(function, low: float, high: float) -> float:
    left = function(low)
    for _ in range(70):
        middle = (low+high)/2
        value = function(middle)
        if value == 0:
            return middle
        if (value > 0) == (left > 0):
            low, left = middle, value
        else:
            high = middle
    return (low+high)/2


def real_geometry(n: int, points: int = 160) -> list[tuple]:
    """Display-only compactified real branches, including the n=2 isolated point.

    Return (q,v) arrays, q=(2/pi)atan(x/(6n+3)), v=(2/pi)atan(y).
    Limits at infinity and poles are drawing endpoints, never exact hits.
    """
    import numpy as np
    n = integer(n)
    if points < 16:
        raise ValueError("at least 16 drawing points are required")
    S = 6*n+3
    coefficient = float(Fraction(S**3-375, 6*S**3))
    intervals = []
    isolated = []
    if coefficient > 0:
        right = 2.0
        while right*(right-1)**2 < coefficient:
            right *= 2
        outer = -_bisect(lambda w: w*(w-1)**2-coefficient, 1.0, right)
        intervals.extend([(-1.0, compact(Fraction(outer)), 1.0, 0.0),
                          (0.0, 1.0, math.inf, 1.0)])
        if n == 2:
            isolated.append((compact(Fraction(-1, 3)), 0.0))
        elif coefficient < 4.0/27.0:
            f = lambda u: u*(1+u)**2+coefficient
            a = _bisect(f, -1.0, -1.0/3.0)
            b = _bisect(f, -1.0/3.0, 0.0)
            intervals.append((compact(Fraction(a)), compact(Fraction(b)), 0.0, 0.0))
    else:
        right = 1.0
        while right*(right+1)**2 < -coefficient:
            right *= 2
        endpoint = _bisect(lambda u: u*(1+u)**2+coefficient, 0.0, right)
        intervals.extend([(-1.0, -0.5, 1.0, math.inf),
                          (-0.5, 0.0, math.inf, math.inf),
                          (compact(Fraction(endpoint)), 1.0, 0.0, 1.0)])
    result = []
    a = np.linspace(0.0, 1.0, points)
    spacing = (1-np.cos(np.pi*a))/2
    for low, high, left_y, right_y in intervals:
        q = low+(high-low)*spacing
        v = np.empty(points)
        v[0], v[-1] = 2/math.pi*math.atan(left_y), 2/math.pi*math.atan(right_y)
        u = np.tan(np.pi*q[1:-1]/2)
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            square = 1+coefficient/(u*(1+u)**2)
            v[1:-1] = 2/np.pi*np.arctan(np.sqrt(np.maximum(0.0, square)))
        result.extend([(q, v), (q, -v)])
    for q, v in isolated:
        result.append((np.array([q]), np.array([v])))
    return result


def verified_points(records: list[dict], low: int, high: int) -> list[dict]:
    """Recompute marker classifications; saved flags are never authoritative."""
    found = {}
    for record in records:
        point = check_point(record["n"], record["x"], record["y"])
        if not point["exact"]:
            raise ValueError("saved point is not an exact solution of the original equation")
        n = integer(point["n"])
        if not low <= n <= high:
            raise ValueError("saved point is outside the campaign n interval")
        point["y"] = str(abs(Fraction(point["y"])))
        point = check_point(n, point["x"], point["y"])
        found[(n, integer(point["x"]), Fraction(point["y"]))] = point
    return [found[key] for key in sorted(found)]


def load_snapshot(directory: str | Path) -> dict:
    from campaign import (load_manifest, read_low_height, region_from_manifest,
                          saved_tasks)
    directory = Path(directory)
    manifest = load_manifest(directory)
    region = region_from_manifest(manifest)
    low, high = integer(manifest["n_min"]), integer(manifest["n_max"])
    tasks = saved_tasks(directory, region, integer(manifest["band_width"]), manifest=manifest)
    points = [p for row in tasks for p in row.get("points", [])]
    small = read_low_height(directory, region, primitive=manifest["target"] == "primitive", manifest=manifest) or {}
    points.extend(small.get("points", []))
    checked = verified_points(points, low, high)
    cube_keys = {tuple(sorted(integer(v) for v in p["cube_triple"]))
                 for p in checked if p["integral_lift"]}
    return {"directory": directory, "manifest": manifest, "low": low, "high": high,
            "tasks": tasks, "points": checked, "lowheight": small,
            "cube_count": len(cube_keys), "equation_point_count": len(checked),
            "primitive_point_count": sum(p["primitive"] for p in checked),
            "complete_tasks": sum(t["status"] == "complete" for t in tasks),
            "partial_tasks": sum(t["status"] == "partial" for t in tasks),
            "error_tasks": sum(t["status"] == "error" for t in tasks),
            "tiles": sum(integer(t.get("tiles_count", 0)) for t in tasks),
            "lattice_points": sum(integer(t.get("lattice_points", 0)) for t in tasks)}


def completed_intervals(snapshot: dict) -> dict[int, list[tuple[int, int]]]:
    """Merge validated prefixes, including those retained after a failed resume."""
    groups = {}
    for record in snapshot["tasks"]:
        task = record["task"]
        height, right = integer(task["height"]), integer(task["index_stop"])
        left = integer(record["next_index"])
        if left < right:
            groups.setdefault(height, []).append((left, right))
    result = {}
    for H, intervals in groups.items():
        merged = []
        for lo, hi in sorted(intervals):
            if merged and lo <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
            else:
                merged.append((lo, hi))
        result[H] = merged
    return result


def _axes(ax, three=False):
    xticks = [-1, compact(-2), compact(-1), 0, compact(1), compact(2), 1]
    ax.set_xlim(-1.01, 1.01)
    ax.set_xticks(xticks, ["−∞", "−2", "−1", "0", "1", "2", "+∞"])
    ax.set_xlabel("x / (6n + 3), compactified", labelpad=10)
    values, labels = [-1, -.5, 0, .5, 1], ["−∞", "−1", "0", "1", "+∞"]
    if three:
        ax.set_zlim(-1.02, 1.02)
        ax.set_zticks(values, labels)
        ax.set_zlabel("y, compactified", labelpad=10)
    else:
        ax.set_ylim(-1.02, 1.02)
        ax.set_yticks(values, labels)
        ax.set_ylabel("y, compactified")
    ax.grid(alpha=.16)


def _style(point):
    if point["primitive"]:
        return GREEN, "*", 115
    if point["integral_lift"]:
        return ORANGE, "o", 46
    return PURPLE, "D", 42


def _point_coordinates(point):
    n, x = integer(point["n"]), integer(point["x"])
    y = abs(Fraction(point["y"]))
    qs, vs = [compact(Fraction(x, 6*n+3))], [compact(y)]
    if y:
        qs *= 2
        vs.append(-vs[0])
    return qs, vs


def _point_legend():
    from matplotlib.lines import Line2D
    return [Line2D([], [], color=BLUE, label="Real geometry; includes irrational y"),
            Line2D([], [], color=GREEN, marker="*", linestyle="", markersize=11, label="Exact primitive cubes"),
            Line2D([], [], color=ORANGE, marker="o", linestyle="", label="Exact nonprimitive cubes"),
            Line2D([], [], color=PURPLE, marker="D", linestyle="", label="Exact rational-only manual check")]


class CampaignViewer:
    """Own callback references and three linked figures for a saved campaign."""
    def __init__(self, directory, geometry_slices=24):
        import matplotlib.pyplot as plt
        from matplotlib.widgets import Button, TextBox
        self.snapshot = load_snapshot(directory)
        self.manual = {}
        self.message = "Enter exact integer n and x to check one point. Manual checks do not extend native coverage."
        self.selected_n = (integer(self.snapshot["points"][0]["n"])
                           if self.snapshot["points"] else self.snapshot["low"])
        self.task_index = 0
        self.base_n = geometry_values(self.snapshot["low"], self.snapshot["high"], geometry_slices)
        self.geometry_n = sorted(set(self.base_n) | {integer(p["n"]) for p in self.snapshot["points"]})
        self.figure2d = plt.figure(figsize=(12.6, 8.1), facecolor="white")
        self.figure3d = plt.figure(figsize=(13.0, 9.2), facecolor="white")
        self.coverage = plt.figure(figsize=(13.0, 9.2), facecolor="white")
        self.ax2 = self.figure2d.add_axes([.085, .28, .86, .49])
        self.ax3 = self.figure3d.add_axes([.12, .14, .75, .62], projection="3d")
        self.cov_ax = self.coverage.add_axes([.085, .43, .69, .34])
        self.zoom_ax = self.coverage.add_axes([.085, .19, .85, .13])
        self.title2 = self.figure2d.text(.05, .95, "", fontsize=17, color=INK, va="top")
        self.info2 = self.figure2d.text(.05, .86, "", fontsize=10, va="top")
        self.detail = self.figure2d.text(.05, .19, self.message, fontsize=9, va="top", family="monospace", wrap=True)
        self.title3 = self.figure3d.text(.05, .95, "", fontsize=17, color=INK, va="top")
        self.info3 = self.figure3d.text(.05, .86, "", fontsize=10, va="top")
        self.figure3d.text(.05, .07, "Real geometry is a visual reference, not independent n-slice search coverage.\n"
                           "Native coverage is shown in the separate height / ratio figure. Exact hits are rechecked before plotting.", fontsize=10)
        self.cov_title = self.coverage.text(.05, .95, "Elkies–Jahnel search coverage", fontsize=18, color=INK, va="top")
        self.cov_info = self.coverage.text(.05, .88, "", fontsize=10, va="top")
        self.cov_detail = self.coverage.text(.05, .13, "", fontsize=9, va="top", family="monospace")
        self.n_box = TextBox(self.figure2d.add_axes([.13, .075, .37, .045]), "Integer n: ", initial=str(self.selected_n))
        self.x_box = TextBox(self.figure2d.add_axes([.64, .075, .23, .045]), "Integer x: ", initial="")
        self.check_button = Button(self.figure2d.add_axes([.88, .075, .08, .045]), "Check x")
        self.n_box.on_submit(self.set_n)
        self.x_box.on_submit(self.check_x)
        self.check_button.on_clicked(lambda event: self.check_x(self.x_box.text))
        self.prev = Button(self.coverage.add_axes([.085, .025, .15, .04]), "Previous task")
        self.nxt = Button(self.coverage.add_axes([.25, .025, .15, .04]), "Next task")
        self.prev.on_clicked(lambda event: self.select_task(-1))
        self.nxt.on_clicked(lambda event: self.select_task(1))
        self.task_box = TextBox(self.coverage.add_axes([.62, .025, .22, .04]), "Saved task number: ", initial="1")
        self.task_box.on_submit(self.set_task)
        for fig in (self.figure2d, self.figure3d):
            fig.canvas.mpl_connect("pick_event", self.pick)
        for fig, name in ((self.figure2d, "Original equation — exact points"),
                          (self.figure3d, "Original equation — real geometry"),
                          (self.coverage, "Elkies–Jahnel — actual coverage")):
            fig.canvas.manager.set_window_title(name)
        self.draw_2d()
        self.draw_3d()
        self.draw_coverage()
        self.draw_zoom()

    def all_points(self):
        return self.snapshot["points"]+list(self.manual.values())

    def _scatter(self, ax, point, three=False):
        q, v = _point_coordinates(point)
        color, marker, size = _style(point)
        if three:
            n = integer(point["n"])
            depth = self.depth(n)
            artist = ax.scatter(q, [depth]*len(q), v, color=color, marker=marker, s=size,
                                edgecolors="white", linewidths=.6, depthshade=False, picker=5)
        else:
            artist = ax.scatter(q, v, color=color, marker=marker, s=size, edgecolors="white", linewidths=.6, zorder=5, picker=5)
        artist._exact_point = point

    def depth(self, n):
        if self.snapshot["low"] > 0:
            return math.log10(n)
        return math.copysign(math.log10(1+abs(n)), n)

    def draw_2d(self):
        ax = self.ax2
        ax.clear()
        _axes(ax)
        for q, v in real_geometry(self.selected_n, 420):
            ax.plot(q, v, color=BLUE, linewidth=1.6, marker="." if len(q) == 1 else None)
        for point in self.all_points():
            if integer(point["n"]) == self.selected_n:
                self._scatter(ax, point)
        self.title2.set_text(f"Original equation · selected n = {self.selected_n:,}\nReal geometry and exactly verified points")
        self.info2.set_text("This curve is geometry only; native coverage is recorded in height / ratio tiles.\n"
                            f"Mapped cube triples: {self.snapshot['cube_count']:,}; equation representations: {self.snapshot['equation_point_count']:,}; "
                            f"primitive representations: {self.snapshot['primitive_point_count']:,}.\n"
                            f"Manual exact checks: {len(self.manual):,}. Each ±y pair is counted once.")
        ax.legend(handles=_point_legend(), loc="lower left", fontsize=8.4, framealpha=.94, ncols=2)
        self.figure2d.canvas.draw_idle()

    def draw_3d(self):
        ax = self.ax3
        ax.clear()
        _axes(ax, True)
        for n in self.geometry_n:
            for q, v in real_geometry(n, 96):
                ax.plot(q, [self.depth(n)]*len(q), v, color=BLUE, alpha=.36, linewidth=.65)
        for point in self.all_points():
            self._scatter(ax, point, True)
        ax.set_ylabel("n (logarithmic depth)", labelpad=13)
        if self.snapshot["low"] > 0:
            lo, hi = self.depth(self.snapshot["low"]), self.depth(self.snapshot["high"])
            if lo == hi:
                ax.set_ylim(lo-.15, hi+.15)
                ax.set_yticks([lo], [str(self.snapshot["low"])])
            else:
                ticks = [lo]+[float(k) for k in range(math.ceil(lo), math.floor(hi)+1) if lo < k < hi]+[hi]
                ax.set_yticks(ticks, [f"$10^{{{t:g}}}$" for t in ticks])
        ax.view_init(elev=24, azim=-63)
        ax.legend(handles=_point_legend(), loc="upper left", fontsize=8.5)
        self.title3.set_text("Original equation · geometry across the requested n interval\nExact native hits are overlaid; the curves are not search coverage")
        self.info3.set_text(f"Requested n: {self.snapshot['low']:,} to {self.snapshot['high']:,}\n"
                            f"Drawing every one of {len(self.geometry_n):,} selected geometry n-values, including all hit n-values.\n"
                            f"Mapped cube triples: {self.snapshot['cube_count']:,}; equation representations: {self.snapshot['equation_point_count']:,}; "
                            f"primitive representations: {self.snapshot['primitive_point_count']:,}; manual checks: {len(self.manual):,}.")
        self.figure3d.canvas.draw_idle()

    def draw_coverage(self):
        from matplotlib.patches import Patch
        from matplotlib.lines import Line2D
        ax = self.cov_ax
        ax.clear()
        region = self.snapshot["manifest"].get("region", {})
        shells = region.get("shells", [])
        if not shells:
            by_height = {}
            for record in self.snapshot["tasks"]:
                task = record["task"]
                H = integer(task["height"])
                lo, hi = integer(task["index_start"]), integer(task["index_stop"])
                if H not in by_height:
                    by_height[H] = [lo, hi]
                else:
                    by_height[H] = [min(lo, by_height[H][0]), max(hi, by_height[H][1])]
            shells = [dict(height=H,index_start=limits[0],index_stop=limits[1]) for H, limits in sorted(by_height.items())]
        covered = completed_intervals(self.snapshot)
        label_step = max(1, math.ceil(len(shells)/12))
        label_rows = sorted(set(range(0, len(shells), label_step)) | ({len(shells)-1} if shells else set()))
        annotation_rows = set(range(len(shells))) if len(shells) <= 18 else set(label_rows)
        for row, shell in enumerate(shells):
            H, left, right = (integer(shell[k]) for k in ("height", "index_start", "index_stop"))
            lo, width = float(Fraction(left,5*H)), float(Fraction(right-left,5*H))
            ax.broken_barh([(lo,width)], (row-.3,.6), facecolors=GREY, linewidth=0)
            if width < .001:
                ax.plot(float(Fraction(left+right,10*H)), row, marker="|", color=GREY, markersize=5)
            for a, b in covered.get(H, []):
                start, span = float(Fraction(a,5*H)), float(Fraction(b-a,5*H))
                ax.broken_barh([(start,span)], (row-.3,.6), facecolors=BLUE, linewidth=0)
                if span < .001:
                    ax.plot(float(Fraction(a+b,10*H)), row, marker="|", color=BLUE, markersize=9)
            saved = sum(integer(t["task"]["height"]) == H for t in self.snapshot["tasks"])
            if saved and row in annotation_rows:
                ax.annotate(f" {saved} saved", (lo+width,row), xytext=(4,0), textcoords="offset points", fontsize=7, va="center")
        if shells:
            ax.set_yticks(label_rows, [f"{integer(shells[i]['height']):.2e}" for i in label_rows])
            ax.set_ylim(-.7,len(shells)-.3)
        else:
            ax.text(.5,.5,"No native height / ratio bands in this plan",ha="center",va="center",transform=ax.transAxes)
            ax.set_yticks([])
        # Give the extremely narrow high-height plan a visible margin at a/c=0.
        ax.set_xlim(-.01,.86)
        ax.set_xlabel("Native projective ratio a / c")
        ax.set_ylabel("Native shell start H")
        ax.grid(alpha=.15,axis="x")
        self.coverage.legends.clear()
        self.coverage.legend(handles=[Patch(color=GREY,label="Planned; narrow bands are ticks"),
                                      Patch(color=BLUE,label="Completed ratio intervals"),
                                      Line2D([],[],marker="|",linestyle="",color=BLUE,label="Completed interval below plot resolution")],
                             loc="upper left",bbox_to_anchor=(.78,.76),fontsize=8.0,frameon=False)
        planned = integer(self.snapshot["manifest"]["planned_task_count"])
        self.cov_info.set_text(f"Requested n: {self.snapshot['low']:,} to {self.snapshot['high']:,}\n"
                               f"Height shells: {len(shells):,}; planned tasks: {planned:,}; saved: {len(self.snapshot['tasks']):,} "
                               f"({self.snapshot['complete_tasks']:,} complete, {self.snapshot['partial_tasks']:,} partial, {self.snapshot['error_tasks']:,} errors).\n"
                               f"Completed tiles: {self.snapshot['tiles']:,}; lattice points covered by enumeration / root isolation: {self.snapshot['lattice_points']:,}.")
        self.coverage.text(.80,.56,"A tiny completed band\ncan merge into one pixel.\nThe lower panel shows\nits exact local offsets.\n\nThe grey region is a plan,\nnot a searched n interval.",fontsize=9,va="top",color=INK)
        self.coverage.canvas.draw_idle()

    def draw_zoom(self):
        ax = self.zoom_ax
        ax.clear()
        tasks = self.snapshot["tasks"]
        if not tasks:
            ax.text(.5,.5,"No saved native task yet. Low-height checks are recorded separately.",ha="center",va="center",transform=ax.transAxes)
            ax.set_axis_off()
            required = self.snapshot["manifest"].get("region", {}).get("small_height_required", True)
            low_status = ("not required in this n interval" if not required else
                          "complete" if self.snapshot["lowheight"].get("complete") else "not recorded complete")
            self.cov_detail.set_text("Low-height finite check: "+low_status)
            return
        row = tasks[self.task_index]
        task = row["task"]
        H, left, right = (integer(task[k]) for k in ("height", "index_start", "index_stop"))
        nxt = integer(row.get("next_index",right))
        completed = right-nxt
        width = right-left
        view_width = min(width, max(1000, 2*completed))
        ax.broken_barh([(0,float(view_width))],(-.25,.5),facecolors=GREY)
        if completed:
            ax.broken_barh([(0,float(min(completed,view_width)))],(-.25,.5),facecolors=BLUE)
        for tile in row.get("tiles",[]):
            position = right-integer(tile["left"])
            if 0 <= position <= view_width:
                ax.axvline(float(position),color="white",lw=.7,alpha=.8)
        ax.set_xlim(0,max(1,float(view_width)))
        ax.set_ylim(-.65,.65)
        ax.set_yticks([])
        ax.set_xlabel("Exact ratio-grid offset R − i; integer subtraction precedes plotting")
        state = ("CONTINUATION FAILED; prior coverage retained" if row["status"] == "error"
                 else row["status"].upper())
        ax.set_title(f"Saved task {self.task_index+1}/{len(tasks)} · {state} · H = {H}",fontsize=10,loc="left",
                     color=RED if row["status"] == "error" else INK)
        scope = "whole task shown" if view_width == width else "zoom at the searched end; remaining task extends beyond this view"
        closing = "]" if task.get("include_right_endpoint", False) else ")"
        interval = f"Completed [{nxt}, {right}{closing}"
        self.cov_detail.set_text(f"i = (5H)a/c. Task [{left}, {right}{closing}.\n{interval}.\n"
                                 f"Completed width {completed} / assigned width {width}; {scope}.")
        self.coverage.canvas.draw_idle()

    def set_n(self, text):
        try:
            n = integer(text.strip(), "n")
            if not self.snapshot["low"] <= n <= self.snapshot["high"]:
                raise ValueError("n is outside this campaign's requested interval")
            self.selected_n = n
            if self.n_box.text != str(n):
                events = self.n_box.eventson
                self.n_box.eventson = False
                try:
                    self.n_box.set_val(str(n))
                finally:
                    self.n_box.eventson = events
            self.message = f"Selected n={n}. Real geometry only; use Check x for an exact one-point test."
            self.detail.set_text(self.message)
            self.draw_2d()
        except ValueError as error:
            self.detail.set_text(str(error))
            self.figure2d.canvas.draw_idle()

    def check_x(self, text):
        try:
            x = integer(text.strip(), "x")
            point = rational_point_at(self.selected_n, x)
            if point is None:
                self.detail.set_text(f"Exact point check: n={self.selected_n}, x={x}; no rational y.\nThis one-point check does not extend native height / ratio coverage.")
            else:
                key = (self.selected_n,x)
                self.manual[key] = point
                self.detail.set_text(f"MANUAL EXACT CHECK: n={point['n']}; x={point['x']}; |y|={point['y']}\n"
                                     f"Status: {point['status']}; R=0. Full exact record printed in Terminal.")
                print(json.dumps({"source":"manual-one-point-check","point":point},indent=2))
                if self.selected_n not in self.geometry_n:
                    self.geometry_n = sorted(set(self.geometry_n)|{self.selected_n})
                self.draw_2d()
                self.draw_3d()
            self.figure2d.canvas.draw_idle()
        except (ValueError, ArithmeticError) as error:
            self.detail.set_text(str(error))
            self.figure2d.canvas.draw_idle()

    def pick(self, event):
        point = getattr(event.artist,"_exact_point",None)
        if point:
            print(json.dumps(point,indent=2))
            self.detail.set_text(f"EXACT {point['status'].upper()}: n={point['n']}; x={point['x']}; |y|={point['y']}\n"
                                 "R=0. The full exact cube triple and gcd are printed in Terminal.")
            self.figure2d.canvas.draw_idle()

    def select_task(self, delta):
        if self.snapshot["tasks"]:
            self.task_index = (self.task_index+delta)%len(self.snapshot["tasks"])
            self.task_box.set_val(str(self.task_index+1))

    def set_task(self, text):
        try:
            index = integer(text.strip(),"saved task number")-1
            if not 0 <= index < len(self.snapshot["tasks"]):
                raise ValueError("saved task number is outside the available range")
            self.task_index = index
            self.draw_zoom()
        except ValueError as error:
            self.cov_detail.set_text(str(error))
            self.coverage.canvas.draw_idle()


def plot_campaign(directory, *, geometry_slices=24, save_prefix=None, show=True) -> dict[str,str]:
    """Open the saved campaign without rerunning its search; return saved paths."""
    import matplotlib.pyplot as plt
    viewer = CampaignViewer(directory, geometry_slices=geometry_slices)
    # Matplotlib callbacks use weak references; retain the controller on figures.
    for figure in (viewer.figure2d, viewer.figure3d, viewer.coverage):
        figure._elkies_viewer = viewer
    written = {}
    if save_prefix is not None:
        prefix = Path(save_prefix)
        prefix.parent.mkdir(parents=True,exist_ok=True)
        for key,figure in (("equation-2d",viewer.figure2d),("equation-3d",viewer.figure3d),("coverage",viewer.coverage)):
            path = prefix.with_name(prefix.name+"-"+key+".png")
            figure.savefig(path,dpi=155,facecolor="white")
            written[key] = str(path)
        metadata = prefix.with_name(prefix.name+"-plot-summary.json")
        metadata.write_text(json.dumps({
            "geometry_only_n_values":[str(n) for n in viewer.geometry_n],
            "geometry_only_n_count":len(viewer.geometry_n),
            "geometry_is_not_search_coverage":True,
            "mapped_cube_triples":viewer.snapshot["cube_count"],
            "equation_representations":viewer.snapshot["equation_point_count"],
            "primitive_equation_representations":viewer.snapshot["primitive_point_count"],
            "saved_tasks":len(viewer.snapshot["tasks"]),
            "complete_tasks":viewer.snapshot["complete_tasks"],
            "partial_tasks":viewer.snapshot["partial_tasks"],
            "error_tasks":viewer.snapshot["error_tasks"],
            "completed_tiles":str(viewer.snapshot["tiles"]),
            "lattice_points_covered":str(viewer.snapshot["lattice_points"]),
            "manual_point_checks_saved":False,
        },indent=2)+"\n")
        written["metadata"] = str(metadata)
    if show:
        plt.show()
    else:
        for figure in (viewer.figure2d,viewer.figure3d,viewer.coverage):
            plt.close(figure)
    return written
