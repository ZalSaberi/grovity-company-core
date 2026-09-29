#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SITE = "company.localhost"
APP = "company_core"

REPO_ROOT = Path(__file__).resolve().parent
BENCH_ROOT = REPO_ROOT.parent.parent
PKG_ROOT = REPO_ROOT / "company_core"
TEST_FILE = PKG_ROOT / "tests" / "test_project_views.py"
JS_FILE = PKG_ROOT / "public" / "js" / "project_control.js"


def run(*args: str, cwd: Path | None = None) -> None:
    cmd = list(args)
    print("\n>>>", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd or REPO_ROOT), check=True)


if not TEST_FILE.exists():
    raise SystemExit(f"ERROR: missing test file: {TEST_FILE}")

if not JS_FILE.exists():
    raise SystemExit(
        "ERROR: project_control.js is missing from the expected Frappe app path:\n"
        f"{JS_FILE}"
    )

text = TEST_FILE.read_text(encoding="utf-8")

old = '''        app_root = (
            Path(__file__)
            .resolve()
            .parents[2]
        )

        js_path = (
            app_root
            / "public"
            / "js"
            / "project_control.js"
        )
'''

new = '''        app_package_root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        js_path = (
            app_package_root
            / "public"
            / "js"
            / "project_control.js"
        )
'''

if old in text:
    TEST_FILE.write_text(
        text.replace(old, new, 1),
        encoding="utf-8",
    )
    print("PATCHED: company_core/tests/test_project_views.py")
elif new in text:
    print("SKIP: test path is already fixed.")
else:
    raise SystemExit(
        "ERROR: Could not find the expected path block in test_project_views.py.\n"
        "No changes were made."
    )

print("\n=== VERIFY ACTUAL JS PATH ===")
print(JS_FILE)
print("EXISTS:", JS_FILE.exists())

print("\n=== STATIC CHECK ===")
run(
    sys.executable,
    "-m",
    "compileall",
    "-q",
    str(PKG_ROOT),
)

print("\n=== TARGETED PHASE 2E TESTS ===")
run(
    "bench",
    "--site",
    SITE,
    "run-tests",
    "--app",
    APP,
    "--module",
    "company_core.tests.test_project_views",
    cwd=BENCH_ROOT,
)

print("\n=== FULL REGRESSION SUITE ===")
run(
    "bench",
    "--site",
    SITE,
    "run-tests",
    "--app",
    APP,
    cwd=BENCH_ROOT,
)

print("\n" + "=" * 72)
print("PHASE 2E TEST PATH FIX FINISHED SUCCESSFULLY")
print("Expected total: 49 integration tests, all OK.")
print("=" * 72)

run(
    "git",
    "status",
    "--short",
    cwd=REPO_ROOT,
)
