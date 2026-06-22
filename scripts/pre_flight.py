"""Pre-flight gate for avalone-landing."""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src" / "avalone_landing"


def run(cmd: list[str], timeout: int = 60) -> None:
    print(">>>", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, timeout=timeout)
    if result.returncode != 0:
        print("FAILED")
        sys.exit(1)
    print("OK")


def main() -> None:
    print("=" * 60)
    print("Avalone landing pre-flight")
    print("=" * 60)

    for f in sorted(SRC.rglob("*.py")):
        run([sys.executable, "-m", "py_compile", str(f)])

    tests_dir = ROOT / "tests"
    if tests_dir.exists() and any(tests_dir.iterdir()):
        run([sys.executable, "-m", "pytest", "-q"])
    else:
        print(">>> no tests")

    # Start server briefly and hit healthz
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "avalone_landing.web.app:app",
         "--host", "127.0.0.1", "--port", "8811"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        time.sleep(2)
        run(["curl", "-fsS", "http://127.0.0.1:8811/healthz"], timeout=10)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("=" * 60)
    print("PASS")


if __name__ == "__main__":
    main()
