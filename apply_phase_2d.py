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
backup_root = REPO_ROOT / ".phase_backups" / f"phase-2d-{timestamp}"
backup_root.mkdir(parents=True, exist_ok=True)

for relative in [
    "company_core/hooks.py",
    "company_core/permissions.py",
]:
    src = REPO_ROOT / relative
    if src.exists():
        dst = backup_root / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

print(f"Backup created at: {backup_root.relative_to(REPO_ROOT)}")

task_contributor_py = """
from frappe.model.document import Document


class TaskContributor(Document):
    pass
"""

task_contributor_json = {
    "actions": [],
    "doctype": "DocType",
    "editable_grid": 1,
    "engine": "InnoDB",
    "field_order": ["user"],
    "fields": [
        {
            "fieldname": "user",
            "fieldtype": "Link",
            "in_list_view": 1,
            "label": "User",
            "options": "User",
            "reqd": 1
        }
    ],
    "index_web_pages_for_search": 0,
    "istable": 1,
    "links": [],
    "module": "Company Core",
    "name": "Task Contributor",
    "permissions": [],
    "states": [],
    "track_changes": 0
}

task_setup_py = """
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import (
    add_permission,
    setup_custom_perms,
    update_permission_property,
)

from company_core.setup import ensure_security_baseline


def ensure_task_permission(role):
    setup_custom_perms("Task")

    permission_exists = frappe.db.exists(
        "Custom DocPerm",
        {
            "parent": "Task",
            "role": role,
            "permlevel": 0,
            "if_owner": 0,
        },
    )

    if not permission_exists:
        add_permission(
            "Task",
            role,
            permlevel=0,
            ptype="read",
        )

    permissions = {
        "select": 1,
        "read": 1,
        "write": 1,
        "create": 1,
        "delete": 1,
        "submit": 0,
        "cancel": 0,
    }

    for permission_type, value in permissions.items():
        update_permission_property(
            "Task",
            role,
            0,
            permission_type,
            value,
        )

    frappe.clear_cache(doctype="Task")


def ensure_task_fields():
    custom_fields = {
        "Task": [
            {
                "fieldname": "custom_grovity_task_section",
                "label": "Grovity Task Control",
                "fieldtype": "Section Break",
                "insert_after": "is_milestone",
            },
            {
                "fieldname": "custom_milestone",
                "label": "Milestone",
                "fieldtype": "Link",
                "options": "Task",
                "insert_after": "custom_grovity_task_section",
                "description": "Link this task to a milestone inside the same project.",
            },
            {
                "fieldname": "custom_contributors",
                "label": "Contributors",
                "fieldtype": "Table",
                "options": "Task Contributor",
                "insert_after": "custom_milestone",
            },
            {
                "fieldname": "custom_task_progress_column",
                "fieldtype": "Column Break",
                "insert_after": "custom_contributors",
            },
            {
                "fieldname": "custom_planned_progress",
                "label": "Planned Progress",
                "fieldtype": "Percent",
                "insert_after": "custom_task_progress_column",
            },
            {
                "fieldname": "custom_actual_progress",
                "label": "Actual Progress",
                "fieldtype": "Percent",
                "read_only": 1,
                "insert_after": "custom_planned_progress",
                "description": "Mirrors ERPNext Task % Progress.",
            },
            {
                "fieldname": "custom_deliverable",
                "label": "Deliverable",
                "fieldtype": "Check",
                "default": "0",
                "insert_after": "custom_actual_progress",
            },
            {
                "fieldname": "custom_delay_reason",
                "label": "Delay Reason",
                "fieldtype": "Small Text",
                "insert_after": "custom_deliverable",
            },
        ]
    }

    create_custom_fields(custom_fields, update=True)
    frappe.clear_cache(doctype="Task")


def ensure_task_extensions():
    ensure_security_baseline()
    ensure_task_permission("Company User")
    ensure_task_fields()
    frappe.clear_cache()
"""

task_events_py = """
import frappe
from frappe import _
from frappe.utils import flt


def validate_task_extensions(doc, method=None):
    validate_progress(doc)
    validate_milestone(doc)
    validate_contributors(doc)
    sync_actual_progress(doc)


def validate_progress(doc):
    planned = flt(doc.get("custom_planned_progress") or 0)
    actual = flt(doc.get("progress") or 0)

    if planned < 0 or planned > 100:
        frappe.throw(_("Planned Progress must be between 0 and 100."))

    if actual < 0 or actual > 100:
        frappe.throw(_("Task Progress must be between 0 and 100."))


def validate_milestone(doc):
    milestone = doc.get("custom_milestone")

    if not milestone:
        return

    if doc.name and milestone == doc.name:
        frappe.throw(_("A task cannot use itself as its milestone."))

    milestone_data = frappe.db.get_value(
        "Task",
        milestone,
        ["project", "is_milestone"],
        as_dict=True,
    )

    if not milestone_data:
        frappe.throw(_("Milestone Task does not exist."))

    if not milestone_data.is_milestone:
        frappe.throw(_("Selected Milestone must be a Task marked as Is Milestone."))

    if doc.project != milestone_data.project:
        frappe.throw(_("Task and Milestone must belong to the same Project."))


def validate_contributors(doc):
    seen = set()

    for row in doc.get("custom_contributors") or []:
        user = row.user

        if not user:
            continue

        if user in seen:
            frappe.throw(_("Contributor {0} is duplicated.").format(user))

        seen.add(user)


def sync_actual_progress(doc):
    doc.custom_actual_progress = flt(doc.get("progress") or 0)
"""

