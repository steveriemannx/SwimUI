#!/usr/bin/env python3
"""Swim test runner.

Each test is a ``.sw`` program in ``tests/cases``; its expected stdout lives in
``tests/expected/<name>.out``.  Programs in ``tests/errors`` are expected to
fail to compile; the first line of ``tests/errors/<name>.err`` is a substring
that must appear in the compiler output.

Usage:
    python3 tests/run_tests.py [--filter SUBSTR] [--update] [--jobs N]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import difflib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SWIM = ROOT / "bin" / "Swim"
CASES = ROOT / "tests" / "cases"
PROJECTS = ROOT / "tests" / "projects"
EXPECTED = ROOT / "tests" / "expected"
ERRORS = ROOT / "tests" / "errors"


def case_flags(case: Path) -> list[str]:
    """Optional ``<name>.flags`` file with extra compiler flags (e.g. -D X)."""
    flags_file = case.with_suffix(".flags")
    if flags_file.exists():
        return flags_file.read_text(encoding="utf8").split()
    return []


def run_program(path: Path) -> tuple[int, str, str]:
    env = dict(os.environ)
    env.setdefault("SWIM_CACHE", str(Path(tempfile.gettempdir()) /
                                     "Swim-test-cache"))
    cmd = [str(SWIM), "run", *case_flags(path), str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout, proc.stderr


def expected_path(name: str) -> Path:
    return EXPECTED / (name + ".out")


def check_case(case: Path, update: bool) -> tuple[bool, str]:
    name = case.stem
    if case.parent.parent == PROJECTS:
        name = case.parent.name
    code, out, err = run_program(case)
    if code != 0:
        return False, f"{name}: program exited with {code}\n{err}"
    exp = expected_path(name)
    if update:
        exp.parent.mkdir(parents=True, exist_ok=True)
        exp.write_text(out)
        return True, f"{name}: updated"
    if not exp.exists():
        return False, f"{name}: missing expected output ({exp})"
    want = exp.read_text()
    if out == want:
        return True, ""
    diff = "\n".join(difflib.unified_diff(
        want.splitlines(), out.splitlines(),
        fromfile="expected", tofile="actual", lineterm=""))
    return False, f"{name}: output mismatch\n{diff}"


def check_error_case(case: Path) -> tuple[bool, str]:
    name = case.stem
    if case.parent != ERRORS:
        name = case.parent.name
    code, out, err = run_program(case)
    if code == 0:
        return False, f"{name}: expected a compile error, but it compiled"
    err_file = ERRORS / (name + ".err")
    if err_file.exists():
        text = err_file.read_text().strip()
        if not text:
            return True, ""
        needle = text.splitlines()[0]
        combined = out + err
        if needle not in combined:
            return False, (f"{case.name}: expected error containing "
                           f"{needle!r}, got:\n{combined}")
    return True, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", default="")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    cases = sorted(CASES.glob("*.sw"))
    projects = sorted(PROJECTS.glob("*/main.sw")) if PROJECTS.exists() else []
    cases += projects
    errors = sorted(ERRORS.glob("*.sw"))
    if ERRORS.exists():
        errors += sorted(ERRORS.glob("*/main.sw"))
    if args.filter:
        cases = [c for c in cases
                 if args.filter in (c.parent.name if c.name == "main.sw"
                                    else c.stem)]
        errors = [c for c in errors
                  if args.filter in (c.parent.name if c.name == "main.sw"
                                     else c.stem)]

    failures: list[str] = []
    passed = 0

    def job(case: Path) -> tuple[bool, str]:
        is_error = case.parent == ERRORS or case.parent.parent == ERRORS
        if is_error:
            return check_error_case(case)
        return check_case(case, args.update)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(job, c): c for c in cases + errors}
        for fut in concurrent.futures.as_completed(futures):
            ok, msg = fut.result()
            if ok:
                passed += 1
                if args.verbose and msg:
                    print(msg)
            else:
                failures.append(msg)

    total = len(cases) + len(errors)
    for msg in failures:
        print(msg)
        print("-" * 60)
    print(f"{passed}/{total} tests passed")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
