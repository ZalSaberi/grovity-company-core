import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_status_history_fields():
    custom_fields = {
        "Project": [
            {
                "fieldname": "custom_status_change_reason",
                "label": "Status Change Reason",
                "fieldtype": "Small Text",
                "insert_after": "custom_project_status",
                "no_copy": 1,
                "description": (
                    "Required when Project Lifecycle Status changes. "
                    "The reason is copied to Project Status History "
                    "and cleared after the transition is recorded."
                ),
            },
        ]
    }

    create_custom_fields(
        custom_fields,
        update=True,
    )

    frappe.clear_cache(doctype="Project")
