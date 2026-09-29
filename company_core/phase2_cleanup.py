
from __future__ import annotations

import time

import frappe


MAX_RETRIES = 4


def _delete_with_retry(
    doctype,
    name,
):
    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        try:
            if not frappe.db.exists(
                doctype,
                name,
            ):
                return True

            frappe.delete_doc(
                doctype,
                name,
                ignore_permissions=True,
                force=True,
            )

            frappe.db.commit()
            return True

        except frappe.QueryDeadlockError:
            frappe.db.rollback()

            if attempt >= MAX_RETRIES:
                raise

            time.sleep(
                0.20 * attempt
            )


@frappe.whitelist()
def cleanup_stale_scale_data():
    frappe.set_user(
        "Administrator"
    )

    projects = frappe.get_all(
        "Project",
        filters={
            "project_name": [
                "like",
                "SCALE %",
            ],
        },
        pluck="name",
    )

    if projects:
        histories = frappe.get_all(
            "Project Status History",
            filters={
                "project": [
                    "in",
                    projects,
                ],
            },
            pluck="name",
        )

        for name in histories:
            _delete_with_retry(
                "Project Status History",
                name,
            )

        suspensions = frappe.get_all(
            "Suspension Event",
            filters={
                "project": [
                    "in",
                    projects,
                ],
            },
            pluck="name",
        )

        for name in suspensions:
            _delete_with_retry(
                "Suspension Event",
                name,
            )

        tasks = frappe.get_all(
            "Task",
            filters={
                "project": [
                    "in",
                    projects,
                ],
            },
            pluck="name",
        )

        for name in tasks:
            _delete_with_retry(
                "Task",
                name,
            )

        memberships = frappe.get_all(
            "Project Membership",
            filters={
                "project": [
                    "in",
                    projects,
                ],
            },
            pluck="name",
        )

        for name in memberships:
            _delete_with_retry(
                "Project Membership",
                name,
            )

        for name in projects:
            _delete_with_retry(
                "Project",
                name,
            )

    users = frappe.get_all(
        "User",
        filters={
            "email": [
                "like",
                "scale.%@grovity.test",
            ],
        },
        pluck="name",
    )

    for name in users:
        _delete_with_retry(
            "User",
            name,
        )

    frappe.db.commit()

    result = {
        "projects_removed": len(
            projects
        ),
        "users_removed": len(
            users
        ),
    }

    print(result)
    return result
