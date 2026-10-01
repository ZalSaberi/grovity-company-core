import frappe
from frappe import _
from frappe.model.document import Document


PROTECTED_FIELDS = (
    "project",
    "meeting_datetime",
    "participants",
    "agenda",
    "summary",
    "decisions",
)


class ProjectMeeting(Document):
    def before_insert(self):
        if not self.prepared_by:
            self.prepared_by = frappe.session.user

        self.pm_confirmation = 0
        self.ceo_confirmation = 0
        self.status = "Draft"

    def validate(self):
        self._validate_participants()
        self._validate_confirmation_changes()
        self._validate_final_lock()
        self._sync_status()

    def _validate_participants(self):
        seen = set()

        for row in self.participants or []:
            user = row.user

            if not user:
                continue

            if user in seen:
                frappe.throw(
                    _("Participant {0} is duplicated.").format(user)
                )

            seen.add(user)

            if not frappe.db.exists(
                "Project Membership",
                {
                    "project": self.project,
                    "user": user,
                    "status": "Active",
                },
            ):
                frappe.throw(
                    _(
                        "Participant {0} must have an active "
                        "Project Membership."
                    ).format(user)
                )

    def _validate_confirmation_changes(self):
        previous = self.get_doc_before_save()

        if not previous:
            return

        changed = (
            previous.pm_confirmation != self.pm_confirmation
            or previous.ceo_confirmation != self.ceo_confirmation
        )

        if changed and not getattr(
            self.flags,
            "confirmation_service",
            False,
        ):
            frappe.throw(
                _(
                    "Meeting confirmations must be changed "
                    "using the confirmation actions."
                )
            )

        if self.ceo_confirmation and not self.pm_confirmation:
            frappe.throw(
                _("PM confirmation is required before CEO confirmation.")
            )

    def _validate_final_lock(self):
        previous = self.get_doc_before_save()

        if not previous or previous.status != "Final":
            return

        for fieldname in PROTECTED_FIELDS:
            if previous.get(fieldname) != self.get(fieldname):
                frappe.throw(
                    _("Final meetings cannot be edited directly.")
                )

    def _sync_status(self):
        if self.ceo_confirmation:
            self.status = "Final"
        elif self.pm_confirmation:
            self.status = "PM Confirmed"
        else:
            self.status = "Draft"
