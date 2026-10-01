#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
PKG_ROOT = REPO_ROOT / "company_core"

TARGET_BRANCH = "phase-3-operations"
COMMIT_MESSAGE = "feat: complete phase 3 operations and notification hardening"

TEMP_PATHS = [
    "apply_phase_3.py",
    "apply_phase_3_notification_hardening.py",
    "finalize_phase_3_notification_hardening.py",
    "fix_phase3_notification_benchmark_v2.py",
    "fix_phase_3_action_owner.py",
    "fix_phase_3_notification_test_isolation.py",
    "fix_phase_3_notification_test_v2.py",
    "rebuild_phase_3_clean.py",
    "recover_phase_3_notification_tests.py",
    "recover_phase_3_notification_tests_v3.py",
    "company_core/recover_phase_3_notification_tests.py",
    "cleanup_checkpoint_phase3.py",
]

PRODUCT_PATHS = [
    ".gitignore",
    "company_core/hooks.py",
    "company_core/company_core/doctype/grovity_notification_settings",
    "company_core/company_core/doctype/meeting_action",
    "company_core/company_core/doctype/meeting_participant",
    "company_core/company_core/doctype/notification_delivery",
    "company_core/company_core/doctype/progress_report",
    "company_core/company_core/doctype/project_meeting",
    "company_core/notification_admin.py",
    "company_core/notification_engine.py",
    "company_core/notification_health.py",
    "company_core/notification_setup.py",
    "company_core/operations_notifications.py",
    "company_core/operations_permissions.py",
    "company_core/operations_service.py",
    "company_core/phase3_health.py",
    "company_core/phase3_notification_benchmark.py",
    "company_core/phase3_operations_benchmark.py",
    "company_core/public/js/meeting_action.js",
    "company_core/public/js/progress_report.js",
    "company_core/public/js/project_meeting.js",
    "company_core/tests/test_phase3_notification_hardening.py",
    "company_core/tests/test_phase3_operations.py",
    "docs/phase_3_operations.md",
]


def run(*args: str, check: bool = True, capture: bool = False):
    cmd = list(args)
    print("\n>>>", " ".join(cmd))
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        check=check,
        text=True,
        capture_output=capture,
    )


def git_output(*args: str) -> str:
    return run("git", *args, capture=True).stdout.strip()


if not (REPO_ROOT / ".git").exists():
    raise SystemExit(
        "ERROR: Run this from the company_core git repository root."
    )

if not (PKG_ROOT / "hooks.py").exists():
    raise SystemExit(
        "ERROR: company_core/hooks.py not found."
    )

required_product_files = [
    "company_core/notification_engine.py",
    "company_core/notification_health.py",
    "company_core/phase3_notification_benchmark.py",
    "company_core/tests/test_phase3_notification_hardening.py",
    "company_core/tests/test_phase3_operations.py",
]

for relative in required_product_files:
    if not (REPO_ROOT / relative).exists():
        raise SystemExit(
            f"ERROR: Required Phase 3 product file is missing: {relative}"
        )


print("=== PHASE 3 REPO CLEANUP + CHECKPOINT ===")

current_branch = git_output(
    "rev-parse",
    "--abbrev-ref",
    "HEAD",
)

print("Current branch:", current_branch)

if current_branch == "phase-2-project-core":
    branches = git_output(
        "branch",
        "--format=%(refname:short)",
    ).splitlines()

    if TARGET_BRANCH in branches:
        raise SystemExit(
            f"ERROR: Branch {TARGET_BRANCH!r} already exists. "
            "Refusing to switch branches with uncommitted Phase 3 work."
        )

    run(
        "git",
        "switch",
        "-c",
        TARGET_BRANCH,
    )

    current_branch = TARGET_BRANCH

elif current_branch != TARGET_BRANCH:
    print(
        f"NOTE: Keeping current branch {current_branch!r}. "
        f"No automatic branch change was made."
    )


# ---------------------------------------------------------------------
# Backup disposable scripts before removing them.
# ---------------------------------------------------------------------

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup_dir = (
    REPO_ROOT
    / ".phase_backups"
    / f"repo-cleanup-phase3-{stamp}"
)
backup_dir.mkdir(
    parents=True,
    exist_ok=True,
)

for relative in TEMP_PATHS:
    path = REPO_ROOT / relative

    if not path.exists():
        continue

    destination = backup_dir / relative
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # This script cannot copy itself over itself while it is still
    # needed; copy first, delete only near the end.
    shutil.copy2(
        path,
        destination,
    )

print(
    "Temporary-script backup:",
    backup_dir.relative_to(REPO_ROOT),
)


