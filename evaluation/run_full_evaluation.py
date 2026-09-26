#!/usr/bin/env python3
"""Run extraction, full app scenarios, annotation scoring, and paper tables."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--rules-only", action="store_true", help="Skip all local LLM calls")
    parser.add_argument("--models", help="Comma-separated local 8B/3B Ollama model tags")
    parser.add_argument("--limit", type=int, help="Optional case limit for a smoke run")
    args = parser.parse_args()
    base = [sys.executable]
    commands = [base + [str(ROOT / "evaluation" / "run_evaluation.py"), "--repeats", str(args.repeats)]]
    system = base + [str(ROOT / "evaluation" / "run_system_evaluation.py")]
    if args.rules_only:
        system.extend([
            "--rules-only",
            "--output",
            str(ROOT / "evaluation" / "system_rules_only.json"),
        ])
    if args.models:
        system.extend(["--models", args.models])
    if args.limit is not None:
        system.extend(["--limit", str(args.limit)])
    commands.append(system)
    commands.append(base + [str(ROOT / "evaluation" / "score_annotations.py")])
    commands.append(base + [str(ROOT / "evaluation" / "generate_paper_tables.py")])
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
