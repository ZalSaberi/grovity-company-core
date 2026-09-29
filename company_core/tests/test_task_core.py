
import frappe
from frappe.tests import IntegrationTestCase

from company_core.task_setup import ensure_task_extensions


class TestTaskCore(IntegrationTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        ensure_task_extensions()

        suffix = frappe.generate_hash(length=6)

        self.sara = f"task.sara.{suffix}@grovity.test"
        self.zahra = f"task.zahra.{suffix}@grovity.test"

        self._create_user(self.sara, "Sara")
        self._create_user(self.zahra, "Zahra")

        self.project_a = self._create_project(f"Task Project A {suffix}")
        self.project_b = self._create_project(f"Task Project B {suffix}")

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

    def _create_user(self, email, first_name):
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": first_name,
                "enabled": 1,
                "send_welcome_email": 0,
            }
        )
        user.append("roles", {"role": "Company User"})
        return user.insert(ignore_permissions=True)

    def _create_project(self, project_name):
        return frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": project_name,
                "status": "Open",
                "custom_project_status": "Active",
            }
        ).insert(ignore_permissions=True)

    def _create_membership(self, project, user, membership_role):
        return frappe.get_doc(
            {
                "doctype": "Project Membership",
                "project": project,
                "user": user,
                "membership_role": membership_role,
                "status": "Active",
                "start_date": frappe.utils.today(),
            }
        ).insert(ignore_permissions=True)

    def _make_task(self, project, subject, contributors=None, **kwargs):
        data = {
            "doctype": "Task",
            "project": project,
            "subject": subject,
            "status": "Open",
            "priority": "Medium",
        }
        data.update(kwargs)
        task = frappe.get_doc(data)

        for user in contributors or []:
            task.append("custom_contributors", {"user": user})

        return task

    def test_task_extension_fields_exist(self):
        meta = frappe.get_meta("Task")
        expected = [
            "custom_milestone",
            "custom_contributors",
            "custom_planned_progress",
            "custom_actual_progress",
            "custom_deliverable",
            "custom_delay_reason",
        ]
        for fieldname in expected:
            self.assertIsNotNone(
                meta.get_field(fieldname),
                msg=f"Missing Task field: {fieldname}",
            )

    def test_project_manager_can_create_task(self):
        frappe.set_user(self.zahra)
        task = self._make_task(self.project_b.name, "Manager Task")
        task.insert()
        self.assertTrue(task.name)

    def test_contributor_cannot_create_task(self):
        frappe.set_user(self.sara)
        task = self._make_task(
            self.project_a.name,
            "Contributor Create Attempt",
        )
        with self.assertRaises(frappe.PermissionError):
            task.insert()

    def test_contributor_only_sees_relevant_task(self):
        task_visible = self._make_task(
            self.project_a.name,
            "Sara Relevant Task",
            contributors=[self.sara],
        ).insert(ignore_permissions=True)

        task_hidden = self._make_task(
            self.project_a.name,
            "Sara Unrelated Task",
        ).insert(ignore_permissions=True)

        other_project = self._make_task(
            self.project_b.name,
            "Other Project Task",
        ).insert(ignore_permissions=True)

        frappe.set_user(self.sara)

        visible = frappe.get_list(
            "Task",
            filters={
                "name": [
                    "in",
                    [
                        task_visible.name,
                        task_hidden.name,
                        other_project.name,
                    ],
                ]
            },
            pluck="name",
        )

        self.assertIn(task_visible.name, visible)
        self.assertNotIn(task_hidden.name, visible)
        self.assertNotIn(other_project.name, visible)

    def test_contributor_can_update_relevant_task(self):
        task = self._make_task(
            self.project_a.name,
            "Contributor Editable",
            contributors=[self.sara],
        ).insert(ignore_permissions=True)

        frappe.set_user(self.sara)

        document = frappe.get_doc("Task", task.name)
        document.description = "Contributor update"
        document.save()

        self.assertEqual(document.description, "Contributor update")

    def test_contributor_cannot_update_unrelated_task(self):
        task = self._make_task(
            self.project_a.name,
            "Contributor Hidden",
        ).insert(ignore_permissions=True)

        frappe.set_user(self.sara)

        document = frappe.get_doc("Task", task.name)
        document.description = "Unauthorized edit"

        with self.assertRaises(frappe.PermissionError):
            document.save()

    def test_milestone_must_be_same_project(self):
        milestone = self._make_task(
            self.project_a.name,
            "Project A Milestone",
            is_milestone=1,
        ).insert(ignore_permissions=True)

        task = self._make_task(
            self.project_b.name,
            "Cross Project Task",
            custom_milestone=milestone.name,
        )

        with self.assertRaises(frappe.ValidationError):
            task.insert(ignore_permissions=True)

    def test_progress_and_deliverable_fields(self):
        task = self._make_task(
            self.project_b.name,
            "Progress Task",
            progress=35,
            custom_planned_progress=50,
            custom_deliverable=1,
            custom_delay_reason="Waiting for hardware",
        )
        task.insert(ignore_permissions=True)

        self.assertEqual(task.custom_actual_progress, 35)
        self.assertEqual(task.custom_planned_progress, 50)
        self.assertEqual(task.custom_deliverable, 1)
        self.assertEqual(
            task.custom_delay_reason,
            "Waiting for hardware",
        )

    def test_duplicate_contributors_are_rejected(self):
        task = self._make_task(
            self.project_a.name,
            "Duplicate Contributors",
            contributors=[self.sara, self.sara],
        )
        with self.assertRaises(frappe.ValidationError):
            task.insert(ignore_permissions=True)

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()
