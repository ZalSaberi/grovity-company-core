from __future__ import annotations

from datetime import datetime, time

import frappe
import frappe.share
from frappe import _
from frappe.utils import add_to_date, getdate

from company_core.calendar_permissions import is_privileged


TERMINAL_TASK_STATUSES = {"Completed", "Cancelled"}
TERMINAL_ACTION_STATUSES = {"Completed", "Cancelled"}


def _calendar_ready() -> bool:
    return frappe.db.has_column("Event", "custom_grovity_managed")


def _company_owner_users() -> set[str]:
    if not frappe.db.exists("Role", "Company Owner"):
        return set()
    return set(
        frappe.get_all(
            "Has Role",
            filters={"role": "Company Owner", "parenttype": "User"},
            pluck="parent",
            limit=0,
        )
    )


def _candidate_project_users(project: str | None) -> set[str]:
    users = {"Administrator"} | _company_owner_users()
    if project and frappe.db.exists("DocType", "Project Membership"):
        filters = {"project": project, "status": "Active"}
        excluded = getattr(frappe.flags, "grovity_exclude_membership", None)
        if excluded:
            filters["name"] = ["!=", excluded]
        users.update(
            frappe.get_all(
                "Project Membership",
                filters=filters,
                pluck="user",
                limit=0,
            )
        )
    return {
        user
        for user in users
        if user and frappe.db.exists("User", {"name": user, "enabled": 1})
    }


def _visible_users_for_doc(doc) -> list[str]:
    users: list[str] = []
    for user in sorted(_candidate_project_users(getattr(doc, "project", None))):
        if user == "Administrator":
            users.append(user)
            continue
        try:
            if frappe.has_permission(doc.doctype, ptype="read", doc=doc, user=user):
                users.append(user)
        except Exception:
            continue
    return users


def _set_event_participants(event, users: list[str]):
    event.set("event_participants", [])
    for user in users:
        if user == "Administrator":
            continue
        event.append(
            "event_participants",
            {
                "reference_doctype": "User",
                "reference_docname": user,
                "email": user,
            },
        )


def _sync_event_shares(event_name: str, users: list[str], owner: str):
    desired = {user for user in users if user and user not in {owner, "Administrator"}}
    current = set(
        frappe.get_all(
            "DocShare",
            filters={
                "share_doctype": "Event",
                "share_name": event_name,
                "everyone": 0,
            },
            pluck="user",
            limit=0,
        )
    )

    for user in sorted(desired - current):
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

    for user in sorted(current - desired):
        frappe.share.remove(
            "Event",
            event_name,
            user,
            flags={"ignore_permissions": True},
        )


def _find_managed_event(source_doctype: str, source_name: str):
    return frappe.db.get_value(
        "Event",
        {
            "custom_grovity_managed": 1,
            "custom_source_doctype": source_doctype,
            "custom_source_name": source_name,
        },
        "name",
    )


def _close_managed_event(source_doctype: str, source_name: str):
    if not _calendar_ready():
        return None
    name = _find_managed_event(source_doctype, source_name)
    if not name:
        return None
    event = frappe.get_doc("Event", name)
    frappe.flags.in_grovity_calendar_sync = True
    try:
        event.status = "Cancelled"
        event.custom_archived = 1
        event.send_reminder = 0
        event.save(ignore_permissions=True)
    finally:
        frappe.flags.in_grovity_calendar_sync = False
    return event.name


def _upsert_managed_event(
    *,
    source_doc,
    kind: str,
    subject: str,
    starts_on,
    ends_on=None,
    all_day: int = 0,
    blocks_availability: int = 0,
    calendar_owner: str | None = None,
):
    if not _calendar_ready():
        return None

    source_doctype = source_doc.doctype
    source_name = source_doc.name
    existing = _find_managed_event(source_doctype, source_name)
    event = frappe.get_doc("Event", existing) if existing else frappe.new_doc("Event")

    if event.is_new():
        event.owner = "Administrator"

    event.subject = subject
    event.event_category = "Meeting" if kind == "Project Meeting" else "Event"
    event.event_type = "Private"
    event.status = "Open"
    event.starts_on = starts_on
    event.ends_on = ends_on
    event.all_day = all_day
    event.send_reminder = 0
    event.sync_with_google_calendar = 0
    event.custom_grovity_managed = 1
    event.custom_grovity_kind = kind
    event.custom_calendar_owner = calendar_owner or "Administrator"
    event.custom_related_project = getattr(source_doc, "project", None)
    event.custom_source_doctype = source_doctype
    event.custom_source_name = source_name
    event.custom_blocks_availability = blocks_availability
    event.custom_archived = 0
    event.reference_doctype = source_doctype
    event.reference_docname = source_name

    users = _visible_users_for_doc(source_doc)
    _set_event_participants(event, users)

    frappe.flags.in_grovity_calendar_sync = True
    try:
        if event.is_new():
            event.insert(ignore_permissions=True)
        else:
            event.save(ignore_permissions=True)
    finally:
        frappe.flags.in_grovity_calendar_sync = False

    _sync_event_shares(event.name, users, event.owner)
    return event.name


