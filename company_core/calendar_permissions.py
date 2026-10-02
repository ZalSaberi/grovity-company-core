from __future__ import annotations

import frappe


PRIVILEGED_ROLES = {"Company Owner", "System Manager"}


def is_privileged(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    return bool(PRIVILEGED_ROLES.intersection(frappe.get_roles(user)))


def get_meeting_request_permission_query_conditions(user=None):
    user = user or frappe.session.user
    if is_privileged(user):
        return None
    escaped = frappe.db.escape(user)
    return (
        f"(`tabMeeting Request`.`requester` = {escaped} "
        f"or `tabMeeting Request`.`target_user` = {escaped})"
    )


def has_meeting_request_permission(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if is_privileged(user):
        return True
    if ptype == "create":
        return True
    if ptype == "delete":
        return False
    if ptype == "write":
        return user == doc.requester and doc.status == "Requested"
    return user in {doc.requester, doc.target_user}


def get_calendar_preference_permission_query_conditions(user=None):
    user = user or frappe.session.user
    if is_privileged(user):
        return None
    return f"`tabGrovity Calendar Preference`.`user` = {frappe.db.escape(user)}"


def has_calendar_preference_permission(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if is_privileged(user):
        return True
    if ptype == "create":
        return True
    if ptype == "delete":
        return False
    return doc.user == user
