from datetime import date, timedelta

import frappe
from frappe.tests import IntegrationTestCase

from company_core.notification_engine import (
    collect_due_events,
    dispatch_events,
)
from company_core.notification_setup import ensure_notification_settings
from company_core.notification_templates import (
    EVENT_CODES,
    SMS_MAX_UNICODE_CHARS,
    load_templates,
    render_delivery,
)
from company_core.operations_service import (
    confirm_meeting_as_pm,
    publish_meeting_summary,
    review_progress_report,
    submit_progress_report,
)


class TestPhase3NotificationTemplates(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")

        cls.suffix = frappe.generate_hash(length=8)
        cls.manager = f"tpl.manager.{cls.suffix}@grovity.test"
        cls.contributor = f"tpl.contributor.{cls.suffix}@grovity.test"

        for email, first_name in (
            (cls.manager, "Template Manager"),
            (cls.contributor, "Template Contributor"),
        ):
            user = frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": first_name,
                "enabled": 1,
                "send_welcome_email": 0,
            })
            user.append("roles", {"role": "Company User"})
            user.insert(ignore_permissions=True)

        cls.project = frappe.get_doc({
            "doctype": "Project",
            "project_name": f"Template Project {cls.suffix}",
            "status": "Open",
            "custom_project_status": "Active",
        }).insert(ignore_permissions=True)

        for user, role in (
            (cls.manager, "Project Manager"),
            (cls.contributor, "Contributor"),
        ):
            frappe.get_doc({
                "doctype": "Project Membership",
                "project": cls.project.name,
                "user": user,
                "membership_role": role,
                "status": "Active",
                "start_date": frappe.utils.today(),
            }).insert(ignore_permissions=True)

        ensure_notification_settings()
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        settings = frappe.get_single("Grovity Notification Settings")
        settings.enable_in_app = 1
        settings.enable_email = 0
        settings.enable_sms = 0
        settings.save(ignore_permissions=True)

    def test_01_template_doctype_and_defaults(self):
        self.assertTrue(
            frappe.db.exists("DocType", "Grovity Notification Template")
        )
        existing = set(
            frappe.get_all(
                "Grovity Notification Template",
                pluck="event_code",
                limit=0,
            )
        )
        self.assertTrue(set(EVENT_CODES).issubset(existing))

    def test_02_persian_sms_is_capped(self):
        template = load_templates(["DEADLINE_OVERDUE"])["DEADLINE_OVERDUE"]
        event = frappe._dict({
            "source_doctype": "Task",
            "source_name": "TASK-TEMPLATE-SMS",
            "project": self.project.name,
            "event_code": "DEADLINE_OVERDUE",
            "stage": "Overdue",
            "context": {
                "project_name": "پروژه بسیار طولانی برای آزمون سامانه اعلان گروویتی",
                "item_title": "عنوان بسیار طولانی وظیفه برای بررسی محدودیت طول پیامک فارسی در سامانه",
                "deadline": "2026-10-01",
                "overdue_days": 12,
            },
        })
        _, message = render_delivery(
            event,
            "SMS",
            self.contributor,
            template=template,
        )
        self.assertLessEqual(len(message), SMS_MAX_UNICODE_CHARS)
        self.assertIn("Grovity", message)

    def test_03_deadline_delivery_uses_template(self):
        due = date.today() + timedelta(days=3)
        task = frappe.get_doc({
            "doctype": "Task",
            "project": self.project.name,
            "subject": "Template Deadline Test",
            "status": "Open",
            "priority": "Medium",
            "exp_end_date": due.isoformat(),
        })
        task.append(
            "custom_contributors",
            {"user": self.contributor},
        )
        task.insert(ignore_permissions=True)

        events = collect_due_events(
            current_date=date.today().isoformat(),
            project=self.project.name,
        )
        event = next(
            item
            for item in events
            if item.source_doctype == "Task"
            and item.source_name == task.name
        )
        result = dispatch_events([event])
        self.assertGreater(result["sent"], 0)

        delivery = frappe.get_all(
            "Notification Delivery",
            filters={
                "source_doctype": "Task",
                "source_name": task.name,
                "channel": "In-App",
                "recipient_user": self.contributor,
            },
            fields=["event_code", "subject"],
            order_by="creation desc",
            limit=1,
        )[0]

        self.assertEqual(delivery.event_code, "DEADLINE_T3")
        self.assertIn("۳ روز", delivery.subject)

    def _meeting_with_action(self):
        meeting = frappe.get_doc({
            "doctype": "Project Meeting",
            "project": self.project.name,
            "meeting_datetime": (
                str(date.today() - timedelta(days=1))
                + " 10:00:00"
            ),
            "agenda": "Template layer agenda",
            "summary": "<p>خلاصه جلسه برای آزمون لایه قالب‌ها</p>",
            "decisions": "<p>تصمیم جلسه برای آزمون</p>",
        })
        meeting.append(
            "participants",
            {"user": self.contributor},
        )
        meeting.insert(ignore_permissions=True)

        action = frappe.get_doc({
            "doctype": "Meeting Action",
            "project": self.project.name,
            "meeting": meeting.name,
            "description": "تهیه بسته نهایی پروژه",
            "assigned_to": self.contributor,
            "deadline": (
                date.today() + timedelta(days=3)
            ).isoformat(),
            "priority": "High",
            "status": "Open",
        }).insert(ignore_permissions=True)

        frappe.set_user(self.manager)
        confirm_meeting_as_pm(meeting.name)
        return meeting, action

    def test_04_publish_summary_notifies_participants_and_action_owner(self):
        meeting, action = self._meeting_with_action()

        result = publish_meeting_summary(meeting.name)
        self.assertFalse(result["already_published"])
        self.assertEqual(result["summary_recipients"], 1)
        self.assertEqual(result["action_notifications"], 1)

        meeting.reload()
        self.assertEqual(meeting.summary_published, 1)
        self.assertEqual(meeting.summary_published_by, self.manager)

        summary_delivery = frappe.db.exists(
            "Notification Delivery",
            {
                "source_doctype": "Project Meeting",
                "source_name": meeting.name,
                "event_code": "MEETING_SUMMARY_PUBLISHED",
                "channel": "In-App",
                "recipient_user": self.contributor,
            },
        )
        action_delivery = frappe.db.exists(
            "Notification Delivery",
            {
                "source_doctype": "Meeting Action",
                "source_name": action.name,
                "event_code": "MEETING_ACTION_ASSIGNED",
                "channel": "In-App",
                "recipient_user": self.contributor,
            },
        )
        self.assertTrue(summary_delivery)
        self.assertTrue(action_delivery)

    def test_05_publish_summary_is_idempotent(self):
        meeting, _ = self._meeting_with_action()
        first = publish_meeting_summary(meeting.name)
        before = frappe.db.count(
            "Notification Delivery",
            filters={
                "source_doctype": ["in", ["Project Meeting", "Meeting Action"]],
                "project": self.project.name,
            },
        )
        second = publish_meeting_summary(meeting.name)
        after = frappe.db.count(
            "Notification Delivery",
            filters={
                "source_doctype": ["in", ["Project Meeting", "Meeting Action"]],
                "project": self.project.name,
            },
        )

        self.assertFalse(first["already_published"])
        self.assertTrue(second["already_published"])
        self.assertEqual(before, after)

    def test_06_published_summary_content_is_locked(self):
        meeting, _ = self._meeting_with_action()
        publish_meeting_summary(meeting.name)

        meeting.reload()
        meeting.summary = "<p>تغییر غیرمجاز</p>"
        with self.assertRaises(frappe.ValidationError):
            meeting.save(ignore_permissions=True)

    def test_07_revision_request_notifies_submitter(self):
        frappe.set_user(self.contributor)
        report = frappe.get_doc({
            "doctype": "Progress Report",
            "project": self.project.name,
            "period": "2026-W40",
            "progress_percent": 60,
            "completed": "Completed",
            "in_progress": "In progress",
            "issues": "Issue",
            "risks": "Risk",
            "next_actions": "Next action",
        }).insert()

        submit_progress_report(report.name)

        frappe.set_user(self.manager)
        review_progress_report(
            report.name,
            "Revision Requested",
            "لطفاً بخش ریسک‌ها تکمیل شود.",
        )

        delivery = frappe.db.exists(
            "Notification Delivery",
            {
                "source_doctype": "Progress Report",
                "source_name": report.name,
                "event_code": "PROGRESS_REPORT_REVISION_REQUESTED",
                "channel": "In-App",
                "recipient_user": self.contributor,
            },
        )
        self.assertTrue(delivery)

    def test_08_template_records_are_editable_without_code_change(self):
        template = frappe.get_doc(
            "Grovity Notification Template",
            "DEADLINE_T7",
        )
        original = template.in_app_subject
        template.in_app_subject = "آزمون قالب قابل ویرایش | {{ item_title }}"
        template.save(ignore_permissions=True)

        loaded = load_templates(["DEADLINE_T7"])["DEADLINE_T7"]
        event = frappe._dict({
            "source_doctype": "Task",
            "source_name": "TASK-EDITABLE-TEMPLATE",
            "project": self.project.name,
            "event_code": "DEADLINE_T7",
            "stage": "T-7",
            "context": {
                "item_title": "وظیفه آزمایشی",
                "project_name": self.project.name,
            },
        })
        subject, _ = render_delivery(
            event,
            "In-App",
            self.contributor,
            template=loaded,
        )
        self.assertIn("آزمون قالب قابل ویرایش", subject)

        template.in_app_subject = original
        template.save(ignore_permissions=True)
