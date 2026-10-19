#!/usr/bin/env python3
"""Run extraction, app scenarios, and labeled annotation scoring."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--rules-only", action="store_true", help="Skip all local LLM calls")
    parser.add_argument("--models", help="Comma-separated local 8B/3B Ollama model tags")
    parser.add_argument("--limit", type=int, help="Optional case limit for a smoke run")
    args = parser.parse_args()
    base = [sys.executable]
    scripts = ROOT / "evaluation" / "scripts"
    latest = ROOT / "evaluation" / "latest"
    commands = [base + [str(scripts / "run_evaluation.py"), "--repeats", str(args.repeats)]]
    system = base + [str(scripts / "run_system_evaluation.py")]
    if args.rules_only:
        system.extend([
            "--rules-only",
            "--output",
            str(latest / "system_rules_only.json"),
        ])
    if args.models:
        system.extend(["--models", args.models])
    if args.limit is not None:
        system.extend(["--limit", str(args.limit)])
    commands.append(system)
    system_results = latest / ("system_rules_only.json" if args.rules_only else "system_results.json")
    commands.append(base + [str(scripts / "score_annotations.py"),
                            "--system-results", str(system_results)])
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
