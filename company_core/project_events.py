import frappe
from frappe import _
from frappe.utils import now_datetime


STATUS_FIELD = "custom_project_status"
REASON_FIELD = "custom_status_change_reason"


def validate_project_status_change(doc, method=None):
    previous = doc.get_doc_before_save()

    if not previous:
        return

    old_status = previous.get(STATUS_FIELD)
    new_status = doc.get(STATUS_FIELD)

    if old_status == new_status:
        return

    reason = (doc.get(REASON_FIELD) or "").strip()

    if not reason:
        frappe.throw(
            _(
                "Status Change Reason is required when "
                "Project Lifecycle Status changes."
            )
        )


def record_project_status_change(doc, method=None):
    previous = doc.get_doc_before_save()

    if not previous:
        return

    old_status = previous.get(STATUS_FIELD)
    new_status = doc.get(STATUS_FIELD)

    if old_status == new_status:
        return

    reason = (doc.get(REASON_FIELD) or "").strip()

    history = frappe.get_doc(
        {
            "doctype": "Project Status History",
            "project": doc.name,
            "old_status": old_status or "",
            "new_status": new_status or "",
            "changed_at": now_datetime(),
            "changed_by": frappe.session.user,
            "reason": reason,
        }
    )

    history.insert(ignore_permissions=True)

    frappe.db.set_value(
        "Project",
        doc.name,
        REASON_FIELD,
        None,
        update_modified=False,
    )

    doc.set(REASON_FIELD, None)
