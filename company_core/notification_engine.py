from __future__ import annotations

import hashlib
from collections import defaultdict
from html import escape

import frappe
from frappe.utils import add_days, cint, getdate, now_datetime, today

from company_core.notification_templates import load_templates, render_delivery


REMINDER_DAYS = {7: "T-7", 3: "T-3", 1: "T-1", 0: "Due Date"}

STAGE_EVENT_CODES = {
    "T-7": "DEADLINE_T7",
    "T-3": "DEADLINE_T3",
    "T-1": "DEADLINE_T1",
    "Due Date": "DEADLINE_DUE",
    "Overdue": "DEADLINE_OVERDUE",
}


def get_settings():
    doc = frappe.get_single("Grovity Notification Settings")
    return frappe._dict({
        "enable_in_app": cint(doc.enable_in_app),
        "enable_email": cint(doc.enable_email),
        "enable_sms": cint(doc.enable_sms),
        "email_from_name": doc.email_from_name or "Grovity Project Management",
        "sms_t7": cint(doc.sms_t7),
        "sms_t3": cint(doc.sms_t3),
        "sms_t1": cint(doc.sms_t1),
        "sms_due_date": cint(doc.sms_due_date),
        "sms_overdue": cint(doc.sms_overdue),
        "retry_limit": max(cint(doc.retry_limit), 1),
    })


def channels_for_stage(stage, settings=None):
    settings = settings or get_settings()
    channels = []
    if settings.enable_in_app:
        channels.append("In-App")
    if settings.enable_email:
        channels.append("Email")
    sms_field = {
        "T-7": "sms_t7",
        "T-3": "sms_t3",
        "T-1": "sms_t1",
        "Due Date": "sms_due_date",
        "Overdue": "sms_overdue",
    }.get(stage)
    if settings.enable_sms and sms_field and cint(settings.get(sms_field)):
        channels.append("SMS")
    return channels


def channels_for_event(event, settings=None, template=None):
    settings = settings or get_settings()

    if template and not cint(template.enabled):
        return []

    if event.get("stage") in STAGE_EVENT_CODES:
        channels = channels_for_stage(event.stage, settings)
        if not template:
            return channels
        allowed = {
            "In-App": cint(template.enable_in_app),
            "Email": cint(template.enable_email),
            "SMS": cint(template.enable_sms),
        }
        return [channel for channel in channels if allowed.get(channel)]

    if not template:
        return channels_for_stage(event.get("stage"), settings)

    channels = []
    if settings.enable_in_app and cint(template.enable_in_app):
        channels.append("In-App")
    if settings.enable_email and cint(template.enable_email):
        channels.append("Email")
    if settings.enable_sms and cint(template.enable_sms):
        channels.append("SMS")
    return channels


def _stage(due_date, current_date):
    if not due_date:
        return None
    delta = (getdate(due_date) - getdate(current_date)).days
    if delta in REMINDER_DAYS:
        return REMINDER_DAYS[delta]
    if delta < 0:
        return "Overdue"
    return None


def _group(rows, key, value):
    result = defaultdict(list)
    for row in rows:
        result[row.get(key)].append(row.get(value))
    return result


def _unique_users(users):
    return sorted({user for user in users if user and user != "Guest"})


def _overdue_days(due_date, current_date):
    if not due_date:
        return 0
    delta = (getdate(current_date) - getdate(due_date)).days
    return max(delta, 0)


