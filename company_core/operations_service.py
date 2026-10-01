from __future__ import annotations

import re
from html import escape, unescape

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from company_core.notification_engine import dispatch_events
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


def _plain_html(value):
    return " ".join(
        unescape(
            re.sub(r"<[^>]+>", " ", str(value or ""))
        ).split()
    )


def _project_label(project):
    return (
        frappe.db.get_value("Project", project, "project_name")
        or project
        or ""
    )


def _meeting_action_snapshot(meeting_name):
    actions = frappe.get_all(
        "Meeting Action",
        filters={
            "meeting": meeting_name,
            "status": ["!=", "Cancelled"],
        },
        fields=[
            "name",
            "description",
            "assigned_to",
            "deadline",
            "priority",
            "status",
        ],
        order_by="deadline asc, creation asc",
        limit=0,
    )

    if not actions:
        return actions, "اقدامی ثبت نشده است.", "<p>اقدامی ثبت نشده است.</p>"

    text_lines = []
    html_rows = []
    for index, action in enumerate(actions, 1):
        description = _plain_html(action.description)
        text_lines.append(
            f"{index}. {description} | مسئول: {action.assigned_to} | موعد: {action.deadline}"
        )
        html_rows.append(
            "<li>"
            f"<strong>{escape(description)}</strong><br>"
            f"مسئول: {escape(action.assigned_to or '')}<br>"
            f"موعد: {escape(str(action.deadline or ''))}"
            "</li>"
        )

    return actions, "\n".join(text_lines), "<ol>" + "".join(html_rows) + "</ol>"


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
def publish_meeting_summary(meeting):
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
            _("Only the Project Manager can publish the meeting summary."),
            frappe.PermissionError,
        )

    if doc.summary_published:
        return {
            "meeting": doc.name,
            "already_published": True,
            "summary_recipients": 0,
            "action_notifications": 0,
        }

    if not doc.pm_confirmation:
        frappe.throw(
            _("PM confirmation is required before publishing the meeting summary.")
        )

    if get_datetime(doc.meeting_datetime) > now_datetime():
        frappe.throw(
            _("The meeting summary cannot be published before the meeting time.")
        )

    if not _plain_html(doc.summary):
        frappe.throw(
            _("Meeting Summary is required before publication.")
        )

    participants = sorted({
        row.user
        for row in (doc.participants or [])
        if row.user and row.user != "Guest"
    })
    if not participants:
        frappe.throw(
            _("At least one Meeting Participant is required before publication.")
        )

    actions, action_items, action_items_html = _meeting_action_snapshot(doc.name)
    project_name = _project_label(doc.project)

    doc.flags.publication_service = True
    doc.summary_published = 1
    doc.summary_published_at = now_datetime()
    doc.summary_published_by = frappe.session.user
    doc.save(ignore_permissions=True)

    summary_event = frappe._dict({
        "source_doctype": "Project Meeting",
        "source_name": doc.name,
        "project": doc.project,
        "event_code": "MEETING_SUMMARY_PUBLISHED",
        "stage": "",
        "recipients": participants,
        "context": {
            "project_name": project_name,
            "meeting_datetime": doc.meeting_datetime,
            "meeting_title": _plain_html(doc.agenda) or doc.name,
            "meeting_summary": doc.summary or "",
            "decisions": doc.decisions or "<p>—</p>",
            "action_items": action_items,
            "action_items_html": action_items_html,
            "item_title": doc.name,
            "status": doc.status,
        },
    })

    events = [summary_event]
    for action in actions:
        if not action.assigned_to:
            continue
        events.append(
            frappe._dict({
                "source_doctype": "Meeting Action",
                "source_name": action.name,
                "project": doc.project,
                "event_code": "MEETING_ACTION_ASSIGNED",
                "stage": "",
                "recipients": [action.assigned_to],
                "context": {
                    "project_name": project_name,
                    "item_type": "اقدام جلسه",
                    "item_title": _plain_html(action.description),
                    "deadline": action.deadline,
                    "assigned_to": action.assigned_to,
                    "priority": action.priority or "",
                    "status": action.status or "",
                    "meeting_datetime": doc.meeting_datetime,
                    "meeting_title": _plain_html(doc.agenda) or doc.name,
                },
            })
        )

    result = dispatch_events(events)
    frappe.db.commit()

    return {
        "meeting": doc.name,
        "already_published": False,
        "summary_recipients": len(participants),
        "action_notifications": len(events) - 1,
        "delivery_result": result,
    }


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

    if decision == "Revision Requested" and doc.submitted_by:
        event = frappe._dict({
            "source_doctype": "Progress Report",
            "source_name": doc.name,
            "project": doc.project,
            "event_code": "PROGRESS_REPORT_REVISION_REQUESTED",
            "event_token": str(doc.modified),
            "stage": "",
            "recipients": [doc.submitted_by],
            "context": {
                "project_name": _project_label(doc.project),
                "item_type": "گزارش پیشرفت",
                "item_title": doc.name,
                "report_period": doc.period,
                "manager_comment": doc.manager_comment,
                "status": doc.approval_status,
                "assigned_to": doc.submitted_by,
            },
        })
        dispatch_events([event])

    return doc.name
