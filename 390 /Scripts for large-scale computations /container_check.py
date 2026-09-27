#!/usr/bin/env python3
"""Run CE390's real worker in restricted Docker containers and verify its returns.

Requires Python 3.10+ and a working Docker CLI/daemon. No CE jobs are submitted.
Evidence is retained in a new, empty --output-dir, including failures.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import uuid

from run_task import load_json, sha256_file, validate_task


ROOT = Path(__file__).resolve().parent


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


class Check:
    def __init__(self, image: str, output: Path):
        self.output = output
        self.image = image
        self.uid = os.getuid() or 10001
        self.gid = os.getgid() if os.getuid() else 10001
        self.commands: list[dict] = []
        self.containers: list[dict] = []
        self.worker_sha256: str | None = None
        self.report: dict = {
            "schema": "ce390-container-check-v1", "status": "running",
            "requested_image": image, "non_root_user": f"{self.uid}:{self.gid}",
            "commands": self.commands, "containers": self.containers,
            "limitations": ["Local Docker validation, not a Charity Engine submission.",
                            "Short deadlines test continuation; they do not establish hour-long performance.",
                            "An empty verified hit file does not establish existence of a solution."],
        }
        (output / "commands").mkdir()

    def command(self, argv: list[str], *, timeout: int = 120, check: bool = True) -> str:
        stem = f"{len(self.commands) + 1:03d}"
        entry = {"argv": argv, "display": shlex.join(argv), "timeout_seconds": timeout,
                 "stdout": f"commands/{stem}.stdout.txt", "stderr": f"commands/{stem}.stderr.txt"}
        self.commands.append(entry)
        started = time.monotonic()
        try:
            result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=timeout, cwd=ROOT)
            stdout, stderr, returncode = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            returncode = None
            entry["timed_out"] = True
        except OSError as exc:
            stdout, stderr, returncode = "", str(exc) + "\n", None
            entry["launch_error"] = str(exc)
        entry.update(returncode=returncode, elapsed_seconds=round(time.monotonic() - started, 6))
        (self.output / entry["stdout"]).write_text(stdout, encoding="utf-8")
        (self.output / entry["stderr"]).write_text(stderr, encoding="utf-8")
        save(self.output / "report.json", self.report)
        if check and returncode != 0:
            raise RuntimeError(f"Command failed ({returncode}): {shlex.join(argv)}; see commands/{stem}.*.txt")
        return stdout

    def container(self, label: str, task_path: Path, results: Path, *, mode: str,
                  expected_exit: int = 0, check_image_files: bool = False,
                  stop_after_checkpoint: bool = False) -> dict:
        inputs = self.output / "inputs" / label
        inputs.mkdir(parents=True)
        shutil.copyfile(task_path, inputs / "task.json")
        inputs.chmod(0o755)
        (inputs / "task.json").chmod(0o644)
        results.mkdir(parents=True)
        results.chmod(0o777 if os.getuid() == 0 else 0o755)
        evidence = self.output / "containers" / label
        evidence.mkdir(parents=True)
        # UUID prevents collisions with other checks running on the same daemon.
        name = "ce390-check-" + uuid.uuid4().hex[:16]
        record = {"label": label, "name": name, "mode": mode,
                  "task_sha256": sha256_file(inputs / "task.json"),
                  "results": str(results.relative_to(self.output))}
        self.containers.append(record)
        argv = ["docker", "create", "--name", name, "--network", "none", "--cpus", "1",
                "--memory", "512m", "--memory-swap", "512m", "--pids-limit", "64",
                "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--user", f"{self.uid}:{self.gid}", "--env", "PYTHONDONTWRITEBYTECODE=1",
                "--tmpfs", "/tmp:rw,nosuid,nodev,size=16m",
                "--mount", f"type=bind,src={inputs},dst=/local/input,readonly",
                "--mount", f"type=bind,src={results},dst=/local/output"]
        if mode == "override":
            argv.extend(["--entrypoint", "/app/run_task.sh"])
        argv.append(self.image)
        if mode == "explicit":
            argv.extend(["/app/run_task.sh", "--task", "/local/input/task.json",
                         "--output-dir", "/local/output"])
        require(mode in {"default", "explicit", "override"}, "Unknown launch mode")
        created = False
        try:
            self.command(argv)
            created = True
            if check_image_files:
                files = evidence / "image-files"
                files.mkdir()
                for name_in_app in ("run_task.py", "verify.py", "campaign.py", "run_task.sh", "container_entrypoint.sh"):
                    self.command(["docker", "cp", f"{name}:/app/{name_in_app}", str(files / name_in_app)])
                    require(sha256_file(files / name_in_app) == sha256_file(ROOT / name_in_app),
                            f"Image source differs from this checkout: {name_in_app}")
                self.command(["docker", "cp", f"{name}:/app/bin/cf_worker", str(files / "cf_worker")])
                self.worker_sha256 = sha256_file(files / "cf_worker")
                self.report["worker_sha256"] = self.worker_sha256
            # Do not --rm: retain inspect/log evidence even when the process fails.
            if stop_after_checkpoint:
                self.command(["docker", "start", name])
                wait_until = time.monotonic() + 5
                started = False
                while time.monotonic() < wait_until:
                    if (results / "status.json").is_file():
                        before_signal = load_json(results / "status.json")
                        if (before_signal.get("state") == "running"
                                and int(before_signal["counters_this_invocation"]["fibers_completed"]) > 0):
                            record["before_signal"] = before_signal
                            started = True
                            break
                    time.sleep(0.05)
                require(started, f"{label}: no checkpoint proving actual worker progress within five seconds")
                self.command(["docker", "stop", "--time", "10", name], timeout=20)
            else:
                self.command(["docker", "start", "--attach", name], timeout=180, check=False)
                record["attach_returncode"] = self.commands[-1]["returncode"]
            inspected = json.loads(self.command(["docker", "inspect", name]))[0]
            save(evidence / "inspect.json", inspected)
            record["state"] = inspected["State"]
            logs = self.command(["docker", "logs", name], check=False)
            (evidence / "combined-stdout.log").write_text(logs, encoding="utf-8")
            state = inspected["State"]
            require(not state["Running"] and not state.get("OOMKilled", False),
                    f"{label}: container still running or killed for exceeding memory")
            require(state["ExitCode"] == expected_exit,
                    f"{label}: expected exit {expected_exit}, received {state['ExitCode']}")
            if not stop_after_checkpoint:
                require(record["attach_returncode"] == expected_exit,
                        f"{label}: Docker attach did not report the expected exit status")
            require(record["task_sha256"] == sha256_file(inputs / "task.json"),
                    f"{label}: input task changed")
            if expected_exit:
                failures = list(results.glob("startup-error-*.json"))
                require(bool(failures), f"{label}: startup error was not retrievable")
                require(all(load_json(p).get("state") == "error" for p in failures),
                        f"{label}: invalid startup-error artifact")
                return {}
            require(not list(results.glob("startup-error-*.json")), f"{label}: unexpected startup error")
            status = load_json(results / "status.json")
            returned = load_json(results / "task.json")
            validate_task(returned)
            require(returned["search"].get("require_integer_sqrt") is True
                    and returned["search"]["signs"] == "all", f"{label}: search policy changed")
            require(status["state"] in {"partial", "complete"}, f"{label}: unsuccessful worker state")
            require(float(status["elapsed_seconds"]) <= returned["execution"]["time_limit_seconds"] + 10,
                    f"{label}: worker exceeded its budget plus the 10-second test tolerance")
            require(status["worker_sha256"] == self.worker_sha256, f"{label}: worker hash mismatch")
            require(returned == load_json(task_path), f"{label}: returned task differs from submitted task")
            if stop_after_checkpoint:
                require(status["state"] == "partial" and status["reason"] == "signal",
                        f"{label}: SIGTERM did not produce a clean partial return")
                continuation = load_json(results / "continuation.task.json")
                validate_task(continuation)
                checkpoint = load_json(results / "checkpoint.json")
                require(continuation["task_id"] == returned["task_id"] == checkpoint["task_id"]
                        and continuation["resume_index"] == status["next_index"] == checkpoint["next_index"]
                        and continuation["expected_worker_sha256"] == self.worker_sha256 == checkpoint["worker_sha256"],
                        f"{label}: signal continuation lost task identity, cursor, or worker pin")
            record["status"] = status
            return status
        finally:
            if created:
                self.command(["docker", "rm", "--force", name], check=False)

    def collect(self, page: Path, results: Path, collected: Path, *, require_complete: bool = True) -> dict:
        self.command([sys.executable, str(ROOT / "collector.py"), "--page", str(page),
                      "--results-dir", str(results), "--output-dir", str(collected)], check=False)
        require(self.commands[-1]["returncode"] == (0 if require_complete else 2),
                "Collector exit status does not match the expected coverage")
        summary = load_json(collected / "summary.json")
        require(summary["complete_selected_page"] == require_complete and not summary["error_returns"]
                and not summary["running_returns"] and not summary["missing_tasks"], "Incomplete or failed coverage")
        require(all((not require_complete or not t["gaps"]) and t["overlapping_returned_indices"] == "0"
                    for t in summary["tasks"]), "Coverage gaps or overlapping retained indices")
        self.command([sys.executable, str(ROOT / "verify.py"), str(collected / "hits.jsonl"),
                      "--require-integer-sqrt", "--signs", "all"])
        return summary

    def run(self, resume_candidates: int | None, max_invocations: int) -> None:
        self.command(["docker", "version"])
        inspected = json.loads(self.command(["docker", "image", "inspect", self.image]))[0]
        save(self.output / "image-inspect.json", inspected)
        require(inspected["Os"] == "linux" and inspected["Architecture"] == "amd64",
                "CE390 deployment image must be linux/amd64")
        self.image = inspected["Id"]  # Pin every invocation to the inspected image.
        self.report.update(image_id=self.image, image_repo_digests=inspected.get("RepoDigests", []))

        supplied = ROOT / "examples" / "pilot"
        pages = sorted(supplied.glob("page-*.json"))
        require(len(pages) == 1, "Expected exactly one supplied pilot page")
        page = load_json(pages[0])
        require(len(page["tasks"]) == 1, "Expected one task in the supplied pilot page")
        pilot_task = supplied / page["tasks"][0]["file"]
        saved_pilot = self.output / "supplied-pilot"
        saved_pilot.mkdir()
        for path in (pages[0], pilot_task):
            shutil.copyfile(path, saved_pilot / path.name)
        self.report["supplied_pilot_sha256"] = {p.name: sha256_file(p) for p in (pages[0], pilot_task)}
        status = self.container("pilot", pilot_task, self.output / "pilot-results" / "run-01",
                                mode="default", check_image_files=True)
        require(status["complete"], "Supplied pilot did not complete within its assigned budget")
        self.report["pilot"] = self.collect(saved_pilot / pages[0].name, self.output / "pilot-results",
                                           self.output / "pilot-collected")

        # Aim for about four seconds of real worker time, with 1-second budgets.
        # The cap bounds work on unusually fast or noisy machines; lack of an
        # observed interruption is a failure, never a claimed continuation pass.
        count = resume_candidates or max(60000, min(2000000, math.ceil(
            4 * int(status["next_index"]) / max(float(status["elapsed_seconds"]), 0.01))))
        self.report["continuation_candidate_indices"] = count
        generated = self.output / "continuation-tasks"
        self.command([sys.executable, str(ROOT / "campaign.py"), "--campaign-id", "ce390-container-continuation",
                      "--q-min", "100000001", "--q-max", str(100000001 + 2 * (count - 1)),
                      "--candidates-per-task", str(count), "--task-count", "1", "--seconds", "1",
                      "--checkpoint-seconds", "1", "--require-integer-sqrt", "--signs", "all",
                      "--output-dir", str(generated)])
        next_task = next(generated.glob("task-*.json"))
        original = load_json(next_task)
        cursor = 0
        partials = 0
        for i in range(1, max_invocations + 1):
            results = self.output / "continuation-results" / f"run-{i:02d}"
            status = self.container(f"continuation-{i:02d}", next_task, results, mode="explicit")
            require(status["task_id"] == original["task_id"], "Continuation changed task identity")
            require(int(status["invocation_coverage"]["start"]) == cursor, "Continuation skipped or replayed retained indices")
            cursor = int(status["next_index"])
            if status["complete"]:
                require(cursor == count, "Completed continuation has wrong final cursor")
                break
            require(status["reason"] == "time_limit", "Partial task was not interrupted by its deadline")
            partials += 1
            next_task = results / "continuation.task.json"
            require(next_task.is_file(), "Missing retrievable continuation task")
            continuation = load_json(next_task)
            validate_task(continuation)
            require(int(continuation["resume_index"]) == cursor
                    and continuation["expected_worker_sha256"] == self.worker_sha256,
                    "Continuation lost its cursor or worker pin")
        else:
            raise RuntimeError(f"Continuation did not finish after {max_invocations} containers; inspect retained evidence")
        require(partials > 0, "No real deadline observed; rerun with a larger --resume-candidates value")
        self.report["deadline_interruptions"] = partials
        self.report["continuation"] = self.collect(next(generated.glob("page-*.json")),
            self.output / "continuation-results", self.output / "continuation-collected")

        signal_tasks = self.output / "signal-tasks"
        self.command([sys.executable, str(ROOT / "campaign.py"), "--campaign-id", "ce390-container-signal",
                      "--q-min", "100000001", "--q-max", "119999999",
                      "--candidates-per-task", "10000000", "--task-count", "1", "--seconds", "60",
                      "--checkpoint-seconds", "1", "--require-integer-sqrt", "--signs", "all",
                      "--output-dir", str(signal_tasks)])
        self.container("signal", next(signal_tasks.glob("task-*.json")),
                       self.output / "signal-results" / "run-01", mode="explicit", stop_after_checkpoint=True)
        self.report["signal"] = self.collect(next(signal_tasks.glob("page-*.json")),
            self.output / "signal-results", self.output / "signal-collected", require_complete=False)

        invalid = self.output / "invalid-task.json"
        save(invalid, {"schema": "deliberately-invalid-validation-input"})
        self.container("invalid-input", invalid, self.output / "invalid-results", mode="override", expected_exit=2)
        self.report["status"] = "passed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="already-built linux/amd64 Docker image tag or digest")
    parser.add_argument("--output-dir", type=Path, required=True, help="new or empty host directory for all evidence")
    parser.add_argument("--resume-candidates", type=int, help="override the adaptive continuation-test size (at least 60000)")
    parser.add_argument("--max-invocations", type=int, default=20, help="maximum one-second continuation containers (default: 20)")
    args = parser.parse_args()
    if args.resume_candidates is not None and args.resume_candidates < 60000:
        parser.error("--resume-candidates must be at least 60000")
    if not 2 <= args.max_invocations <= 100:
        parser.error("--max-invocations must be between 2 and 100")
    output = args.output_dir.resolve()
    if "," in str(output):
        parser.error("--output-dir must not contain a comma (Docker mount syntax)")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error("--output-dir must be new or empty; prior evidence is never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    checker = Check(args.image, output)
    started = time.monotonic()
    try:
        checker.run(args.resume_candidates, args.max_invocations)
    except (OSError, ValueError, KeyError, RuntimeError, StopIteration) as exc:
        checker.report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        checker.report["elapsed_seconds"] = round(time.monotonic() - started, 6)
        save(output / "report.json", checker.report)
    print(json.dumps({"status": checker.report["status"], "report": str(output / "report.json"),
                      "error": checker.report.get("error")}, sort_keys=True))
    return 0 if checker.report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
