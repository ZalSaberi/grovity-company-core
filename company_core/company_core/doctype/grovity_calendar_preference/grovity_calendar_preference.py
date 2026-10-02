from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, get_time

from company_core.calendar_permissions import is_privileged


ALLOWED_SLOT_MINUTES = {15, 30, 45, 60, 90, 120}


class GrovityCalendarPreference(Document):
    def validate(self):
        actor = frappe.session.user
        if not self.user:
            self.user = actor

        if not is_privileged(actor) and self.user != actor:
            frappe.throw(
                _("You can only manage your own calendar preference."),
                frappe.PermissionError,
            )

        if int(self.slot_minutes or 0) not in ALLOWED_SLOT_MINUTES:
            frappe.throw(_("Slot Minutes must be one of 15, 30, 45, 60, 90, 120."))

        if not self.workday_start or not self.workday_end:
            frappe.throw(_("Workday start and end are required."))

        if get_time(self.workday_end) <= get_time(self.workday_start):
            frappe.throw(_("Workday end must be after workday start."))

        if "Company Owner" in frappe.get_roles(self.user):
            self.retain_permanently = 1
            self.retention_days = 0

        if cint(self.retain_permanently):
            self.retention_days = 0
        elif cint(self.retention_days) < 1:
            frappe.throw(_("Retention Days must be at least 1 unless retention is permanent."))
