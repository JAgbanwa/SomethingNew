#!/usr/bin/env python3
"""Validate, stage and submit a bounded Charity Engine primitive-375 campaign.

Default is a local dry run. --submit and --retrieve require CE_AUTH_TOKEN in the
environment. The token is passed only to ce-cli at execution time; plans, ledgers
and logs never contain it. No credentials are forwarded into the compute job.

The ledger reserves each batch's worst-case allocation before invoking ce-cli.
An ambiguous failure remains charged and cannot be submitted again. Retrieval
requires the original nonempty CLI checkpoint and reuses the same arguments.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
from urllib.parse import urlsplit

from gap_common import atomic_json, load_json
from run_ce_bundle import now, validate_bundle

MAX_COPIES = 500
AUTH_PLACEHOLDER = "<CE_AUTH_TOKEN>"
LEDGER_SCHEMA = "ce375-submission-ledger-v1"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def resolve_cli(value: str) -> str:
    found = shutil.which(value)
    if found:
        return str(Path(found).resolve())
    return str(Path(value).expanduser().resolve())


def make_plan(args: argparse.Namespace, bundle: dict) -> dict:
    info = validate_bundle(bundle)
    maximum = Decimal(str(args.max_core_hours))
    if not maximum.is_finite() or maximum <= 0:
        raise ValueError("max-core-hours must be finite and positive")
    if info.reserved_core_hours > maximum:
        raise ValueError(f"allocation reserves {info.reserved_core_hours} core-hours, above the {maximum} limit")
    if not isinstance(args.image, str) or not args.image.startswith("docker:") or len(args.image) <= 7 \
            or any(char.isspace() for char in args.image):
        raise ValueError("--image must be a Docker Hub image of the form docker:owner/image:version")
    app = args.image
    if args.image_tar_url:
        url = args.image_tar_url
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None \
                or parsed.password is not None or parsed.query or parsed.fragment \
                or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in url):
            raise ValueError("--image-tar-url must be a public HTTPS URL without credentials, query or fragment")
        # Official CE custom-container syntax: this entire string is one --app
        # argument, never a shell command or two separate CLI arguments.
        app = f"{args.image} {url}"
    state_dir = Path(args.workdir or (Path(args.manifest).resolve().parent / "ce-launch")).resolve()
    public = {"schema": "ce375-launch-plan-v1", "manifest_sha256": digest(bundle),
              "campaign_id": info.campaign_id, "image": args.image, "image_tar_url": args.image_tar_url,
              "app": app, "instance_type": args.instance_type,
              "ce_cli": resolve_cli(args.ce_cli), "workdir": str(state_dir),
              "max_instance_hours": decimal_text(info.hours), "cores_per_instance": info.cores,
              "max_core_hours": decimal_text(maximum),
              "total_reserved_core_hours": decimal_text(info.reserved_core_hours), "batches": []}
    for offset in range(0, len(info.groups), MAX_COPIES):
        index = offset // MAX_COPIES
        groups = info.groups[offset:offset + MAX_COPIES]
        reserved = len(groups) * info.hours * info.cores
        batch_bundle = dict(bundle, groups=groups, group_offset=offset,
                            parent_manifest_sha256=public["manifest_sha256"],
                            total_reserved_core_hours=float(reserved))
        directory = state_dir / f"batch-{index:04d}"
        checkpoint = directory / "ce-checkpoint.sqlite"
        batch_label = f"{info.campaign_id}-{public['manifest_sha256'][:10]}-{index:04d}"
        command = [public["ce_cli"], "--app", app, "--auth", AUTH_PLACEHOLDER,
                   "--commandline", "python3 /app/run_ce_bundle.py --manifest /local/input/bundle.json --output-dir /local/output",
                   "--instancetype", args.instance_type, "--hours", decimal_text(info.hours),
                   "--copies", str(len(groups)), "--inputfile", str(directory / "bundle.json"),
                   "--checkpoint", "true", "--checkpointfile", str(checkpoint),
                   "--exitafterstart", "true", "--outputdir", str(directory / "results" / "%JOBKEY%"),
                   "--batch", batch_label, "--tag", public["manifest_sha256"],
                   "--result-storage", "temporary"]
        public["batches"].append({"index": index, "group_offset": offset, "copies": len(groups),
                                  "reserved_core_hours": decimal_text(reserved),
                                  "bundle": batch_bundle, "bundle_sha256": digest(batch_bundle),
                                  "inputfile": str(directory / "bundle.json"), "checkpointfile": str(checkpoint),
                                  "command": command, "command_sha256": digest(command)})
    public["plan_sha256"] = digest(public)
    return public


@contextmanager
def locked_workdir(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".ledger.lock").open("a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def stage_plan(plan: dict) -> None:
    """Inputs become immutable once an existing plan or ledger binds this directory."""
    directory = Path(plan["workdir"])
    old_plan_path = directory / "plan.json"
    if old_plan_path.exists() and load_json(old_plan_path).get("plan_sha256") != plan["plan_sha256"]:
        raise ValueError("this workdir already holds a different plan; keep it for retrieval and use a new workdir")
    for batch in plan["batches"]:
        path = Path(batch["inputfile"])
        if path.exists() and digest(load_json(path)) != batch["bundle_sha256"]:
            raise ValueError(f"staged batch input changed: {path}")
    for batch in plan["batches"]:
        path = Path(batch["inputfile"])
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            atomic_json(path, batch["bundle"])
    if not old_plan_path.exists():
        atomic_json(old_plan_path, plan)


def read_ledger(path: Path, plan: dict) -> dict | None:
    if not path.exists():
        return None
    ledger = load_json(path)
    if not isinstance(ledger, dict) or ledger.get("schema") != LEDGER_SCHEMA \
            or ledger.get("plan_sha256") != plan["plan_sha256"]:
        raise ValueError("ledger does not match this exact launch plan")
    expected = {str(batch["index"]): batch for batch in plan["batches"]}
    if set(ledger.get("batches", {})) != set(expected):
        raise ValueError("ledger batch set is inconsistent with the plan")
    total = Decimal(0)
    for key, record in ledger["batches"].items():
        batch = expected[key]
        if record.get("state") not in {"planned", "reserved", "submitted", "unknown"} \
                or record.get("command_sha256") != batch["command_sha256"] \
                or record.get("reserved_core_hours") != batch["reserved_core_hours"]:
            raise ValueError("ledger batch identity or reservation is inconsistent with the plan")
        if record["state"] != "planned":
            total += Decimal(record["reserved_core_hours"])
    if total != Decimal(ledger.get("reserved_core_hours", "-1")) or total > Decimal(plan["max_core_hours"]):
        raise ValueError("ledger reservation total is inconsistent or exceeds the budget")
    return ledger


def new_ledger(plan: dict) -> dict:
    return {"schema": LEDGER_SCHEMA, "plan_sha256": plan["plan_sha256"],
            "manifest_sha256": plan["manifest_sha256"], "campaign_id": plan["campaign_id"],
            "created": now(), "reserved_core_hours": "0", "max_core_hours": plan["max_core_hours"],
            "batches": {str(batch["index"]): {"state": "planned", "command_sha256": batch["command_sha256"],
                                               "reserved_core_hours": batch["reserved_core_hours"]}
                        for batch in plan["batches"]}}


def safe_text(value: str | None, token: str) -> str:
    return (value or "").replace(token, "<redacted>") if token else (value or "")


def invoke(batch: dict, token: str) -> subprocess.CompletedProcess:
    command = list(batch["command"])
    command[command.index("--auth") + 1] = token
    child_env = dict(os.environ)
    child_env.pop("CE_AUTH_TOKEN", None)
    return subprocess.run(command, env=child_env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=False)


def run(args: argparse.Namespace) -> int:
    bundle = load_json(args.manifest)
    plan = make_plan(args, bundle)
    directory = Path(plan["workdir"])
    active = args.submit or args.retrieve
    token = os.environ.get("CE_AUTH_TOKEN", "") if active else ""
    if active and not token.strip():
        raise ValueError("blocked: CE_AUTH_TOKEN is not set; the default dry run needs no credential")
    if active and (not Path(plan["ce_cli"]).is_file() or not os.access(plan["ce_cli"], os.X_OK)):
        raise ValueError("blocked: --ce-cli must point to an executable Charity Engine CLI")
    with locked_workdir(directory):
        ledger_path = directory / "submission-ledger.json"
        ledger = read_ledger(ledger_path, plan)
        stage_plan(plan)
        review = {"mode": "retrieve" if args.retrieve else "submit" if args.submit else "dry-run",
                  "campaign_id": plan["campaign_id"], "manifest_sha256": plan["manifest_sha256"],
                  "instances": sum(batch["copies"] for batch in plan["batches"]),
                  "cores_per_instance": plan["cores_per_instance"],
                  "max_instance_hours": plan["max_instance_hours"],
                  "total_reserved_core_hours": plan["total_reserved_core_hours"],
                  "budget_limit_core_hours": plan["max_core_hours"], "workdir": str(directory),
                  "batches": [{key: batch[key] for key in ("index", "copies", "group_offset", "inputfile",
                                                          "checkpointfile", "reserved_core_hours", "command")}
                              for batch in plan["batches"]]}
        print(json.dumps(review, indent=2, sort_keys=True), flush=True)
        if not active:
            return 0
        if args.retrieve:
            if ledger is None:
                raise ValueError("refusing retrieval: no submission ledger exists; retrieval must never create a job")
            batches = [batch for batch in plan["batches"] if ledger["batches"][str(batch["index"])]["state"] != "planned"]
            if not batches:
                raise ValueError("refusing retrieval: there are no previously reserved batches")
            # Check every batch before making any external call. A missing CLI
            # checkpoint would cause ce-cli to create a job during 'retrieval'.
            for batch in batches:
                checkpoint = Path(batch["checkpointfile"])
                if not checkpoint.is_file() or checkpoint.stat().st_size == 0:
                    raise ValueError(f"refusing retrieval for batch {batch['index']}: the original nonempty CLI checkpoint is absent; reconcile the job in CE before any retry")
        else:
            if ledger is None:
                ledger = new_ledger(plan)
                atomic_json(ledger_path, ledger)
            ambiguous = [key for key, record in ledger["batches"].items() if record["state"] in {"reserved", "unknown"}]
            if ambiguous:
                raise ValueError("refusing resubmission: batches " + ", ".join(ambiguous)
                                 + " have an ambiguous reservation; retrieve with their original checkpoints or reconcile in CE")
            batches = [batch for batch in plan["batches"] if ledger["batches"][str(batch["index"])]["state"] == "planned"]
            for batch in batches:
                if Path(batch["checkpointfile"]).exists():
                    raise ValueError(f"unreserved batch {batch['index']} already has a checkpoint; refusing to guess its ownership")
        assert ledger is not None
        if not batches:
            print("All batches already have reservations; no jobs were submitted. Use --retrieve for results.")
            return 0
        for batch in batches:
            record = ledger["batches"][str(batch["index"])]
            if not args.retrieve:
                total = Decimal(ledger["reserved_core_hours"]) + Decimal(batch["reserved_core_hours"])
                if total > Decimal(plan["max_core_hours"]):
                    raise ValueError("reservation would exceed the hard core-hour budget")
                record.update(state="reserved", reserved_at=now())
                ledger["reserved_core_hours"] = decimal_text(total)
                atomic_json(ledger_path, ledger)  # Must be durable before the external process starts.
            phase = "retrieve" if args.retrieve else "submit"
            try:
                result = invoke(batch, token)
                stdout, stderr = safe_text(result.stdout, token), safe_text(result.stderr, token)
                log_dir = Path(batch["inputfile"]).parent
                (log_dir / f"ce-{phase}.stdout.log").write_text(stdout, encoding="utf-8")
                (log_dir / f"ce-{phase}.stderr.log").write_text(stderr, encoding="utf-8")
                if stdout:
                    print(stdout, end="" if stdout.endswith("\n") else "\n")
                if stderr:
                    print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr)
                record.update(last_action=phase, last_action_at=now(), last_exit_code=result.returncode)
                checkpoint = Path(batch["checkpointfile"])
                checkpoint_ok = checkpoint.is_file() and checkpoint.stat().st_size > 0
                if result.returncode != 0 or not checkpoint_ok:
                    record["state"] = "unknown"
                    atomic_json(ledger_path, ledger)
                    print(f"Batch {batch['index']} is unknown; its core-hour reservation remains charged. "
                          "Do not resubmit it. Preserve the checkpoint and reconcile or retrieve.", file=sys.stderr)
                    return 1
                record["state"] = "submitted"
                atomic_json(ledger_path, ledger)
            except BaseException as exc:
                record.update(state="unknown", last_action=phase, last_action_at=now())
                atomic_json(ledger_path, ledger)
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                # Exception strings from subprocess wrappers can contain argv.
                # Never persist them or echo a credential-bearing command.
                print(f"Batch {batch['index']} is unknown after {type(exc).__name__}; its reservation remains charged.",
                      file=sys.stderr)
                return 1
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--image", required=True, help="docker:owner/image:version; use an immutable version")
    parser.add_argument("--image-tar-url", help="optional public HTTPS docker-save archive; forms CE's single 'docker:image URL' app argument")
    parser.add_argument("--ce-cli", default="ce-cli", help="path to the Charity Engine CLI executable")
    parser.add_argument("--workdir", "--state-dir", type=Path,
                        help="persistent staging, checkpoint and ledger directory (default: manifest directory/ce-launch)")
    parser.add_argument("--instance-type", choices=("C.2x2", "C.2x4"), default="C.2x2")
    parser.add_argument("--max-core-hours", type=float, default=1800,
                        help="hard worst-case allocation limit for this manifest and ledger (default 1800)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--submit", action="store_true", help="submit unreserved batches; needs CE_AUTH_TOKEN")
    mode.add_argument("--retrieve", action="store_true", help="poll/download only already reserved checkpointed batches")
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (OSError, ValueError, KeyError, TypeError, InvalidOperation) as exc:
        print(f"ce_submit: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("ce_submit: interrupted; preserve the ledger and checkpoints before any further action", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
