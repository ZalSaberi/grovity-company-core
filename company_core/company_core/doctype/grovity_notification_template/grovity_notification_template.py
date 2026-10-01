import frappe
from frappe import _
from frappe.model.document import Document

from company_core.notification_templates import EVENT_CODES, SMS_MAX_UNICODE_CHARS


class GrovityNotificationTemplate(Document):
    def validate(self):
        if self.event_code not in EVENT_CODES:
            frappe.throw(
                _("Unsupported notification event code: {0}").format(
                    self.event_code
                )
            )

        if self.enabled and not (
            self.enable_in_app
            or self.enable_email
            or self.enable_sms
        ):
            frappe.throw(
                _("At least one notification channel must be enabled for an active template.")
            )

        if self.enable_sms and not (self.sms_body or "").strip():
            frappe.throw(
                _("SMS Body is required when SMS is enabled.")
            )

        if self.sms_body and len(self.sms_body) > 400:
            frappe.throw(
                _(
                    "SMS template source is too long. "
                    "Keep SMS templates concise; rendered Persian SMS messages "
                    "are capped at {0} characters."
                ).format(SMS_MAX_UNICODE_CHARS)
            )
