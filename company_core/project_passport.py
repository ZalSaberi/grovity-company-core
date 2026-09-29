
import frappe
from frappe import _
from frappe.utils import flt


def _get_readable_project(project):
    if not project:
        frappe.throw(
            _("Project is required.")
        )

    doc = frappe.get_doc(
        "Project",
        project,
    )

    if not frappe.has_permission(
        "Project",
        ptype="read",
        doc=doc,
        user=frappe.session.user,
    ):
        frappe.throw(
            _("Not permitted to view this Project."),
            frappe.PermissionError,
        )

    return doc


def _display_name(user):
    if not user:
        return ""

    return (
        frappe.db.get_value(
            "User",
            user,
            "full_name",
        )
        or user
    )


@frappe.whitelist()
def get_project_passport(project):
    doc = _get_readable_project(
        project
    )

    memberships = frappe.get_all(
        "Project Membership",
        filters={
            "project": project,
            "status": "Active",
        },
        fields=[
            "user",
            "membership_role",
        ],
        order_by="creation asc",
    )

    manager_users = [
        row.user
        for row in memberships
        if row.membership_role
        == "Project Manager"
    ]

    managers = [
        {
            "user": user,
            "name": _display_name(user),
        }
        for user in manager_users
    ]

    observers = sum(
        1
        for row in memberships
        if row.membership_role
        == "Observer"
    )

    team = sum(
        1
        for row in memberships
        if row.membership_role
        != "Observer"
    )

    finance_status = (
        doc.get(
            "custom_finance_status"
        )
        or _("Not configured")
    )

    legal_status = (
        doc.get(
            "custom_legal_status"
        )
        or _("Not configured")
    )

    deadline = (
        doc.get("expected_end_date")
        or doc.get("actual_end_date")
        or None
    )

    progress = flt(
        doc.get("percent_complete")
        or 0
    )

    contract_value = flt(
        doc.get(
            "custom_contract_value"
        )
        or 0
    )

    collected_amount = flt(
        doc.get(
            "custom_collected_amount"
        )
        or 0
    )

    project_cost = flt(
        doc.get(
            "custom_project_cost"
        )
        or 0
    )

    return {
        "project": doc.name,
        "project_name": (
            doc.get("project_name")
            or doc.name
        ),
        "managers": managers,
        "manager_display": (
            ", ".join(
                manager["name"]
                for manager in managers
            )
            or _("Unassigned")
        ),
        "progress": round(
            progress,
            1,
        ),
        "health": (
            doc.get(
                "custom_project_health"
            )
            or _("Not set")
        ),
        "deadline": deadline,
        "team_count": team,
        "observer_count": observers,
        "contract_value": contract_value,
        "collected_amount": (
            collected_amount
        ),
        "project_cost": project_cost,
        "finance_status": finance_status,
        "legal_status": legal_status,
    }
