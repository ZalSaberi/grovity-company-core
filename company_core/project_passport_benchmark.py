
from __future__ import annotations

import statistics
import time

import frappe

from company_core.project_passport import (
    get_project_passport,
)
from company_core.project_passport_setup import (
    ensure_project_passport,
)


ITERATIONS = 40
WARMUPS = 5


def _percentile(
    values,
    percentile,
):
    ordered = sorted(
        values
    )

    rank = (
        len(ordered) - 1
    ) * percentile

    lower = int(rank)
    upper = min(
        lower + 1,
        len(ordered) - 1,
    )

    fraction = rank - lower

    return (
        ordered[lower]
        + (
            ordered[upper]
            - ordered[lower]
        )
        * fraction
    )


def run():
    frappe.set_user(
        "Administrator"
    )

    ensure_project_passport()

    suffix = frappe.generate_hash(
        length=8
    )

    email = (
        f"passport.perf.{suffix}"
        "@grovity.test"
    )

    created = {
        "user": None,
        "project": None,
        "membership": None,
    }

    try:
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": "Passport Perf",
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

        user.insert(
            ignore_permissions=True
        )

        created["user"] = user.name

        project = frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": (
                    f"Passport PERF {suffix}"
                ),
                "status": "Open",
                "custom_project_status": "Active",
                "custom_project_health": "Healthy",
                "custom_contract_value": 100000,
                "custom_collected_amount": 45000,
                "custom_project_cost": 22000,
            }
        ).insert(
            ignore_permissions=True
        )

        created["project"] = project.name

        membership = frappe.get_doc(
            {
                "doctype": "Project Membership",
                "project": project.name,
                "user": email,
                "membership_role": "Project Manager",
                "status": "Active",
                "start_date": frappe.utils.today(),
            }
        ).insert(
            ignore_permissions=True
        )

        created["membership"] = (
            membership.name
        )

        frappe.db.commit()

        frappe.set_user(
            email
        )

        for _ in range(
            WARMUPS
        ):
            get_project_passport(
                project.name
            )

        samples = []

        for _ in range(
            ITERATIONS
        ):
            started = (
                time.perf_counter()
            )

            get_project_passport(
                project.name
            )

            samples.append(
                (
                    time.perf_counter()
                    - started
                )
                * 1000
            )

        avg = statistics.fmean(
            samples
        )

        p50 = _percentile(
            samples,
            0.50,
        )

        p95 = _percentile(
            samples,
            0.95,
        )

        maximum = max(
            samples
        )

        print("")
        print("=" * 72)
        print(
            "PHASE 2F PROJECT PASSPORT "
            "RUNTIME BENCHMARK"
        )
        print("=" * 72)
        print(
            f"Iterations : {ITERATIONS}"
        )
        print(
            f"Average    : {avg:.2f} ms"
        )
        print(
            f"P50        : {p50:.2f} ms"
        )
        print(
            f"P95        : {p95:.2f} ms"
        )
        print(
            f"Max        : {maximum:.2f} ms"
        )
        print("=" * 72)
        print("")

        return {
            "operation": (
                "Project Passport endpoint"
            ),
            "iterations": ITERATIONS,
            "avg_ms": round(
                avg,
                2,
            ),
            "p50_ms": round(
                p50,
                2,
            ),
            "p95_ms": round(
                p95,
                2,
            ),
            "max_ms": round(
                maximum,
                2,
            ),
        }

    finally:
        frappe.set_user(
            "Administrator"
        )

        if (
            created["membership"]
            and frappe.db.exists(
                "Project Membership",
                created["membership"],
            )
        ):
            frappe.delete_doc(
                "Project Membership",
                created["membership"],
                ignore_permissions=True,
                force=True,
            )

        if (
            created["project"]
            and frappe.db.exists(
                "Project",
                created["project"],
            )
        ):
            frappe.delete_doc(
                "Project",
                created["project"],
                ignore_permissions=True,
                force=True,
            )

        if (
            created["user"]
            and frappe.db.exists(
                "User",
                created["user"],
            )
        ):
            frappe.delete_doc(
                "User",
                created["user"],
                ignore_permissions=True,
                force=True,
            )

        frappe.db.commit()
