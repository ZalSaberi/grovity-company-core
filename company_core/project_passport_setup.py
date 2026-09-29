
import frappe
from frappe.custom.doctype.custom_field.custom_field import (
    create_custom_fields,
)


def ensure_project_passport_fields():
    custom_fields = {
        "Project": [
            {
                "fieldname": "custom_grovity_passport_section",
                "label": "Project Passport",
                "fieldtype": "Section Break",
                "insert_after": "project_name",
            },
            {
                "fieldname": "custom_project_passport",
                "label": "Project Passport",
                "fieldtype": "HTML",
                "insert_after": "custom_grovity_passport_section",
            },
            {
                "fieldname": "custom_grovity_project_control_section",
                "label": "Grovity Project Control",
                "fieldtype": "Section Break",
                "insert_after": "custom_project_passport",
            },
            {
                "fieldname": "custom_project_cost",
                "label": "Project Cost",
                "fieldtype": "Currency",
                "insert_after": "custom_collected_amount",
                "description": (
                    "Current project cost snapshot. "
                    "Detailed finance logic will be implemented "
                    "in the Finance phase."
                ),
            },
            {
                "fieldname": "custom_finance_status",
                "label": "Finance Status",
                "fieldtype": "Data",
                "insert_after": "custom_project_cost",
                "description": (
                    "Finance taxonomy will be finalized "
                    "in the Finance phase."
                ),
            },
            {
                "fieldname": "custom_legal_status",
                "label": "Legal Status",
                "fieldtype": "Data",
                "insert_after": "custom_finance_status",
                "description": (
                    "Legal taxonomy will be finalized "
                    "in the Legal and Contract Gates phase."
                ),
            },
        ]
    }

    create_custom_fields(
        custom_fields,
        update=True,
    )

    frappe.clear_cache(
        doctype="Project"
    )


def ensure_project_passport():
    ensure_project_passport_fields()
    frappe.clear_cache()
