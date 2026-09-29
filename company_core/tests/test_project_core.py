import frappe
from frappe.tests import IntegrationTestCase

from company_core.setup import (
    PROJECT_HEALTH_OPTIONS,
    PROJECT_STATUS_OPTIONS,
    PROJECT_TYPE_OPTIONS,
    ensure_phase2_project_core,
)


class TestProjectCore(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        frappe.set_user("Administrator")
        ensure_phase2_project_core()

    def test_project_core_fields_exist(self):
        meta = frappe.get_meta("Project")

        expected_fields = [
            "custom_project_type",
            "custom_project_category",
            "custom_project_status",
            "custom_project_health",
            "custom_confidentiality_level",
            "custom_actual_start_date",
            "custom_actual_end_date",
            "custom_technology_tags",
            "custom_contract_value",
            "custom_collected_amount",
            "custom_google_drive_folder",
            "custom_repository_url",
        ]

        for fieldname in expected_fields:
            self.assertIsNotNone(
                meta.get_field(fieldname),
                msg=f"Missing Project field: {fieldname}",
            )

    def test_project_core_taxonomies(self):
        meta = frappe.get_meta("Project")

        project_type = meta.get_field(
            "custom_project_type"
        ).options.splitlines()

        project_status = meta.get_field(
            "custom_project_status"
        ).options.splitlines()

        project_health = meta.get_field(
            "custom_project_health"
        ).options.splitlines()

        self.assertEqual(
            project_type,
            PROJECT_TYPE_OPTIONS,
        )

        self.assertEqual(
            project_status,
            PROJECT_STATUS_OPTIONS,
        )

        self.assertEqual(
            project_health,
            PROJECT_HEALTH_OPTIONS,
        )

    def test_project_core_values_can_be_saved(self):
        project = frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": (
                    f"AUTO Project Core "
                    f"{frappe.generate_hash(length=6)}"
                ),
                "status": "Open",
                "custom_project_type": "Strategic R&D",
                "custom_project_category": "Autonomous Systems",
                "custom_project_status": "Active",
                "custom_project_health": "Healthy",
                "custom_confidentiality_level": "Internal",
                "custom_actual_start_date": "2026-09-01",
                "custom_technology_tags": (
                    "AI, UAV, Navigation, SLAM"
                ),
                "custom_contract_value": 70000000,
                "custom_collected_amount": 20000000,
                "custom_google_drive_folder": (
                    "https://drive.google.com/"
                ),
                "custom_repository_url": (
                    "https://github.com/example/project"
                ),
            }
        ).insert(ignore_permissions=True)

        saved_project = frappe.get_doc(
            "Project",
            project.name,
        )

        self.assertEqual(
            saved_project.custom_project_type,
            "Strategic R&D",
        )

        self.assertEqual(
            saved_project.custom_project_status,
            "Active",
        )

        self.assertEqual(
            saved_project.custom_project_health,
            "Healthy",
        )

        self.assertEqual(
            saved_project.custom_contract_value,
            70000000,
        )

        self.assertEqual(
            saved_project.custom_collected_amount,
            20000000,
        )

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        super().tearDownClass()
