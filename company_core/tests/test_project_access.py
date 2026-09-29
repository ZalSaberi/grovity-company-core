import frappe
from frappe.client import get_list as api_get_list
from frappe.desk.search import search_link
from frappe.tests import IntegrationTestCase

from company_core.setup import ensure_security_baseline


class TestProjectAccess(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        frappe.set_user("Administrator")
        ensure_security_baseline()

        cls.sara = "auto.sara@grovity.test"
        cls.zahra = "auto.zahra@grovity.test"

        cls._create_user(cls.sara, "Sara")
        cls._create_user(cls.zahra, "Zahra")

        cls.project_a = frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": "AUTO Project A",
                "status": "Open",
            }
        ).insert(ignore_permissions=True)

        cls.project_b = frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": "AUTO Project B",
                "status": "Open",
            }
        ).insert(ignore_permissions=True)

        cls.membership_a = frappe.get_doc(
            {
                "doctype": "Project Membership",
                "project": cls.project_a.name,
                "user": cls.sara,
                "membership_role": "Contributor",
                "status": "Active",
                "start_date": frappe.utils.today(),
            }
        ).insert(ignore_permissions=True)

        cls.membership_b = frappe.get_doc(
            {
                "doctype": "Project Membership",
                "project": cls.project_b.name,
                "user": cls.zahra,
                "membership_role": "Project Manager",
                "status": "Active",
                "start_date": frappe.utils.today(),
            }
        ).insert(ignore_permissions=True)

    @classmethod
    def _create_user(cls, email, first_name):
        if frappe.db.exists("User", email):
            user = frappe.get_doc("User", email)

            existing_roles = {
                row.role
                for row in user.roles
            }

            if "Company User" not in existing_roles:
                user.append(
                    "roles",
                    {
                        "role": "Company User",
                    },
                )
                user.save(ignore_permissions=True)

            return

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

        user.insert(ignore_permissions=True)

    def test_sara_only_sees_project_a(self):
        frappe.set_user(self.sara)

        projects = frappe.get_list(
            "Project",
            filters={
                "name": [
                    "in",
                    [
                        self.project_a.name,
                        self.project_b.name,
                    ],
                ]
            },
            pluck="name",
        )

        self.assertIn(
            self.project_a.name,
            projects,
        )

        self.assertNotIn(
            self.project_b.name,
            projects,
        )

    def test_zahra_only_sees_project_b(self):
        frappe.set_user(self.zahra)

        projects = frappe.get_list(
            "Project",
            filters={
                "name": [
                    "in",
                    [
                        self.project_a.name,
                        self.project_b.name,
                    ],
                ]
            },
            pluck="name",
        )

        self.assertNotIn(
            self.project_a.name,
            projects,
        )

        self.assertIn(
            self.project_b.name,
            projects,
        )

    def test_sara_cannot_open_project_b(self):
        frappe.set_user(self.sara)

        project_b = frappe.get_doc(
            "Project",
            self.project_b.name,
        )

        self.assertFalse(
            frappe.has_permission(
                "Project",
                ptype="read",
                doc=project_b,
                user=self.sara,
            )
        )

    def test_zahra_cannot_open_project_a(self):
        frappe.set_user(self.zahra)

        project_a = frappe.get_doc(
            "Project",
            self.project_a.name,
        )

        self.assertFalse(
            frappe.has_permission(
                "Project",
                ptype="read",
                doc=project_a,
                user=self.zahra,
            )
        )

    def test_sara_only_sees_own_project_membership(self):
        frappe.set_user(self.sara)

        memberships = frappe.get_list(
            "Project Membership",
            filters={
                "name": [
                    "in",
                    [
                        self.membership_a.name,
                        self.membership_b.name,
                    ],
                ]
            },
            pluck="name",
        )

        self.assertIn(
            self.membership_a.name,
            memberships,
        )

        self.assertNotIn(
            self.membership_b.name,
            memberships,
        )

    def test_project_manager_can_write_own_project(self):
        frappe.set_user(self.zahra)

        self.assertTrue(
            frappe.has_permission(
                "Project",
                ptype="write",
                doc=self.project_b,
                user=self.zahra,
            )
        )

    def test_contributor_cannot_write_own_project(self):
        frappe.set_user(self.sara)

        self.assertFalse(
            frappe.has_permission(
                "Project",
                ptype="write",
                doc=self.project_a,
                user=self.sara,
            )
        )

    def test_project_manager_cannot_write_other_project(self):
        frappe.set_user(self.zahra)

        self.assertFalse(
            frappe.has_permission(
                "Project",
                ptype="write",
                doc=self.project_a,
                user=self.zahra,
            )
        )

    def test_company_user_cannot_create_project(self):
        frappe.set_user(self.sara)

        self.assertFalse(
            frappe.has_permission(
                "Project",
                ptype="create",
                user=self.sara,
            )
        )

    def test_link_search_hides_other_project(self):
        frappe.set_user(self.sara)

        results = search_link(
            doctype="Project",
            txt="",
            filters={
                "name": [
                    "in",
                    [
                        self.project_a.name,
                        self.project_b.name,
                    ],
                ]
            },
            page_length=20,
        )

        project_names = [
            row["value"]
            for row in results
        ]

        self.assertIn(
            self.project_a.name,
            project_names,
        )

        self.assertNotIn(
            self.project_b.name,
            project_names,
        )

    def test_api_list_hides_other_project(self):
        frappe.set_user(self.sara)

        results = api_get_list(
            doctype="Project",
            fields=["name"],
            filters={
                "name": [
                    "in",
                    [
                        self.project_a.name,
                        self.project_b.name,
                    ],
                ]
            },
            limit_page_length=20,
        )

        project_names = [
            row["name"]
            for row in results
        ]

        self.assertIn(
            self.project_a.name,
            project_names,
        )

        self.assertNotIn(
            self.project_b.name,
            project_names,
        )

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        super().tearDownClass()
