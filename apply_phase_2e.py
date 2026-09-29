#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


SITE = "company.localhost"
APP = "company_core"
KANBAN_BOARD = "Grovity Task Board"

REPO_ROOT = Path(__file__).resolve().parent
BENCH_ROOT = REPO_ROOT.parent.parent
PKG_ROOT = REPO_ROOT / "company_core"

if not (PKG_ROOT / "hooks.py").exists():
    raise SystemExit(
        "ERROR: Put this file in the root of apps/company_core and run it there.\n"
        f"Expected: {PKG_ROOT / 'hooks.py'}"
    )

if not (BENCH_ROOT / "sites").exists():
    raise SystemExit(
        "ERROR: Could not detect frappe-bench root.\n"
        f"Detected: {BENCH_ROOT}"
    )


def run(*args: str, cwd: Path | None = None) -> None:
    cmd = list(args)
    print("\n>>>", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd or REPO_ROOT), check=True)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(f"WRITE  {path.relative_to(REPO_ROOT)}")


timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup_root = REPO_ROOT / ".phase_backups" / f"phase-2e-{timestamp}"
backup_root.mkdir(parents=True, exist_ok=True)

hooks_path = PKG_ROOT / "hooks.py"
if hooks_path.exists():
    backup_path = backup_root / "company_core" / "hooks.py"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(hooks_path, backup_path)

print(f"Backup created at: {backup_root.relative_to(REPO_ROOT)}")


project_views_setup_py = r'''
import frappe


KANBAN_BOARD_NAME = "Grovity Task Board"


def ensure_task_kanban_board():
    existing = frappe.db.exists(
        "Kanban Board",
        KANBAN_BOARD_NAME,
    )

    if existing:
        board = frappe.get_doc(
            "Kanban Board",
            existing,
        )

        changed = False

        if board.reference_doctype != "Task":
            board.reference_doctype = "Task"
            changed = True

        if board.field_name != "status":
            board.field_name = "status"
            changed = True

        if board.private:
            board.private = 0
            changed = True

        if changed:
            board.save(ignore_permissions=True)

        return board.name

    status_field = frappe.get_meta(
        "Task"
    ).get_field("status")

    if not status_field:
        frappe.throw(
            "Task status field is required "
            "for the Grovity Kanban board."
        )

    board = frappe.get_doc(
        {
            "doctype": "Kanban Board",
            "kanban_board_name": KANBAN_BOARD_NAME,
            "reference_doctype": "Task",
            "field_name": "status",
            "private": 0,
            "show_labels": 0,
        }
    )

    for option in (
        status_field.options or ""
    ).splitlines():
        option = option.strip()

        if not option:
            continue

        board.append(
            "columns",
            {
                "column_name": option,
            },
        )

    board.insert(ignore_permissions=True)

    return board.name


def ensure_project_views():
    ensure_task_kanban_board()
    frappe.clear_cache(doctype="Task")
    frappe.clear_cache(doctype="Project")
    frappe.clear_cache()
'''

project_views_py = r'''
import frappe
from frappe import _
from frappe.utils import flt


def _get_readable_project(project):
    if not project:
        frappe.throw(
            _("Project is required.")
        )

    doc = frappe.get_doc(
        "Project",
        project,
    )

    allowed = frappe.has_permission(
        "Project",
        ptype="read",
        doc=doc,
        user=frappe.session.user,
    )

    if not allowed:
        frappe.throw(
            _("Not permitted to view this Project."),
            frappe.PermissionError,
        )

    return doc


@frappe.whitelist()
def get_project_view_summary(project):
    _get_readable_project(project)

    tasks = frappe.get_list(
        "Task",
        filters={
            "project": project,
        },
        fields=[
            "name",
            "status",
            "progress",
            "is_milestone",
        ],
        limit=0,
    )

    total = len(tasks)

    milestones = sum(
        1
        for task in tasks
        if task.is_milestone
    )

    completed = sum(
        1
        for task in tasks
        if task.status == "Completed"
    )

    overdue = sum(
        1
        for task in tasks
        if task.status == "Overdue"
    )

    working = sum(
        1
        for task in tasks
        if task.status in (
            "Open",
            "Working",
            "Pending Review",
            "Overdue",
        )
    )

    average_progress = 0.0

    if total:
        average_progress = sum(
            flt(task.progress or 0)
            for task in tasks
        ) / total

    return {
        "project": project,
        "visible_tasks": total,
        "milestones": milestones,
        "working": working,
        "completed": completed,
        "overdue": overdue,
        "average_progress": round(
            average_progress,
            1,
        ),
    }
'''

