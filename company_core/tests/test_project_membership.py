import frappe
from frappe.tests import IntegrationTestCase


class TestProjectMembership(IntegrationTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

        suffix = frappe.generate_hash(length=6)

        self.user = f"member-{suffix}@grovity.test"

        frappe.get_doc(
            {
                "doctype": "User",
                "email": self.user,
                "first_name": "Membership Test",
                "enabled": 1,
                "send_welcome_email": 0,
            }
        ).insert(ignore_permissions=True)

        self.project = frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": f"Membership Test {suffix}",
                "status": "Open",
            }
        ).insert(ignore_permissions=True)

    def make_membership(self, **kwargs):
        data = {
            "doctype": "Project Membership",
            "project": self.project.name,
            "user": self.user,
            "membership_role": "Contributor",
            "status": "Active",
            "start_date": "2026-09-01",
        }

        data.update(kwargs)

        return frappe.get_doc(data)

    def test_end_date_cannot_be_before_start_date(self):
        membership = self.make_membership(
            end_date="2026-08-31",
        )

        with self.assertRaises(frappe.ValidationError):
            membership.insert(ignore_permissions=True)

    def test_ended_membership_requires_end_date(self):
        membership = self.make_membership(
            status="Ended",
        )

        with self.assertRaises(frappe.ValidationError):
            membership.insert(ignore_permissions=True)

    def test_duplicate_active_membership_is_rejected(self):
        self.make_membership().insert(ignore_permissions=True)

        duplicate = self.make_membership()

        with self.assertRaises(frappe.ValidationError):
            duplicate.insert(ignore_permissions=True)

    def test_valid_membership_can_be_created(self):
        membership = self.make_membership()

        membership.insert(ignore_permissions=True)

        self.assertTrue(membership.name)
        self.assertEqual(membership.status, "Active")
