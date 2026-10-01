from __future__ import annotations

import statistics
import time
from datetime import date, timedelta
from unittest.mock import patch

import frappe

from company_core.notification_engine import (
    collect_due_events,
    process_due_notifications,
)


SCAN_ITERATIONS = 30
DEDUP_ITERATIONS = 15

TASK_COUNT = 40
ACTION_COUNT = 10
MEETING_COUNT = 10

EXPECTED_EVENTS = (
    TASK_COUNT
    + ACTION_COUNT
    + MEETING_COUNT
)

STEADY_QUERY_P95_LIMIT = 10
STEADY_QUERY_MAX_LIMIT = 12


def _percentile(
    values,
    percentile,
):
    values = sorted(
        values
    )

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


def _stats(values):
    return {
        "avg": round(
            statistics.fmean(
                values
            ),
            2,
        ),
        "p50": round(
            _percentile(
                values,
                0.50,
            ),
            2,
        ),
        "p95": round(
            _percentile(
                values,
                0.95,
            ),
            2,
        ),
        "max": round(
            max(values),
            2,
        ),
    }


def _counted_scan(
    *,
    current_date,
    project,
):
    original_sql = (
        frappe.db.sql
    )

    with patch.object(
        frappe.db,
        "sql",
        wraps=original_sql,
    ) as sql_mock:
        started = (
            time.perf_counter()
        )

        events = (
            collect_due_events(
                current_date=(
                    current_date
                ),
                project=project,
            )
        )

        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000

        query_count = (
            sql_mock.call_count
        )

    return (
        events,
        elapsed_ms,
        query_count,
    )


def _cleanup_project(
    project,
):
    if not project:
        return

    source_pairs = []

    for doctype in (
        "Task",
        "Meeting Action",
        "Project Meeting",
    ):
        names = frappe.get_all(
            doctype,
            filters={
                "project": project,
            },
            pluck="name",
        )

        source_pairs.extend(
            (
                doctype,
                name,
            )
            for name in names
        )

    for doctype, name in source_pairs:
        logs = frappe.get_all(
            "Notification Log",
            filters={
                "document_type": (
                    doctype
                ),
                "document_name": (
                    name
                ),
            },
            pluck="name",
        )

        for log in logs:
            frappe.delete_doc(
                "Notification Log",
                log,
                ignore_permissions=True,
                force=True,
            )

    deliveries = frappe.get_all(
        "Notification Delivery",
        filters={
            "project": project,
        },
        pluck="name",
    )

    for name in deliveries:
        frappe.delete_doc(
            "Notification Delivery",
            name,
            ignore_permissions=True,
            force=True,
        )

    for doctype in (
        "Meeting Action",
        "Project Meeting",
        "Task",
        "Project Membership",
    ):
        names = frappe.get_all(
            doctype,
            filters={
                "project": project,
            },
            pluck="name",
        )

        for name in names:
            frappe.delete_doc(
                doctype,
                name,
                ignore_permissions=True,
                force=True,
            )

    if frappe.db.exists(
        "Project",
        project,
    ):
        frappe.delete_doc(
            "Project",
            project,
            ignore_permissions=True,
            force=True,
        )

    frappe.db.commit()


