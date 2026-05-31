from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_step(label: str, command: list[str]) -> int:
    print(f"\n=== {label} ===")
    result = subprocess.run(command, cwd=REPO_ROOT)
    if result.returncode == 0:
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label} -> exit={result.returncode}")
    return result.returncode


def main() -> int:
    failures = 0
    reliability_command = [sys.executable, "scripts/reliability_check.py"]
    if os.name == "nt":
        reliability_command.append("--skip-local-health")
    failures += run_step("Unit Tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]) != 0
    failures += run_step("Reliability Check", reliability_command) != 0

    if failures:
        print(f"\nResult: full check finished with {failures} failed step(s).")
        return 1

    print("\nResult: full check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
