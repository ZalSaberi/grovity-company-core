from datetime import date, timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from company_core.notification_engine import (
    channels_for_stage,
    collect_due_events,
    dispatch_events,
    get_settings,
    process_due_notifications,
)


class TestPhase3NotificationHardening(
    IntegrationTestCase
):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        frappe.set_user("Administrator")

        cls.suffix = frappe.generate_hash(
            length=10
        )

        cls.project = frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": (
                    f"Notify Test {cls.suffix}"
                ),
                "status": "Open",
                "custom_project_status": "Active",
            }
        ).insert(
            ignore_permissions=True
        )

        frappe.get_doc(
            {
                "doctype": "Project Membership",
                "project": cls.project.name,
                "user": "Administrator",
                "membership_role": "Project Manager",
                "status": "Active",
                "start_date": frappe.utils.today(),
            }
        ).insert(
            ignore_permissions=True
        )

    def setUp(self):
        frappe.set_user("Administrator")

        settings = frappe.get_single(
            "Grovity Notification Settings"
        )

        settings.enable_in_app = 1
        settings.enable_email = 0
        settings.enable_sms = 0

        settings.sms_t7 = 0
        settings.sms_t3 = 0
        settings.sms_t1 = 1
        settings.sms_due_date = 1
        settings.sms_overdue = 1

        settings.retry_limit = 3

        settings.save(
            ignore_permissions=True
        )

    def _event(self, stage):
        return frappe._dict(
            {
                "source_doctype": "Project",
                "source_name": self.project.name,
                "project": self.project.name,
                "stage": stage,
                "subject": (
                    f"[Grovity][{stage}] Test"
                ),
                "message": (
                    "Notification hardening test."
                ),
                "recipients": [
                    "Administrator"
                ],
            }
        )

    def test_01_doctypes_exist(self):
        self.assertTrue(
            frappe.db.exists(
                "DocType",
                "Grovity Notification Settings",
            )
        )

        self.assertTrue(
            frappe.db.exists(
                "DocType",
                "Notification Delivery",
            )
        )

    def test_02_channel_policy(self):
        settings = get_settings()

        self.assertEqual(
            channels_for_stage(
                "T-7",
                settings,
            ),
            [
                "In-App",
            ],
        )

        settings.enable_email = 1
        settings.enable_sms = 1

        self.assertEqual(
            channels_for_stage(
                "T-1",
                settings,
            ),
            [
                "In-App",
                "Email",
                "SMS",
            ],
        )

    def test_03_in_app_dedup(self):
        event = self._event("T-7")

        first = dispatch_events(
            [event]
        )

        second = dispatch_events(
            [event]
        )

        self.assertEqual(
            first["created"],
            1,
        )

        self.assertEqual(
            first["sent"],
            1,
        )

        self.assertEqual(
            second["created"],
            0,
        )

        self.assertEqual(
            second["deduplicated"],
            1,
        )

    def test_04_email_uses_queue(self):
        settings = frappe.get_single(
            "Grovity Notification Settings"
        )

        settings.enable_in_app = 0
        settings.enable_email = 1
        settings.save(
            ignore_permissions=True
        )

        fake_queue = frappe._dict(
            {
                "name": "EMAIL-QUEUE-TEST"
            }
        )

        def destination(user, channel):
            if channel == "Email":
                return "notify-test@example.com"

            return user

        with (
            patch(
                "company_core.notification_engine._destination",
                side_effect=destination,
            ),
            patch(
                "company_core.notification_engine.frappe.db.exists",
                return_value=True,
            ),
            patch(
                "company_core.notification_engine.frappe.sendmail",
                return_value=fake_queue,
            ) as mocked_sendmail,
        ):
            result = dispatch_events(
                [
                    self._event("T-3")
                ]
            )

        self.assertEqual(
            result["queued"],
            1,
        )

        self.assertEqual(
            result["failed"],
            0,
        )

        mocked_sendmail.assert_called_once()

    def test_05_sms_uses_frappe_sms(self):
        settings = frappe.get_single(
            "Grovity Notification Settings"
        )

        settings.enable_in_app = 0
        settings.enable_sms = 1
        settings.sms_t1 = 1
        settings.save(
            ignore_permissions=True
        )

        def destination(user, channel):
            if channel == "SMS":
                return "+989121234567"

            return user

        with (
            patch(
                "company_core.notification_engine._destination",
                side_effect=destination,
            ),
            patch(
                (
                    "frappe.core.doctype."
                    "sms_settings.sms_settings."
                    "send_sms"
                ),
                return_value=True,
            ) as mocked_sms,
        ):
            result = dispatch_events(
                [
                    self._event("T-1")
                ]
            )

        self.assertEqual(
            result["sent"],
            1,
        )

        self.assertEqual(
            result["failed"],
            0,
        )

        mocked_sms.assert_called_once()

    def test_06_provider_failures_are_non_blocking(self):
        settings = frappe.get_single(
            "Grovity Notification Settings"
        )

        settings.enable_in_app = 0
        settings.enable_email = 1
        settings.enable_sms = 1
        settings.sms_due_date = 1
        settings.save(
            ignore_permissions=True
        )

        def destination(user, channel):
            if channel == "Email":
                return "notify-test@example.com"

            if channel == "SMS":
                return "+989121234568"

            return user

        with (
            patch(
                "company_core.notification_engine._destination",
                side_effect=destination,
            ),
            patch(
                "company_core.notification_engine.frappe.db.exists",
                return_value=True,
            ),
            patch(
                "company_core.notification_engine.frappe.sendmail",
                side_effect=RuntimeError(
                    "smtp down"
                ),
            ),
            patch(
                (
                    "frappe.core.doctype."
                    "sms_settings.sms_settings."
                    "send_sms"
                ),
                side_effect=RuntimeError(
                    "sms down"
                ),
            ),
        ):
            result = dispatch_events(
                [
                    self._event("Due Date")
                ]
            )

        self.assertEqual(
            result["created"],
            2,
        )

        self.assertEqual(
            result["failed"],
            2,
        )

        self.assertEqual(
            result["deduplicated"],
            0,
        )

    def test_07_batched_collector_finds_task(self):
        due = (
            date.today()
            + timedelta(
                days=3
            )
        )

        task = frappe.get_doc(
            {
                "doctype": "Task",
                "project": self.project.name,
                "subject": (
                    "Batched Collector Test"
                ),
                "status": "Open",
                "priority": "Medium",
                "exp_end_date": (
                    due.isoformat()
                ),
            }
        )

        task.append(
            "custom_contributors",
            {
                "user": "Administrator",
            },
        )

        task.insert(
            ignore_permissions=True
        )

        events = collect_due_events(
            current_date=(
                date.today().isoformat()
            ),
            project=self.project.name,
        )

        matching = [
            event
            for event in events
            if (
                event.source_doctype == "Task"
                and event.source_name == task.name
            )
        ]

        self.assertEqual(
            len(matching),
            1,
        )

        self.assertIn(
            "Administrator",
            matching[0].recipients,
        )

    def test_08_dry_run_has_no_delivery_rows(self):
        before = frappe.db.count(
            "Notification Delivery"
        )

        result = dispatch_events(
            [
                self._event("Overdue")
            ],
            dry_run=True,
        )

        after = frappe.db.count(
            "Notification Delivery"
        )

        self.assertEqual(
            before,
            after,
        )

        self.assertEqual(
            result["created"],
            1,
        )

    def test_09_process_contract(self):
        result = process_due_notifications(
            current_date=(
                date.today().isoformat()
            ),
            project=self.project.name,
            dry_run=True,
        )

        self.assertIn(
            "total",
            result,
        )

        self.assertIn(
            "events",
            result,
        )

        self.assertIn(
            "created",
            result,
        )

        self.assertIn(
            "deduplicated",
            result,
        )

    def test_10_scheduler_hardening_jobs(self):
        hooks = frappe.get_hooks(
            "scheduler_events"
        )

        hook_text = str(hooks)

        self.assertIn(
            (
                "company_core."
                "notification_engine."
                "reconcile_email_deliveries"
            ),
            hook_text,
        )

        self.assertIn(
            (
                "company_core."
                "notification_engine."
                "retry_failed_deliveries"
            ),
            hook_text,
        )