def collect_due_events(current_date=None, project=None):
    current_date = current_date or today()
    horizon = add_days(current_date, 7)

    task_filters = {
        "exp_end_date": ["<=", horizon],
        "status": ["not in", ["Completed", "Cancelled"]],
    }
    action_filters = {
        "deadline": ["<=", horizon],
        "status": ["not in", ["Completed", "Cancelled"]],
    }
    meeting_filters = {"meeting_datetime": ["<=", horizon]}

    if project:
        task_filters["project"] = project
        action_filters["project"] = project
        meeting_filters["project"] = project

    tasks = frappe.get_all(
        "Task",
        filters=task_filters,
        fields=[
            "name",
            "subject",
            "project",
            "exp_end_date",
            "is_milestone",
            "custom_deliverable",
            "status",
            "priority",
        ],
        limit=0,
    )
    actions = frappe.get_all(
        "Meeting Action",
        filters=action_filters,
        fields=[
            "name",
            "project",
            "description",
            "assigned_to",
            "deadline",
            "status",
            "priority",
        ],
        limit=0,
    )
    meetings = frappe.get_all(
        "Project Meeting",
        filters=meeting_filters,
        fields=["name", "project", "meeting_datetime", "prepared_by", "status"],
        limit=0,
    )

    projects = {row.project for row in tasks + actions + meetings if row.project}
    managers = defaultdict(list)
    if projects:
        managers = _group(
            frappe.get_all(
                "Project Membership",
                filters={
                    "project": ["in", list(projects)],
                    "status": "Active",
                    "membership_role": "Project Manager",
                },
                fields=["project", "user"],
                limit=0,
            ),
            "project",
            "user",
        )

    task_names = [row.name for row in tasks]
    contributors = defaultdict(list)
    assignments = defaultdict(list)
    if task_names:
        contributors = _group(
            frappe.get_all(
                "Task Contributor",
                filters={"parent": ["in", task_names], "parenttype": "Task"},
                fields=["parent", "user"],
                limit=0,
            ),
            "parent",
            "user",
        )
        assignments = _group(
            frappe.get_all(
                "ToDo",
                filters={
                    "reference_type": "Task",
                    "reference_name": ["in", task_names],
                    "status": ["!=", "Cancelled"],
                },
                fields=["reference_name", "allocated_to"],
                limit=0,
            ),
            "reference_name",
            "allocated_to",
        )

    meeting_names = [row.name for row in meetings]
    participants = defaultdict(list)
    if meeting_names:
        participants = _group(
            frappe.get_all(
                "Meeting Participant",
                filters={"parent": ["in", meeting_names], "parenttype": "Project Meeting"},
                fields=["parent", "user"],
                limit=0,
            ),
            "parent",
            "user",
        )

    events = []

    for row in tasks:
        stage = _stage(row.exp_end_date, current_date)
        if not stage:
            continue
        if row.is_milestone:
            kind = "نقطه عطف"
        elif row.custom_deliverable:
            kind = "تحویل‌دادنی"
        else:
            kind = "وظیفه"

        recipients = managers[row.project] + contributors[row.name] + assignments[row.name]
        events.append(frappe._dict({
            "source_doctype": "Task",
            "source_name": row.name,
            "project": row.project,
            "stage": stage,
            "event_code": STAGE_EVENT_CODES[stage],
            "recipients": _unique_users(recipients),
            "context": {
                "project_name": row.project,
                "item_type": kind,
                "item_title": row.subject,
                "deadline": row.exp_end_date,
                "remaining_days": max((getdate(row.exp_end_date) - getdate(current_date)).days, 0),
                "overdue_days": _overdue_days(row.exp_end_date, current_date),
                "status": row.status,
                "assigned_to": ", ".join(_unique_users(contributors[row.name] + assignments[row.name])),
                "priority": row.priority or "",
            },
        }))

    for row in actions:
        stage = _stage(row.deadline, current_date)
        if not stage:
            continue
        recipients = [row.assigned_to, *managers[row.project]]
        events.append(frappe._dict({
            "source_doctype": "Meeting Action",
            "source_name": row.name,
            "project": row.project,
            "stage": stage,
            "event_code": STAGE_EVENT_CODES[stage],
            "recipients": _unique_users(recipients),
            "context": {
                "project_name": row.project,
                "item_type": "اقدام جلسه",
                "item_title": row.description,
                "deadline": row.deadline,
                "remaining_days": max((getdate(row.deadline) - getdate(current_date)).days, 0),
                "overdue_days": _overdue_days(row.deadline, current_date),
                "status": row.status,
                "assigned_to": row.assigned_to or "",
                "priority": row.priority or "",
            },
        }))

    for row in meetings:
        stage = _stage(row.meeting_datetime, current_date)
        if not stage:
            continue
        recipients = [row.prepared_by, *managers[row.project], *participants[row.name]]
        events.append(frappe._dict({
            "source_doctype": "Project Meeting",
            "source_name": row.name,
            "project": row.project,
            "stage": stage,
            "event_code": "MEETING_REMINDER",
            "recipients": _unique_users(recipients),
            "context": {
                "project_name": row.project,
                "item_type": "جلسه پروژه",
                "item_title": row.name,
                "deadline": row.meeting_datetime,
                "meeting_datetime": row.meeting_datetime,
                "meeting_title": row.name,
                "remaining_days": max((getdate(row.meeting_datetime) - getdate(current_date)).days, 0),
                "overdue_days": _overdue_days(row.meeting_datetime, current_date),
                "status": row.status,
                "assigned_to": row.prepared_by or "",
            },
        }))

    return events


