
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

from company_core.project_passport import (
    get_project_passport,
)
from company_core.project_passport_setup import (
    ensure_project_passport,
)


class TestProjectPassport(
    IntegrationTestCase
):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        frappe.set_user(
            "Administrator"
        )

        ensure_project_passport()

    def setUp(self):
        frappe.set_user(
            "Administrator"
        )

        suffix = frappe.generate_hash(
            length=6
        )

        self.manager = (
            f"passport.manager.{suffix}"
            "@grovity.test"
        )

        self.contributor = (
            f"passport.contributor.{suffix}"
            "@grovity.test"
        )

        self.observer = (
            f"passport.observer.{suffix}"
            "@grovity.test"
        )

        self.other_user = (
            f"passport.other.{suffix}"
            "@grovity.test"
        )

        for email, first_name in (
            (
                self.manager,
                "Passport Manager",
            ),
            (
                self.contributor,
                "Passport Contributor",
            ),
            (
                self.observer,
                "Passport Observer",
            ),
            (
                self.other_user,
                "Passport Other",
            ),
        ):
            self._create_user(
                email,
                first_name,
            )

        self.project = (
            self._create_project(
                f"Passport Project {suffix}"
            )
        )

        self.other_project = (
            self._create_project(
                f"Passport Other {suffix}"
            )
        )

        self._create_membership(
            self.project.name,
            self.manager,
            "Project Manager",
        )

        self._create_membership(
            self.project.name,
            self.contributor,
            "Contributor",
        )

        self._create_membership(
            self.project.name,
            self.observer,
            "Observer",
        )

        self._create_membership(
            self.other_project.name,
            self.other_user,
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
                "custom_project_health": "Healthy",
                "custom_contract_value": 100000,
                "custom_collected_amount": 40000,
                "custom_project_cost": 25000,
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

    def test_passport_fields_exist(
        self,
    ):
        meta = frappe.get_meta(
            "Project"
        )

        for fieldname in (
            "custom_project_passport",
            "custom_project_cost",
            "custom_finance_status",
            "custom_legal_status",
        ):
            self.assertIsNotNone(
                meta.get_field(
                    fieldname
                ),
                msg=(
                    "Missing Project Passport field: "
                    f"{fieldname}"
                ),
            )

    def test_passport_reports_manager_team_and_observers(
        self,
    ):
        frappe.set_user(
            self.contributor
        )

        passport = (
            get_project_passport(
                self.project.name
            )
        )

        self.assertEqual(
            passport["team_count"],
            2,
        )

        self.assertEqual(
            passport["observer_count"],
            1,
        )

        self.assertEqual(
            len(
                passport["managers"]
            ),
            1,
        )

        self.assertEqual(
            passport["managers"][0]["user"],
            self.manager,
        )

    def test_passport_reports_commercial_snapshot(
        self,
    ):
        frappe.set_user(
            self.manager
        )

        passport = (
            get_project_passport(
                self.project.name
            )
        )

        self.assertEqual(
            passport["contract_value"],
            100000,
        )

        self.assertEqual(
            passport["collected_amount"],
            40000,
        )

        self.assertEqual(
            passport["project_cost"],
            25000,
        )

        self.assertEqual(
            passport["health"],
            "Healthy",
        )

    def test_passport_uses_safe_unconfigured_statuses(
        self,
    ):
        frappe.set_user(
            self.manager
        )

        passport = (
            get_project_passport(
                self.project.name
            )
        )

        self.assertEqual(
            passport["finance_status"],
            "Not configured",
        )

        self.assertEqual(
            passport["legal_status"],
            "Not configured",
        )

    def test_project_member_can_read_passport(
        self,
    ):
        frappe.set_user(
            self.contributor
        )

        passport = (
            get_project_passport(
                self.project.name
            )
        )

        self.assertEqual(
            passport["project"],
            self.project.name,
        )

    def test_other_project_passport_is_denied(
        self,
    ):
        frappe.set_user(
            self.contributor
        )

        with self.assertRaises(
            frappe.PermissionError
        ):
            get_project_passport(
                self.other_project.name
            )

    def test_project_js_contains_passport_and_views(
        self,
    ):
        app_package_root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        js_path = (
            app_package_root
            / "public"
            / "js"
            / "project_control.js"
        )

        self.assertTrue(
            js_path.exists()
        )

        source = js_path.read_text(
            encoding="utf-8"
        )

        for marker in (
            "load_project_passport",
            "custom_project_passport",
            "Finance Status",
            "Legal Status",
            "Task List",
            "Kanban",
            "Gantt",
            "Milestones",
        ):
            self.assertIn(
                marker,
                source,
            )

    def tearDown(self):
        frappe.set_user(
            "Administrator"
        )

        super().tearDown()
