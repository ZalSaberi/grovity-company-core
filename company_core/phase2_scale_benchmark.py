
from __future__ import annotations

import json
import statistics
import time

import frappe
from frappe.desk.calendar import get_events

from company_core.project_passport import (
    get_project_passport,
)


PROJECT_COUNT = 10
TASKS_PER_PROJECT = 12
READ_ITERATIONS = 30
WARMUPS = 5


def _percentile(
    values,
    percentile,
):
    values = sorted(
        values
    )

    if len(values) == 1:
        return values[0]

    rank = (
        len(values) - 1
    ) * percentile

    lower = int(rank)
    upper = min(
        lower + 1,
        len(values) - 1,
    )

    fraction = rank - lower

    return (
        values[lower]
        + (
            values[upper]
            - values[lower]
        )
        * fraction
    )


def _measure(
    name,
    function,
):
    for _ in range(
        WARMUPS
    ):
        function()

    samples = []

    for _ in range(
        READ_ITERATIONS
    ):
        started = (
            time.perf_counter()
        )

        function()

        samples.append(
            (
                time.perf_counter()
                - started
            )
            * 1000
        )

    return {
        "operation": name,
        "avg_ms": round(
            statistics.fmean(
                samples
            ),
            2,
        ),
        "p50_ms": round(
            _percentile(
                samples,
                0.50,
            ),
            2,
        ),
        "p95_ms": round(
            _percentile(
                samples,
                0.95,
            ),
            2,
        ),
        "max_ms": round(
            max(samples),
            2,
        ),
    }


def _create_user(
    email,
    first_name,
):
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


