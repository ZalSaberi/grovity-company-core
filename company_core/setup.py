import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import (
    add_permission,
    setup_custom_perms,
    update_permission_property,
)


PROJECT_TYPE_OPTIONS = [
    "Commercial",
    "Strategic R&D",
    "Research / Academic",
    "Internal",
    "Grant / Funded",
    "Other",
]

PROJECT_STATUS_OPTIONS = [
    "Draft",
    "Planned",
    "Active",
    "Suspended",
    "Delayed",
    "Awaiting Customer",
    "Awaiting Payment",
    "Under Review",
    "Completed",
    "Closed",
    "Cancelled",
]

PROJECT_HEALTH_OPTIONS = [
    "Healthy",
    "Attention",
    "At Risk",
    "Critical",
]

TECHNOLOGY_TAG_OPTIONS = [
    "AI",
    "Computer Vision",
    "Robotics",
    "UAV",
    "Navigation",
    "SLAM",
    "VIO",
    "Embedded",
    "Software",
    "Mechanical",
    "Control",
    "IoT",
    "Other",
]


def ensure_role(role_name):
    if not frappe.db.exists("Role", role_name):
        frappe.get_doc(
            {
                "doctype": "Role",
                "role_name": role_name,
                "desk_access": 1,
            }
        ).insert(ignore_permissions=True)
    else:
        frappe.db.set_value(
            "Role",
            role_name,
            "desk_access",
            1,
        )


def ensure_project_permission(role):
    setup_custom_perms("Project")

    permission_exists = frappe.db.exists(
        "Custom DocPerm",
        {
            "parent": "Project",
            "role": role,
            "permlevel": 0,
            "if_owner": 0,
        },
    )

    if not permission_exists:
        add_permission(
            "Project",
            role,
            permlevel=0,
            ptype="read",
        )

    permissions = {
        "select": 1,
        "read": 1,
        "write": 1,
        "create": 0,
        "delete": 0,
        "submit": 0,
        "cancel": 0,
    }

    for permission_type, value in permissions.items():
        update_permission_property(
            "Project",
            role,
            0,
            permission_type,
            value,
        )

    frappe.clear_cache(doctype="Project")


def ensure_security_baseline():
    ensure_role("Company Owner")
    ensure_role("Company User")

    ensure_project_permission("Company User")

    frappe.clear_cache()


def ensure_project_core_fields():
    custom_fields = {
        "Project": [
            {
                "fieldname": "custom_grovity_project_control_section",
                "label": "Grovity Project Control",
                "fieldtype": "Section Break",
                "insert_after": "project_name",
            },
            {
                "fieldname": "custom_project_type",
                "label": "Project Type",
                "fieldtype": "Select",
                "options": "\n".join(PROJECT_TYPE_OPTIONS),
                "insert_after": "custom_grovity_project_control_section",
            },
            {
                "fieldname": "custom_project_category",
                "label": "Project Category",
                "fieldtype": "Data",
                "insert_after": "custom_project_type",
            },
            {
                "fieldname": "custom_project_status",
                "label": "Project Lifecycle Status",
                "fieldtype": "Select",
                "options": "\n".join(PROJECT_STATUS_OPTIONS),
                "default": "Draft",
                "insert_after": "custom_project_category",
            },
            {
                "fieldname": "custom_project_health",
                "label": "Project Health",
                "fieldtype": "Select",
                "options": "\n".join(PROJECT_HEALTH_OPTIONS),
                "insert_after": "custom_project_status",
            },
            {
                "fieldname": "custom_confidentiality_level",
                "label": "Confidentiality Level",
                "fieldtype": "Data",
                "insert_after": "custom_project_health",
                "description": (
                    "Confidentiality taxonomy will be finalized "
                    "with the Legal and Contract Gate layer."
                ),
            },
            {
                "fieldname": "custom_grovity_project_dates_column",
                "fieldtype": "Column Break",
                "insert_after": "custom_confidentiality_level",
            },
            {
                "fieldname": "custom_actual_start_date",
                "label": "Actual Start Date",
                "fieldtype": "Date",
                "insert_after": "custom_grovity_project_dates_column",
            },
            {
                "fieldname": "custom_actual_end_date",
                "label": "Actual End Date",
                "fieldtype": "Date",
                "insert_after": "custom_actual_start_date",
            },
            {
                "fieldname": "custom_technology_tags",
                "label": "Technology Tags",
                "fieldtype": "Small Text",
                "insert_after": "custom_actual_end_date",
                "description": (
                    "Controlled technology taxonomy. "
                    "Examples: AI, UAV, Navigation, SLAM."
                ),
            },
            {
                "fieldname": "custom_grovity_commercial_section",
                "label": "Commercial & Integrations",
                "fieldtype": "Section Break",
                "insert_after": "custom_technology_tags",
            },
            {
                "fieldname": "custom_contract_value",
                "label": "Contract Value",
                "fieldtype": "Currency",
                "insert_after": "custom_grovity_commercial_section",
            },
            {
                "fieldname": "custom_collected_amount",
                "label": "Collected Amount",
                "fieldtype": "Currency",
                "insert_after": "custom_contract_value",
            },
            {
                "fieldname": "custom_grovity_links_column",
                "fieldtype": "Column Break",
                "insert_after": "custom_collected_amount",
            },
            {
                "fieldname": "custom_google_drive_folder",
                "label": "Google Drive Folder",
                "fieldtype": "Data",
                "options": "URL",
                "insert_after": "custom_grovity_links_column",
            },
            {
                "fieldname": "custom_repository_url",
                "label": "Repository URL",
                "fieldtype": "Data",
                "options": "URL",
                "insert_after": "custom_google_drive_folder",
            },
        ]
    }

    create_custom_fields(
        custom_fields,
        update=True,
    )

    frappe.clear_cache(doctype="Project")


def ensure_phase2_project_core():
    ensure_security_baseline()
    ensure_project_core_fields()

    frappe.clear_cache()
