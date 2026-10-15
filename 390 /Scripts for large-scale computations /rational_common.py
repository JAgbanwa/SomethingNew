"""Exact task space and independent certificates for equal reduced denominators.

This is a NEW task schema. It never reinterprets legacy integer-coordinate jobs.
See RATIONAL_COORDINATES.md for the proof and the meaning of each policy.
"""
from __future__ import annotations
from fractions import Fraction
from math import gcd, isqrt
from typing import Any, Iterator
from parameter_space import _floor_sum
from run_task import (SIGN_POLICIES, HEX64, integer, small_int, keys, digest,
                      task_identity)

SCHEMA = "ce390-rational-task-v1"
PARAMETERIZATION = "equal-reduced-coordinate-denominator-v1"
PAGE_SCHEMA = "ce390-rational-page-v1"
CONGRUENCE_POLICIES = ("none", "numerators", "rational-mod")
BOUND_KEYS = ("n_min", "n_max", "x_min", "x_max")


def validate_search(search: Any) -> dict:
    keys(search, set(BOUND_KEYS) | {"signs", "coordinate_denominator",
         "require_integer_sqrt", "congruence_policy", "require_noninteger_d"}, set(), "search")
    bounds = {k: integer(search[k], k, positive=True) for k in BOUND_KEYS}
    b = integer(search["coordinate_denominator"], "coordinate_denominator", positive=True)
    if bounds["n_min"] < 2 or bounds["n_min"] > bounds["n_max"] or bounds["x_min"] > bounds["x_max"]:
        raise ValueError("ordered magnitude bounds must have n_min >= 2")
    if bounds["x_min"] <= 6*bounds["n_max"]:
        raise ValueError("this slope enclosure requires x_min > 6*n_max")
    if search["signs"] not in SIGN_POLICIES:
        raise ValueError("invalid sign policy")
    for k in ("require_integer_sqrt", "require_noninteger_d"):
        if type(search[k]) is not bool:
            raise ValueError(k + " must be an explicit boolean")
    policy = search["congruence_policy"]
    if policy not in CONGRUENCE_POLICIES:
        raise ValueError("explicit congruence policy required: none, numerators, rational-mod")
    if policy == "rational-mod" and gcd(b, 84) != 1:
        raise ValueError("rational-mod requires a denominator coprime to 84")
    return dict(bounds=bounds, denominator=b)


