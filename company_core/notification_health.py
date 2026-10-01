import frappe

from company_core.notification_templates import EVENT_CODES


def _outgoing_email_configured():
    return bool(
        frappe.db.exists(
            "Email Account",
            {
                "enable_outgoing": 1,
                "default_outgoing": 1,
            },
        )
    )


def _sms_configured():
    if frappe.get_hooks("send_sms"):
        return True
    if not frappe.db.exists("DocType", "SMS Settings"):
        return False
    return bool(frappe.db.get_single_value("SMS Settings", "sms_gateway_url"))


def run():
    for doctype in (
        "Grovity Notification Settings",
        "Grovity Notification Template",
        "Notification Delivery",
    ):
        if not frappe.db.exists("DocType", doctype):
            raise RuntimeError(f"Missing DocType: {doctype}")

    if not frappe.get_meta("User").has_field("mobile_no"):
        raise RuntimeError("User.mobile_no field is required for SMS.")

    hook_text = str(frappe.get_hooks("scheduler_events"))
    required_jobs = (
        "company_core.operations_notifications.process_due_notifications",
        "company_core.notification_engine.reconcile_email_deliveries",
        "company_core.notification_engine.retry_failed_deliveries",
    )
    for job in required_jobs:
        if job not in hook_text:
            raise RuntimeError(f"Missing scheduler job: {job}")

    existing_templates = set(
        frappe.get_all(
            "Grovity Notification Template",
            filters={"event_code": ["in", list(EVENT_CODES)]},
            pluck="event_code",
            limit=0,
        )
    )
    missing_templates = [
        code for code in EVENT_CODES
        if code not in existing_templates
    ]
    if missing_templates:
        raise RuntimeError(
            "Missing notification templates: "
            + ", ".join(missing_templates)
        )

    result = {
        "status": "ok",
        "email_outgoing_configured": _outgoing_email_configured(),
        "email_default_outgoing_configured": _outgoing_email_configured(),
        "sms_configured": _sms_configured(),
        "user_mobile_field": "mobile_no",
        "delivery_log": "Notification Delivery",
        "template_doctype": "Grovity Notification Template",
        "template_count": len(existing_templates),
        "email_provider": "Frappe Email Queue / Default Outgoing Email Account",
        "sms_provider": "Frappe SMS Settings / send_sms hook",
    }
    print(result)
    return result
