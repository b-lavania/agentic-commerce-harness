"""CLI: python -m ach.harness.cli run-all"""

from __future__ import annotations

import argparse
import sys

from ach.harness.runner import run_all, run_scenario
from ach.harness.trace import document_from_results, write_trace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ach-harness")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_all = sub.add_parser("run-all", help="Run all H1/H2 scenarios")
    p_all.add_argument("--jsonl", default=None, help="Write trajectories JSONL")
    p_all.add_argument("--view", default=None, help="Write a three-lane replay HTML page")

    p_one = sub.add_parser("run", help="Run one scenario file")
    p_one.add_argument("path")
    p_one.add_argument("--jsonl", default=None)
    p_one.add_argument("--view", default=None, help="Write a three-lane replay HTML page")

    args = parser.parse_args(argv)
    if args.cmd == "run-all":
        results = run_all(jsonl_path=args.jsonl)
        failed = [r for r in results if not r.passed]
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            print(f"{status}  {r.scenario_id}  milestones={r.milestones}")
            for f in r.failures:
                print(f"       - {f}")
        print(f"\n{len(results) - len(failed)}/{len(results)} passed")
        if args.view:
            write_trace(args.view, document_from_results(results))
        return 1 if failed else 0

    if args.cmd == "run":
        result = run_scenario(args.path)
        if args.view:
            write_trace(args.view, document_from_results([result], title=result.scenario_id))
        if args.jsonl:
            from pathlib import Path

            path = Path(args.jsonl)
            path.write_text(
                "\n".join(r.model_dump_json() for r in result.trajectories) + "\n",
                encoding="utf-8",
            )
        print("PASS" if result.passed else "FAIL", result.scenario_id)
        for f in result.failures:
            print(" -", f)
        return 0 if result.passed else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
