import frappe
from frappe.tests import IntegrationTestCase

from company_core.setup import (
    ensure_phase2_project_core,
)
from company_core.status_history_setup import (
    ensure_status_history_fields,
)


class TestProjectStatusHistory(
    IntegrationTestCase
):
    def setUp(self):
        frappe.set_user(
            "Administrator"
        )

        ensure_phase2_project_core()
        ensure_status_history_fields()

        suffix = frappe.generate_hash(
            length=6
        )

        self.sara = (
            f"status.sara.{suffix}"
            "@grovity.test"
        )

        self.zahra = (
            f"status.zahra.{suffix}"
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
            f"Status Project A {suffix}"
        )

        self.project_b = self._create_project(
            f"Status Project B {suffix}"
        )

        self.membership_a = (
            self._create_membership(
                self.project_a.name,
                self.sara,
                "Contributor",
            )
        )

        self.membership_b = (
            self._create_membership(
                self.project_b.name,
                self.zahra,
                "Project Manager",
            )
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
                "custom_project_status": "Draft",
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

    def _change_status(
        self,
        project,
        new_status,
        reason,
    ):
        frappe.set_user(
            "Administrator"
        )

        document = frappe.get_doc(
            "Project",
            project.name,
        )

        document.custom_project_status = (
            new_status
        )

        document.custom_status_change_reason = (
            reason
        )

        document.save(
            ignore_permissions=True
        )

        return document

    def _get_history(
        self,
        project,
    ):
        return frappe.get_all(
            "Project Status History",
            filters={
                "project": project.name,
            },
            fields=[
                "name",
                "project",
                "old_status",
                "new_status",
                "changed_at",
                "changed_by",
                "reason",
            ],
            order_by="changed_at asc",
        )

    def test_status_change_creates_history(
        self,
    ):
        self._change_status(
            self.project_a,
            "Active",
            "Contract signed",
        )

        history = self._get_history(
            self.project_a
        )

        self.assertEqual(
            len(history),
            1,
        )

        row = history[0]

        self.assertEqual(
            row.old_status,
            "Draft",
        )

        self.assertEqual(
            row.new_status,
            "Active",
        )

        self.assertEqual(
            row.reason,
            "Contract signed",
        )

        self.assertEqual(
            row.changed_by,
            "Administrator",
        )

        self.assertTrue(
            row.changed_at
        )

    def test_status_change_requires_reason(
        self,
    ):
        project = frappe.get_doc(
            "Project",
            self.project_a.name,
        )

        project.custom_project_status = (
            "Active"
        )

        project.custom_status_change_reason = (
            None
        )

        with self.assertRaises(
            frappe.ValidationError
        ):
            project.save(
                ignore_permissions=True
            )

    def test_no_history_without_status_change(
        self,
    ):
        project = frappe.get_doc(
            "Project",
            self.project_a.name,
        )

        project.custom_project_health = (
            "Attention"
        )

        project.save(
            ignore_permissions=True
        )

        history = self._get_history(
            self.project_a
        )

        self.assertEqual(
            len(history),
            0,
        )

    def test_reason_is_cleared_after_transition(
        self,
    ):
        self._change_status(
            self.project_a,
            "Active",
            "Kickoff approved",
        )

        project = frappe.get_doc(
            "Project",
            self.project_a.name,
        )

        self.assertFalse(
            project.custom_status_change_reason
        )

    def test_user_only_sees_own_project_history(
        self,
    ):
        self._change_status(
            self.project_a,
            "Active",
            "Sara project started",
        )

        self._change_status(
            self.project_b,
            "Active",
            "Zahra project started",
        )

        history_a = self._get_history(
            self.project_a
        )[0]

        history_b = self._get_history(
            self.project_b
        )[0]

        frappe.set_user(
            self.sara
        )

        visible = frappe.get_list(
            "Project Status History",
            filters={
                "name": [
                    "in",
                    [
                        history_a.name,
                        history_b.name,
                    ],
                ]
            },
            pluck="name",
        )

        self.assertIn(
            history_a.name,
            visible,
        )

        self.assertNotIn(
            history_b.name,
            visible,
        )

    def test_user_cannot_read_other_history(
        self,
    ):
        self._change_status(
            self.project_b,
            "Active",
            "Private transition",
        )

        history = self._get_history(
            self.project_b
        )[0]

        history_doc = frappe.get_doc(
            "Project Status History",
            history.name,
        )

        frappe.set_user(
            self.sara
        )

        self.assertFalse(
            frappe.has_permission(
                "Project Status History",
                ptype="read",
                doc=history_doc,
                user=self.sara,
            )
        )

    def test_history_is_immutable(
        self,
    ):
        self._change_status(
            self.project_a,
            "Active",
            "Immutable record test",
        )

        history = self._get_history(
            self.project_a
        )[0]

        history_doc = frappe.get_doc(
            "Project Status History",
            history.name,
        )

        history_doc.reason = (
            "Someone tried to edit history"
        )

        with self.assertRaises(
            frappe.ValidationError
        ):
            history_doc.save(
                ignore_permissions=True
            )

    def tearDown(self):
        frappe.set_user(
            "Administrator"
        )

        super().tearDown()