def run():
    frappe.set_user(
        "Administrator"
    )

    suffix = frappe.generate_hash(
        length=8
    )

    manager = (
        f"scale.manager.{suffix}"
        "@grovity.test"
    )

    contributor = (
        f"scale.contributor.{suffix}"
        "@grovity.test"
    )

    created_users = []
    created_projects = []
    created_memberships = []
    created_tasks = []

    results = []

    try:
        for email, first_name in (
            (
                manager,
                "Scale Manager",
            ),
            (
                contributor,
                "Scale Contributor",
            ),
        ):
            user = _create_user(
                email,
                first_name,
            )

            created_users.append(
                user.name
            )

        for project_index in range(
            PROJECT_COUNT
        ):
            project = frappe.get_doc(
                {
                    "doctype": "Project",
                    "project_name": (
                        "SCALE "
                        f"{project_index + 1:02d} "
                        f"{suffix}"
                    ),
                    "status": "Open",
                    "custom_project_status": "Active",
                    "custom_project_health": "Healthy",
                    "custom_contract_value": 1000000,
                    "custom_collected_amount": 500000,
                    "custom_project_cost": 250000,
                }
            ).insert(
                ignore_permissions=True
            )

            created_projects.append(
                project.name
            )

            for user, role in (
                (
                    manager,
                    "Project Manager",
                ),
                (
                    contributor,
                    "Contributor",
                ),
            ):
                membership = frappe.get_doc(
                    {
                        "doctype": "Project Membership",
                        "project": project.name,
                        "user": user,
                        "membership_role": role,
                        "status": "Active",
                        "start_date": frappe.utils.today(),
                    }
                ).insert(
                    ignore_permissions=True
                )

                created_memberships.append(
                    membership.name
                )

            for task_index in range(
                TASKS_PER_PROJECT
            ):
                task = frappe.get_doc(
                    {
                        "doctype": "Task",
                        "project": project.name,
                        "subject": (
                            "Scale Task "
                            f"{project_index + 1:02d}-"
                            f"{task_index + 1:02d}"
                        ),
                        "status": "Open",
                        "priority": "Medium",
                        "progress": (
                            task_index * 8
                        ) % 100,
                        "is_milestone": (
                            1
                            if task_index == 0
                            else 0
                        ),
                        "exp_start_date": (
                            "2026-09-01 09:00:00"
                        ),
                        "exp_end_date": (
                            "2026-12-01 17:00:00"
                        ),
                        "custom_planned_progress": 50,
                    }
                )

                if task_index % 2 == 0:
                    task.append(
                        "custom_contributors",
                        {
                            "user": contributor,
                        },
                    )

                task.insert(
                    ignore_permissions=True
                )

                created_tasks.append(
                    task.name
                )

        frappe.db.commit()

        target_project = (
            created_projects[0]
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
                    target_project,
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

        frappe.set_user(
            manager
        )

        results.append(
            _measure(
                "10-project Project list",
                lambda: frappe.get_list(
                    "Project",
                    fields=[
                        "name",
                        "project_name",
                    ],
                    limit=50,
                ),
            )
        )

        results.append(
            _measure(
                "Manager all accessible tasks",
                lambda: frappe.get_list(
                    "Task",
                    fields=[
                        "name",
                        "project",
                        "status",
                        "progress",
                    ],
                    limit=500,
                ),
            )
        )

        results.append(
            _measure(
                "Manager 12-task project list",
                lambda: frappe.get_list(
                    "Task",
                    filters={
                        "project": target_project,
                    },
                    fields=[
                        "name",
                        "subject",
                        "status",
                        "progress",
                    ],
                    limit=50,
                ),
            )
        )

        results.append(
            _measure(
                "Project Passport at scale",
                lambda: get_project_passport(
                    target_project
                ),
            )
        )

        frappe.set_user(
            contributor
        )

        results.append(
            _measure(
                "Contributor visible task list",
                lambda: frappe.get_list(
                    "Task",
                    filters={
                        "project": target_project,
                    },
                    fields=[
                        "name",
                        "subject",
                        "status",
                        "progress",
                    ],
                    limit=50,
                ),
            )
        )

        results.append(
            _measure(
                "Contributor Gantt at scale",
                lambda: get_events(
                    doctype="Task",
                    start=(
                        "2026-08-01 00:00:00"
                    ),
                    end=(
                        "2027-01-01 23:59:59"
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
            )
        )

        print("")
        print("=" * 92)
        print(
            "PHASE 2G SCALE ACCEPTANCE "
            f"({PROJECT_COUNT} PROJECTS / "
            f"{PROJECT_COUNT * TASKS_PER_PROJECT} TASKS)"
        )
        print("=" * 92)
        print(
            f"{'Operation':42}"
            f"{'avg ms':>12}"
            f"{'p50 ms':>12}"
            f"{'p95 ms':>12}"
            f"{'max ms':>12}"
        )
        print("-" * 92)

        for row in results:
            print(
                f"{row['operation'][:42]:42}"
                f"{row['avg_ms']:>12.2f}"
                f"{row['p50_ms']:>12.2f}"
                f"{row['p95_ms']:>12.2f}"
                f"{row['max_ms']:>12.2f}"
            )

        print("=" * 92)
        print("")
        print(
            "Reference Phase 2E/2F local baselines:"
        )
        print(
            "Project list p95 ~1.26 ms | "
            "Contributor task list p95 ~1.90 ms | "
            "Gantt p95 ~2.07 ms | "
            "Passport p95 ~1.90 ms"
        )
        print("")
        print(
            "Scale results are informational. "
            "Compare p95 values for regression trends."
        )
        print("")

        return results

    finally:
        frappe.set_user(
            "Administrator"
        )

        from company_core.phase2_cleanup import (
            _delete_with_retry,
        )

        for name in created_tasks:
            _delete_with_retry(
                "Task",
                name,
            )

        for name in created_memberships:
            _delete_with_retry(
                "Project Membership",
                name,
            )

        for name in created_projects:
            _delete_with_retry(
                "Project",
                name,
            )

        for name in created_users:
            _delete_with_retry(
                "User",
                name,
            )

        frappe.db.commit()
