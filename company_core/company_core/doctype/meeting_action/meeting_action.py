import frappe
from frappe import _
from frappe.model.document import Document


class MeetingAction(Document):
    def validate(self):
        self._validate_meeting_project()
        self._validate_assigned_user()
        self._validate_linked_task()

    def _validate_meeting_project(self):
        meeting_project = frappe.db.get_value(
            "Project Meeting",
            self.meeting,
            "project",
        )

        if not meeting_project:
            frappe.throw(_("Project Meeting does not exist."))

        if meeting_project != self.project:
            frappe.throw(
                _("Meeting Action must belong to the Meeting project.")
            )

    def _validate_assigned_user(self):
        if not self.assigned_to:
            frappe.throw(_("Assigned To is required."))

        if not frappe.db.exists(
            "Project Membership",
            {
                "project": self.project,
                "user": self.assigned_to,
                "status": "Active",
            },
        ):
            frappe.throw(
                _("Assigned user must have an active Project Membership.")
            )

    def _validate_linked_task(self):
        if not self.linked_task:
            return

        task_project = frappe.db.get_value(
            "Task",
            self.linked_task,
            "project",
        )

        if task_project != self.project:
            frappe.throw(
                _("Linked Task must belong to the same Project.")
            )
