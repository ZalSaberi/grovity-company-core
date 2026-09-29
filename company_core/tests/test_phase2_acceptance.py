
import json

import frappe
from frappe.desk.calendar import get_events
from frappe.tests import IntegrationTestCase

from company_core.project_passport import (
    get_project_passport,
)
from company_core.project_passport_setup import (
    ensure_project_passport,
)
from company_core.project_views_setup import (
    ensure_project_views,
)
from company_core.task_setup import (
    ensure_task_extensions,
)


class TestPhase2Acceptance(
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
        ensure_project_passport()

        cls.suffix = frappe.generate_hash(
            length=8
        )

        cls.manager = (
            f"phase2.manager.{cls.suffix}"
            "@grovity.test"
        )

        cls.contributor = (
            f"phase2.contributor.{cls.suffix}"
            "@grovity.test"
        )

        cls.observer = (
            f"phase2.observer.{cls.suffix}"
            "@grovity.test"
        )

        cls.other_manager = (
            f"phase2.other.{cls.suffix}"
            "@grovity.test"
        )

        cls.created_users = []
        cls.created_memberships = []
        cls.created_projects = []
        cls.created_tasks = []

        for email, first_name in (
            (
                cls.manager,
                "Phase2 Manager",
            ),
            (
                cls.contributor,
                "Phase2 Contributor",
            ),
            (
                cls.observer,
                "Phase2 Observer",
            ),
            (
                cls.other_manager,
                "Phase2 Other Manager",
            ),
        ):
            user = cls._create_user(
                email,
                first_name,
            )

            cls.created_users.append(
                user.name
            )

        cls.project = cls._create_project(
            f"Phase2 Acceptance {cls.suffix}"
        )

        cls.other_project = cls._create_project(
            f"Phase2 Other {cls.suffix}"
        )

        cls.created_projects.extend(
            [
                cls.project.name,
                cls.other_project.name,
            ]
        )

        for project, user, role in (
            (
                cls.project.name,
                cls.manager,
                "Project Manager",
            ),
            (
                cls.project.name,
                cls.contributor,
                "Contributor",
            ),
            (
                cls.project.name,
                cls.observer,
                "Observer",
            ),
            (
                cls.other_project.name,
                cls.other_manager,
                "Project Manager",
            ),
        ):
            membership = (
                cls._create_membership(
                    project,
                    user,
                    role,
                )
            )

            cls.created_memberships.append(
                membership.name
            )

        cls.dependency = cls._create_task(
            cls.project.name,
            "Foundation Task",
            progress=100,
            custom_planned_progress=100,
        )

        cls.milestone = cls._create_task(
            cls.project.name,
            "Acceptance Milestone",
            is_milestone=1,
            progress=50,
            custom_planned_progress=60,
        )

        cls.task = frappe.get_doc(
            {
                "doctype": "Task",
                "project": cls.project.name,
                "subject": "Acceptance Work Package",
                "status": "Working",
                "priority": "High",
                "progress": 35,
                "exp_start_date": (
                    "2026-09-01 09:00:00"
                ),
                "exp_end_date": (
                    "2026-10-31 17:00:00"
                ),
                "custom_milestone": (
                    cls.milestone.name
                ),
                "custom_planned_progress": 55,
                "custom_deliverable": 1,
                "custom_delay_reason": (
                    "Hardware lead time"
                ),
            }
        )

        cls.task.append(
            "custom_contributors",
            {
                "user": cls.contributor,
            },
        )

        cls.task.append(
            "depends_on",
            {
                "task": cls.dependency.name,
            },
        )

        cls.task.insert(
            ignore_permissions=True
        )

        cls.other_task = cls._create_task(
            cls.other_project.name,
            "Other Project Private Task",
            progress=10,
            custom_planned_progress=20,
        )

        cls.created_tasks.extend(
            [
                cls.dependency.name,
                cls.milestone.name,
                cls.task.name,
                cls.other_task.name,
            ]
        )

        frappe.db.commit()

    @classmethod
    def _create_user(
        cls,
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

    @classmethod
    def _create_project(
        cls,
        project_name,
    ):
        return frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": project_name,
                "status": "Open",
                "custom_project_status": "Active",
                "custom_project_health": "Healthy",
                "custom_contract_value": 500000,
                "custom_collected_amount": 200000,
                "custom_project_cost": 90000,
            }
        ).insert(
            ignore_permissions=True
        )

    @classmethod
    def _create_membership(
        cls,
        project,
        user,
        role,
    ):
        return frappe.get_doc(
            {
                "doctype": "Project Membership",
                "project": project,
                "user": user,
                "membership_role": role,
                "status": "Active",
                "start_date": frappe.utils.today(),
            }
        ).insert(
            ignore_permissions=True
        )

    @classmethod
    def _create_task(
        cls,
        project,
        subject,
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
                "2026-10-31 17:00:00"
            ),
        }

        data.update(
            kwargs
        )

        return frappe.get_doc(
            data
        ).insert(
            ignore_permissions=True
        )

    def setUp(self):
        frappe.set_user(
            "Administrator"
        )

    def test_01_project_manager_and_team_are_assignable(
        self,
    ):
        rows = frappe.get_all(
            "Project Membership",
            filters={
                "project": self.project.name,
                "status": "Active",
            },
            fields=[
                "user",
                "membership_role",
            ],
        )

        roles = {
            row.user: row.membership_role
            for row in rows
        }

        self.assertEqual(
            roles[self.manager],
            "Project Manager",
        )

        self.assertEqual(
            roles[self.contributor],
            "Contributor",
        )

        self.assertEqual(
            roles[self.observer],
            "Observer",
        )

    def test_02_project_manager_can_create_task(
        self,
    ):
        frappe.set_user(
            self.manager
        )

        task = frappe.get_doc(
            {
                "doctype": "Task",
                "project": self.project.name,
                "subject": (
                    "PM Acceptance Create"
                ),
                "status": "Open",
                "priority": "Medium",
                "exp_start_date": (
                    "2026-09-10 09:00:00"
                ),
                "exp_end_date": (
                    "2026-09-15 17:00:00"
                ),
            }
        )

        task.insert()

        self.assertTrue(
            task.name
        )

    def test_03_milestone_dependency_and_deadline_are_saved(
        self,
    ):
        task = frappe.get_doc(
            "Task",
            self.task.name,
        )

        self.assertEqual(
            task.custom_milestone,
            self.milestone.name,
        )

        dependency_names = {
            row.task
            for row in task.depends_on
        }

        self.assertIn(
            self.dependency.name,
            dependency_names,
        )

        self.assertTrue(
            task.exp_start_date
        )

        self.assertTrue(
            task.exp_end_date
        )

    def test_04_progress_and_deliverable_are_recordable(
        self,
    ):
        task = frappe.get_doc(
            "Task",
            self.task.name,
        )

        self.assertEqual(
            task.progress,
            35,
        )

        self.assertEqual(
            task.custom_actual_progress,
            35,
        )

        self.assertEqual(
            task.custom_planned_progress,
            55,
        )

        self.assertEqual(
            task.custom_deliverable,
            1,
        )

        self.assertEqual(
            task.custom_delay_reason,
            "Hardware lead time",
        )

    def test_05_contributor_can_work_only_on_relevant_task(
        self,
    ):
        frappe.set_user(
            self.contributor
        )

        visible = frappe.get_list(
            "Task",
            filters={
                "project": self.project.name,
            },
            pluck="name",
        )

        self.assertIn(
            self.task.name,
            visible,
        )

        self.assertNotIn(
            self.dependency.name,
            visible,
        )

        self.assertNotIn(
            self.other_task.name,
            visible,
        )

        task = frappe.get_doc(
            "Task",
            self.task.name,
        )

        task.description = (
            "Contributor acceptance update"
        )

        task.save()

        self.assertEqual(
            task.description,
            "Contributor acceptance update",
        )

    def test_06_observer_cannot_see_unassigned_tasks(
        self,
    ):
        frappe.set_user(
            self.observer
        )

        visible = frappe.get_list(
            "Task",
            filters={
                "project": self.project.name,
            },
            pluck="name",
        )

        self.assertEqual(
            visible,
            [],
        )

    def test_07_gantt_respects_project_task_permissions(
        self,
    ):
        frappe.set_user(
            self.contributor
        )

        events = get_events(
            doctype="Task",
            start="2026-08-01 00:00:00",
            end="2026-11-30 23:59:59",
            field_map=json.dumps(
                {
                    "start": "exp_start_date",
                    "end": "exp_end_date",
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
                        self.project.name,
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
            self.task.name,
            names,
        )

        self.assertNotIn(
            self.dependency.name,
            names,
        )

        self.assertNotIn(
            self.other_task.name,
            names,
        )

    def test_08_project_passport_is_end_to_end(
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

        self.assertEqual(
            passport["team_count"],
            2,
        )

        self.assertEqual(
            passport["observer_count"],
            1,
        )

        self.assertEqual(
            passport["contract_value"],
            500000,
        )

        self.assertEqual(
            passport["collected_amount"],
            200000,
        )

        self.assertEqual(
            passport["project_cost"],
            90000,
        )

    def test_09_status_transition_creates_audit_history(
        self,
    ):
        frappe.set_user(
            self.manager
        )

        project = frappe.get_doc(
            "Project",
            self.project.name,
        )

        project.custom_project_status = (
            "Under Review"
        )

        project.custom_status_change_reason = (
            "Phase 2 acceptance audit"
        )

        project.save()

        row = frappe.get_all(
            "Project Status History",
            filters={
                "project": self.project.name,
                "new_status": "Under Review",
            },
            fields=[
                "old_status",
                "new_status",
                "reason",
                "changed_by",
            ],
            order_by="creation desc",
            limit=1,
        )[0]

        self.assertEqual(
            row.old_status,
            "Active",
        )

        self.assertEqual(
            row.new_status,
            "Under Review",
        )

        self.assertEqual(
            row.reason,
            "Phase 2 acceptance audit",
        )

        self.assertEqual(
            row.changed_by,
            self.manager,
        )

    def test_10_suspension_lifecycle_is_recordable(
        self,
    ):
        frappe.set_user(
            self.manager
        )

        event = frappe.get_doc(
            {
                "doctype": "Suspension Event",
                "project": self.project.name,
                "start_date": "2026-10-01",
                "reason_category": "Technical",
                "description": (
                    "Acceptance suspension"
                ),
                "responsible_side": (
                    "Internal Team"
                ),
                "approved_by": self.manager,
            }
        )

        event.insert()

        self.assertTrue(
            event.name
        )

        event.end_date = (
            "2026-10-03"
        )

        event.save()

        self.assertEqual(
            str(event.end_date),
            "2026-10-03",
        )

    @classmethod
    def tearDownClass(cls):
        frappe.set_user(
            "Administrator"
        )

        for doctype, filters in (
            (
                "Project Status History",
                {
                    "project": [
                        "in",
                        cls.created_projects,
                    ]
                },
            ),
            (
                "Suspension Event",
                {
                    "project": [
                        "in",
                        cls.created_projects,
                    ]
                },
            ),
        ):
            names = frappe.get_all(
                doctype,
                filters=filters,
                pluck="name",
            )

            for name in names:
                if frappe.db.exists(
                    doctype,
                    name,
                ):
                    frappe.delete_doc(
                        doctype,
                        name,
                        ignore_permissions=True,
                        force=True,
                    )

        for name in cls.created_tasks:
            if frappe.db.exists(
                "Task",
                name,
            ):
                frappe.delete_doc(
                    "Task",
                    name,
                    ignore_permissions=True,
                    force=True,
                )

        for name in cls.created_memberships:
            if frappe.db.exists(
                "Project Membership",
                name,
            ):
                frappe.delete_doc(
                    "Project Membership",
                    name,
                    ignore_permissions=True,
                    force=True,
                )

        for name in cls.created_projects:
            if frappe.db.exists(
                "Project",
                name,
            ):
                frappe.delete_doc(
                    "Project",
                    name,
                    ignore_permissions=True,
                    force=True,
                )

        for name in cls.created_users:
            if frappe.db.exists(
                "User",
                name,
            ):
                frappe.delete_doc(
                    "User",
                    name,
                    ignore_permissions=True,
                    force=True,
                )

        frappe.db.commit()

        super().tearDownClass()
