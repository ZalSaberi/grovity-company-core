import frappe
from frappe import _

from company_core.permissions import is_privileged_user


def _require_admin():
    if not is_privileged_user(frappe.session.user):
        frappe.throw(_("Only Company Owner / System Manager may test notification channels."), frappe.PermissionError)


@frappe.whitelist()
def send_test_email(recipient):
    _require_admin()
    if not recipient:
        frappe.throw(_("Recipient email is required."))
    queue_doc = frappe.sendmail(
        recipients=[recipient],
        subject="[Grovity] Email channel test",
        message="<p>Grovity email delivery channel is working.</p>",
        now=False,
        queue_separately=False,
        add_unsubscribe_link=False,
        is_notification=True,
    )
    frappe.db.commit()
    result = {"queued": bool(queue_doc), "email_queue": getattr(queue_doc, "name", None)}
    print(result)
    return result


@frappe.whitelist()
def send_test_sms(mobile):
    _require_admin()
    if not mobile:
        frappe.throw(_("Mobile number is required."))
    from frappe.core.doctype.sms_settings.sms_settings import send_sms
    result = send_sms([mobile], "Grovity SMS channel test.")
    frappe.db.commit()
    response = {"requested": True, "mobile": mobile, "provider_result": str(result)}
    print(response)
    return response
