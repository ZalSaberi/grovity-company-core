import frappe


REQUIRED_DOCTYPES = (
    "Meeting Participant",
    "Project Meeting",
    "Meeting Action",
    "Progress Report",
)


def run():
    problems = []

    for doctype in REQUIRED_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            problems.append(f"Missing DocType: {doctype}")

    meta = frappe.get_meta("Meeting Action")
    fieldnames = {field.fieldname for field in meta.fields}

    if "assigned_to" not in fieldnames:
        problems.append("Meeting Action.assigned_to is missing")

    custom_owner = [
        field
        for field in meta.fields
        if field.fieldname == "owner"
    ]

    if custom_owner:
        problems.append(
            "Meeting Action contains a custom owner field collision"
        )

    hooks = frappe.get_hooks()
    scheduler = hooks.get("scheduler_events", {})

    notification_job = (
        "company_core.operations_notifications."
        "process_due_notifications"
    )

    if notification_job not in scheduler.get("daily", []):
        problems.append("Phase 3 daily notification job is not registered")

    if problems:
        raise RuntimeError(" | ".join(problems))

    result = {
        "status": "ok",
        "doctypes": list(REQUIRED_DOCTYPES),
        "meeting_action_assignee_field": "assigned_to",
        "scheduler_job": notification_job,
    }

    print(result)
    return result
