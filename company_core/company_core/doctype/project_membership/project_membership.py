# Copyright (c) 2026, Sanabad Sustainable Energy (SSE) and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class ProjectMembership(Document):
    def validate(self):
        self.validate_dates()
        self.validate_duplicate_active_membership()
        self.validate_ended_membership()

    def validate_dates(self):
        if self.start_date and self.end_date:
            if getdate(self.end_date) < getdate(self.start_date):
                frappe.throw(
                    _("End Date cannot be earlier than Start Date.")
                )

    def validate_duplicate_active_membership(self):
        if self.status != "Active":
            return

        filters = {
            "project": self.project,
            "user": self.user,
            "status": "Active",
        }

        if not self.is_new():
            filters["name"] = ["!=", self.name]

        existing_membership = frappe.db.exists(
            "Project Membership",
            filters,
        )

        if existing_membership:
            frappe.throw(
                _("This user already has an active membership for this project.")
            )

    def validate_ended_membership(self):
        if self.status == "Ended" and not self.end_date:
            frappe.throw(
                _("End Date is required when membership status is Ended.")
            )