def _event_key(event, channel, user):
    raw = "|".join([
        event.get("source_doctype") or "",
        event.get("source_name") or "",
        event.get("event_code") or event.get("stage") or "",
        event.get("event_token") or "",
        channel or "",
        user or "",
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _destination(user, channel):
    if channel == "In-App":
        return user
    if channel == "Email":
        return frappe.db.get_value("User", user, "email") or (user if "@" in (user or "") else None)
    if channel == "SMS":
        return frappe.db.get_value("User", user, "mobile_no")
    return None


def _delivery(event, user, channel, template=None):
    key = _event_key(event, channel, user)
    existing = frappe.db.get_value("Notification Delivery", {"event_key": key}, "name")
    if existing:
        return frappe.get_doc("Notification Delivery", existing), False

    subject, message = render_delivery(event, channel, user, template=template)

    doc = frappe.get_doc({
        "doctype": "Notification Delivery",
        "event_key": key,
        "source_doctype": event.get("source_doctype"),
        "source_name": event.get("source_name"),
        "project": event.get("project"),
        "stage": event.get("stage") or "",
        "event_code": event.get("event_code") or "",
        "channel": channel,
        "recipient_user": user,
        "destination": _destination(user, channel) or "",
        "subject": subject,
        "message": message,
        "status": "Pending",
        "attempt_count": 0,
    })
    try:
        doc.insert(ignore_permissions=True)
        return doc, True
    except frappe.DuplicateEntryError:
        name = frappe.db.get_value("Notification Delivery", {"event_key": key}, "name")
        return frappe.get_doc("Notification Delivery", name), False


def _update(doc, **values):
    values["last_attempt_at"] = now_datetime()
    frappe.db.set_value("Notification Delivery", doc.name, values, update_modified=True)
    for fieldname, value in values.items():
        doc.set(fieldname, value)


def _in_app(doc):
    if not doc.destination:
        _update(doc, status="Skipped", attempt_count=cint(doc.attempt_count) + 1, last_error="Recipient missing.")
        return "Skipped"
    frappe.get_doc({
        "doctype": "Notification Log",
        "subject": doc.subject,
        "for_user": doc.destination,
        "type": "Alert",
        "document_type": doc.source_doctype,
        "document_name": doc.source_name,
        "from_user": "Administrator",
    }).insert(ignore_permissions=True)
    _update(doc, status="Sent", attempt_count=cint(doc.attempt_count) + 1, sent_at=now_datetime(), last_error="")
    return "Sent"


def _email(doc):
    if not doc.destination:
        _update(doc, status="Skipped", attempt_count=cint(doc.attempt_count) + 1, last_error="User has no email address.")
        return "Skipped"
    if not frappe.db.exists("Email Account", {"enable_outgoing": 1, "default_outgoing": 1}):
        _update(
            doc,
            status="Failed",
            attempt_count=cint(doc.attempt_count) + 1,
            last_error="No default outgoing Email Account is configured.",
        )
        return "Failed"
    try:
        q = frappe.sendmail(
            recipients=[doc.destination],
            subject=doc.subject,
            message=doc.message or "<p>Grovity notification.</p>",
            reference_doctype=doc.source_doctype,
            reference_name=doc.source_name,
            now=False,
            queue_separately=False,
            add_unsubscribe_link=False,
            is_notification=True,
        )
        _update(
            doc,
            status="Queued",
            attempt_count=cint(doc.attempt_count) + 1,
            provider_reference=getattr(q, "name", None) or "",
            queued_at=now_datetime(),
            last_error="",
        )
        return "Queued"
    except Exception:
        _update(doc, status="Failed", attempt_count=cint(doc.attempt_count) + 1, last_error=frappe.get_traceback())
        return "Failed"


def _sms(doc):
    if not doc.destination:
        _update(doc, status="Skipped", attempt_count=cint(doc.attempt_count) + 1, last_error="User has no mobile number.")
        return "Skipped"
    try:
        from frappe.core.doctype.sms_settings.sms_settings import send_sms
        result = send_sms([doc.destination], doc.message)
        _update(
            doc,
            status="Sent",
            attempt_count=cint(doc.attempt_count) + 1,
            provider_reference=(str(result) if result is not None else "")[:140],
            sent_at=now_datetime(),
            last_error="",
        )
        return "Sent"
    except Exception:
        _update(doc, status="Failed", attempt_count=cint(doc.attempt_count) + 1, last_error=frappe.get_traceback())
        return "Failed"


def dispatch_events(events, dry_run=False):
    settings = get_settings()
    event_codes = [event.get("event_code") for event in events if event.get("event_code")]
    templates = load_templates(event_codes)
    result = {"created": 0, "sent": 0, "queued": 0, "failed": 0, "skipped": 0, "deduplicated": 0}

    for event in events:
        template = templates.get(event.get("event_code"))
        channels = channels_for_event(event, settings, template=template)
        for user in sorted(set(event.get("recipients") or [])):
            for channel in channels:
                if dry_run:
                    result["created"] += 1
                    continue
                doc, created = _delivery(event, user, channel, template=template)
                if not created:
                    result["deduplicated"] += 1
                    continue
                result["created"] += 1
                status = _in_app(doc) if channel == "In-App" else (_email(doc) if channel == "Email" else _sms(doc))
                key = {"Sent": "sent", "Queued": "queued", "Failed": "failed", "Skipped": "skipped"}.get(status)
                if key:
                    result[key] += 1

    result["total"] = result["created"]
    return result


def process_due_notifications(current_date=None, project=None, dry_run=False):
    events = collect_due_events(current_date=current_date, project=project)
    result = dispatch_events(events, dry_run=bool(dry_run))
    result["events"] = len(events)
    if not dry_run:
        frappe.db.commit()
    return result


def reconcile_email_deliveries(limit=200):
    rows = frappe.get_all(
        "Notification Delivery",
        filters={"channel": "Email", "status": "Queued", "provider_reference": ["!=", ""]},
        fields=["name", "provider_reference"],
        limit=limit,
    )
    updated = 0
    for row in rows:
        status = frappe.db.get_value("Email Queue", row.provider_reference, "status")
        if status == "Sent":
            frappe.db.set_value(
                "Notification Delivery",
                row.name,
                {"status": "Sent", "sent_at": now_datetime(), "last_error": ""},
                update_modified=True,
            )
            updated += 1
        elif status == "Error":
            frappe.db.set_value(
                "Notification Delivery",
                row.name,
                {"status": "Failed", "last_error": "Email Queue ended in Error."},
                update_modified=True,
            )
            updated += 1
    if updated:
        frappe.db.commit()
    return {"checked": len(rows), "updated": updated}


def retry_failed_deliveries(limit=100):
    settings = get_settings()
    rows = frappe.get_all(
        "Notification Delivery",
        filters={
            "status": "Failed",
            "attempt_count": ["<", settings.retry_limit],
            "channel": ["in", ["Email", "SMS"]],
        },
        fields=["name", "channel"],
        order_by="modified asc",
        limit=limit,
    )
    result = {"retried": 0, "sent": 0, "queued": 0, "failed": 0, "skipped": 0}
    for row in rows:
        doc = frappe.get_doc("Notification Delivery", row.name)
        status = _email(doc) if row.channel == "Email" else _sms(doc)
        result["retried"] += 1
        key = status.lower()
        if key in result:
            result[key] += 1
    if result["retried"]:
        frappe.db.commit()
    return result
