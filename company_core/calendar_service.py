from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

import frappe
import frappe.share
from frappe import _
from frappe.utils import add_days, add_to_date, cint, get_datetime, get_time, getdate, now_datetime, today

from company_core.calendar_permissions import is_privileged


WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _get_preference(user: str):
    if frappe.db.exists("Grovity Calendar Preference", user):
        return frappe.get_doc("Grovity Calendar Preference", user)

    owner = "Company Owner" in frappe.get_roles(user)
    doc = frappe.get_doc(
        {
            "doctype": "Grovity Calendar Preference",
            "user": user,
            "allow_meeting_requests": 1,
            "working_days": "Saturday,Sunday,Monday,Tuesday,Wednesday,Thursday",
            "workday_start": "09:00:00",
            "workday_end": "18:00:00",
            "slot_minutes": 30,
            "retain_permanently": 1 if owner else 0,
            "retention_days": 0 if owner else 30,
            "monthly_summary_email": 0 if owner else 1,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def _busy_ranges(target_user: str, start_dt: datetime, end_dt: datetime):
    return frappe.db.sql(
        """
        SELECT DISTINCT e.starts_on, COALESCE(e.ends_on, e.starts_on) AS ends_on
        FROM `tabEvent` e
        WHERE e.status = 'Open'
          AND COALESCE(e.custom_archived, 0) = 0
          AND COALESCE(e.custom_blocks_availability, 1) = 1
          AND e.starts_on < %(end_dt)s
          AND COALESCE(e.ends_on, e.starts_on) > %(start_dt)s
          AND (
              e.owner = %(target_user)s
              OR e.custom_calendar_owner = %(target_user)s
              OR EXISTS (
                  SELECT 1
                  FROM `tabEvent Participants` ep
                  WHERE ep.parent = e.name
                    AND ep.parenttype = 'Event'
                    AND (
                        ep.email = %(target_user)s
                        OR (
                            ep.reference_doctype = 'User'
                            AND ep.reference_docname = %(target_user)s
                        )
                    )
              )
              OR EXISTS (
                  SELECT 1
                  FROM `tabDocShare` ds
                  WHERE ds.share_doctype = 'Event'
                    AND ds.share_name = e.name
                    AND ds.user = %(target_user)s
                    AND ds.read = 1
              )
          )
        ORDER BY e.starts_on
        """,
        {"target_user": target_user, "start_dt": start_dt, "end_dt": end_dt},
        as_dict=True,
    )


def _interval_is_free(target_user: str, start_dt: datetime, end_dt: datetime) -> bool:
    return not bool(_busy_ranges(target_user, start_dt, end_dt))


@frappe.whitelist()
def get_free_slots(target_user: str, date: str, duration_minutes: int | None = None):
    if not frappe.db.exists("User", {"name": target_user, "enabled": 1}):
        frappe.throw(_("Target user does not exist or is disabled."))

    pref = _get_preference(target_user)
    caller = frappe.session.user
    if (
        not cint(pref.allow_meeting_requests)
        and caller != target_user
        and not is_privileged(caller)
    ):
        frappe.throw(_("This user is not accepting meeting requests."), frappe.PermissionError)

    day = getdate(date)
    working_days = {
        value.strip()
        for value in (pref.working_days or "").split(",")
        if value.strip()
    }
    if working_days and WEEKDAY_NAMES[day.weekday()] not in working_days:
        return []

    duration = int(duration_minutes or pref.slot_minutes or 30)
    if duration < 15 or duration > 480:
        frappe.throw(_("Duration must be between 15 and 480 minutes."))

    day_start = datetime.combine(day, get_time(pref.workday_start))
    day_end = datetime.combine(day, get_time(pref.workday_end))
    busy = _busy_ranges(target_user, day_start, day_end)

    slots = []
    cursor = day_start
    step = timedelta(minutes=int(pref.slot_minutes or 30))
    duration_delta = timedelta(minutes=duration)

    while cursor + duration_delta <= day_end:
        slot_end = cursor + duration_delta
        collision = any(
            cursor < get_datetime(row.ends_on) and slot_end > get_datetime(row.starts_on)
            for row in busy
        )
        if not collision:
            slots.append(
                {
                    "start": cursor.strftime("%Y-%m-%d %H:%M:%S"),
                    "end": slot_end.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        cursor += step

    return slots


def _set_request_fields(doc, **values):
    frappe.flags.in_meeting_request_service = True
    try:
        for key, value in values.items():
            doc.set(key, value)
        doc.save(ignore_permissions=True)
    finally:
        frappe.flags.in_meeting_request_service = False


def _email_enabled() -> bool:
    if not frappe.db.exists("DocType", "Grovity Notification Settings"):
        return False
    return bool(cint(frappe.get_single("Grovity Notification Settings").enable_email))


def _notify(user: str, request_name: str, subject: str, body: str):
    if not user or not frappe.db.exists("User", {"name": user, "enabled": 1}):
        return

    frappe.get_doc(
        {
            "doctype": "Notification Log",
            "for_user": user,
            "from_user": frappe.session.user,
            "type": "Alert",
            "subject": subject,
            "email_content": body,
            "document_type": "Meeting Request",
            "document_name": request_name,
        }
    ).insert(ignore_permissions=True)

    if _email_enabled():
        frappe.sendmail(recipients=[user], subject=subject, message=body)


def notify_new_meeting_request(doc):
    _notify(
        doc.target_user,
        doc.name,
        f"New meeting request: {doc.subject}",
        (
            f"<p>You have a new meeting request from {escape(doc.requester)}.</p>"
            f"<p>Preferred start: {escape(str(doc.preferred_start))}</p>"
            f"<p>Subject: {escape(doc.subject)}</p>"
        ),
    )


def _share_event(event_name: str, users: set[str], owner: str):
    for user in sorted(users):
        if not user or user in {owner, "Administrator"}:
            continue
        frappe.share.add_docshare(
            "Event",
            event_name,
            user=user,
            read=1,
            write=0,
            share=0,
            notify=0,
            flags={"ignore_share_permission": True},
        )


def _create_calendar_event(doc, start_dt: datetime, end_dt: datetime):
    event = frappe.get_doc(
        {
            "doctype": "Event",
            "subject": doc.subject,
            "event_category": "Meeting",
            "event_type": "Private",
            "starts_on": start_dt,
            "ends_on": end_dt,
            "status": "Open",
            "all_day": 0,
            "send_reminder": 1,
            "sync_with_google_calendar": 0,
            "description": doc.discussion_points or doc.subject,
            "reference_doctype": "Meeting Request",
            "reference_docname": doc.name,
            "custom_grovity_kind": "Meeting Request",
            "custom_calendar_owner": doc.target_user,
            "custom_related_project": doc.related_project,
            "custom_grovity_managed": 1,
            "custom_source_doctype": "Meeting Request",
            "custom_source_name": doc.name,
            "custom_blocks_availability": 1,
            "custom_archived": 0,
        }
    )
    event.owner = doc.target_user
    for user in sorted({doc.requester, doc.target_user}):
        event.append(
            "event_participants",
            {
                "reference_doctype": "User",
                "reference_docname": user,
                "email": user,
            },
        )

    frappe.flags.in_grovity_calendar_sync = True
    try:
        event.insert(ignore_permissions=True)
    finally:
        frappe.flags.in_grovity_calendar_sync = False

    _share_event(event.name, {doc.requester, doc.target_user}, event.owner)
    return event.name


def _create_project_meeting(doc, start_dt: datetime):
    if not doc.related_project:
        frappe.throw(_("Related Project is required."))

    for user in {doc.requester, doc.target_user}:
        membership = frappe.db.exists(
            "Project Membership",
            {"project": doc.related_project, "user": user, "status": "Active"},
        )
        if not membership and not is_privileged(user):
            frappe.throw(
                _("{0} must have active project membership before a Project Meeting can be created.").format(user)
            )

    meeting = frappe.get_doc(
        {
            "doctype": "Project Meeting",
            "project": doc.related_project,
            "meeting_datetime": start_dt,
            "agenda": (doc.subject + "\n\n" + (doc.discussion_points or "")).strip(),
        }
    )
    for user in sorted({doc.requester, doc.target_user}):
        if frappe.db.exists(
            "Project Membership",
            {"project": doc.related_project, "user": user, "status": "Active"},
        ):
            meeting.append("participants", {"user": user})
    meeting.insert(ignore_permissions=True)

    event_name = frappe.db.get_value(
        "Event",
        {
            "custom_grovity_managed": 1,
            "custom_source_doctype": "Project Meeting",
            "custom_source_name": meeting.name,
        },
        "name",
    )
    return meeting.name, event_name


@frappe.whitelist()
def accept_meeting_request(name: str):
    doc = frappe.get_doc("Meeting Request", name)
    actor = frappe.session.user

    if doc.status == "Requested":
        if actor != doc.target_user and not is_privileged(actor):
            frappe.throw(_("Only the requested person can accept this request."), frappe.PermissionError)
        start_dt = get_datetime(doc.preferred_start)
        end_dt = get_datetime(doc.preferred_end)
        notify_user = doc.requester
    elif doc.status == "Alternative Proposed":
        if actor != doc.requester and not is_privileged(actor):
            frappe.throw(_("Only the requester can accept the proposed alternative."), frappe.PermissionError)
        start_dt = get_datetime(doc.alternative_start)
        end_dt = get_datetime(doc.alternative_end)
        notify_user = doc.target_user
    else:
        frappe.throw(_("This request cannot be accepted in its current state."))

    if not _interval_is_free(doc.target_user, start_dt, end_dt):
        frappe.throw(_("The selected time is no longer available."))

    project_meeting = None
    if doc.meeting_mode == "Project Meeting":
        project_meeting, event_name = _create_project_meeting(doc, start_dt)
    else:
        event_name = _create_calendar_event(doc, start_dt, end_dt)

    _set_request_fields(
        doc,
        status="Scheduled",
        scheduled_event=event_name,
        project_meeting=project_meeting,
        responded_by=actor,
        responded_at=now_datetime(),
    )
    _notify(
        notify_user,
        doc.name,
        f"Meeting scheduled: {doc.subject}",
        f"The meeting request has been scheduled for {start_dt}.",
    )
    return {
        "name": doc.name,
        "status": "Scheduled",
        "event": event_name,
        "project_meeting": project_meeting,
    }


@frappe.whitelist()
def reject_meeting_request(name: str, note: str | None = None):
    doc = frappe.get_doc("Meeting Request", name)
    actor = frappe.session.user
    if doc.status != "Requested":
        frappe.throw(_("Only a requested meeting can be rejected."))
    if actor != doc.target_user and not is_privileged(actor):
        frappe.throw(_("Only the requested person can reject this request."), frappe.PermissionError)

    _set_request_fields(
        doc,
        status="Rejected",
        response_note=note or "",
        responded_by=actor,
        responded_at=now_datetime(),
    )
    _notify(
        doc.requester,
        doc.name,
        f"Meeting request rejected: {doc.subject}",
        note or "The request was rejected.",
    )
    return {"name": doc.name, "status": "Rejected"}


@frappe.whitelist()
def propose_alternative(
    name: str,
    alternative_start: str,
    alternative_end: str | None = None,
    note: str | None = None,
):
    doc = frappe.get_doc("Meeting Request", name)
    actor = frappe.session.user
    if doc.status != "Requested":
        frappe.throw(_("An alternative can only be proposed for a requested meeting."))
    if actor != doc.target_user and not is_privileged(actor):
        frappe.throw(_("Only the requested person can propose an alternative."), frappe.PermissionError)

    start_dt = get_datetime(alternative_start)
    end_dt = (
        get_datetime(alternative_end)
        if alternative_end
        else add_to_date(start_dt, minutes=int(doc.duration_minutes or 30))
    )
    if end_dt <= start_dt:
        frappe.throw(_("Alternative End must be after Alternative Start."))
    if not _interval_is_free(doc.target_user, start_dt, end_dt):
        frappe.throw(_("The proposed alternative time is not free."))

    _set_request_fields(
        doc,
        status="Alternative Proposed",
        alternative_start=start_dt,
        alternative_end=end_dt,
        response_note=note or "",
        responded_by=actor,
        responded_at=now_datetime(),
    )
    _notify(
        doc.requester,
        doc.name,
        f"Alternative time proposed: {doc.subject}",
        f"Alternative: {start_dt} to {end_dt}. {note or ''}",
    )
    return {"name": doc.name, "status": "Alternative Proposed"}


@frappe.whitelist()
def cancel_meeting_request(name: str, note: str | None = None):
    doc = frappe.get_doc("Meeting Request", name)
    actor = frappe.session.user
    if actor not in {doc.requester, doc.target_user} and not is_privileged(actor):
        frappe.throw(_("You cannot cancel this meeting request."), frappe.PermissionError)
    if doc.status in {"Rejected", "Cancelled"}:
        return {"name": doc.name, "status": doc.status}

    if doc.scheduled_event and frappe.db.exists("Event", doc.scheduled_event):
        event = frappe.get_doc("Event", doc.scheduled_event)
        frappe.flags.in_grovity_calendar_sync = True
        try:
            event.status = "Cancelled"
            event.custom_archived = 1
            event.send_reminder = 0
            event.save(ignore_permissions=True)
        finally:
            frappe.flags.in_grovity_calendar_sync = False

    _set_request_fields(
        doc,
        status="Cancelled",
        response_note=note or doc.response_note,
        responded_by=actor,
        responded_at=now_datetime(),
    )
    other = doc.target_user if actor == doc.requester else doc.requester
    _notify(other, doc.name, f"Meeting cancelled: {doc.subject}", note or "The meeting was cancelled.")
    return {"name": doc.name, "status": "Cancelled"}


def _month_bounds(reference_date=None):
    ref = getdate(reference_date or today())
    first_this = ref.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev, last_prev


def _user_event_rows(user: str, start_date, end_date):
    return frappe.db.sql(
        """
        SELECT DISTINCT e.name, e.subject, e.starts_on, e.ends_on, e.custom_grovity_kind
        FROM `tabEvent` e
        LEFT JOIN `tabDocShare` ds
          ON ds.share_doctype='Event' AND ds.share_name=e.name AND ds.user=%(user)s AND ds.read=1
        WHERE date(e.starts_on) BETWEEN %(start)s AND %(end)s
          AND (
              e.owner=%(user)s
              OR e.custom_calendar_owner=%(user)s
              OR ds.name IS NOT NULL
          )
        ORDER BY e.starts_on
        """,
        {"user": user, "start": start_date, "end": end_date},
        as_dict=True,
    )


def process_monthly_calendar_lifecycle(reference_date=None):
    start_date, end_date = _month_bounds(reference_date)

    pm_users = set(
        frappe.get_all(
            "Project Membership",
            filters={"membership_role": "Project Manager", "status": "Active"},
            pluck="user",
            limit=0,
        )
    ) if frappe.db.exists("DocType", "Project Membership") else set()

    owner_users = set(
        frappe.get_all(
            "Has Role",
            filters={"role": "Company Owner", "parenttype": "User"},
            pluck="parent",
            limit=0,
        )
    ) if frappe.db.exists("Role", "Company Owner") else set()

    summary_sent = 0
    archived = 0

    for user in sorted(pm_users | owner_users):
        if not frappe.db.exists("User", {"name": user, "enabled": 1}):
            continue
        pref = _get_preference(user)
        rows = _user_event_rows(user, start_date, end_date)

        if cint(pref.monthly_summary_email) and rows and _email_enabled():
            body_rows = "".join(
                "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    escape(str(row.starts_on)),
                    escape(row.custom_grovity_kind or "Event"),
                    escape(row.subject or ""),
                )
                for row in rows
            )
            frappe.sendmail(
                recipients=[user],
                subject=f"Grovity monthly calendar summary — {start_date.strftime('%Y-%m')}",
                message=(
                    "<p>Monthly calendar summary:</p>"
                    "<table border='1' cellpadding='5'><tr><th>Time</th><th>Type</th><th>Subject</th></tr>"
                    + body_rows
                    + "</table>"
                ),
            )
            summary_sent += 1

        if cint(pref.retain_permanently):
            continue

        cutoff = getdate(add_days(today(), -int(pref.retention_days or 30)))
        old_personal = frappe.get_all(
            "Event",
            filters={
                "custom_grovity_kind": "Personal Plan",
                "custom_calendar_owner": user,
                "custom_archived": 0,
                "starts_on": ["<", cutoff],
            },
            pluck="name",
            limit=0,
        )
        for event_name in old_personal:
            frappe.db.set_value(
                "Event",
                event_name,
                {"custom_archived": 1, "status": "Closed", "send_reminder": 0},
                update_modified=False,
            )
            archived += 1

    return {
        "summary_sent": summary_sent,
        "archived": archived,
        "period": f"{start_date}..{end_date}",
    }