project_control_js = r'''
(() => {
    const KANBAN_BOARD = "Grovity Task Board";

    function open_task_view(frm, view, extra_filters = {}) {
        frappe.route_options = {
            project: frm.doc.name,
            ...extra_filters,
        };

        if (view === "Kanban") {
            frappe.set_route([
                "List",
                "Task",
                "Kanban",
                KANBAN_BOARD,
            ]);
            return;
        }

        frappe.set_route([
            "List",
            "Task",
            view,
        ]);
    }

    function add_project_control_buttons(frm) {
        const group = __("Project Control");

        frm.add_custom_button(
            __("Task List"),
            () => open_task_view(frm, "List"),
            group
        );

        frm.add_custom_button(
            __("Kanban"),
            () => open_task_view(frm, "Kanban"),
            group
        );

        frm.add_custom_button(
            __("Gantt"),
            () => open_task_view(frm, "Gantt"),
            group
        );

        frm.add_custom_button(
            __("Milestones"),
            () => open_task_view(
                frm,
                "List",
                { is_milestone: 1 }
            ),
            group
        );
    }

    function add_project_control_summary(frm) {
        frappe.call({
            method: (
                "company_core.project_views."
                + "get_project_view_summary"
            ),
            args: {
                project: frm.doc.name,
            },
            callback(r) {
                const summary = r.message;

                if (!summary) {
                    return;
                }

                frm.dashboard.add_indicator(
                    __("{0} Visible Tasks", [
                        summary.visible_tasks,
                    ]),
                    "blue"
                );

                frm.dashboard.add_indicator(
                    __("{0} Milestones", [
                        summary.milestones,
                    ]),
                    "purple"
                );

                frm.dashboard.add_indicator(
                    __("{0}% Avg Progress", [
                        summary.average_progress,
                    ]),
                    "green"
                );

                if (summary.overdue) {
                    frm.dashboard.add_indicator(
                        __("{0} Overdue", [
                            summary.overdue,
                        ]),
                        "red"
                    );
                }
            },
        });
    }

    frappe.ui.form.on("Project", {
        refresh(frm) {
            if (frm.is_new()) {
                return;
            }

            add_project_control_buttons(frm);
            add_project_control_summary(frm);
        },
    });
})();
'''

hooks_block = r'''

# === GROVITY PHASE 2E PROJECT VIEWS ===

doctype_js = globals().get(
    "doctype_js",
    {},
)

doctype_js.update(
    {
        "Project": (
            "public/js/project_control.js"
        ),
    }
)
'''

test_project_views_py = r'''
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

        app_root = (
            Path(__file__)
            .resolve()
            .parents[2]
        )

        js_path = (
            app_root
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
'''


write_text(
    PKG_ROOT / "project_views_setup.py",
    project_views_setup_py,
)

write_text(
    PKG_ROOT / "project_views.py",
    project_views_py,
)

write_text(
    PKG_ROOT / "public" / "js" / "project_control.js",
    project_control_js,
)

write_text(
    PKG_ROOT / "tests" / "test_project_views.py",
    test_project_views_py,
)


hooks_text = hooks_path.read_text(
    encoding="utf-8"
)

marker = (
    "# === GROVITY PHASE 2E PROJECT VIEWS ==="
)

if marker not in hooks_text:
    hooks_path.write_text(
        hooks_text.rstrip()
        + hooks_block
        + "\n",
        encoding="utf-8",
    )
    print("PATCH  company_core/hooks.py")
else:
    print(
        "SKIP   company_core/hooks.py "
        "(already patched)"
    )


print("\n=== STATIC CHECKS ===")

run(
    sys.executable,
    "-m",
    "compileall",
    "-q",
    str(PKG_ROOT),
)

node = shutil.which("node")

if node:
    run(
        node,
        "--check",
        str(
            PKG_ROOT
            / "public"
            / "js"
            / "project_control.js"
        ),
    )
else:
    print(
        "WARN: node not found; "
        "JavaScript syntax check skipped."
    )


print("\n=== FRAPPE APPLY ===")

run(
    "bench",
    "--site",
    SITE,
    "migrate",
    cwd=BENCH_ROOT,
)

run(
    "bench",
    "--site",
    SITE,
    "execute",
    (
        "company_core.project_views_setup."
        "ensure_project_views"
    ),
    cwd=BENCH_ROOT,
)

run(
    "bench",
    "--site",
    SITE,
    "clear-cache",
    cwd=BENCH_ROOT,
)


print("\n=== REGRESSION TESTS ===")

run(
    "bench",
    "--site",
    SITE,
    "run-tests",
    "--app",
    APP,
    cwd=BENCH_ROOT,
)


print("\n" + "=" * 72)
print(
    "PHASE 2E APPLY SCRIPT FINISHED "
    "SUCCESSFULLY"
)
print(
    "Expected total after this phase: "
    "49 integration tests."
)
print(
    "Native ERPNext Task List / Kanban / "
    "Gantt are reused."
)
print(
    "No git commit was created automatically."
)
print("=" * 72)

run(
    "git",
    "status",
    "--short",
    cwd=REPO_ROOT,
)
