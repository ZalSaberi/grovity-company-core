
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

    allowed = frappe.has_permission(
        "Project",
        ptype="read",
        doc=doc,
        user=frappe.session.user,
    )

    if not allowed:
        frappe.throw(
            _("Not permitted to view this Project."),
            frappe.PermissionError,
        )

    return doc


@frappe.whitelist()
def get_project_view_summary(project):
    _get_readable_project(project)

    tasks = frappe.get_list(
        "Task",
        filters={
            "project": project,
        },
        fields=[
            "name",
            "status",
            "progress",
            "is_milestone",
        ],
        limit=0,
    )

    total = len(tasks)

    milestones = sum(
        1
        for task in tasks
        if task.is_milestone
    )

    completed = sum(
        1
        for task in tasks
        if task.status == "Completed"
    )

    overdue = sum(
        1
        for task in tasks
        if task.status == "Overdue"
    )

    working = sum(
        1
        for task in tasks
        if task.status in (
            "Open",
            "Working",
            "Pending Review",
            "Overdue",
        )
    )

    average_progress = 0.0

    if total:
        average_progress = sum(
            flt(task.progress or 0)
            for task in tasks
        ) / total

    return {
        "project": project,
        "visible_tasks": total,
        "milestones": milestones,
        "working": working,
        "completed": completed,
        "overdue": overdue,
        "average_progress": round(
            average_progress,
            1,
        ),
    }