def run():
    frappe.set_user(
        "Administrator"
    )

    settings = frappe.get_single(
        "Grovity Notification Settings"
    )

    original_settings = {
        "enable_in_app": (
            settings.enable_in_app
        ),
        "enable_email": (
            settings.enable_email
        ),
        "enable_sms": (
            settings.enable_sms
        ),
    }

    project = None

    try:
        # Benchmark only the in-app path.
        # Email/SMS provider latency is external and measured
        # separately during real channel acceptance.
        settings.enable_in_app = 1
        settings.enable_email = 0
        settings.enable_sms = 0

        settings.save(
            ignore_permissions=True
        )

        suffix = frappe.generate_hash(
            length=10
        )

        project_doc = (
            frappe.get_doc(
                {
                    "doctype": "Project",
                    "project_name": (
                        "NOTIFY PERF "
                        f"{suffix}"
                    ),
                    "status": "Open",
                    "custom_project_status": (
                        "Active"
                    ),
                }
            ).insert(
                ignore_permissions=True
            )
        )

        project = (
            project_doc.name
        )

        frappe.get_doc(
            {
                "doctype": (
                    "Project Membership"
                ),
                "project": project,
                "user": (
                    "Administrator"
                ),
                "membership_role": (
                    "Project Manager"
                ),
                "status": "Active",
                "start_date": (
                    frappe.utils.today()
                ),
            }
        ).insert(
            ignore_permissions=True
        )

        due_date = (
            date.today()
            + timedelta(
                days=3
            )
        )

        for index in range(
            TASK_COUNT
        ):
            task = frappe.get_doc(
                {
                    "doctype": "Task",
                    "project": project,
                    "subject": (
                        "Notification Perf "
                        f"Task {index}"
                    ),
                    "status": "Open",
                    "priority": "Medium",
                    "exp_end_date": (
                        due_date.isoformat()
                    ),
                }
            )

            task.append(
                "custom_contributors",
                {
                    "user": (
                        "Administrator"
                    ),
                },
            )

            task.insert(
                ignore_permissions=True
            )

        meetings = []

        for index in range(
            MEETING_COUNT
        ):
            meeting = frappe.get_doc(
                {
                    "doctype": (
                        "Project Meeting"
                    ),
                    "project": project,
                    "meeting_datetime": (
                        due_date.isoformat()
                        + " 10:00:00"
                    ),
                    "agenda": (
                        "Notification Perf "
                        f"Meeting {index}"
                    ),
                    "prepared_by": (
                        "Administrator"
                    ),
                }
            ).insert(
                ignore_permissions=True
            )

            meetings.append(
                meeting.name
            )

        for index in range(
            ACTION_COUNT
        ):
            frappe.get_doc(
                {
                    "doctype": (
                        "Meeting Action"
                    ),
                    "project": project,
                    "meeting": (
                        meetings[index]
                    ),
                    "description": (
                        "Notification Perf "
                        f"Action {index}"
                    ),
                    "assigned_to": (
                        "Administrator"
                    ),
                    "deadline": (
                        due_date.isoformat()
                    ),
                    "priority": "Medium",
                    "status": "Open",
                }
            ).insert(
                ignore_permissions=True
            )

        frappe.db.commit()

        current_date = (
            date.today().isoformat()
        )

        # -------------------------------------------------------------
        # Cold scan
        #
        # Keep it visible for observability, but DO NOT use it for the
        # N+1 guard. The first call can legitimately populate Frappe
        # metadata/cache and therefore issue extra one-time queries.
        # -------------------------------------------------------------

        (
            cold_events,
            cold_ms,
            cold_queries,
        ) = _counted_scan(
            current_date=(
                current_date
            ),
            project=project,
        )

        if len(cold_events) != (
            EXPECTED_EVENTS
        ):
            raise RuntimeError(
                "Cold notification scan "
                "event-count mismatch."
            )

        # -------------------------------------------------------------
        # Warm-up
        #
        # One explicit unmeasured call ensures metadata/cache setup is
        # outside the steady-state performance sample.
        # -------------------------------------------------------------

        warm_events = (
            collect_due_events(
                current_date=(
                    current_date
                ),
                project=project,
            )
        )

        if len(warm_events) != (
            EXPECTED_EVENTS
        ):
            raise RuntimeError(
                "Warm-up notification scan "
                "event-count mismatch."
            )

        # -------------------------------------------------------------
        # Steady-state repeated measurement
        # -------------------------------------------------------------

        scan_times = []
        query_counts = []

        for _ in range(
            SCAN_ITERATIONS
        ):
            (
                events,
                elapsed_ms,
                query_count,
            ) = _counted_scan(
                current_date=(
                    current_date
                ),
                project=project,
            )

            if len(events) != (
                EXPECTED_EVENTS
            ):
                raise RuntimeError(
                    "Measured notification "
                    "event-count mismatch."
                )

            scan_times.append(
                elapsed_ms
            )

            query_counts.append(
                query_count
            )

        scan_stats = _stats(
            scan_times
        )

        query_stats = _stats(
            query_counts
        )

        # -------------------------------------------------------------
        # Actual write dispatch
        # -------------------------------------------------------------

        started = (
            time.perf_counter()
        )

        first_dispatch = (
            process_due_notifications(
                current_date=(
                    current_date
                ),
                project=project,
            )
        )

        first_dispatch_ms = (
            time.perf_counter()
            - started
        ) * 1000

        if (
            first_dispatch["created"]
            != EXPECTED_EVENTS
        ):
            raise RuntimeError(
                "Initial dispatch did not "
                "create the expected "
                "60 deliveries."
            )

        # -------------------------------------------------------------
        # Dedup benchmark
        # -------------------------------------------------------------

        dedup_times = []

        for _ in range(
            DEDUP_ITERATIONS
        ):
            started = (
                time.perf_counter()
            )

            repeated = (
                process_due_notifications(
                    current_date=(
                        current_date
                    ),
                    project=project,
                )
            )

            elapsed_ms = (
                time.perf_counter()
                - started
            ) * 1000

            dedup_times.append(
                elapsed_ms
            )

            if (
                repeated["created"]
                != 0
            ):
                raise RuntimeError(
                    "Notification "
                    "deduplication failed."
                )

            if (
                repeated[
                    "deduplicated"
                ]
                != EXPECTED_EVENTS
            ):
                raise RuntimeError(
                    "Notification "
                    "deduplication count "
                    "mismatch."
                )

        dedup_stats = _stats(
            dedup_times
        )

        print("")
        print("=" * 88)
        print(
            "PHASE 3 NOTIFICATION "
            "PERFORMANCE / QUERY BENCHMARK V2"
        )
        print("=" * 88)

        print(
            f"Events                       : "
            f"{EXPECTED_EVENTS}"
        )

        print("")
        print(
            "Cold-start observability "
            "(not used for N+1 guard)"
        )

        print(
            f"Cold scan duration           : "
            f"{cold_ms:.2f} ms"
        )

        print(
            f"Cold scan DB queries         : "
            f"{cold_queries}"
        )

        print("")
        print(
            "Steady-state scan "
            f"({SCAN_ITERATIONS} runs)"
        )

        print(
            f"Scan AVG                     : "
            f"{scan_stats['avg']:.2f} ms"
        )

        print(
            f"Scan P50                     : "
            f"{scan_stats['p50']:.2f} ms"
        )

        print(
            f"Scan P95                     : "
            f"{scan_stats['p95']:.2f} ms"
        )

        print(
            f"Scan MAX                     : "
            f"{scan_stats['max']:.2f} ms"
        )

        print(
            f"DB queries AVG               : "
            f"{query_stats['avg']:.2f}"
        )

        print(
            f"DB queries P50               : "
            f"{query_stats['p50']:.2f}"
        )

        print(
            f"DB queries P95               : "
            f"{query_stats['p95']:.2f}"
        )

        print(
            f"DB queries MAX               : "
            f"{int(query_stats['max'])}"
        )

        print("")
        print(
            "Write + dedup"
        )

        print(
            f"Initial 60-delivery dispatch : "
            f"{first_dispatch_ms:.2f} ms"
        )

        print(
            f"Created deliveries           : "
            f"{first_dispatch['created']}"
        )

        print(
            f"Dedup iterations             : "
            f"{DEDUP_ITERATIONS}"
        )

        print(
            f"Dedup P95                    : "
            f"{dedup_stats['p95']:.2f} ms"
        )

        print("=" * 88)

        # -------------------------------------------------------------
        # N+1 guard
        #
        # Guard steady-state behavior, not one-time metadata/cache
        # population. For 60 events the collector should stay roughly
        # constant-query because recipients are loaded in batches.
        # -------------------------------------------------------------

        if (
            query_stats["p95"]
            > STEADY_QUERY_P95_LIMIT
        ):
            raise RuntimeError(
                "Steady-state query-count "
                "P95 guard failed: "
                f"{query_stats['p95']} > "
                f"{STEADY_QUERY_P95_LIMIT}. "
                "Possible N+1 regression."
            )

        if (
            query_stats["max"]
            > STEADY_QUERY_MAX_LIMIT
        ):
            raise RuntimeError(
                "Steady-state query-count "
                "MAX guard failed: "
                f"{query_stats['max']} > "
                f"{STEADY_QUERY_MAX_LIMIT}. "
                "Possible N+1 regression."
            )

        result = {
            "status": "ok",
            "events": (
                EXPECTED_EVENTS
            ),
            "cold_start": {
                "duration_ms": round(
                    cold_ms,
                    2,
                ),
                "queries": (
                    cold_queries
                ),
            },
            "steady_state": {
                "iterations": (
                    SCAN_ITERATIONS
                ),
                "duration_ms": (
                    scan_stats
                ),
                "query_count": (
                    query_stats
                ),
            },
            "dispatch": {
                "duration_ms": round(
                    first_dispatch_ms,
                    2,
                ),
                "created": (
                    first_dispatch[
                        "created"
                    ]
                ),
            },
            "dedup": {
                "iterations": (
                    DEDUP_ITERATIONS
                ),
                "duration_ms": (
                    dedup_stats
                ),
            },
        }

        print("")
        print(
            "QUERY-COUNT GUARD: PASS"
        )

        return result

    finally:
        frappe.set_user(
            "Administrator"
        )

        if project:
            _cleanup_project(
                project
            )

        settings = frappe.get_single(
            "Grovity Notification Settings"
        )

        for (
            fieldname,
            value,
        ) in (
            original_settings.items()
        ):
            settings.set(
                fieldname,
                value,
            )

        settings.save(
            ignore_permissions=True
        )

        frappe.db.commit()