def validate_grovity_event(doc, method=None):
    if not _calendar_ready() or not getattr(doc, "custom_grovity_kind", None):
        return

    # Grovity calendar records are private by design. Free/Busy is exposed by API,
    # not by making the source Event public.
    doc.event_type = "Private"

    if doc.custom_grovity_kind == "Personal Plan":
        if not doc.custom_calendar_owner:
            doc.custom_calendar_owner = frappe.session.user
        if (
            not is_privileged(frappe.session.user)
            and doc.custom_calendar_owner != frappe.session.user
        ):
            frappe.throw(
                _("You can only create personal calendar entries for yourself."),
                frappe.PermissionError,
            )
        doc.custom_grovity_managed = 0
        doc.custom_source_doctype = None
        doc.custom_source_name = None

    if doc.custom_grovity_managed and not getattr(
        frappe.flags, "in_grovity_calendar_sync", False
    ):
        old = doc.get_doc_before_save()
        if old and not is_privileged(frappe.session.user):
            protected = (
                "starts_on",
                "ends_on",
                "subject",
                "custom_source_doctype",
                "custom_source_name",
                "custom_related_project",
                "custom_calendar_owner",
                "custom_grovity_kind",
                "custom_blocks_availability",
                "description",
                "status",
            )
            if any(doc.get(field) != old.get(field) for field in protected):
                frappe.throw(
                    _("This calendar entry is managed by Grovity. Edit the source document instead."),
                    frappe.PermissionError,
                )


# === GROVITY PHASE 3C MISSING PROJECT GUARD ===
def _guard_missing_project_source(doc):
    project = getattr(doc, "project", None)
    if not project or frappe.db.exists("Project", project):
        return False

    event_name = _find_managed_event(doc.doctype, doc.name)
    if event_name:
        frappe.db.set_value(
            "Event",
            event_name,
            {
                "status": "Cancelled",
                "custom_archived": 1,
                "custom_related_project": None,
                "send_reminder": 0,
            },
            update_modified=False,
        )
    return True


def sync_task_calendar(doc, method=None):
    if _guard_missing_project_source(doc):
        return None
    if not _calendar_ready():
        return None
    if doc.status in TERMINAL_TASK_STATUSES or not doc.exp_end_date:
        return _close_managed_event(doc.doctype, doc.name)

    deadline = getdate(doc.exp_end_date)
    start = datetime.combine(deadline, time.min)
    end = datetime.combine(deadline, time(23, 59, 59))
    is_milestone = bool(getattr(doc, "is_milestone", 0))
    kind = "Milestone" if is_milestone else "Task Deadline"
    prefix = "Milestone" if is_milestone else "Task"

    return _upsert_managed_event(
        source_doc=doc,
        kind=kind,
        subject=f"[{prefix}] {doc.subject}",
        starts_on=start,
        ends_on=end,
        all_day=1,
        blocks_availability=0,
    )


def sync_project_meeting_calendar(doc, method=None):
    if _guard_missing_project_source(doc):
        return None
    if not _calendar_ready() or not doc.meeting_datetime:
        return None
    participants = [row.user for row in (doc.participants or []) if row.user]
    owner = doc.prepared_by or (participants[0] if participants else "Administrator")
    return _upsert_managed_event(
        source_doc=doc,
        kind="Project Meeting",
        subject=f"[Meeting] {doc.project} — {doc.name}",
        starts_on=doc.meeting_datetime,
        ends_on=add_to_date(doc.meeting_datetime, hours=1),
        all_day=0,
        blocks_availability=1,
        calendar_owner=owner,
    )


def sync_meeting_action_calendar(doc, method=None):
    if _guard_missing_project_source(doc):
        return None
    if not _calendar_ready():
        return None
    if doc.status in TERMINAL_ACTION_STATUSES or not doc.deadline:
        return _close_managed_event(doc.doctype, doc.name)

    deadline = getdate(doc.deadline)
    return _upsert_managed_event(
        source_doc=doc,
        kind="Meeting Action",
        subject=f"[Action] {doc.description}",
        starts_on=datetime.combine(deadline, time.min),
        ends_on=datetime.combine(deadline, time(23, 59, 59)),
        all_day=1,
        blocks_availability=0,
        calendar_owner=doc.assigned_to or "Administrator",
    )


def archive_source_event(doc, method=None):
    return _close_managed_event(doc.doctype, doc.name)


def resync_project_calendar_access(doc, method=None):
    if not _calendar_ready() or not getattr(doc, "project", None):
        return
    project = doc.project
    for name in frappe.get_all("Task", filters={"project": project}, pluck="name", limit=0):
        sync_task_calendar(frappe.get_doc("Task", name))
    for name in frappe.get_all(
        "Project Meeting", filters={"project": project}, pluck="name", limit=0
    ):
        sync_project_meeting_calendar(frappe.get_doc("Project Meeting", name))
    for name in frappe.get_all(
        "Meeting Action", filters={"project": project}, pluck="name", limit=0
    ):
        sync_meeting_action_calendar(frappe.get_doc("Meeting Action", name))


def resync_project_calendar_access_on_trash(doc, method=None):
    frappe.flags.grovity_exclude_membership = doc.name
    try:
        return resync_project_calendar_access(doc, method)
    finally:
        frappe.flags.grovity_exclude_membership = None


def backfill_calendar_events():
    if not _calendar_ready():
        return {"tasks": 0, "meetings": 0, "actions": 0}

    counts = {"tasks": 0, "meetings": 0, "actions": 0}
    for name in frappe.get_all(
        "Task", filters={"exp_end_date": ["is", "set"]}, pluck="name", limit=0
    ):
        sync_task_calendar(frappe.get_doc("Task", name))
        counts["tasks"] += 1

    for name in frappe.get_all("Project Meeting", pluck="name", limit=0):
        sync_project_meeting_calendar(frappe.get_doc("Project Meeting", name))
        counts["meetings"] += 1

    for name in frappe.get_all(
        "Meeting Action", filters={"deadline": ["is", "set"]}, pluck="name", limit=0
    ):
        sync_meeting_action_calendar(frappe.get_doc("Meeting Action", name))
        counts["actions"] += 1

    frappe.db.commit()
    return counts
