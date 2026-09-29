import frappe
from frappe import _
from frappe.model.document import Document


class ProjectStatusHistory(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw(
                _(
                    "Project Status History records "
                    "are immutable."
                )
            )
