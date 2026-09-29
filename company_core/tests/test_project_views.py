
import json
from pathlib import Path

import erpnext
import frappe
from frappe.desk.calendar import get_events
from frappe.tests import IntegrationTestCase

from company_core.project_views import (
    get_project_view_summary,
)
from company_core.project_views_setup import (
    KANBAN_BOARD_NAME,
    ensure_project_views,
)
from company_core.task_setup import (
    ensure_task_extensions,
)


class TestProjectViews(
    IntegrationTestCase
):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        frappe.set_user(
            "Administrator"
        )

        ensure_task_extensions()
        ensure_project_views()

    def setUp(self):
        frappe.set_user(
            "Administrator"
        )

        suffix = frappe.generate_hash(
            length=6
        )

        self.sara = (
            f"views.sara.{suffix}"
            "@grovity.test"
        )

        self.zahra = (
            f"views.zahra.{suffix}"
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

        self.project_a = (
            self._create_project(
                f"Views Project A {suffix}"
            )
        )

        self.project_b = (
            self._create_project(
                f"Views Project B {suffix}"
            )
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

    def _make_task(
        self,
        project,
        subject,
        contributors=None,
        **kwargs,
    ):
        data = {
            "doctype": "Task",
            "project": project,
            "subject": subject,
            "status": "Open",
            "priority": "Medium",
            "exp_start_date": (
                "2026-09-01 09:00:00"
            ),
            "exp_end_date": (
                "2026-10-01 17:00:00"
            ),
        }

        data.update(kwargs)

        task = frappe.get_doc(data)

        for user in (
            contributors or []
        ):
            task.append(
                "custom_contributors",
                {
                    "user": user,
                },
            )

        return task

    def test_native_task_gantt_primitives_exist(
        self,
    ):
        meta = frappe.get_meta(
            "Task"
        )

        required = [
            "project",
            "exp_start_date",
            "exp_end_date",
            "progress",
            "depends_on",
            "is_milestone",
        ]

        for fieldname in required:
            self.assertIsNotNone(
                meta.get_field(fieldname),
                msg=(
                    "Missing native Task field: "
                    f"{fieldname}"
                ),
            )

        calendar_js = (
            Path(erpnext.__file__).resolve().parent
            / "projects"
            / "doctype"
            / "task"
            / "task_calendar.js"
        )

        self.assertTrue(
            calendar_js.exists()
        )

        source = calendar_js.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'gantt: true',
            source,
        )

        self.assertIn(
            'fieldname: "project"',
            source,
        )

    def test_task_status_supports_kanban(
        self,
    ):
        status_field = (
            frappe.get_meta("Task")
            .get_field("status")
        )

        self.assertIsNotNone(
            status_field
        )

        self.assertEqual(
            status_field.fieldtype,
            "Select",
        )

        options = (
            status_field.options or ""
        ).splitlines()

        self.assertIn(
            "Open",
            options,
        )

        self.assertIn(
            "Completed",
            options,
        )

    def test_grovity_task_kanban_board_exists(
        self,
    ):
        board = frappe.get_doc(
            "Kanban Board",
            KANBAN_BOARD_NAME,
        )

        self.assertEqual(
            board.reference_doctype,
            "Task",
        )

        self.assertEqual(
            board.field_name,
            "status",
        )

        columns = {
            row.column_name
            for row in board.columns
        }

        self.assertIn(
            "Open",
            columns,
        )

        self.assertIn(
            "Completed",
            columns,
        )

    def test_project_form_hook_registered(
        self,
    ):
        hooks = frappe.get_hooks(
            "doctype_js"
        )

        self.assertIn(
            "public/js/project_control.js",
            str(hooks),
        )

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

        for label in (
            "Task List",
            "Kanban",
            "Gantt",
            "Milestones",
        ):
            self.assertIn(
                label,
                source,
            )

        self.assertIn(
            "is_milestone",
            source,
        )

    def test_project_summary_manager_sees_all_tasks(
        self,
    ):
        self._make_task(
            self.project_b.name,
            "Manager Task 1",
            progress=20,
        ).insert(
            ignore_permissions=True
        )

        self._make_task(
            self.project_b.name,
            "Manager Milestone",
            is_milestone=1,
            progress=40,
        ).insert(
            ignore_permissions=True
        )

        self._make_task(
            self.project_b.name,
            "Manager Completed",
            status="Completed",
            progress=100,
        ).insert(
            ignore_permissions=True
        )

        frappe.set_user(
            self.zahra
        )

        summary = (
            get_project_view_summary(
                self.project_b.name
            )
        )

        self.assertEqual(
            summary["visible_tasks"],
            3,
        )

        self.assertEqual(
            summary["milestones"],
            1,
        )

        self.assertEqual(
            summary["completed"],
            1,
        )

    def test_project_summary_contributor_does_not_leak(
        self,
    ):
        self._make_task(
            self.project_a.name,
            "Visible To Sara",
            contributors=[
                self.sara,
            ],
        ).insert(
            ignore_permissions=True
        )

        self._make_task(
            self.project_a.name,
            "Hidden From Sara",
        ).insert(
            ignore_permissions=True
        )

        frappe.set_user(
            self.sara
        )

        summary = (
            get_project_view_summary(
                self.project_a.name
            )
        )

        self.assertEqual(
            summary["visible_tasks"],
            1,
        )

    def test_summary_denies_other_project(
        self,
    ):
        frappe.set_user(
            self.sara
        )

        with self.assertRaises(
            frappe.PermissionError
        ):
            get_project_view_summary(
                self.project_b.name
            )

    def test_gantt_events_respect_task_permissions(
        self,
    ):
        visible = self._make_task(
            self.project_a.name,
            "Visible Gantt Task",
            contributors=[
                self.sara,
            ],
        ).insert(
            ignore_permissions=True
        )

        hidden = self._make_task(
            self.project_a.name,
            "Hidden Gantt Task",
        ).insert(
            ignore_permissions=True
        )

        frappe.set_user(
            self.sara
        )

        events = get_events(
            doctype="Task",
            start="2026-08-01 00:00:00",
            end="2026-11-01 23:59:59",
            field_map=json.dumps(
                {
                    "start": (
                        "exp_start_date"
                    ),
                    "end": (
                        "exp_end_date"
                    ),
                    "id": "name",
                    "title": "subject",
                    "progress": "progress",
                }
            ),
            filters=json.dumps(
                [
                    [
                        "Task",
                        "project",
                        "=",
                        self.project_a.name,
                    ]
                ]
            ),
            fields=json.dumps(
                [
                    "name",
                    "subject",
                    "exp_start_date",
                    "exp_end_date",
                    "progress",
                ]
            ),
        )

        names = {
            row.name
            for row in events
        }

        self.assertIn(
            visible.name,
            names,
        )

        self.assertNotIn(
            hidden.name,
            names,
        )

    def tearDown(self):
        frappe.set_user(
            "Administrator"
        )

        super().tearDown()
