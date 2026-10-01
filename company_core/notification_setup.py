import frappe

from company_core.notification_templates import ensure_default_templates


DEFAULTS = {
    "enable_in_app": 1,
    "enable_email": 0,
    "enable_sms": 0,
    "email_from_name": "Grovity Project Management",
    "sms_t7": 0,
    "sms_t3": 0,
    "sms_t1": 1,
    "sms_due_date": 1,
    "sms_overdue": 1,
    "retry_limit": 3,
}


def ensure_notification_settings():
    doc = frappe.get_single("Grovity Notification Settings")
    changed = False
    for fieldname, value in DEFAULTS.items():
        if doc.get(fieldname) in (None, ""):
            doc.set(fieldname, value)
            changed = True
    if changed:
        doc.save(ignore_permissions=True)

    template_result = ensure_default_templates()
    frappe.db.commit()

    result = {
        "settings": {
            fieldname: doc.get(fieldname)
            for fieldname in DEFAULTS
        },
        "templates": template_result,
    }
    print(result)
    return result
