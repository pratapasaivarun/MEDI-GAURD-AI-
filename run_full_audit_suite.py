from __future__ import annotations
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
results = []
for test in sorted(root.glob("test_*.py")):
    try:
        completed = subprocess.run([sys.executable, str(test)], cwd=root, capture_output=True, text=True, timeout=240)
        output = (completed.stdout + "\n" + completed.stderr).strip()
        status = "PASS" if completed.returncode == 0 else "FAIL"
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        output = (stdout + "\n" + stderr).strip()
        status = "TIMEOUT"
    results.append((test.name, status, output[-4000:]))

report = []
for name, status, output in results:
    report.append(f"=== {name}: {status} ===\n{output}\n")
summary = f"SUMMARY total={len(results)} pass={sum(s == 'PASS' for _, s, _ in results)} fail={sum(s == 'FAIL' for _, s, _ in results)} timeout={sum(s == 'TIMEOUT' for _, s, _ in results)}"
report.append(summary)
print(summary)
for name, status, _ in results:
    print(f"{status}: {name}")
sys.exit(0 if all(status == "PASS" for _, status, _ in results) else 1)
