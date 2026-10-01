from datetime import date, timedelta

import frappe
from frappe.tests import IntegrationTestCase

from company_core.notification_engine import collect_due_events


class TestPhase3MeetingReminderCompletion(IntegrationTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def test_01_meeting_reminder_template_and_sms_policy(self):
        self.assertTrue(
            frappe.db.exists(
                "Grovity Notification Template",
                "MEETING_REMINDER",
            )
        )

        self.assertEqual(
            frappe.db.get_value(
                "Grovity Notification Template",
                "MEETING_REMINDER",
                "enable_sms",
            ),
            0,
        )

        for code in ("DEADLINE_T7", "DEADLINE_T3"):
            self.assertEqual(
                frappe.db.get_value(
                    "Grovity Notification Template",
                    code,
                    "enable_sms",
                ),
                0,
            )

    def test_02_meeting_collector_uses_meeting_reminder_event_code(self):
        suffix = frappe.generate_hash(length=8)

        project = frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": f"Meeting Reminder {suffix}",
                "status": "Open",
                "custom_project_status": "Active",
            }
        ).insert(ignore_permissions=True)

        frappe.get_doc(
            {
                "doctype": "Project Membership",
                "project": project.name,
                "user": "Administrator",
                "membership_role": "Project Manager",
                "status": "Active",
                "start_date": frappe.utils.today(),
            }
        ).insert(ignore_permissions=True)

        meeting = frappe.get_doc(
            {
                "doctype": "Project Meeting",
                "project": project.name,
                "meeting_datetime": (
                    str(date.today() + timedelta(days=3))
                    + " 10:00:00"
                ),
                "agenda": "Meeting reminder completion test",
            }
        ).insert(ignore_permissions=True)

        events = collect_due_events(
            current_date=date.today().isoformat(),
            project=project.name,
        )

        matching = [
            event
            for event in events
            if (
                event.source_doctype == "Project Meeting"
                and event.source_name == meeting.name
            )
        ]

        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].stage, "T-3")
        self.assertEqual(
            matching[0].event_code,
            "MEETING_REMINDER",
        )
