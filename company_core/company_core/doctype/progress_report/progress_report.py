import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


CONTENT_FIELDS = (
    "project",
    "period",
    "progress_percent",
    "completed",
    "in_progress",
    "issues",
    "risks",
    "next_actions",
)


class ProgressReport(Document):
    def before_insert(self):
        if not self.submitted_by:
            self.submitted_by = frappe.session.user

        self.approval_status = "Draft"

    def validate(self):
        self._validate_progress()
        self._validate_workflow_transition()
        self._validate_approved_lock()

    def _validate_progress(self):
        progress = flt(self.progress_percent or 0)

        if progress < 0 or progress > 100:
            frappe.throw(
                _("Progress Percent must be between 0 and 100.")
            )

    def _validate_workflow_transition(self):
        previous = self.get_doc_before_save()

        if not previous:
            return

        if previous.approval_status == self.approval_status:
            return

        if not getattr(self.flags, "workflow_service", False):
            frappe.throw(
                _(
                    "Approval Status must be changed using "
                    "the Progress Report workflow actions."
                )
            )

    def _validate_approved_lock(self):
        previous = self.get_doc_before_save()

        if not previous or previous.approval_status != "Approved":
            return

        for fieldname in CONTENT_FIELDS:
            if previous.get(fieldname) != self.get(fieldname):
                frappe.throw(
                    _("Approved Progress Reports are immutable.")
                )
