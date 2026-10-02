from __future__ import annotations

import frappe


REQUIRED_EVENT_FIELDS = (
    "custom_grovity_kind",
    "custom_calendar_owner",
    "custom_related_project",
    "custom_blocks_availability",
    "custom_grovity_managed",
    "custom_source_doctype",
    "custom_source_name",
    "custom_archived",
)


def run():
    meta = frappe.get_meta("Event")
    missing_fields = [field for field in REQUIRED_EVENT_FIELDS if not meta.has_field(field)]
    hooks = frappe.get_hooks("scheduler_events") or {}
    monthly = hooks.get("monthly", [])
    if isinstance(monthly, str):
        monthly = [monthly]

    result = {
        "status": "ok" if not missing_fields else "error",
        "meeting_request_doctype": bool(frappe.db.exists("DocType", "Meeting Request")),
        "calendar_preference_doctype": bool(
            frappe.db.exists("DocType", "Grovity Calendar Preference")
        ),
        "missing_event_fields": missing_fields,
        "managed_event_count": (
            frappe.db.count("Event", {"custom_grovity_managed": 1})
            if not missing_fields
            else 0
        ),
        "preference_count": (
            frappe.db.count("Grovity Calendar Preference")
            if frappe.db.exists("DocType", "Grovity Calendar Preference")
            else 0
        ),
        "monthly_lifecycle_registered": (
            "company_core.calendar_service.process_monthly_calendar_lifecycle" in monthly
        ),
        "calendar_route": "/app/event/view/calendar/default",
        "google_sync_default": "off_until_phase_11",
    }
    print(result)
    return result
