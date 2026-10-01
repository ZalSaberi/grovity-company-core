from __future__ import annotations

import statistics
import time
from datetime import date, timedelta

import frappe

from company_core.operations_notifications import process_due_notifications
from company_core.phase2_cleanup import _delete_with_retry


ITERATIONS = 30
WARMUPS = 5


def _percentile(values, percentile):
    values = sorted(values)
    rank = (len(values) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(values) - 1)
    fraction = rank - lower
    return values[lower] + (values[upper] - values[lower]) * fraction


def _measure(name, function):
    for _ in range(WARMUPS):
        function()

    samples = []

    for _ in range(ITERATIONS):
        started = time.perf_counter()
        function()
        samples.append((time.perf_counter() - started) * 1000)

    return {
        "operation": name,
        "avg_ms": round(statistics.fmean(samples), 2),
        "p50_ms": round(_percentile(samples, 0.50), 2),
        "p95_ms": round(_percentile(samples, 0.95), 2),
        "max_ms": round(max(samples), 2),
    }


def run():
    frappe.set_user("Administrator")

    suffix = frappe.generate_hash(length=8)
    manager = f"opsperf.manager.{suffix}@grovity.test"
    contributor = f"opsperf.contributor.{suffix}@grovity.test"

    created = {
        "users": [],
        "projects": [],
        "memberships": [],
        "meetings": [],
        "actions": [],
        "reports": [],
        "notifications": [],
    }

    results = []

    try:
        for email, first_name in (
            (manager, "Ops Perf Manager"),
            (contributor, "Ops Perf Contributor"),
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
            user.append("roles", {"role": "Company User"})
            user.insert(ignore_permissions=True)
            created["users"].append(user.name)

        project = frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": f"Operations PERF {suffix}",
                "status": "Open",
                "custom_project_status": "Active",
            }
        ).insert(ignore_permissions=True)
        created["projects"].append(project.name)

        for user, role in (
            (manager, "Project Manager"),
            (contributor, "Contributor"),
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
            ).insert(ignore_permissions=True)
            created["memberships"].append(membership.name)

        for index in range(12):
            meeting = frappe.get_doc(
                {
                    "doctype": "Project Meeting",
                    "project": project.name,
                    "meeting_datetime": (
                        str(date.today() + timedelta(days=3))
                        + " 10:00:00"
                    ),
                    "agenda": f"Benchmark Meeting {index}",
                }
            )
            meeting.append("participants", {"user": contributor})
            meeting.insert(ignore_permissions=True)
            created["meetings"].append(meeting.name)

            action = frappe.get_doc(
                {
                    "doctype": "Meeting Action",
                    "project": project.name,
                    "meeting": meeting.name,
                    "description": f"Benchmark Action {index}",
                    "assigned_to": contributor,
                    "deadline": (
                        date.today() + timedelta(days=3)
                    ).isoformat(),
                    "priority": "Medium",
                    "status": "Open",
                }
            ).insert(ignore_permissions=True)
            created["actions"].append(action.name)

            report = frappe.get_doc(
                {
                    "doctype": "Progress Report",
                    "project": project.name,
                    "period": f"PERF-{index:02d}",
                    "progress_percent": (index * 7) % 100,
                    "submitted_by": contributor,
                    "approval_status": "Draft",
                }
            ).insert(ignore_permissions=True)
            created["reports"].append(report.name)

        frappe.db.commit()
        frappe.set_user(manager)

        results.append(
            _measure(
                "Project Meeting list",
                lambda: frappe.get_list(
                    "Project Meeting",
                    filters={"project": project.name},
                    fields=["name", "meeting_datetime", "status"],
                    limit=50,
                ),
            )
        )

        results.append(
            _measure(
                "Meeting Action list",
                lambda: frappe.get_list(
                    "Meeting Action",
                    filters={"project": project.name},
                    fields=["name", "assigned_to", "deadline", "status"],
                    limit=50,
                ),
            )
        )

        results.append(
            _measure(
                "Progress Report list",
                lambda: frappe.get_list(
                    "Progress Report",
                    filters={"project": project.name},
                    fields=["name", "period", "approval_status"],
                    limit=50,
                ),
            )
        )

        frappe.set_user("Administrator")

        started = time.perf_counter()
        notification_result = process_due_notifications(
            date.today().isoformat(),
            project.name,
        )
        notification_ms = (time.perf_counter() - started) * 1000

        results.append(
            {
                "operation": "Notification scan + dispatch",
                "avg_ms": round(notification_ms, 2),
                "p50_ms": round(notification_ms, 2),
                "p95_ms": round(notification_ms, 2),
                "max_ms": round(notification_ms, 2),
            }
        )

        created["notifications"] = frappe.get_all(
            "Notification Log",
            filters={
                "document_name": [
                    "in",
                    created["meetings"] + created["actions"],
                ],
            },
            pluck="name",
        )

        print("")
        print("=" * 88)
        print("PHASE 3 OPERATIONS RUNTIME BENCHMARK")
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
        print("Notifications created:", notification_result["total"])
        return results

    finally:
        frappe.set_user("Administrator")

        for name in created["notifications"]:
            _delete_with_retry("Notification Log", name)

        for doctype, names in (
            ("Progress Report", created["reports"]),
            ("Meeting Action", created["actions"]),
            ("Project Meeting", created["meetings"]),
            ("Project Membership", created["memberships"]),
            ("Project", created["projects"]),
            ("User", created["users"]),
        ):
            for name in names:
                _delete_with_retry(doctype, name)

        frappe.db.commit()
