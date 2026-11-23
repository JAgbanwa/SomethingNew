#!/usr/bin/env python3
"""Check an already-built search image using local Docker, without network or CE.

Example (after building the image separately):
  python3 container_check.py --image primitive375:local --output-dir container-check

The output directory must be empty. It receives generated fixtures, container
outputs, independently collected results, logs and report.json. No image is
built or pulled. Every container uses --network none and is removed afterwards.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

from gap_common import METHOD, PAGE_SCHEMA, TASK_SCHEMA, atomic_json, load_json, sha256_file, verify_hit

ROOT = Path(__file__).resolve().parent
KNOWN_600 = (358469562197, -313190404198, -248487937861)


def text_output(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


class Harness:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.runtime_image = args.image
        self.out = args.output_dir.resolve()
        self.docker = shutil.which(args.docker)
        if not self.docker:
            raise ValueError("Docker CLI is unavailable; run this integration check on a Docker-enabled host or CI runner")
        if not args.image or args.image.startswith("-") or args.image.startswith("docker:") \
                or any(char.isspace() for char in args.image):
            raise ValueError("--image must be a local Docker image tag or digest, without the CE 'docker:' prefix")
        if args.timeout <= 0:
            raise ValueError("--timeout must be positive")
        if "," in str(self.out):
            raise ValueError("--output-dir cannot contain a comma because Docker --mount uses comma delimiters")
        if self.out.exists() and any(self.out.iterdir()):
            raise ValueError("--output-dir must be empty; preserve previous test evidence in its existing directory")
        self.source_hash = sha256_file(ROOT / "src" / "gap_worker.cpp")
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "logs").mkdir()
        self.environment = dict(os.environ)
        self.environment.pop("CE_AUTH_TOKEN", None)
        self.run_id = uuid.uuid4().hex[:12]
        self.report = {"schema": "ce375-container-check-v1", "state": "running", "image": args.image,
                       "expected_worker_source_sha256": self.source_hash, "checks": []}

    def execute(self, name: str, command: list[str], *, timeout: int | None = None) -> str:
        started = time.monotonic()
        stdout, stderr, exit_code = "", "", None
        error = None
        try:
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    env=self.environment, timeout=timeout or self.args.timeout, check=False)
            stdout, stderr, exit_code = result.stdout, result.stderr, result.returncode
            if exit_code != 0:
                error = f"{name} exited with status {exit_code}; see logs/{name}.stderr.log"
        except subprocess.TimeoutExpired as exc:
            stdout, stderr = text_output(exc.stdout), text_output(exc.stderr)
            error = f"{name} exceeded its timeout; see logs/{name}.stdout.log and stderr.log"
        finally:
            (self.out / "logs" / f"{name}.stdout.log").write_text(stdout, encoding="utf-8")
            (self.out / "logs" / f"{name}.stderr.log").write_text(stderr, encoding="utf-8")
            self.report["checks"].append({"name": name, "command": command, "exit_code": exit_code,
                                           "seconds": round(time.monotonic() - started, 3), "error": error})
        if error:
            raise RuntimeError(error)
        return stdout

    def container(self, name: str, arguments: list[str] | None = None, *, input_dir: Path | None = None,
                  output_dir: Path | None = None, copy_index: int | None = None) -> str:
        container_name = f"ce375-check-{self.run_id}-{name}"
        command = [self.docker, "run", "--rm", "--pull=never", "--name", container_name,
                   "--network", "none", "--read-only", "--cpus", "2", "--memory", "512m",
                   "--tmpfs", "/tmp:rw,nosuid,size=64m"]
        if hasattr(os, "getuid"):
            command += ["--user", f"{os.getuid()}:{os.getgid()}"]
        if input_dir is not None:
            command += ["--mount", f"type=bind,source={input_dir.resolve()},target=/local/input,readonly"]
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            command += ["--mount", f"type=bind,source={output_dir.resolve()},target=/local/output"]
        if copy_index is not None:
            command += ["--env", f"CE_JOB_COPY={copy_index}"]
        command.append(self.runtime_image)
        command += arguments or []
        try:
            return self.execute(name, command)
        finally:
            # Killing a timed-out docker client does not reliably stop the
            # daemon's container. Explicitly remove this uniquely named one.
            try:
                subprocess.run([self.docker, "rm", "--force", container_name], capture_output=True,
                               env=self.environment, timeout=15, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass

    @staticmethod
    def task(campaign: str, task_id: str, lo: int, hi: int) -> dict:
        return {"schema": TASK_SCHEMA, "method": METHOD, "campaign_id": campaign, "task_id": task_id,
                "k": 375, "d_start": str(lo), "d_stop": str(hi), "ratio_max": 64,
                "primitive_only": True, "height_min": "0", "deadline_seconds": 20}

    @staticmethod
    def page(campaign: str, tasks: list[dict]) -> dict:
        return {"schema": PAGE_SCHEMA, "method": METHOD, "campaign_id": campaign, "k": 375,
                "d_start": tasks[0]["d_start"], "d_stop": tasks[-1]["d_stop"], "ratio_max": 64,
                "primitive_only": True, "height_min": "0", "rho": None,
                "tasks": [{"task_id": task["task_id"], "d_start": task["d_start"], "d_stop": task["d_stop"]}
                          for task in tasks]}

    def check_task(self, task: dict, output: Path, worker_hash: str) -> None:
        status = load_json(output / "status.json")
        checkpoint = load_json(output / "checkpoint.json")
        if load_json(output / "task.json") != task:
            raise ValueError(f"returned task differs from its input: {task['task_id']}")
        for record in (status, checkpoint):
            if record.get("task_id") != task["task_id"] or record.get("campaign_id") != task["campaign_id"]:
                raise ValueError(f"wrong task identity: {task['task_id']}")
            if record.get("worker_sha256") != worker_hash:
                raise ValueError(f"task used a different worker binary: {task['task_id']}")
            if not record.get("primitive_only") or int(record.get("height_min", -1)) != 0:
                raise ValueError(f"search constraints changed: {task['task_id']}")
        if status.get("state") != "complete" or int(checkpoint["covered_start"]) != int(task["d_start"]) \
                or int(checkpoint["d_next"]) != int(task["d_stop"]):
            raise ValueError(f"task did not completely cover its small test interval: {task['task_id']}")

    def collect(self, name: str, page: Path, results: Path, expected_count: int) -> dict:
        output = self.out / "collected" / name
        self.execute(f"collect-{name}", [sys.executable, str(ROOT / "collect_gap.py"), "--page", str(page),
                                         "--results", str(results), "--output-dir", str(output), "--require-complete"])
        summary = load_json(output / "summary.json")
        if summary["errors"] or summary["gaps"] or summary["d_values_covered"] != expected_count:
            raise ValueError(f"collector did not certify the expected coverage for {name}")
        return summary

    def run(self) -> int:
        try:
            image_id = self.execute("image-inspect", [self.docker, "image", "inspect", "--format", "{{.Id}}", self.args.image],
                                    timeout=min(30, self.args.timeout)).strip()
            if not image_id.startswith("sha256:"):
                raise ValueError("Docker did not return an immutable local image ID")
            self.report["image_id"] = image_id
            self.runtime_image = image_id  # Every launch tests the same image even if its tag moves.
            source_code = (
                "import hashlib,json,pathlib; p=pathlib.Path('/app/src/gap_worker.cpp'); "
                "s=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "
                "pathlib.Path('/app/source.sha256').read_text().split()[0]; "
                "b=hashlib.sha256(pathlib.Path('/app/bin/gap_worker').read_bytes()).hexdigest(); "
                "print(json.dumps({'source_sha256':s,'worker_sha256':b}))"
            )
            identity = json.loads(self.container("worker-identity", ["python3", "-c", source_code]))
            if identity["source_sha256"] != self.source_hash:
                raise ValueError("container source SHA-256 differs from this checkout; rebuild the intended image")
            self.report.update(identity)

            campaign = "container-check-bundle"
            tasks = [self.task(campaign, f"{campaign}-{i}", 1000 + i * 1000, 2000 + i * 1000) for i in range(2)]
            bundle_input = self.out / "fixtures" / "bundle" / "input"
            bundle_input.mkdir(parents=True)
            atomic_json(bundle_input / "bundle.json", {"schema": "ce375-bundle-v1", "campaign_id": campaign,
                        "groups": [tasks], "max_instance_hours": 1, "cores_per_instance": 2,
                        "total_reserved_core_hours": 2, "worker_source_sha256": self.source_hash})
            bundle_page = bundle_input.parent / "page.json"
            atomic_json(bundle_page, self.page(campaign, tasks))
            bundle_output = self.out / "results" / "bundle"
            self.container("bundle-default-entrypoint", input_dir=bundle_input, output_dir=bundle_output, copy_index=0)
            bundle_status = load_json(bundle_output / "bundle.status.json")
            if bundle_status.get("state") != "complete" or len(bundle_status.get("tasks", [])) != 2:
                raise ValueError("default entrypoint did not finish both bundled tasks")
            for task in tasks:
                self.check_task(task, bundle_output / task["task_id"], identity["worker_sha256"])
            self.report["bundle_summary"] = self.collect("bundle", bundle_page, bundle_output, 2000)

            campaign = "container-check-single"
            task = self.task(campaign, f"{campaign}-0", 3000, 4000)
            single_input = self.out / "fixtures" / "single" / "input"
            single_input.mkdir(parents=True)
            atomic_json(single_input / "task.json", task)
            single_page = single_input.parent / "page.json"
            atomic_json(single_page, self.page(campaign, [task]))
            single_output = self.out / "results" / "single"
            self.container("single-argument-entrypoint", ["--deadline-seconds", "20", "--chunk", "256"],
                           input_dir=single_input, output_dir=single_output)
            self.check_task(task, single_output, identity["worker_sha256"])
            self.report["single_summary"] = self.collect("single", single_page, single_output, 1000)

            # This historical primitive solution exercises a positive result,
            # large exact arithmetic, and another non-cubefree input in the
            # actual compiled image. Only three nearby d values are searched.
            x, y, z = KNOWN_600
            d = abs(x + y)
            expected = {"k": 600, "x": str(x), "y": str(y), "z": str(z), "d": str(d)}
            verify_hit(expected, 600, primitive_only=True)
            native = self.container("known-primitive-600", ["/app/bin/gap_worker", "--k", "600",
                                    "--d-start", str(d - 1), "--d-stop", str(d + 2), "--ratio-max", "6",
                                    "--primitive-only", "--height-min", "0", "--deadline-seconds", "20", "--chunk", "3"])
            records = [json.loads(line) for line in native.splitlines() if line.strip()]
            hits = [record for record in records if record.get("type") == "hit"]
            for hit in hits:
                verify_hit(hit, 600, primitive_only=True)
            if not any(sorted(int(hit[key]) for key in ("x", "y", "z")) == sorted(KNOWN_600) for hit in hits):
                raise ValueError("the container failed to rediscover the known primitive 600 solution")
            ends = [record for record in records if record.get("type") == "end"]
            if not ends or ends[-1].get("state") != "complete" or int(ends[-1]["d_next"]) != d + 2:
                raise ValueError("known-solution native check did not finish its three-d interval")
            self.report["known_primitive_600"] = expected
            self.report["state"] = "passed"
            print(f"Container checks passed for {self.args.image} ({image_id}).")
            print(f"Two bundled tasks, one single task, source/binary identity, complete collection, and primitive 600 verified.")
            print(f"Evidence: {self.out / 'report.json'}")
            return 0
        except Exception as exc:
            self.report.update(state="failed", error=str(exc))
            raise
        finally:
            atomic_json(self.out / "report.json", self.report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", required=True, help="already-built local Docker image tag or digest")
    parser.add_argument("--output-dir", type=Path, required=True, help="empty directory for fixtures, outputs and evidence")
    parser.add_argument("--docker", default="docker", help="Docker CLI executable (default: docker)")
    parser.add_argument("--timeout", type=int, default=120, help="maximum seconds for each command (default 120)")
    args = parser.parse_args(argv)
    try:
        return Harness(args).run()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f"container_check: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