class RationalAQ:
    """All integer (a,q) in a proved enclosure for ONE exact coordinate denominator.

    Rows are increasing q, then a. No parity/mod-3 sieve is assumed for
    rational coordinates. Noncoprime pairs remain indexed. Prefix counting
    is logarithmic, not a loop over the huge implicit parameter space.
    """
    MODE = "equal-denominator-general-aq-v1"

    def __init__(self, search: dict, q_min: int = 1, q_max: int | None = None):
        parsed = validate_search(search)
        b = parsed["denominator"]
        v = {k: b*n for k,n in parsed["bounds"].items()}
        Xmin, Xmax, Nmin, Nmax = (v[k] for k in ("x_min", "x_max", "n_min", "n_max"))
        K = Fraction(36*Nmax**3 + 65*b**3, Xmin*(Xmin-6*Nmax))
        integral = search["require_integer_sqrt"]
        self.empty = integral and K < 1
        # For integral y, b*y and its gap from |X+6N| are integers.
        if integral:
            K = Fraction(K.numerator // K.denominator)
        self.lower = Fraction(12*Nmin + (1 if integral else 0), Xmax)
        self.upper = (12*Nmax + K) / Xmin
        if not 0 < self.lower <= self.upper < 1:
            raise ValueError("derived slope enclosure must lie strictly between 0 and 1")
        # If Y=b*y has reduced denominator v, then v^2 divides |X|.
        # Therefore q divides v*|X| and q <= |X|*floor(sqrt(|X|)).
        self.full_q_max = Xmax if integral else Xmax*isqrt(Xmax)
        self.q_min, self.q_max = q_min, self.full_q_max if q_max is None else q_max
        if (type(self.q_min) is not int or type(self.q_max) is not int
                or not 1 <= self.q_min <= self.q_max <= self.full_q_max):
            raise ValueError("q window must be inside the full proved positive enclosure")
        self._base = self._prefix(self.q_min-1)
        self.count = self._prefix(self.q_max)-self._base

    def numerator_bounds(self, q: int) -> tuple[int,int]:
        lo = -(-self.lower.numerator*q // self.lower.denominator)
        hi = self.upper.numerator*q // self.upper.denominator
        return lo, hi

    def _prefix(self, q: int) -> int:
        if q <= 0 or self.empty:
            return 0
        U, L = self.upper, self.lower
        return (_floor_sum(q, U.denominator, U.numerator, U.numerator)
                - _floor_sum(q, L.denominator, L.numerator, L.numerator-1))

    def candidate(self, index: int) -> tuple[int,int]:
        if type(index) is not int or not 0 <= index < self.count:
            raise ValueError("candidate index outside rational parameter space")
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
            raise ValueError("fiber outside rational parameter space")
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
                    raise RuntimeError("rational parameter iterator exhausted early")


def validate_task(task: Any) -> dict:
    keys(task, {"schema", "parameterization", "campaign_id", "task_id", "search", "fibers", "slice", "execution"},
         {"resume_index", "expected_worker_sha256", "expected_implementation_sha256"}, "rational task")
    if task["schema"] != SCHEMA or task["parameterization"] != PARAMETERIZATION:
        raise ValueError("not an equal-reduced-denominator task; legacy tasks require run_task.py")
    import re
    if not isinstance(task["campaign_id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", task["campaign_id"]):
        raise ValueError("campaign_id must be 1-96 safe ASCII characters")
    p = validate_search(task["search"])
    keys(task["fibers"], {"mode", "q_min", "q_max"}, set(), "fibers")
    if task["fibers"]["mode"] != RationalAQ.MODE:
        raise ValueError("unsupported rational fiber mode")
    qmin = integer(task["fibers"]["q_min"], "q_min", positive=True)
    qmax = integer(task["fibers"]["q_max"], "q_max", positive=True)
    space = RationalAQ(task["search"], qmin, qmax)
    keys(task["slice"], {"start", "stop"}, set(), "slice")
    start = integer(task["slice"]["start"], "slice.start")
    stop = integer(task["slice"]["stop"], "slice.stop", positive=True)
    resume = integer(task.get("resume_index", str(start)), "resume_index")
    if not 0 <= start < stop <= space.count or not start <= resume <= stop:
        raise ValueError("slice/resume outside rational parameter enclosure")
    ex = task["execution"]
    keys(ex, {"time_limit_seconds", "precision_bits", "max_precision_bits", "checkpoint_seconds"}, set(), "execution")
    seconds = small_int(ex["time_limit_seconds"], 1, 6600, "time_limit_seconds")
    precision = small_int(ex["precision_bits"], 64, 16384, "precision_bits")
    maxp = small_int(ex["max_precision_bits"], precision, 65536, "max_precision_bits")
    cps = small_int(ex["checkpoint_seconds"], 1, 60, "checkpoint_seconds")
    if task["task_id"] != task_identity(task):
        raise ValueError("task identity does not match its immutable rational search")
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



def coordinate_congruences(N: int, X: int, b: int, policy: str) -> bool:
    if policy == "none":
        return True
    if policy not in CONGRUENCE_POLICIES:
        raise ValueError("invalid coordinate congruence policy")
    if policy == "rational-mod" and gcd(b,84) != 1:
        raise ValueError("rational-mod requires b coprime to 84")
    factor=1 if policy=="numerators" else b
    return (N-factor)%3==0 and (X-5*factor)%12==0 and X%7!=0


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
    if n.denominator != b or x.denominator != b:
        raise ValueError("n and x must BOTH have the task's exact reduced denominator")
    for key,value in (("n",n),("x",x)):
        if not parsed["bounds"][key+"_min"] <= abs(value) <= parsed["bounds"][key+"_max"]:
            raise ValueError("rational " + key + " is outside the magnitude bounds")
    signs=("p" if n>0 else "n")+("p" if x>0 else "n")
    if search["signs"] not in ("all",signs):
        raise ValueError("rational certificate violates sign policy")
    N,X=n.numerator,x.numerator
    if not coordinate_congruences(N,X,b,search["congruence_policy"]):
        raise ValueError("rational certificate violates explicit congruence policy")
    # b*|X|*y has an integer square, hence is an integer whenever y is rational.
    M=X*X*(X+6*N)**2+(36*N**3-65*b**3)*X
    if M<0:
        raise ValueError("negative radicand")
    m=isqrt(M)
    if m*m!=M or y!=Fraction(m,b*abs(X)):
        raise ValueError("certificate fails the exact principal square-root check")
    A,S=36*n**3-65,x+6*n
    if y*y!=S*S+A/x or gap!=y-S or A!=-2*d*x*x*gap or d!=-(y+S)/(2*x):
        raise ValueError("certificate fails original unsquared equation")
    if type(record.get("sqrt_integer")) is not bool or record["sqrt_integer"]!=(y.denominator==1):
        raise ValueError("incorrect square-root integer flag")
    if search["require_integer_sqrt"] and y.denominator!=1:
        raise ValueError("principal radical is not an integer")
    if search["require_noninteger_d"] and d.denominator==1:
        raise ValueError("d must be noninteger under this task's policy")
    out={k+s:str(getattr(v,attr)) for k,v in values.items()
         for s,attr in (("_num","numerator"),("_den","denominator"))}
    out["sqrt_integer"]=y.denominator==1
    return out


def validate_hit(record: dict, a: int, q: int, search: dict) -> dict:
    out=verify_record(record,search)
    n,x,y=(rational(out,k) for k in ("n","x","y"))
    if not 0<a<q or gcd(a,q)!=1 or abs(y/abs(x)-1+6*n/x)!=Fraction(a,q):
        raise ValueError("rational certificate belongs to another slope fiber")
    return out


def certificate_key(record: dict) -> str:
    return digest({k: record[k] for k in ("n_num","n_den","x_num","x_den","y_num","y_den","d_num","d_den")})
