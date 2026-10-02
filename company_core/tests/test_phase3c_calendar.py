from __future__ import annotations

from datetime import timedelta

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, now_datetime, today

from company_core.calendar_service import accept_meeting_request, get_free_slots
from company_core.calendar_sync import sync_task_calendar


class TestPhase3CCalendar(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.user_a = cls._ensure_user("phase3c.a@example.com", "Phase3C A")
        cls.user_b = cls._ensure_user("phase3c.b@example.com", "Phase3C B")
        cls.user_c = cls._ensure_user("phase3c.c@example.com", "Phase3C C")

    @staticmethod
    def _ensure_user(email, full_name):
        if not frappe.db.exists("User", email):
            user = frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": full_name,
                    "enabled": 1,
                    "send_welcome_email": 0,
                    "user_type": "System User",
                }
            ).insert(ignore_permissions=True)
            if frappe.db.exists("Role", "Company User"):
                user.add_roles("Company User")
        return email

    def setUp(self):
        frappe.set_user("Administrator")
        if frappe.db.exists("DocType", "Grovity Notification Settings"):
            frappe.db.set_single_value("Grovity Notification Settings", "enable_email", 0)

    def _set_preference(self, user):
        values = {
            "allow_meeting_requests": 1,
            "working_days": "Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday",
            "workday_start": "09:00:00",
            "workday_end": "12:00:00",
            "slot_minutes": 30,
            "retention_days": 30,
            "retain_permanently": 0,
            "monthly_summary_email": 0,
        }
        if frappe.db.exists("Grovity Calendar Preference", user):
            doc = frappe.get_doc("Grovity Calendar Preference", user)
            doc.update(values)
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc(
                {"doctype": "Grovity Calendar Preference", "user": user, **values}
            )
            doc.insert(ignore_permissions=True)
        return doc

    def test_01_event_extensions_and_doctypes_exist(self):
        meta = frappe.get_meta("Event")
        for field in (
            "custom_grovity_kind",
            "custom_calendar_owner",
            "custom_related_project",
            "custom_blocks_availability",
            "custom_grovity_managed",
            "custom_source_doctype",
            "custom_source_name",
            "custom_archived",
        ):
            self.assertTrue(meta.has_field(field), field)

        self.assertTrue(frappe.db.exists("DocType", "Meeting Request"))
        self.assertTrue(frappe.db.exists("DocType", "Grovity Calendar Preference"))

    def test_02_free_busy_hides_private_details(self):
        self._set_preference(self.user_b)
        day = add_days(today(), 1)
        event = frappe.get_doc(
            {
                "doctype": "Event",
                "subject": "SECRET PRIVATE SUBJECT",
                "event_type": "Private",
                "event_category": "Event",
                "starts_on": f"{day} 10:00:00",
                "ends_on": f"{day} 10:30:00",
                "custom_grovity_kind": "Personal Plan",
                "custom_calendar_owner": self.user_b,
                "custom_blocks_availability": 1,
            }
        )
        event.owner = self.user_b
        event.insert(ignore_permissions=True)

        frappe.set_user(self.user_a)
        slots = get_free_slots(self.user_b, str(day), 30)
        self.assertNotIn("SECRET PRIVATE SUBJECT", str(slots))
        starts = {row["start"] for row in slots}
        self.assertNotIn(f"{day} 10:00:00", starts)
        self.assertIn(f"{day} 09:00:00", starts)

    def test_03_accept_request_creates_private_calendar_event(self):
        self._set_preference(self.user_b)
        start = now_datetime() + timedelta(days=5)
        start = start.replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=30)

        frappe.set_user(self.user_a)
        request = frappe.get_doc(
            {
                "doctype": "Meeting Request",
                "target_user": self.user_b,
                "subject": "Phase 3C acceptance",
                "preferred_start": start,
                "preferred_end": end,
                "duration_minutes": 30,
                "discussion_points": "Private request details",
            }
        ).insert()
        self.assertEqual(request.requester, self.user_a)
        self.assertEqual(request.status, "Requested")

        frappe.set_user(self.user_b)
        result = accept_meeting_request(request.name)
        self.assertEqual(result["status"], "Scheduled")
        self.assertTrue(result["event"])

        event = frappe.get_doc("Event", result["event"])
        self.assertEqual(event.event_type, "Private")
        self.assertEqual(event.custom_grovity_kind, "Meeting Request")
        self.assertEqual(event.custom_calendar_owner, self.user_b)
        self.assertEqual(event.custom_blocks_availability, 1)

        updated = frappe.get_doc("Meeting Request", request.name)
        self.assertEqual(updated.status, "Scheduled")
        self.assertEqual(updated.scheduled_event, event.name)

    def test_04_request_is_hidden_from_third_user(self):
        start = now_datetime() + timedelta(days=8)
        frappe.set_user(self.user_a)
        request = frappe.get_doc(
            {
                "doctype": "Meeting Request",
                "target_user": self.user_b,
                "subject": "Permission isolation",
                "preferred_start": start,
                "duration_minutes": 30,
            }
        ).insert()

        frappe.set_user(self.user_c)
        visible = frappe.get_list(
            "Meeting Request",
            filters={"name": request.name},
            pluck="name",
        )
        self.assertEqual(visible, [])
        self.assertFalse(frappe.has_permission("Meeting Request", doc=request, user=self.user_c))

    def test_05_task_deadline_sync_is_non_blocking(self):
        frappe.set_user("Administrator")
        suffix = frappe.generate_hash(length=8)
        project = frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": f"P3C {suffix}",
                "status": "Open",
                "custom_project_status": "Active",
            }
        ).insert(ignore_permissions=True)

        task = frappe.get_doc(
            {
                "doctype": "Task",
                "subject": f"P3C task {suffix}",
                "project": project.name,
                "status": "Open",
                "exp_end_date": add_days(today(), 3),
            }
        ).insert(ignore_permissions=True)

        sync_task_calendar(task)
        event_name = frappe.db.get_value(
            "Event",
            {
                "custom_source_doctype": "Task",
                "custom_source_name": task.name,
                "custom_grovity_managed": 1,
            },
            "name",
        )
        self.assertTrue(event_name)
        event = frappe.get_doc("Event", event_name)
        self.assertEqual(event.event_type, "Private")
        self.assertEqual(event.custom_blocks_availability, 0)
        self.assertIn(event.custom_grovity_kind, ("Task Deadline", "Milestone"))

    def test_06_phase3c_hooks_registered(self):
        hooks = frappe.get_hooks()
        monthly = frappe.get_hooks("scheduler_events").get("monthly", [])
        if isinstance(monthly, str):
            monthly = [monthly]
        self.assertIn(
            "company_core.calendar_service.process_monthly_calendar_lifecycle",
            monthly,
        )

        pqc = hooks.get("permission_query_conditions", {})
        self.assertIn("Meeting Request", pqc)
        self.assertIn("Grovity Calendar Preference", pqc)
