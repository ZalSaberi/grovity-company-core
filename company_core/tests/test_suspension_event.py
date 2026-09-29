import frappe
from frappe.tests import IntegrationTestCase

from company_core.setup import (
    ensure_phase2_project_core,
)


class TestSuspensionEvent(
    IntegrationTestCase
):
    def setUp(self):
        frappe.set_user("Administrator")

        ensure_phase2_project_core()

        suffix = frappe.generate_hash(
            length=6
        )

        self.sara = (
            f"susp.sara.{suffix}"
            "@grovity.test"
        )

        self.zahra = (
            f"susp.zahra.{suffix}"
            "@grovity.test"
        )

        self._create_user(
            self.sara,
            "Sara",
        )

        self._create_user(
            self.zahra,
            "Zahra",
        )

        self.project_a = self._create_project(
            f"Suspension Project A {suffix}"
        )

        self.project_b = self._create_project(
            f"Suspension Project B {suffix}"
        )

        self._create_membership(
            self.project_a.name,
            self.sara,
            "Contributor",
        )

        self._create_membership(
            self.project_b.name,
            self.zahra,
            "Project Manager",
        )

    def _create_user(
        self,
        email,
        first_name,
    ):
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": first_name,
                "enabled": 1,
                "send_welcome_email": 0,
            }
        )

        user.append(
            "roles",
            {
                "role": "Company User",
            },
        )

        return user.insert(
            ignore_permissions=True
        )

    def _create_project(
        self,
        project_name,
    ):
        return frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": project_name,
                "status": "Open",
                "custom_project_status": "Active",
            }
        ).insert(
            ignore_permissions=True
        )

    def _create_membership(
        self,
        project,
        user,
        membership_role,
    ):
        return frappe.get_doc(
            {
                "doctype": "Project Membership",
                "project": project,
                "user": user,
                "membership_role": membership_role,
                "status": "Active",
                "start_date": frappe.utils.today(),
            }
        ).insert(
            ignore_permissions=True
        )

    def _make_event(
        self,
        project,
        **kwargs,
    ):
        data = {
            "doctype": "Suspension Event",
            "project": project,
            "start_date": "2026-09-30",
            "reason_category": "Technical",
            "description": "Technical blocker",
            "responsible_side": "Internal Team",
        }

        data.update(kwargs)

        return frappe.get_doc(data)

    def test_valid_suspension_event_can_be_created(
        self,
    ):
        event = self._make_event(
            self.project_a.name
        )

        event.insert(
            ignore_permissions=True
        )

        self.assertTrue(
            event.name
        )

        self.assertEqual(
            event.reason_category,
            "Technical",
        )

    def test_end_date_cannot_be_before_start_date(
        self,
    ):
        event = self._make_event(
            self.project_a.name,
            end_date="2026-09-29",
        )

        with self.assertRaises(
            frappe.ValidationError
        ):
            event.insert(
                ignore_permissions=True
            )

    def test_duplicate_open_suspension_is_rejected(
        self,
    ):
        self._make_event(
            self.project_a.name
        ).insert(
            ignore_permissions=True
        )

        duplicate = self._make_event(
            self.project_a.name
        )

        with self.assertRaises(
            frappe.ValidationError
        ):
            duplicate.insert(
                ignore_permissions=True
            )

    def test_project_manager_can_create_own_suspension(
        self,
    ):
        frappe.set_user(
            self.zahra
        )

        event = self._make_event(
            self.project_b.name
        )

        event.insert()

        self.assertTrue(
            event.name
        )

    def test_contributor_cannot_create_suspension(
        self,
    ):
        frappe.set_user(
            self.sara
        )

        event = self._make_event(
            self.project_a.name
        )

        with self.assertRaises(
            frappe.PermissionError
        ):
            event.insert()

    def test_user_only_sees_own_project_suspensions(
        self,
    ):
        event_a = self._make_event(
            self.project_a.name
        ).insert(
            ignore_permissions=True
        )

        event_b = self._make_event(
            self.project_b.name
        ).insert(
            ignore_permissions=True
        )

        frappe.set_user(
            self.sara
        )

        visible = frappe.get_list(
            "Suspension Event",
            filters={
                "name": [
                    "in",
                    [
                        event_a.name,
                        event_b.name,
                    ],
                ]
            },
            pluck="name",
        )

        self.assertIn(
            event_a.name,
            visible,
        )

        self.assertNotIn(
            event_b.name,
            visible,
        )

    def test_manager_can_update_but_contributor_cannot(
        self,
    ):
        event_a = self._make_event(
            self.project_a.name
        ).insert(
            ignore_permissions=True
        )

        event_b = self._make_event(
            self.project_b.name
        ).insert(
            ignore_permissions=True
        )

        frappe.set_user(
            self.zahra
        )

        manager_event = frappe.get_doc(
            "Suspension Event",
            event_b.name,
        )

        manager_event.description = (
            "Manager updated description"
        )

        manager_event.save()

        frappe.set_user(
            self.sara
        )

        contributor_event = frappe.get_doc(
            "Suspension Event",
            event_a.name,
        )

        contributor_event.description = (
            "Contributor tried to edit"
        )

        with self.assertRaises(
            frappe.PermissionError
        ):
            contributor_event.save()

    def tearDown(self):
        frappe.set_user(
            "Administrator"
        )

        super().tearDown()
