import frappe
from frappe.permissions import (
    add_permission,
    setup_custom_perms,
    update_permission_property,
)


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
