from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


EVENT_CUSTOM_FIELDS = [
    {
        "fieldname": "custom_grovity_section",
        "label": "Grovity Calendar",
        "fieldtype": "Section Break",
        "insert_after": "description",
        "collapsible": 1,
    },
    {
        "fieldname": "custom_grovity_kind",
        "label": "Grovity Entry Type",
        "fieldtype": "Select",
        "options": "\nPersonal Plan\nProject Meeting\nTask Deadline\nMilestone\nMeeting Action\nMeeting Request",
        "insert_after": "custom_grovity_section",
        "in_standard_filter": 1,
    },
    {
        "fieldname": "custom_calendar_owner",
        "label": "Calendar Owner",
        "fieldtype": "Link",
        "options": "User",
        "insert_after": "custom_grovity_kind",
        "in_standard_filter": 1,
    },
    {
        "fieldname": "custom_related_project",
        "label": "Related Project",
        "fieldtype": "Link",
        "options": "Project",
        "insert_after": "custom_calendar_owner",
        "in_standard_filter": 1,
    },
    {
        "fieldname": "custom_blocks_availability",
        "label": "Blocks Availability",
        "fieldtype": "Check",
        "default": "1",
        "insert_after": "custom_related_project",
        "description": "If enabled, this entry makes the calendar owner busy for meeting requests.",
    },
    {
        "fieldname": "custom_grovity_managed",
        "label": "Managed by Grovity",
        "fieldtype": "Check",
        "default": "0",
        "read_only": 1,
        "hidden": 1,
        "insert_after": "custom_blocks_availability",
    },
    {
        "fieldname": "custom_source_doctype",
        "label": "Source DocType",
        "fieldtype": "Link",
        "options": "DocType",
        "read_only": 1,
        "hidden": 1,
        "insert_after": "custom_grovity_managed",
    },
    {
        "fieldname": "custom_source_name",
        "label": "Source Document",
        "fieldtype": "Dynamic Link",
        "options": "custom_source_doctype",
        "read_only": 1,
        "hidden": 1,
        "insert_after": "custom_source_doctype",
    },
    {
        "fieldname": "custom_archived",
        "label": "Archived by Grovity",
        "fieldtype": "Check",
        "default": "0",
        "read_only": 1,
        "hidden": 1,
        "insert_after": "custom_source_name",
    },
]


def ensure_calendar_custom_fields():
    create_custom_fields({"Event": EVENT_CUSTOM_FIELDS}, update=True)
    return {"event_custom_fields": len(EVENT_CUSTOM_FIELDS)}
