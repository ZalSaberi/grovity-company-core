
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import (
    add_permission,
    setup_custom_perms,
    update_permission_property,
)

from company_core.setup import ensure_security_baseline


def ensure_task_permission(role):
    setup_custom_perms("Task")

    permission_exists = frappe.db.exists(
        "Custom DocPerm",
        {
            "parent": "Task",
            "role": role,
            "permlevel": 0,
            "if_owner": 0,
        },
    )

    if not permission_exists:
        add_permission(
            "Task",
            role,
            permlevel=0,
            ptype="read",
        )

    permissions = {
        "select": 1,
        "read": 1,
        "write": 1,
        "create": 1,
        "delete": 1,
        "submit": 0,
        "cancel": 0,
    }

    for permission_type, value in permissions.items():
        update_permission_property(
            "Task",
            role,
            0,
            permission_type,
            value,
        )

    frappe.clear_cache(doctype="Task")


def ensure_task_fields():
    custom_fields = {
        "Task": [
            {
                "fieldname": "custom_grovity_task_section",
                "label": "Grovity Task Control",
                "fieldtype": "Section Break",
                "insert_after": "is_milestone",
            },
            {
                "fieldname": "custom_milestone",
                "label": "Milestone",
                "fieldtype": "Link",
                "options": "Task",
                "insert_after": "custom_grovity_task_section",
                "description": "Link this task to a milestone inside the same project.",
            },
            {
                "fieldname": "custom_contributors",
                "label": "Contributors",
                "fieldtype": "Table",
                "options": "Task Contributor",
                "insert_after": "custom_milestone",
            },
            {
                "fieldname": "custom_task_progress_column",
                "fieldtype": "Column Break",
                "insert_after": "custom_contributors",
            },
            {
                "fieldname": "custom_planned_progress",
                "label": "Planned Progress",
                "fieldtype": "Percent",
                "insert_after": "custom_task_progress_column",
            },
            {
                "fieldname": "custom_actual_progress",
                "label": "Actual Progress",
                "fieldtype": "Percent",
                "read_only": 1,
                "insert_after": "custom_planned_progress",
                "description": "Mirrors ERPNext Task % Progress.",
            },
            {
                "fieldname": "custom_deliverable",
                "label": "Deliverable",
                "fieldtype": "Check",
                "default": "0",
                "insert_after": "custom_actual_progress",
            },
            {
                "fieldname": "custom_delay_reason",
                "label": "Delay Reason",
                "fieldtype": "Small Text",
                "insert_after": "custom_deliverable",
            },
        ]
    }

    create_custom_fields(custom_fields, update=True)
    frappe.clear_cache(doctype="Task")


def ensure_task_extensions():
    ensure_security_baseline()
    ensure_task_permission("Company User")
    ensure_task_fields()
    frappe.clear_cache()
