"""Exact target: den(n) divides 6 and den(x)=den(y)=b in lowest terms.

This NEW schema does not reinterpret integer tasks or the superseded n/x
common-denominator proposal. All coverage statements are for a selected b.
"""
from __future__ import annotations
from fractions import Fraction
from math import gcd, isqrt, prod
from functools import lru_cache
from q_sieve import forbidden_primes
from typing import Any, Iterator
from parameter_space import _floor_sum
from aq_traversal import InterleavedAQ
from run_task import (SIGN_POLICIES, HEX64, integer, small_int, keys, digest,
                      task_identity)

SCHEMA = "ce390-xy-task-v1"
PARAMETERIZATION = "n-sixths-equal-xy-denominators-v1"
PAGE_SCHEMA = "ce390-xy-page-v1"
CONGRUENCE_POLICIES = ("none", "numerators", "rational-mod")
BOUND_KEYS = ("n_min", "n_max", "x_min", "x_max")


@lru_cache(maxsize=1)
def _prime_product() -> int:
    return prod(forbidden_primes())


@lru_cache(maxsize=4096)
def reject_xy_q(q: int) -> bool:
    """Additional prime obstruction for the CORRECTED equal-x/y target.

    q|X and X|k^3-390, where k=6*n is integral and gcd(X,b)=1.
    For p>3 the roots of k^3=390 correspond to those of 36*t^3=65
    by k=6*t. The prime list is reused, not the old integer-y policy.
    """
    if type(q) is not int or q<=0:
        raise ValueError("q must be a positive integer")
    return gcd(q,_prime_product())!=1


def validate_search(search: Any) -> dict:
    keys(search, set(BOUND_KEYS) | {"signs", "xy_denominator", "n_denominators",
         "congruence_policy", "require_noninteger_d"}, {"require_integer_components"}, "search")
    bounds = {k: integer(search[k], k, positive=True) for k in BOUND_KEYS}
    b = integer(search["xy_denominator"], "xy_denominator", positive=True)
    # Missing means the earlier broad x/y target, never a silent reinterpretation.
    if type(search.get("require_integer_components", False)) is not bool:
        raise ValueError("require_integer_components must be a boolean")
    if search.get("require_integer_components", False) and b not in (1, 2):
        raise ValueError("both -x+y and -x-y integral force the reduced x/y denominator to be 1 or 2")
    if bounds["n_min"] < 2 or bounds["n_min"] > bounds["n_max"] or bounds["x_min"] > bounds["x_max"]:
        raise ValueError("ordered magnitude bounds must have n_min >= 2")
    if bounds["x_min"] <= 6*bounds["n_max"]:
        raise ValueError("this slope enclosure requires x_min > 6*n_max")
    if search["signs"] not in SIGN_POLICIES:
        raise ValueError("invalid sign policy")
    ds = search["n_denominators"]
    if (not isinstance(ds, list) or not ds or any(type(d) is not int or d not in (1,2,3,6) for d in ds)
            or ds != sorted(set(ds))):
        raise ValueError("n_denominators must be a nonempty sorted subset of [1,2,3,6]")
    if type(search["require_noninteger_d"]) is not bool:
        raise ValueError("require_noninteger_d must be an explicit boolean")
    policy = search["congruence_policy"]
    if policy not in CONGRUENCE_POLICIES:
        raise ValueError("congruence policy must be none, numerators, or rational-mod")
    if policy == "rational-mod" and (gcd(b,84) != 1 or any(gcd(d,3) != 1 for d in ds)):
        raise ValueError("rational-mod requires b coprime to 84 and n denominators coprime to 3")
    return dict(bounds=bounds, denominator=b)


