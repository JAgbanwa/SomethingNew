"""Durable, single-controller accounting for a d-first project's core-hour cap.

One invocation reserves one CPU core for its entire wall-clock lifetime. This
is deliberately conservative relative to CPU time. Failed attempts count;
an unsettled reservation is never automatically refunded after a crash.
"""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
import fcntl
from pathlib import Path
from typing import Iterator

from run_task import atomic_json, load_json

MAX_CORE_HOURS = Decimal("1800")
DEFAULT_PLANNED_CORE_HOURS = Decimal("1600")
NANOSECONDS = 1_000_000_000
BUDGET_SCHEMA = "ce390-core-hour-budget-v1"
LEDGER_SCHEMA = "ce390-dfirst-budget-ledger-v1"


def positive_decimal(value: object, name: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a positive finite number") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return number


def limit_nanoseconds(hours: object) -> int:
    value = positive_decimal(hours, "budget_core_hours")
    if value > MAX_CORE_HOURS:
        raise ValueError("this project's budget cannot exceed 1800 core-hours")
    result = int(value * 3600 * NANOSECONDS)
    if result < NANOSECONDS:
        raise ValueError("budget must provide at least one core-second")
    return result


class Ledger:
    def __init__(self, path: Path, identity: str, limit_ns: int):
        self.path = path
        if path.exists():
            self.data = load_json(path)
            if (self.data.get("schema") != LEDGER_SCHEMA
                    or self.data.get("identity") != identity
                    or self.data.get("limit_ns") != limit_ns):
                raise ValueError("budget ledger belongs to another page, output directory, worker or budget")
            if any(a["state"] == "reserved" for a in self.data["attempts"]):
                raise ValueError("unsettled budget reservation: confirm the old process has stopped and "
                                 "reconcile its actual usage before resuming; no hours were refunded")
            charged = sum(a["charged_ns"] for a in self.data["attempts"])
            if charged != self.data["charged_ns"] or charged < 0:
                raise ValueError("budget ledger accounting is inconsistent")
        else:
            if any(p.name != "budget.lock" for p in path.parent.iterdir()):
                raise ValueError("output directory is not empty but has no budget ledger; refusing to reset usage")
            self.data = {"schema": LEDGER_SCHEMA, "identity": identity,
                         "limit_ns": limit_ns, "charged_ns": 0, "attempts": []}
            self.save()

    @property
    def remaining_ns(self) -> int:
        held = sum(a["reserved_ns"] for a in self.data["attempts"] if a["state"] == "reserved")
        return max(0, self.data["limit_ns"] - self.data["charged_ns"] - held)

    def save(self) -> None:
        atomic_json(self.path, self.data)

    def reserve(self, seconds: int, task_id: str, task_file: str, output_dir: str) -> dict | None:
        if seconds <= 0:
            raise ValueError("reservation must be positive")
        amount = seconds * NANOSECONDS
        if amount > self.remaining_ns:
            return None
        entry = {"number": len(self.data["attempts"]), "state": "reserved",
                 "task_id": task_id, "task_file": task_file, "output_dir": output_dir,
                 "reserved_ns": amount, "charged_ns": 0}
        self.data["attempts"].append(entry)
        self.save()  # fsync file and parent directory before any process starts
        return entry

    def settle(self, entry: dict, elapsed_ns: int, **result: object) -> None:
        if entry["state"] != "reserved" or elapsed_ns < 0:
            raise ValueError("invalid or duplicate budget settlement")
        entry.update(result)
        entry["state"] = "settled"
        entry["charged_ns"] = elapsed_ns
        self.data["charged_ns"] += elapsed_ns
        self.save()
        if elapsed_ns > entry["reserved_ns"] or self.data["charged_ns"] > self.data["limit_ns"]:
            raise RuntimeError("measured runtime exceeded its reservation; actual usage was retained, campaign stopped")


@contextmanager
def locked_ledger(output: Path, identity: str, limit_ns: int) -> Iterator[Ledger]:
    output.mkdir(parents=True, exist_ok=True)
    with (output / "budget.lock").open("a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("another controller holds this campaign's budget lock") from exc
        try:
            yield Ledger(output / "budget.json", identity, limit_ns)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
