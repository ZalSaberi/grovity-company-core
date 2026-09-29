import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class SuspensionEvent(Document):
    def validate(self):
        self.validate_dates()
        self.validate_single_open_suspension()

    def validate_dates(self):
        if self.start_date and self.end_date:
            if getdate(self.end_date) < getdate(self.start_date):
                frappe.throw(
                    _("End Date cannot be earlier than Start Date.")
                )

    def validate_single_open_suspension(self):
        if self.end_date:
            return

        filters = {
            "project": self.project,
            "end_date": ["is", "not set"],
        }

        if not self.is_new():
            filters["name"] = ["!=", self.name]

        existing = frappe.db.exists(
            "Suspension Event",
            filters,
        )

        if existing:
            frappe.throw(
                _(
                    "This project already has an open "
                    "Suspension Event."
                )
            )
