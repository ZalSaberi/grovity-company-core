import frappe

from company_core.permissions import (
    is_active_project_manager,
    is_privileged_user,
)


EXECUTION_ROLES = {
    "Project Manager",
    "Contributor",
    "Intern",
    "Internal Specialist",
}


def get_membership_role(project, user):
    if not project or not user:
        return None

    return frappe.db.get_value(
        "Project Membership",
        {
            "project": project,
            "user": user,
            "status": "Active",
        },
        "membership_role",
    )


def is_meeting_participant(meeting, user):
    if not meeting or not user:
        return False

    return bool(
        frappe.db.exists(
            "Meeting Participant",
            {
                "parent": meeting,
                "parenttype": "Project Meeting",
                "user": user,
            },
        )
    )


def get_project_meeting_permission_query_conditions(user=None):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return ""

    escaped_user = frappe.db.escape(user)

    return f"""
        (
            EXISTS (
                SELECT 1
                FROM `tabProject Membership` pm
                WHERE pm.project = `tabProject Meeting`.project
                  AND pm.user = {escaped_user}
                  AND pm.status = 'Active'
                  AND pm.membership_role = 'Project Manager'
            )
            OR EXISTS (
                SELECT 1
                FROM `tabMeeting Participant` mp
                WHERE mp.parent = `tabProject Meeting`.name
                  AND mp.parenttype = 'Project Meeting'
                  AND mp.user = {escaped_user}
            )
        )
    """


def has_project_meeting_permission(doc, user=None, ptype=None, **kwargs):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return True

    project = getattr(doc, "project", None)

    if not project:
        return False

    if ptype in ("create", "write", "delete"):
        return is_active_project_manager(project, user)

    if ptype in (None, "read", "select"):
        if is_active_project_manager(project, user):
            return True

        return is_meeting_participant(
            getattr(doc, "name", None),
            user,
        )

    return False


def get_meeting_action_permission_query_conditions(user=None):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return ""

    escaped_user = frappe.db.escape(user)

    return f"""
        (
            `tabMeeting Action`.assigned_to = {escaped_user}
            OR EXISTS (
                SELECT 1
                FROM `tabProject Membership` pm
                WHERE pm.project = `tabMeeting Action`.project
                  AND pm.user = {escaped_user}
                  AND pm.status = 'Active'
                  AND pm.membership_role = 'Project Manager'
            )
        )
    """


def has_meeting_action_permission(doc, user=None, ptype=None, **kwargs):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return True

    project = getattr(doc, "project", None)

    if not project:
        return False

    if ptype == "create":
        return is_active_project_manager(project, user)

    if ptype == "delete":
        return is_active_project_manager(project, user)

    if ptype in (None, "read", "select", "write"):
        if is_active_project_manager(project, user):
            return True

        return getattr(doc, "assigned_to", None) == user

    return False


def get_progress_report_permission_query_conditions(user=None):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return ""

    escaped_user = frappe.db.escape(user)

    return f"""
        EXISTS (
            SELECT 1
            FROM `tabProject Membership` pm
            WHERE pm.project = `tabProgress Report`.project
              AND pm.user = {escaped_user}
              AND pm.status = 'Active'
        )
    """


def has_progress_report_permission(doc, user=None, ptype=None, **kwargs):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return True

    project = getattr(doc, "project", None)

    if not project:
        return False

    role = get_membership_role(project, user)

    if not role:
        return False

    if ptype == "create":
        return role in EXECUTION_ROLES

    if ptype == "delete":
        return is_active_project_manager(project, user)

    if ptype == "write":
        if is_active_project_manager(project, user):
            return True

        return (
            getattr(doc, "submitted_by", None) == user
            and getattr(doc, "approval_status", None)
            in ("Draft", "Revision Requested")
        )

    if ptype in (None, "read", "select"):
        return True

    return False
