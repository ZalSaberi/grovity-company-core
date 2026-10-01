import frappe
from frappe import _
from frappe.utils import now_datetime

from company_core.permissions import (
    is_active_project_manager,
    is_privileged_user,
)


def _get_doc_with_permission(doctype, name, ptype="read"):
    doc = frappe.get_doc(doctype, name)

    if not frappe.has_permission(
        doctype,
        ptype=ptype,
        doc=doc,
        user=frappe.session.user,
    ):
        frappe.throw(
            _("Not permitted."),
            frappe.PermissionError,
        )

    return doc


@frappe.whitelist()
def confirm_meeting_as_pm(meeting):
    doc = _get_doc_with_permission(
        "Project Meeting",
        meeting,
        "write",
    )

    if not (
        is_active_project_manager(doc.project, frappe.session.user)
        or is_privileged_user(frappe.session.user)
    ):
        frappe.throw(
            _("Only the Project Manager can confirm this meeting."),
            frappe.PermissionError,
        )

    if doc.status == "Final":
        return doc.name

    doc.flags.confirmation_service = True
    doc.pm_confirmation = 1
    doc.save(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def confirm_meeting_as_ceo(meeting):
    doc = frappe.get_doc("Project Meeting", meeting)

    if not is_privileged_user(frappe.session.user):
        frappe.throw(
            _(
                "Only Company Owner / System Manager can perform "
                "CEO confirmation."
            ),
            frappe.PermissionError,
        )

    if not doc.pm_confirmation:
        frappe.throw(
            _("PM confirmation is required before CEO confirmation.")
        )

    if doc.status == "Final":
        return doc.name

    doc.flags.confirmation_service = True
    doc.ceo_confirmation = 1
    doc.save(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def create_task_from_action(action):
    doc = _get_doc_with_permission(
        "Meeting Action",
        action,
        "write",
    )

    if not (
        is_active_project_manager(doc.project, frappe.session.user)
        or is_privileged_user(frappe.session.user)
    ):
        frappe.throw(
            _("Only the Project Manager can create a Task from an Action."),
            frappe.PermissionError,
        )

    if doc.linked_task:
        return doc.linked_task

    task = frappe.get_doc(
        {
            "doctype": "Task",
            "project": doc.project,
            "subject": (doc.description or "Meeting Action")[:140],
            "status": "Open",
            "priority": "High" if doc.priority == "Urgent" else doc.priority,
            "exp_end_date": doc.deadline,
            "custom_planned_progress": 0,
        }
    )

    if doc.assigned_to:
        task.append(
            "custom_contributors",
            {"user": doc.assigned_to},
        )

    task.insert(ignore_permissions=True)

    frappe.db.set_value(
        "Meeting Action",
        doc.name,
        "linked_task",
        task.name,
        update_modified=True,
    )

    return task.name


@frappe.whitelist()
def submit_progress_report(report):
    doc = _get_doc_with_permission(
        "Progress Report",
        report,
        "write",
    )

    if doc.approval_status not in ("Draft", "Revision Requested"):
        frappe.throw(
            _("Only Draft or Revision Requested reports can be submitted.")
        )

    doc.flags.workflow_service = True
    doc.approval_status = "Submitted"
    doc.submitted_at = now_datetime()
    doc.save(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def review_progress_report(report, decision, comment=None):
    doc = frappe.get_doc("Progress Report", report)

    if not (
        is_active_project_manager(doc.project, frappe.session.user)
        or is_privileged_user(frappe.session.user)
    ):
        frappe.throw(
            _("Only the Project Manager can review this Progress Report."),
            frappe.PermissionError,
        )

    if doc.approval_status != "Submitted":
        frappe.throw(
            _("Only Submitted reports can be reviewed.")
        )

    if decision not in ("Approved", "Revision Requested"):
        frappe.throw(
            _("Decision must be Approved or Revision Requested.")
        )

    if decision == "Revision Requested" and not (comment or "").strip():
        frappe.throw(
            _("Manager Comment is required when requesting revision.")
        )

    doc.flags.workflow_service = True
    doc.approval_status = decision
    doc.manager_comment = comment or ""

    if decision == "Approved":
        doc.approved_by = frappe.session.user
        doc.approved_at = now_datetime()
    else:
        doc.approved_by = None
        doc.approved_at = None

    doc.save(ignore_permissions=True)
    return doc.name
