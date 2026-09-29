
import frappe
from frappe import _
from frappe.utils import flt


def validate_task_extensions(doc, method=None):
    validate_progress(doc)
    validate_milestone(doc)
    validate_contributors(doc)
    sync_actual_progress(doc)


def validate_progress(doc):
    planned = flt(doc.get("custom_planned_progress") or 0)
    actual = flt(doc.get("progress") or 0)

    if planned < 0 or planned > 100:
        frappe.throw(_("Planned Progress must be between 0 and 100."))

    if actual < 0 or actual > 100:
        frappe.throw(_("Task Progress must be between 0 and 100."))


def validate_milestone(doc):
    milestone = doc.get("custom_milestone")

    if not milestone:
        return

    if doc.name and milestone == doc.name:
        frappe.throw(_("A task cannot use itself as its milestone."))

    milestone_data = frappe.db.get_value(
        "Task",
        milestone,
        ["project", "is_milestone"],
        as_dict=True,
    )

    if not milestone_data:
        frappe.throw(_("Milestone Task does not exist."))

    if not milestone_data.is_milestone:
        frappe.throw(_("Selected Milestone must be a Task marked as Is Milestone."))

    if doc.project != milestone_data.project:
        frappe.throw(_("Task and Milestone must belong to the same Project."))


def validate_contributors(doc):
    seen = set()

    for row in doc.get("custom_contributors") or []:
        user = row.user

        if not user:
            continue

        if user in seen:
            frappe.throw(_("Contributor {0} is duplicated.").format(user))

        seen.add(user)


def sync_actual_progress(doc):
    doc.custom_actual_progress = flt(doc.get("progress") or 0)