permissions_block = """

# === GROVITY PHASE 2D TASK CORE ===

def is_task_contributor(task, user):
    if not task or not user:
        return False

    return bool(
        frappe.db.exists(
            "Task Contributor",
            {
                "parent": task,
                "parenttype": "Task",
                "user": user,
            },
        )
    )


def is_task_assigned_to_user(task, user):
    if not task or not user:
        return False

    return bool(
        frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Task",
                "reference_name": task,
                "allocated_to": user,
                "status": ["!=", "Cancelled"],
            },
        )
    )


def can_work_on_task(doc, user):
    project = getattr(doc, "project", None)

    if not project:
        return False

    if is_active_project_manager(project, user):
        return True

    task = getattr(doc, "name", None)

    if not task:
        return False

    if is_task_contributor(task, user):
        return True

    return is_task_assigned_to_user(task, user)


def get_task_permission_query_conditions(user=None):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return ""

    escaped_user = frappe.db.escape(user)

    return f\"\"\"
        EXISTS (
            SELECT 1
            FROM `tabProject Membership` pm
            WHERE pm.project = `tabTask`.project
              AND pm.user = {escaped_user}
              AND pm.status = 'Active'
              AND (
                    pm.membership_role = 'Project Manager'
                    OR EXISTS (
                        SELECT 1
                        FROM `tabTask Contributor` tc
                        WHERE tc.parent = `tabTask`.name
                          AND tc.parenttype = 'Task'
                          AND tc.user = {escaped_user}
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM `tabToDo` td
                        WHERE td.reference_type = 'Task'
                          AND td.reference_name = `tabTask`.name
                          AND td.allocated_to = {escaped_user}
                          AND IFNULL(td.status, 'Open') != 'Cancelled'
                    )
              )
        )
    \"\"\"


def has_task_permission(doc, user=None, ptype=None, **kwargs):
    user = user or frappe.session.user

    if is_privileged_user(user):
        return True

    project = getattr(doc, "project", None)

    if not project:
        return False

    if ptype in (None, "read", "select"):
        return can_work_on_task(doc, user)

    if ptype == "create":
        return is_active_project_manager(project, user)

    if ptype == "write":
        return can_work_on_task(doc, user)

    if ptype == "delete":
        return is_active_project_manager(project, user)

    return False
"""

hooks_block = """

# === GROVITY PHASE 2D TASK CORE ===

permission_query_conditions = globals().get(
    "permission_query_conditions",
    {},
)
permission_query_conditions.update(
    {
        "Task": (
            "company_core.permissions."
            "get_task_permission_query_conditions"
        ),
    }
)

has_permission = globals().get(
    "has_permission",
    {},
)
has_permission.update(
    {
        "Task": (
            "company_core.permissions."
            "has_task_permission"
        ),
    }
)

doc_events = globals().get(
    "doc_events",
    {},
)
doc_events.setdefault(
    "Task",
    {},
)
doc_events["Task"].update(
    {
        "validate": (
            "company_core.task_events."
            "validate_task_extensions"
        ),
    }
)
"""

test_task_core_py = """
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
"""

doctype_dir = PKG_ROOT / "company_core" / "doctype" / "task_contributor"
write_text(doctype_dir / "__init__.py", "")
write_text(doctype_dir / "task_contributor.py", task_contributor_py)
write_text(
    doctype_dir / "task_contributor.json",
    json.dumps(task_contributor_json, ensure_ascii=False, indent=2),
)
write_text(PKG_ROOT / "task_setup.py", task_setup_py)
write_text(PKG_ROOT / "task_events.py", task_events_py)
write_text(PKG_ROOT / "tests" / "test_task_core.py", test_task_core_py)

permissions_path = PKG_ROOT / "permissions.py"
permissions_text = permissions_path.read_text(encoding="utf-8")

for required in ("def is_privileged_user", "def is_active_project_manager"):
    if required not in permissions_text:
        raise SystemExit(
            f"ERROR: permissions.py is missing required helper: {required}\n"
            f"Backup: {backup_root}"
        )

marker = "# === GROVITY PHASE 2D TASK CORE ==="
if marker not in permissions_text:
    permissions_path.write_text(
        permissions_text.rstrip() + permissions_block + "\n",
        encoding="utf-8",
    )
    print("PATCH  company_core/permissions.py")
else:
    print("SKIP   company_core/permissions.py (already patched)")

hooks_path = PKG_ROOT / "hooks.py"
hooks_text = hooks_path.read_text(encoding="utf-8")

if marker not in hooks_text:
    hooks_path.write_text(
        hooks_text.rstrip() + hooks_block + "\n",
        encoding="utf-8",
    )
    print("PATCH  company_core/hooks.py")
else:
    print("SKIP   company_core/hooks.py (already patched)")

print("\n=== STATIC CHECKS ===")
run(sys.executable, "-m", "compileall", "-q", str(PKG_ROOT))

json_path = doctype_dir / "task_contributor.json"
json.loads(json_path.read_text(encoding="utf-8"))
print("JSON OK:", json_path.relative_to(REPO_ROOT))

print("\n=== FRAPPE APPLY ===")
run("bench", "--site", SITE, "migrate", cwd=BENCH_ROOT)
run(
    "bench",
    "--site",
    SITE,
    "execute",
    "company_core.task_setup.ensure_task_extensions",
    cwd=BENCH_ROOT,
)
run("bench", "--site", SITE, "clear-cache", cwd=BENCH_ROOT)

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
print("PHASE 2D APPLY SCRIPT FINISHED SUCCESSFULLY")
print("Expected total after this phase: 41 integration tests.")
print("No git commit was created automatically.")
print("=" * 72)

run("git", "status", "--short", cwd=REPO_ROOT)
