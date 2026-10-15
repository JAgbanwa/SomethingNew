#!/usr/bin/env python3
"""Independently verify rational-coordinate JSONL under one explicit task policy."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from run_task import load_json, integer
from rational_common import (validate_task, verify_record, rational, candidate_index,
                             certificate_key)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--task", type=Path, required=True)
    args=parser.parse_args()
    try:
        task=load_json(args.task)
        parsed=validate_task(task)
        count=0
        seen=set()
        def unique(pairs):
            out={}
            for k,v in pairs:
                if k in out:
                    raise ValueError("duplicate certificate key")
                out[k]=v
            return out
        with args.input.open(encoding="utf-8") as source:
            for number,line in enumerate(source,1):
                if not line.strip():
                    raise ValueError(f"blank record at line {number}")
                row=json.loads(line,object_pairs_hook=unique)
                hit=verify_record(row,task["search"])
                n,x,y=(rational(hit,k) for k in ("n","x","y"))
                slope=abs(y/abs(x)-1+6*n/x)
                index=candidate_index(parsed,slope.numerator,slope.denominator)
                if not parsed["start"]<=index<parsed["stop"]:
                    raise ValueError(f"line {number} belongs to another task slice")
                if "task_id" in row and row["task_id"]!=task["task_id"]:
                    raise ValueError("certificate task identity mismatch")
                if "candidate_index" in row and integer(row["candidate_index"],"candidate_index")!=index:
                    raise ValueError("certificate index mismatch")
                for k,v in (("a",slope.numerator),("q",slope.denominator)):
                    if k in row and integer(row[k],k,positive=True)!=v:
                        raise ValueError("certificate slope mismatch")
                key=certificate_key(hit)
                if "certificate_sha256" in row and row["certificate_sha256"]!=key:
                    raise ValueError("certificate checksum mismatch")
                seen.add(key)
                count+=1
        print(json.dumps({"status":"verified","certificates":count,"unique_solutions":len(seen),
                          "coordinate_denominator":task["search"]["coordinate_denominator"],
                          "note":"Individual rational certificates only, not search coverage."},sort_keys=True))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(json.dumps({"status":"error","error":str(error)},sort_keys=True))
        return 1


if __name__=="__main__":
    raise SystemExit(main())