class XYAQ:
    """Every integer (a,q) in a proved enclosure at one exact x/y denominator.

    Rows are increasing q, then a. All n denominators requested in the task
    are searched WITHIN each fiber, not as extra overlapping index rows.
    No parity/mod-3 restriction is inherited from the old integer search.
    """
    MODE = "n-sixths-xy-general-aq-v1"

    def __init__(self, search: dict, q_min: int = 1, q_max: int | None = None):
        parsed = validate_search(search)
        b = parsed["denominator"]
        bounds = parsed["bounds"]
        Kmin, Kmax = 6*bounds["n_min"], 6*bounds["n_max"]
        self.Vmin, self.Vmax = b*bounds["x_min"], b*bounds["x_max"]
        gap = b**3*(Kmax**3+390) // (6*self.Vmin*(self.Vmin-b*Kmax))
        self.Mmin, self.Mmax = 2*b*Kmin+1, 2*b*Kmax+gap
        # Y=b*y and X+b*k are integers: a nonzero gap has magnitude >=1.
        # Also X divides k^3-390, giving this finite necessary ceiling on b.
        self.max_possible_b = (Kmax**3+390)//bounds["x_min"]
        self.empty = gap == 0 or b > self.max_possible_b
        self.lower = Fraction(self.Mmin, self.Vmax)
        self.upper = Fraction(self.Mmax, self.Vmin)
        if not (0 < self.lower and self.upper < 2) or (not self.empty and self.lower > self.upper):
            raise ValueError("derived slope enclosure must lie strictly between 0 and 2")
        # Equal reduced x/y denominators and integral 6*n imply q | |X|.
        self.full_q_max = self.Vmax
        self.q_min, self.q_max = q_min, self.full_q_max if q_max is None else q_max
        if (type(self.q_min) is not int or type(self.q_max) is not int
                or not 1 <= self.q_min <= self.q_max <= self.full_q_max):
            raise ValueError("q window must be inside the full proved positive enclosure")
        self._base = self._prefix(self.q_min-1)
        self.count = self._prefix(self.q_max)-self._base

    def numerator_bounds(self, q: int) -> tuple[int,int]:
        lo = -(-self.Mmin*q // self.Vmax)
        hi = min(self.Mmax*q // self.Vmin, self.Mmax)
        return lo, hi

    def _prefix(self, q: int) -> int:
        if q <= 0 or self.empty:
            return 0
        first = min(q, self.Vmin)
        upper = _floor_sum(first, self.Vmin, self.Mmax, self.Mmax)
        upper += max(0, q-self.Vmin)*self.Mmax
        lower = _floor_sum(q, self.Vmax, self.Mmin, self.Mmin-1)
        return upper-lower

    def candidate(self, index: int) -> tuple[int,int]:
        if type(index) is not int or not 0 <= index < self.count:
            raise ValueError("candidate index outside x/y parameter space")
        lo, hi, target = self.q_min, self.q_max, self._base+index
        while lo < hi:
            mid = (lo+hi)//2
            if self._prefix(mid) > target:
                hi = mid
            else:
                lo = mid+1
        first, _ = self.numerator_bounds(lo)
        return first+target-self._prefix(lo-1), lo

    def index(self, a: int, q: int) -> int:
        if type(a) is not int or type(q) is not int or self.empty or not self.q_min <= q <= self.q_max:
            raise ValueError("fiber outside x/y parameter space")
        lo, hi = self.numerator_bounds(q)
        if not lo <= a <= hi:
            raise ValueError("numerator outside rational slope enclosure")
        return self._prefix(q-1)-self._base+a-lo

    def iter_candidates(self, start: int, stop: int) -> Iterator[tuple[int,int]]:
        if not 0 <= start <= stop <= self.count:
            raise ValueError("invalid rational candidate slice")
        if start == stop:
            return
        a, q = self.candidate(start)
        _, upper = self.numerator_bounds(q)
        for i in range(start, stop):
            yield a, q
            if i+1 == stop:
                return
            a += 1
            if a <= upper:
                continue
            q += 1
            while True:
                lower, upper = self.numerator_bounds(q)
                if lower <= upper:
                    a = lower
                    break
                # Skip empty denominator rows without scanning each one.
                first_possible = -(-lower*self.upper.denominator // self.upper.numerator)
                q = max(q+1, first_possible)
                if q > self.q_max:
                    raise RuntimeError("x/y parameter iterator exhausted early")


def parameter_space(search: dict, q_min: int = 1, q_max: int | None = None,
                    mode: str = XYAQ.MODE):
    if mode not in (XYAQ.MODE, InterleavedAQ.MODE):
        raise ValueError("unsupported x/y fiber mode")
    base = XYAQ(search, q_min, q_max)
    return base if mode == XYAQ.MODE else InterleavedAQ(base)


def reject_xy_parity(a: int, q: int, b: int) -> bool:
    """Necessary condition only: b=2 forces even reduced a and odd q.

    x=X/2 and y=Y/2 in lowest terms make X,Y odd. With k=6*n integral,
    the slope numerator |Y-|X|+2*k*sign(X)| is even over an odd |X|.
    Reducing by an odd gcd preserves those parities. This never fixes a=2.
    """
    if any(type(v) is not int or v < 1 for v in (a, q, b)):
        raise ValueError("a, q and b must be positive integers")
    return b == 2 and (a % 2 != 0 or q % 2 == 0)


def validate_task(task: Any) -> dict:
    keys(task, {"schema", "parameterization", "campaign_id", "task_id", "search", "fibers", "slice", "execution"},
         {"resume_index", "expected_worker_sha256", "expected_implementation_sha256"}, "x/y task")
    if task["schema"] != SCHEMA or task["parameterization"] != PARAMETERIZATION:
        raise ValueError("not a corrected x/y-denominator task; earlier schemas are not reinterpreted")
    import re
    if not isinstance(task["campaign_id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", task["campaign_id"]):
        raise ValueError("campaign_id must be 1-96 safe ASCII characters")
    p = validate_search(task["search"])
    keys(task["fibers"], {"mode", "q_min", "q_max"}, set(), "fibers")
    qmin = integer(task["fibers"]["q_min"], "q_min", positive=True)
    qmax = integer(task["fibers"]["q_max"], "q_max", positive=True)
    space = parameter_space(task["search"], qmin, qmax, task["fibers"]["mode"])
    keys(task["slice"], {"start", "stop"}, set(), "slice")
    start = integer(task["slice"]["start"], "slice.start")
    stop = integer(task["slice"]["stop"], "slice.stop", positive=True)
    resume = integer(task.get("resume_index", str(start)), "resume_index")
    if not 0 <= start < stop <= space.count or not start <= resume <= stop:
        raise ValueError("slice/resume outside x/y parameter enclosure")
    ex = task["execution"]
    keys(ex, {"time_limit_seconds", "precision_bits", "max_precision_bits", "checkpoint_seconds"}, set(), "execution")
    seconds = small_int(ex["time_limit_seconds"], 1, 6600, "time_limit_seconds")
    precision = small_int(ex["precision_bits"], 64, 16384, "precision_bits")
    maxp = small_int(ex["max_precision_bits"], precision, 65536, "max_precision_bits")
    cps = small_int(ex["checkpoint_seconds"], 1, 60, "checkpoint_seconds")
    if task["task_id"] != task_identity(task):
        raise ValueError("task identity does not match its immutable x/y search")
    for k in ("expected_worker_sha256", "expected_implementation_sha256"):
        if k in task and (not isinstance(task[k], str) or not HEX64.fullmatch(task[k])):
            raise ValueError("invalid " + k)
    return dict(**p, search=task["search"], signs=task["search"]["signs"], parameter_space=space,
                count=space.count, start=start, stop=stop, resume=resume, seconds=seconds,
                precision=precision, max_precision=maxp, checkpoint_seconds=cps)


def candidate(parsed: dict, index: int) -> tuple[int,int]:
    return parsed["parameter_space"].candidate(index)


def candidate_index(parsed: dict, a: int, q: int) -> int:
    return parsed["parameter_space"].index(a,q)


def iter_candidates(parsed: dict, start: int, stop: int):
    return parsed["parameter_space"].iter_candidates(start,stop)


def rational(record: dict, prefix: str) -> Fraction:
    n = integer(record[prefix+"_num"], prefix+"_num", signed=True)
    d = integer(record[prefix+"_den"], prefix+"_den", positive=True)
    if gcd(abs(n),d) != 1:
        raise ValueError(prefix + " must be in lowest terms")
    return Fraction(n,d)



def coordinate_congruences(n: Fraction, x: Fraction, policy: str) -> bool:
    if policy == "none":
        return True
    if policy not in CONGRUENCE_POLICIES:
        raise ValueError("invalid congruence policy")
    if policy == "rational-mod" and (gcd(n.denominator,3) != 1 or gcd(x.denominator,84) != 1):
        raise ValueError("rational congruences require invertible denominators")
    rn = 1 if policy == "numerators" else n.denominator
    rx = 1 if policy == "numerators" else x.denominator
    return (n.numerator-rn)%3 == 0 and (x.numerator-5*rx)%12 == 0 and x.numerator%7 != 0


COMPONENT_KEYS = ("cube_plus", "cube_minus", "cube_third")


def integer_components(n: Fraction, x: Fraction, y: Fraction) -> tuple[int, int, int]:
    """Both signs of -x +/- y and 2*x+6*n; structural check, not an equation check.

    Do not confuse testing ONE sign with the requested simultaneous conditions.
    The caller must separately verify the radical and the cube sum 390.
    """
    values = (-x+y, -x-y, 2*x+6*n)
    if any(v.denominator != 1 for v in values):
        raise ValueError("-x+y, -x-y, and 2*x+6*n must ALL be integers")
    return tuple(v.numerator for v in values)


def verify_record(record: Any, search: dict) -> dict:
    """Independent original-equation verification; does not call the CF worker."""
    parsed = validate_search(search)
    if not isinstance(record, dict):
        raise ValueError("rational certificate must be an object")
    try:
        values = {k: rational(record,k) for k in ("n","x","y","d","gap")}
    except KeyError as e:
        raise ValueError("missing certificate field " + str(e)) from e
    n,x,y,d,gap = (values[k] for k in ("n","x","y","d","gap"))
    b = parsed["denominator"]
    if n.denominator not in search["n_denominators"]:
        raise ValueError("n must have one of the task denominators in [1,2,3,6]")
    if x.denominator != b or y.denominator != b:
        raise ValueError("x and y must BOTH have the task's exact reduced denominator")
    for key,value in (("n",n),("x",x)):
        if not parsed["bounds"][key+"_min"] <= abs(value) <= parsed["bounds"][key+"_max"]:
            raise ValueError("rational " + key + " is outside the magnitude bounds")
    signs=("p" if n>0 else "n")+("p" if x>0 else "n")
    if search["signs"] not in ("all",signs):
        raise ValueError("rational certificate violates sign policy")
    if not coordinate_congruences(n,x,search["congruence_policy"]):
        raise ValueError("certificate violates explicit congruence policy")
    A,S=36*n**3-65,x+6*n
    # Deliberately use the ORIGINAL rational radicand, not the worker cubic.
    radicand=S*S+A/x
    if radicand < 0:
        raise ValueError("negative radicand")
    u,v=isqrt(radicand.numerator),isqrt(radicand.denominator)
    if u*u!=radicand.numerator or v*v!=radicand.denominator or y!=Fraction(u,v):
        raise ValueError("certificate fails the exact principal square-root check")
    if y*y!=radicand or gap!=y-S or A!=-2*d*x*x*gap or d!=-(y+S)/(2*x):
        raise ValueError("certificate fails original unsquared equation")
    if type(record.get("sqrt_integer")) is not bool or record["sqrt_integer"]!=(y.denominator==1):
        raise ValueError("incorrect square-root integer flag")
    if search["require_noninteger_d"] and d.denominator==1:
        raise ValueError("d must be noninteger under this task's policy")
    out={k+s:str(getattr(v,attr)) for k,v in values.items()
         for s,attr in (("_num","numerator"),("_den","denominator"))}
    out["sqrt_integer"]=y.denominator==1
    # The original radical and unsquared equation have already been checked.
    # Also check supplied component fields in older/exploratory certificates.
    component_keys = set(COMPONENT_KEYS) | {"cube_sum"}
    if search.get("require_integer_components", False) or component_keys.intersection(record):
        components = integer_components(n, x, y)
        total = sum(v**3 for v in components)
        if total != 390:
            raise ValueError("integer components fail the exact cube sum 390")
        # Cubes mod 9 force all three components ==1 mod3; parity forces
        # their sum even. Hence n=(A+B+C)/6 is integral, a derived fact.
        if n.denominator != 1:
            raise ValueError("integer cube sum 390 requires integral n")
        for key, value in zip(COMPONENT_KEYS + ("cube_sum",), components + (total,)):
            if key in record and integer(record[key], key, signed=True) != value:
                raise ValueError("incorrect " + key)
            out[key] = str(value)
    return out


def validate_hit(record: dict, a: int, q: int, search: dict) -> dict:
    out=verify_record(record,search)
    n,x,y=(rational(out,k) for k in ("n","x","y"))
    if not 0<a<2*q or gcd(a,q)!=1 or abs(y/abs(x)-1+6*n/x)!=Fraction(a,q):
        raise ValueError("rational certificate belongs to another slope fiber")
    return out


def certificate_key(record: dict) -> str:
    return digest({k: record[k] for k in ("n_num","n_den","x_num","x_den","y_num","y_den","d_num","d_den")})
