#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SITE = "company.localhost"

REPO_ROOT = Path(__file__).resolve().parent
BENCH_ROOT = REPO_ROOT.parent.parent
PKG_ROOT = REPO_ROOT / "company_core"
BENCHMARK_MODULE = PKG_ROOT / "runtime_benchmark.py"


def run_cmd(*args: str, cwd: Path | None = None) -> None:
    cmd = list(args)
    print("\n>>>", " ".join(cmd))
    subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        check=True,
    )


if not (PKG_ROOT / "hooks.py").exists():
    raise SystemExit(
        "ERROR: Put this file in apps/company_core and run it there."
    )

if not (BENCH_ROOT / "sites").exists():
    raise SystemExit(
        f"ERROR: frappe-bench root was not detected: {BENCH_ROOT}"
    )


benchmark_module = r'''
from __future__ import annotations

import json
import statistics
import time
from datetime import date, timedelta

import frappe
from frappe.desk.calendar import get_events
from frappe.desk.search import search_link

from company_core.project_views import get_project_view_summary
from company_core.task_setup import ensure_task_extensions


READ_ITERATIONS = 30
WRITE_ITERATIONS = 8
WARMUP_ITERATIONS = 5


def _ms(seconds):
    return seconds * 1000.0


def _percentile(values, percentile):
    if not values:
        return 0.0

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower

    return (
        ordered[lower]
        + (ordered[upper] - ordered[lower]) * fraction
    )


def _measure(
    name,
    function,
    iterations=READ_ITERATIONS,
    warmups=WARMUP_ITERATIONS,
):
    for _ in range(warmups):
        function()

    samples = []

    for _ in range(iterations):
        started = time.perf_counter()
        function()
        samples.append(
            _ms(time.perf_counter() - started)
        )

    return {
        "operation": name,
        "iterations": iterations,
        "avg_ms": round(
            statistics.fmean(samples),
            2,
        ),
        "p50_ms": round(
            _percentile(samples, 0.50),
            2,
        ),
        "p95_ms": round(
            _percentile(samples, 0.95),
            2,
        ),
        "max_ms": round(
            max(samples),
            2,
        ),
        "min_ms": round(
            min(samples),
            2,
        ),
    }


def _print_report(results):
    print("")
    print("=" * 88)
    print("GROVITY RUNTIME PERFORMANCE BENCHMARK")
    print("=" * 88)
    print(
        f"{'Operation':42}"
        f"{'avg ms':>10}"
        f"{'p50 ms':>10}"
        f"{'p95 ms':>10}"
        f"{'max ms':>10}"
    )
    print("-" * 88)

    for row in results:
        print(
            f"{row['operation'][:42]:42}"
            f"{row['avg_ms']:>10.2f}"
            f"{row['p50_ms']:>10.2f}"
            f"{row['p95_ms']:>10.2f}"
            f"{row['max_ms']:>10.2f}"
        )

    print("=" * 88)
    print("")
    print(
        "NOTE: These are backend application timings inside "
        "Frappe/Docker, not test-suite duration and not browser/network latency."
    )
    print(
        "Use the p95 column as the main baseline for comparing future phases."
    )
    print("")
    print("JSON_RESULT_START")
    print(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
        )
    )
    print("JSON_RESULT_END")


def _create_user(email, first_name):
    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "enabled": 1,
            "send_welcome_email": 0,
        }
    )

    user.append(
        "roles",
        {
            "role": "Company User",
        },
    )

    return user.insert(
        ignore_permissions=True
    )


def _create_project(project_name):
    return frappe.get_doc(
        {
            "doctype": "Project",
            "project_name": project_name,
            "status": "Open",
            "custom_project_status": "Active",
            "custom_project_health": "Healthy",
        }
    ).insert(
        ignore_permissions=True
    )


def _create_membership(
    project,
    user,
    role,
):
    return frappe.get_doc(
        {
            "doctype": "Project Membership",
            "project": project,
            "user": user,
            "membership_role": role,
            "status": "Active",
            "start_date": frappe.utils.today(),
        }
    ).insert(
        ignore_permissions=True
    )


def _create_task(
    project,
    subject,
    contributors=None,
    is_milestone=0,
    progress=0,
):
    task = frappe.get_doc(
        {
            "doctype": "Task",
            "project": project,
            "subject": subject,
            "status": "Open",
            "priority": "Medium",
            "is_milestone": is_milestone,
            "progress": progress,
            "exp_start_date": (
                "2026-09-01 09:00:00"
            ),
            "exp_end_date": (
                "2026-10-15 17:00:00"
            ),
            "custom_planned_progress": 50,
        }
    )

    for user in contributors or []:
        task.append(
            "custom_contributors",
            {
                "user": user,
            },
        )

    return task.insert(
        ignore_permissions=True
    )


def _safe_delete(doctype, name):
    if not name:
        return

    if not frappe.db.exists(
        doctype,
        name,
    ):
        return

    try:
        frappe.delete_doc(
            doctype,
            name,
            ignore_permissions=True,
            force=True,
        )
    except Exception:
        # Cleanup should never hide the benchmark result.
        pass


def run():
    frappe.set_user(
        "Administrator"
    )

    ensure_task_extensions()

    suffix = frappe.generate_hash(
        length=8
    )

    sara = (
        f"perf.sara.{suffix}"
        "@grovity.test"
    )

    zahra = (
        f"perf.zahra.{suffix}"
        "@grovity.test"
    )

    created = {
        "users": [],
        "projects": [],
        "memberships": [],
        "tasks": [],
        "suspensions": [],
        "history": [],
    }

    results = []

    try:
        sara_doc = _create_user(
            sara,
            "Perf Sara",
        )
        created["users"].append(
            sara_doc.name
        )

        zahra_doc = _create_user(
            zahra,
            "Perf Zahra",
        )
        created["users"].append(
            zahra_doc.name
        )

        project_a = _create_project(
            f"PERF Project A {suffix}"
        )
        created["projects"].append(
            project_a.name
        )

        project_b = _create_project(
            f"PERF Project B {suffix}"
        )
        created["projects"].append(
            project_b.name
        )

        membership_a = _create_membership(
            project_a.name,
            sara,
            "Contributor",
        )
        created["memberships"].append(
            membership_a.name
        )

        membership_b = _create_membership(
            project_b.name,
            zahra,
            "Project Manager",
        )
        created["memberships"].append(
            membership_b.name
        )

        visible_tasks = []

        for index in range(12):
            task = _create_task(
                project_a.name,
                (
                    f"PERF Sara Task "
                    f"{index + 1}"
                ),
                contributors=[
                    sara,
                ],
                progress=(
                    index * 7
                ) % 100,
            )
            created["tasks"].append(
                task.name
            )
            visible_tasks.append(task)

        for index in range(8):
            task = _create_task(
                project_a.name,
                (
                    f"PERF Hidden Task "
                    f"{index + 1}"
                ),
                progress=(
                    index * 9
                ) % 100,
            )
            created["tasks"].append(
                task.name
            )

        for index in range(12):
            task = _create_task(
                project_b.name,
                (
                    f"PERF Manager Task "
                    f"{index + 1}"
                ),
                progress=(
                    index * 8
                ) % 100,
                is_milestone=(
                    1 if index in (3, 8) else 0
                ),
            )
            created["tasks"].append(
                task.name
            )

        frappe.db.commit()

        own_project_doc = frappe.get_doc(
            "Project",
            project_a.name,
        )

        other_project_doc = frappe.get_doc(
            "Project",
            project_b.name,
        )

        contributor_task_name = (
            visible_tasks[0].name
        )

        # -------------------------------------------------
        # Contributor read path
        # -------------------------------------------------
        frappe.set_user(
            sara
        )

        results.append(
            _measure(
                "Project list (permission filtered)",
                lambda: frappe.get_list(
                    "Project",
                    fields=[
                        "name",
                        "project_name",
                    ],
                    limit=20,
                ),
            )
        )

        results.append(
            _measure(
                "Task list (contributor filtered)",
                lambda: frappe.get_list(
                    "Task",
                    filters={
                        "project": (
                            project_a.name
                        ),
                    },
                    fields=[
                        "name",
                        "subject",
                        "status",
                        "progress",
                    ],
                    limit=20,
                ),
            )
        )

        results.append(
            _measure(
                "Project direct permission check",
                lambda: frappe.has_permission(
                    "Project",
                    ptype="read",
                    doc=own_project_doc,
                    user=sara,
                ),
                iterations=60,
                warmups=10,
            )
        )

        results.append(
            _measure(
                "Denied project permission check",
                lambda: frappe.has_permission(
                    "Project",
                    ptype="read",
                    doc=other_project_doc,
                    user=sara,
                ),
                iterations=60,
                warmups=10,
            )
        )

        results.append(
            _measure(
                "Project Control summary",
                lambda: get_project_view_summary(
                    project_a.name
                ),
            )
        )

        results.append(
            _measure(
                "Task Link/Search query",
                lambda: search_link(
                    doctype="Task",
                    txt="PERF",
                    filters={
                        "project": (
                            project_a.name
                        ),
                    },
                    page_length=20,
                ),
            )
        )

        gantt_field_map = json.dumps(
            {
                "start": "exp_start_date",
                "end": "exp_end_date",
                "id": "name",
                "title": "subject",
                "progress": "progress",
            }
        )

        gantt_filters = json.dumps(
            [
                [
                    "Task",
                    "project",
                    "=",
                    project_a.name,
                ]
            ]
        )

        gantt_fields = json.dumps(
            [
                "name",
                "subject",
                "exp_start_date",
                "exp_end_date",
                "progress",
            ]
        )

        results.append(
            _measure(
                "Gantt event backend query",
                lambda: get_events(
                    doctype="Task",
                    start=(
                        "2026-08-01 00:00:00"
                    ),
                    end=(
                        "2026-11-01 23:59:59"
                    ),
                    field_map=(
                        gantt_field_map
                    ),
                    filters=(
                        gantt_filters
                    ),
                    fields=(
                        gantt_fields
                    ),
                ),
                iterations=20,
                warmups=5,
            )
        )

        # -------------------------------------------------
        # Contributor real write path
        # Includes an actual DB commit to approximate
        # successful request completion.
        # -------------------------------------------------
        write_counter = {
            "value": 0,
        }

        def contributor_task_save():
            write_counter["value"] += 1

            task = frappe.get_doc(
                "Task",
                contributor_task_name,
            )

            task.description = (
                "Performance write "
                f"{write_counter['value']}"
            )

            task.save()
            frappe.db.commit()

        results.append(
            _measure(
                "Contributor Task save + commit",
                contributor_task_save,
                iterations=WRITE_ITERATIONS,
                warmups=1,
            )
        )

        # -------------------------------------------------
        # Project Manager paths
        # -------------------------------------------------
        frappe.set_user(
            zahra
        )

        results.append(
            _measure(
                "Manager Task list",
                lambda: frappe.get_list(
                    "Task",
                    filters={
                        "project": (
                            project_b.name
                        ),
                    },
                    fields=[
                        "name",
                        "subject",
                        "status",
                        "progress",
                    ],
                    limit=20,
                ),
            )
        )

        results.append(
            _measure(
                "Manager Project summary",
                lambda: get_project_view_summary(
                    project_b.name
                ),
            )
        )

        # -------------------------------------------------
        # Status transition write path
        # -------------------------------------------------
        transition_states = [
            "Under Review",
            "Active",
        ]

        transition_counter = {
            "value": 0,
        }

        def project_status_transition():
            index = (
                transition_counter["value"]
                % len(transition_states)
            )

            transition_counter["value"] += 1

            project = frappe.get_doc(
                "Project",
                project_b.name,
            )

            project.custom_project_status = (
                transition_states[index]
            )

            project.custom_status_change_reason = (
                "Runtime benchmark transition"
            )

            project.save()
            frappe.db.commit()

        results.append(
            _measure(
                "Project status transition + audit + commit",
                project_status_transition,
                iterations=6,
                warmups=0,
            )
        )

        # Track generated history for cleanup.
        frappe.set_user(
            "Administrator"
        )

        history_names = frappe.get_all(
            "Project Status History",
            filters={
                "project": (
                    project_b.name
                ),
            },
            pluck="name",
        )

        created["history"].extend(
            history_names
        )

        # -------------------------------------------------
        # Suspension Event create/close path
        # -------------------------------------------------
        frappe.set_user(
            zahra
        )

        suspension_counter = {
            "value": 0,
        }

        def suspension_cycle():
            suspension_counter["value"] += 1

            today = date.today()
            start = (
                today
                + timedelta(
                    days=suspension_counter["value"]
                )
            )

            event = frappe.get_doc(
                {
                    "doctype": (
                        "Suspension Event"
                    ),
                    "project": (
                        project_b.name
                    ),
                    "start_date": (
                        start.isoformat()
                    ),
                    "reason_category": (
                        "Technical"
                    ),
                    "description": (
                        "Runtime benchmark"
                    ),
                    "responsible_side": (
                        "Internal Team"
                    ),
                    "approved_by": zahra,
                }
            )

            event.insert()
            frappe.db.commit()

            created["suspensions"].append(
                event.name
            )

            event.end_date = (
                start
                + timedelta(days=1)
            ).isoformat()

            event.save()
            frappe.db.commit()

        results.append(
            _measure(
                "Suspension create + close + commits",
                suspension_cycle,
                iterations=5,
                warmups=0,
            )
        )

        _print_report(
            results
        )

        return results

    finally:
        frappe.set_user(
            "Administrator"
        )

        # Discover any benchmark records created before
        # an exception interrupted tracking.
        for project_name in (
            created["projects"]
        ):
            created["history"].extend(
                frappe.get_all(
                    "Project Status History",
                    filters={
                        "project": project_name,
                    },
                    pluck="name",
                )
            )

            created["suspensions"].extend(
                frappe.get_all(
                    "Suspension Event",
                    filters={
                        "project": project_name,
                    },
                    pluck="name",
                )
            )

        # Deduplicate cleanup lists.
        for key in (
            "history",
            "suspensions",
            "tasks",
            "memberships",
            "projects",
            "users",
        ):
            created[key] = list(
                dict.fromkeys(
                    created[key]
                )
            )

        for name in created["history"]:
            _safe_delete(
                "Project Status History",
                name,
            )

        for name in created["suspensions"]:
            _safe_delete(
                "Suspension Event",
                name,
            )

        for name in created["tasks"]:
            _safe_delete(
                "Task",
                name,
            )

        for name in created["memberships"]:
            _safe_delete(
                "Project Membership",
                name,
            )

        for name in created["projects"]:
            _safe_delete(
                "Project",
                name,
            )

        for name in created["users"]:
            _safe_delete(
                "User",
                name,
            )

        frappe.db.commit()
'''

BENCHMARK_MODULE.write_text(
    benchmark_module.rstrip() + "\n",
    encoding="utf-8",
)

print(
    "WRITE",
    BENCHMARK_MODULE.relative_to(
        REPO_ROOT
    ),
)

print("\n=== STATIC CHECK ===")
run_cmd(
    sys.executable,
    "-m",
    "compileall",
    "-q",
    str(PKG_ROOT),
)

print("\n=== RUNTIME BENCHMARK ===")
run_cmd(
    "bench",
    "--site",
    SITE,
    "execute",
    "company_core.runtime_benchmark.run",
    cwd=BENCH_ROOT,
)

print("\n" + "=" * 72)
print("RUNTIME BENCHMARK FINISHED")
print(
    "Send me the table printed above; "
    "we will keep it as the Phase 2E performance baseline."
)
print("=" * 72)
