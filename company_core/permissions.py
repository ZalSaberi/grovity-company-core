import frappe


PRIVILEGED_ROLES = {
    "System Manager",
    "Company Owner",
}


def is_privileged_user(user):
    user = user or frappe.session.user

    if user == "Administrator":
        return True

    user_roles = set(
        frappe.get_roles(user)
    )

    return bool(
        user_roles & PRIVILEGED_ROLES
    )


def has_active_project_membership(
    project,
    user,
):
    if not project or not user:
        return False

    return bool(
        frappe.db.exists(
            "Project Membership",
            {
                "project": project,
                "user": user,
                "status": "Active",
            },
        )
    )


def is_active_project_manager(
    project,
    user,
):
    if not project or not user:
        return False

    return bool(
        frappe.db.exists(
            "Project Membership",
            {
                "project": project,
                "user": user,
                "status": "Active",
                "membership_role": "Project Manager",
            },
        )
    )


def get_project_permission_query_conditions(
    user=None,
):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return ""

    escaped_user = frappe.db.escape(user)

    return f"""
        EXISTS (
            SELECT 1
            FROM `tabProject Membership` pm
            WHERE pm.project = `tabProject`.name
              AND pm.user = {escaped_user}
              AND pm.status = 'Active'
        )
    """


def has_project_permission(
    doc,
    user=None,
    ptype=None,
    **kwargs,
):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return True

    if ptype in (
        "create",
        "delete",
        "submit",
        "cancel",
    ):
        return False

    project = getattr(
        doc,
        "name",
        None,
    )

    if not project:
        return False

    if ptype == "write":
        return is_active_project_manager(
            project,
            user,
        )

    return has_active_project_membership(
        project,
        user,
    )


def get_project_membership_permission_query_conditions(
    user=None,
):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return ""

    escaped_user = frappe.db.escape(user)

    return f"""
        EXISTS (
            SELECT 1
            FROM `tabProject Membership` my_pm
            WHERE my_pm.project =
                `tabProject Membership`.project
              AND my_pm.user = {escaped_user}
              AND my_pm.status = 'Active'
        )
    """


def has_project_membership_permission(
    doc,
    user=None,
    ptype=None,
    **kwargs,
):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return True

    if ptype in (
        "write",
        "create",
        "delete",
        "submit",
        "cancel",
    ):
        return False

    project = getattr(
        doc,
        "project",
        None,
    )

    return has_active_project_membership(
        project,
        user,
    )


def get_project_status_history_permission_query_conditions(
    user=None,
):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return ""

    escaped_user = frappe.db.escape(user)

    return f"""
        EXISTS (
            SELECT 1
            FROM `tabProject Membership` pm
            WHERE pm.project =
                `tabProject Status History`.project
              AND pm.user = {escaped_user}
              AND pm.status = 'Active'
        )
    """


def has_project_status_history_permission(
    doc,
    user=None,
    ptype=None,
    **kwargs,
):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return True

    if ptype not in (
        "read",
        "select",
    ):
        return False

    project = getattr(
        doc,
        "project",
        None,
    )

    return has_active_project_membership(
        project,
        user,
    )


def get_suspension_event_permission_query_conditions(
    user=None,
):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return ""

    escaped_user = frappe.db.escape(user)

    return f"""
        EXISTS (
            SELECT 1
            FROM `tabProject Membership` pm
            WHERE pm.project =
                `tabSuspension Event`.project
              AND pm.user = {escaped_user}
              AND pm.status = 'Active'
        )
    """


def has_suspension_event_permission(
    doc,
    user=None,
    ptype=None,
    **kwargs,
):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return True

    project = getattr(
        doc,
        "project",
        None,
    )

    if not project:
        return False

    if ptype in (
        None,
        "read",
        "select",
    ):
        return has_active_project_membership(
            project,
            user,
        )

    if ptype in (
        "create",
        "write",
    ):
        return is_active_project_manager(
            project,
            user,
        )

    return False

# === GROVITY PHASE 2D TASK CORE ===

def is_task_contributor(task, user):
    if not task or not user:
        return False

    return bool(
        frappe.db.exists(
            "Task Contributor",
            {
                "parent": task,
                "parenttype": "Task",
                "user": user,
            },
        )
    )


def is_task_assigned_to_user(task, user):
    if not task or not user:
        return False

    return bool(
        frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Task",
                "reference_name": task,
                "allocated_to": user,
                "status": ["!=", "Cancelled"],
            },
        )
    )


def can_work_on_task(doc, user):
    project = getattr(doc, "project", None)

    if not project:
        return False

    if is_active_project_manager(project, user):
        return True

    task = getattr(doc, "name", None)

    if not task:
        return False

    if is_task_contributor(task, user):
        return True

    return is_task_assigned_to_user(task, user)


def get_task_permission_query_conditions(user=None):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return ""

    escaped_user = frappe.db.escape(user)

    return f"""
        EXISTS (
            SELECT 1
            FROM `tabProject Membership` pm
            WHERE pm.project = `tabTask`.project
              AND pm.user = {escaped_user}
              AND pm.status = 'Active'
              AND (
                    pm.membership_role = 'Project Manager'
                    OR EXISTS (
                        SELECT 1
                        FROM `tabTask Contributor` tc
                        WHERE tc.parent = `tabTask`.name
                          AND tc.parenttype = 'Task'
                          AND tc.user = {escaped_user}
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM `tabToDo` td
                        WHERE td.reference_type = 'Task'
                          AND td.reference_name = `tabTask`.name
                          AND td.allocated_to = {escaped_user}
                          AND IFNULL(td.status, 'Open') != 'Cancelled'
                    )
              )
        )
    """


def has_task_permission(doc, user=None, ptype=None, **kwargs):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return True

    project = getattr(doc, "project", None)

    if not project:
        return False

    if ptype in (None, "read", "select"):
        return can_work_on_task(doc, user)

    if ptype == "create":
        return is_active_project_manager(project, user)

    if ptype == "write":
        return can_work_on_task(doc, user)

    if ptype == "delete":
        return is_active_project_manager(project, user)

    return False