# ---------------------------------------------------------------------
# Ensure local backup directory never enters Git.
# ---------------------------------------------------------------------

gitignore = REPO_ROOT / ".gitignore"

gitignore_text = (
    gitignore.read_text(encoding="utf-8")
    if gitignore.exists()
    else ""
)

if ".phase_backups/" not in gitignore_text.splitlines():
    with gitignore.open(
        "a",
        encoding="utf-8",
    ) as handle:
        if gitignore_text and not gitignore_text.endswith("\n"):
            handle.write("\n")
        handle.write(".phase_backups/\n")

    print("UPDATED .gitignore -> .phase_backups/")


# ---------------------------------------------------------------------
# Remove disposable installers/fixers from index and working tree.
# ---------------------------------------------------------------------

for relative in TEMP_PATHS:
    path = REPO_ROOT / relative

    # Unstage if present in index. Failure is harmless for untracked paths.
    run(
        "git",
        "restore",
        "--staged",
        "--",
        relative,
        check=False,
    )

    if relative == "cleanup_checkpoint_phase3.py":
        continue

    if path.is_file():
        path.unlink()
        print("REMOVE ", relative)

    elif path.is_dir():
        shutil.rmtree(path)
        print("REMOVE ", relative)


# ---------------------------------------------------------------------
# Validate that no disposable files remain staged.
# ---------------------------------------------------------------------

cached_names = set(
    git_output(
        "diff",
        "--cached",
        "--name-only",
    ).splitlines()
)

bad_staged = sorted(
    cached_names.intersection(
        set(TEMP_PATHS)
    )
)

if bad_staged:
    raise SystemExit(
        "ERROR: Disposable scripts are still staged:\n"
        + "\n".join(bad_staged)
    )


# ---------------------------------------------------------------------
# Stage only canonical Phase 3 product files.
# ---------------------------------------------------------------------

existing_product_paths = [
    relative
    for relative in PRODUCT_PATHS
    if (REPO_ROOT / relative).exists()
]

run(
    "git",
    "add",
    "--",
    *existing_product_paths,
)


# ---------------------------------------------------------------------
# Repository quality checks.
# ---------------------------------------------------------------------

print("\n=== GIT DIFF CHECK ===")
run(
    "git",
    "diff",
    "--check",
)

run(
    "git",
    "diff",
    "--cached",
    "--check",
)

print("\n=== STAGED PHASE 3 CONTENT ===")
run(
    "git",
    "diff",
    "--cached",
    "--name-status",
)


# Guard against accidental secrets in staged content.
print("\n=== SECRET-LIKE TOKEN GUARD ===")

staged_diff = git_output(
    "diff",
    "--cached",
    "--",
    *existing_product_paths,
).lower()

suspicious_literals = [
    "app password",
    "smtp.gmail.com",  # configuration should not be hardcoded in product files
    "api_secret =",
    "password =",
]

hits = [
    token
    for token in suspicious_literals
    if token in staged_diff
]

if hits:
    raise SystemExit(
        "ERROR: Possible credential/config literal found in staged diff: "
        + ", ".join(hits)
        + "\nReview before committing."
    )

print("No obvious credential literals found in staged Phase 3 diff.")


# ---------------------------------------------------------------------
# Commit checkpoint.
# ---------------------------------------------------------------------

staged = git_output(
    "diff",
    "--cached",
    "--name-only",
)

if not staged:
    print("\nNo staged product changes. Nothing to commit.")
else:
    run(
        "git",
        "commit",
        "-m",
        COMMIT_MESSAGE,
    )


# ---------------------------------------------------------------------
# Self cleanup after successful commit.
# ---------------------------------------------------------------------

self_path = REPO_ROOT / "cleanup_checkpoint_phase3.py"

if self_path.exists():
    # It has already been copied into .phase_backups above.
    self_path.unlink()
    print(
        "\nRemoved cleanup_checkpoint_phase3.py from working tree."
    )


print("\n=== FINAL REPOSITORY STATUS ===")
run(
    "git",
    "status",
    "--short",
)

print("\n=== CHECKPOINT ===")
run(
    "git",
    "log",
    "-1",
    "--oneline",
)

print("\n" + "=" * 82)
print("PHASE 3 REPOSITORY CLEANUP + LOCAL CHECKPOINT COMPLETE")
print("")
print("Expected final state:")
print("  - Temporary installer/fixer scripts: removed")
print("  - .phase_backups/: ignored")
print("  - Canonical Phase 3 product files: committed")
print("  - Credentials: not stored in Git")
print("")
print("No push and no release tag were created automatically.")
print("Real Gmail + SMS acceptance still remains before final Phase 3 closure.")
print("=" * 82)
