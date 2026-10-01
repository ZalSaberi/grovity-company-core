from datetime import date, timedelta

import frappe
from frappe.tests import IntegrationTestCase

from company_core.operations_notifications import process_due_notifications
from company_core.operations_service import (
    confirm_meeting_as_ceo,
    confirm_meeting_as_pm,
    create_task_from_action,
    review_progress_report,
    submit_progress_report,
)


class TestPhase3Operations(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")

        cls.suffix = frappe.generate_hash(length=8)
        cls.manager = f"ops.manager.{cls.suffix}@grovity.test"
        cls.contributor = f"ops.contributor.{cls.suffix}@grovity.test"
        cls.observer = f"ops.observer.{cls.suffix}@grovity.test"
        cls.other_manager = f"ops.other.{cls.suffix}@grovity.test"

        for email, first_name in (
            (cls.manager, "Ops Manager"),
            (cls.contributor, "Ops Contributor"),
            (cls.observer, "Ops Observer"),
            (cls.other_manager, "Ops Other Manager"),
        ):
            cls._create_user(email, first_name)

        cls.project = cls._create_project(
            f"Operations Project {cls.suffix}"
        )
        cls.other_project = cls._create_project(
            f"Operations Other {cls.suffix}"
        )

        for project, user, role in (
            (cls.project.name, cls.manager, "Project Manager"),
            (cls.project.name, cls.contributor, "Contributor"),
            (cls.project.name, cls.observer, "Observer"),
            (cls.other_project.name, cls.other_manager, "Project Manager"),
        ):
            cls._create_membership(project, user, role)

        frappe.db.commit()

    @classmethod
    def _create_user(cls, email, first_name):
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": first_name,
                "enabled": 1,
                "send_welcome_email": 0,
            }
        )
        user.append("roles", {"role": "Company User"})
        return user.insert(ignore_permissions=True)

    @classmethod
    def _create_project(cls, project_name):
        return frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": project_name,
                "status": "Open",
                "custom_project_status": "Active",
            }
        ).insert(ignore_permissions=True)

    @classmethod
    def _create_membership(cls, project, user, role):
        return frappe.get_doc(
            {
                "doctype": "Project Membership",
                "project": project,
                "user": user,
                "membership_role": role,
                "status": "Active",
                "start_date": frappe.utils.today(),
            }
        ).insert(ignore_permissions=True)

    def setUp(self):
        frappe.set_user("Administrator")

    def _make_meeting(self, project=None, participants=None, days_from_now=3):
        meeting = frappe.get_doc(
            {
                "doctype": "Project Meeting",
                "project": project or self.project.name,
                "meeting_datetime": (
                    str(date.today() + timedelta(days=days_from_now))
                    + " 10:00:00"
                ),
                "agenda": "Phase 3 test agenda",
                "summary": "Summary",
                "decisions": "Decision",
            }
        )

        for user in participants or []:
            meeting.append("participants", {"user": user})

        return meeting

    def _make_action(self, meeting, assigned_to=None, days_from_now=3):
        return frappe.get_doc(
            {
                "doctype": "Meeting Action",
                "project": meeting.project,
                "meeting": meeting.name,
                "description": "Prepare acceptance package",
                "assigned_to": assigned_to or self.contributor,
                "deadline": (
                    date.today() + timedelta(days=days_from_now)
                ).isoformat(),
                "priority": "High",
                "status": "Open",
            }
        )

    def _make_report(self, project=None, submitted_by=None):
        frappe.set_user(submitted_by or self.contributor)

        return frappe.get_doc(
            {
                "doctype": "Progress Report",
                "project": project or self.project.name,
                "period": "2026-W40",
                "progress_percent": 55,
                "completed": "Completed work",
                "in_progress": "Current work",
                "issues": "Issue",
                "risks": "Risk",
                "next_actions": "Next action",
            }
        )

    def test_01_pm_can_create_meeting(self):
        frappe.set_user(self.manager)
        meeting = self._make_meeting(participants=[self.contributor])
        meeting.insert()
        self.assertTrue(meeting.name)

    def test_02_contributor_cannot_create_meeting(self):
        frappe.set_user(self.contributor)
        meeting = self._make_meeting(participants=[self.contributor])

        with self.assertRaises(frappe.PermissionError):
            meeting.insert()

    def test_03_participant_scope(self):
        meeting = self._make_meeting(
            participants=[self.contributor]
        ).insert(ignore_permissions=True)

        self.assertTrue(
            frappe.has_permission(
                "Project Meeting",
                ptype="read",
                doc=meeting,
                user=self.contributor,
            )
        )

        self.assertFalse(
            frappe.has_permission(
                "Project Meeting",
                ptype="read",
                doc=meeting,
                user=self.observer,
            )
        )

    def test_04_pm_and_ceo_confirmation(self):
        meeting = self._make_meeting(
            participants=[self.contributor]
        ).insert(ignore_permissions=True)

        frappe.set_user(self.manager)
        confirm_meeting_as_pm(meeting.name)

        updated = frappe.get_doc("Project Meeting", meeting.name)
        self.assertEqual(updated.status, "PM Confirmed")

        frappe.set_user("Administrator")
        confirm_meeting_as_ceo(meeting.name)

        updated.reload()
        self.assertEqual(updated.status, "Final")
        self.assertEqual(updated.ceo_confirmation, 1)

    def test_05_final_meeting_locked(self):
        meeting = self._make_meeting(
            participants=[self.contributor]
        ).insert(ignore_permissions=True)

        frappe.set_user(self.manager)
        confirm_meeting_as_pm(meeting.name)

        frappe.set_user("Administrator")
        confirm_meeting_as_ceo(meeting.name)

        meeting.reload()
        meeting.summary = "Changed after final"

        with self.assertRaises(frappe.ValidationError):
            meeting.save(ignore_permissions=True)

    def test_06_action_assignee_can_update(self):
        meeting = self._make_meeting(
            participants=[self.contributor]
        ).insert(ignore_permissions=True)

        action = self._make_action(meeting).insert(ignore_permissions=True)

        self.assertEqual(action.assigned_to, self.contributor)

        frappe.set_user(self.contributor)
        action.reload()
        action.status = "In Progress"
        action.save()

        self.assertEqual(action.status, "In Progress")

    def test_07_action_to_task(self):
        meeting = self._make_meeting(
            participants=[self.contributor]
        ).insert(ignore_permissions=True)

        action = self._make_action(meeting).insert(ignore_permissions=True)

        frappe.set_user(self.manager)
        task_name = create_task_from_action(action.name)

        self.assertTrue(frappe.db.exists("Task", task_name))

        task = frappe.get_doc("Task", task_name)
        contributor_users = {
            row.user
            for row in task.custom_contributors
        }
        self.assertIn(self.contributor, contributor_users)

        action.reload()
        self.assertEqual(action.linked_task, task_name)

    def test_08_contributor_can_create_report(self):
        report = self._make_report()
        report.insert()

        self.assertTrue(report.name)
        self.assertEqual(report.submitted_by, self.contributor)

    def test_09_report_submit_and_approve(self):
        report = self._make_report()
        report.insert()

        submit_progress_report(report.name)
        report.reload()
        self.assertEqual(report.approval_status, "Submitted")

        frappe.set_user(self.manager)
        review_progress_report(
            report.name,
            "Approved",
            "Looks good",
        )

        report.reload()
        self.assertEqual(report.approval_status, "Approved")
        self.assertEqual(report.approved_by, self.manager)

    def test_10_non_pm_cannot_approve(self):
        report = self._make_report()
        report.insert()
        submit_progress_report(report.name)

        frappe.set_user(self.contributor)

        with self.assertRaises(frappe.PermissionError):
            review_progress_report(
                report.name,
                "Approved",
                "",
            )

    def test_11_revision_requires_comment(self):
        report = self._make_report()
        report.insert()
        submit_progress_report(report.name)

        frappe.set_user(self.manager)

        with self.assertRaises(frappe.ValidationError):
            review_progress_report(
                report.name,
                "Revision Requested",
                "",
            )

    def test_12_cross_project_report_hidden(self):
        report = self._make_report(
            project=self.other_project.name,
            submitted_by=self.other_manager,
        )
        report.insert()

        frappe.set_user(self.contributor)

        visible = frappe.get_list(
            "Progress Report",
            filters={"name": report.name},
            pluck="name",
        )

        self.assertEqual(visible, [])

    def test_13_notifications_deduplicate(self):
        meeting = self._make_meeting(
            participants=[self.contributor],
            days_from_now=3,
        ).insert(ignore_permissions=True)

        action = self._make_action(
            meeting,
            days_from_now=3,
        ).insert(ignore_permissions=True)

        task = frappe.get_doc(
            {
                "doctype": "Task",
                "project": self.project.name,
                "subject": "Notification Task",
                "status": "Open",
                "priority": "Medium",
                "exp_end_date": (
                    date.today() + timedelta(days=3)
                ).isoformat(),
            }
        )
        task.append(
            "custom_contributors",
            {"user": self.contributor},
        )
        task.insert(ignore_permissions=True)

        frappe.set_user("Administrator")

        first = process_due_notifications(
            date.today().isoformat(),
            self.project.name,
        )
        second = process_due_notifications(
            date.today().isoformat(),
            self.project.name,
        )

        self.assertGreater(first["total"], 0)
        self.assertEqual(second["total"], 0)

        logs = frappe.get_all(
            "Notification Log",
            filters={
                "document_name": [
                    "in",
                    [meeting.name, action.name, task.name],
                ]
            },
            pluck="name",
        )

        self.assertTrue(logs)

    def test_14_scheduler_hook_registered(self):
        hooks = frappe.get_hooks("scheduler_events")

        self.assertIn(
            (
                "company_core.operations_notifications."
                "process_due_notifications"
            ),
            str(hooks),
        )

    def test_15_doctypes_and_assignee_field_exist(self):
        for doctype in (
            "Meeting Participant",
            "Project Meeting",
            "Meeting Action",
            "Progress Report",
        ):
            self.assertTrue(frappe.db.exists("DocType", doctype))

        meta = frappe.get_meta("Meeting Action")
        self.assertTrue(meta.has_field("assigned_to"))

        custom_owner_fields = [
            field
            for field in meta.fields
            if field.fieldname == "owner"
        ]
        self.assertEqual(custom_owner_fields, [])
