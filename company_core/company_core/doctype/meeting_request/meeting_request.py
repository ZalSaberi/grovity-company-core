from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime

from company_core.calendar_permissions import is_privileged


class MeetingRequest(Document):
    def before_insert(self):
        actor = frappe.session.user
        if not self.requester or not is_privileged(actor):
            self.requester = actor
        self.status = "Requested"

    def after_insert(self):
        from company_core.calendar_service import notify_new_meeting_request

        notify_new_meeting_request(self)

    def validate(self):
        self._validate_users()
        self._validate_times()
        self._validate_project()
        self._protect_service_fields()

    def _validate_users(self):
        for fieldname in ("requester", "target_user"):
            value = self.get(fieldname)
            if not value or not frappe.db.exists("User", {"name": value, "enabled": 1}):
                frappe.throw(_("{0} must be an enabled User.").format(self.meta.get_label(fieldname)))
        if self.requester == self.target_user:
            frappe.throw(_("Requester and target user must be different."))

    def _validate_times(self):
        if not self.preferred_start:
            frappe.throw(_("Preferred Start is required."))
        duration = int(self.duration_minutes or 30)
        if duration < 15 or duration > 480:
            frappe.throw(_("Duration must be between 15 and 480 minutes."))
        self.duration_minutes = duration

        if not self.preferred_end:
            self.preferred_end = add_to_date(self.preferred_start, minutes=duration)
        if get_datetime(self.preferred_end) <= get_datetime(self.preferred_start):
            frappe.throw(_("Preferred End must be after Preferred Start."))

        if self.alternative_start and not self.alternative_end:
            self.alternative_end = add_to_date(self.alternative_start, minutes=duration)
        if self.alternative_start and self.alternative_end:
            if get_datetime(self.alternative_end) <= get_datetime(self.alternative_start):
                frappe.throw(_("Alternative End must be after Alternative Start."))

    def _validate_project(self):
        if self.meeting_mode == "Project Meeting" and not self.related_project:
            frappe.throw(_("Related Project is required for Project Meeting mode."))
        if not self.related_project:
            return
        project = frappe.get_doc("Project", self.related_project)
        for user in {self.requester, self.target_user}:
            if is_privileged(user):
                continue
            if not frappe.has_permission("Project", ptype="read", doc=project, user=user):
                frappe.throw(
                    _("Both meeting participants must be allowed to view the selected project."),
                    frappe.PermissionError,
                )

    def _protect_service_fields(self):
        old = self.get_doc_before_save()
        if not old:
            return
        if self.status != old.status and not getattr(frappe.flags, "in_meeting_request_service", False):
            frappe.throw(_("Meeting Request status can only be changed using workflow actions."))
        for fieldname in (
            "alternative_start",
            "alternative_end",
            "response_note",
            "scheduled_event",
            "project_meeting",
            "responded_by",
            "responded_at",
        ):
            if self.get(fieldname) != old.get(fieldname) and not getattr(
                frappe.flags, "in_meeting_request_service", False
            ):
                frappe.throw(_("{0} is managed by the meeting workflow.").format(self.meta.get_label(fieldname)))
