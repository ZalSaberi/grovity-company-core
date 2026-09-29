#!/usr/bin/env python3
from __future__ import annotations

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

HOOKS_FILE = PKG_ROOT / "hooks.py"
PROJECT_JS = PKG_ROOT / "public" / "js" / "project_control.js"

if not HOOKS_FILE.exists():
    raise SystemExit(
        "ERROR: Put this installer in apps/company_core and run it there."
    )

if not (BENCH_ROOT / "sites").exists():
    raise SystemExit(
        f"ERROR: frappe-bench root not detected: {BENCH_ROOT}"
    )


def run(*args: str, cwd: Path | None = None) -> None:
    cmd = list(args)
    print("\n>>>", " ".join(cmd))
    subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        check=True,
    )


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        content.rstrip() + "\n",
        encoding="utf-8",
    )
    print(
        "WRITE ",
        path.relative_to(REPO_ROOT),
    )


timestamp = datetime.now().strftime(
    "%Y%m%d-%H%M%S"
)

backup_root = (
    REPO_ROOT
    / ".phase_backups"
    / f"phase-2f-{timestamp}"
)

backup_root.mkdir(
    parents=True,
    exist_ok=True,
)

for src in (
    HOOKS_FILE,
    PROJECT_JS,
):
    if not src.exists():
        continue

    relative = src.relative_to(
        REPO_ROOT
    )

    dst = backup_root / relative
    dst.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        src,
        dst,
    )

print(
    "Backup created at:",
    backup_root.relative_to(REPO_ROOT),
)


project_passport_setup_py = r'''
import frappe
from frappe.custom.doctype.custom_field.custom_field import (
    create_custom_fields,
)


def ensure_project_passport_fields():
    custom_fields = {
        "Project": [
            {
                "fieldname": "custom_grovity_passport_section",
                "label": "Project Passport",
                "fieldtype": "Section Break",
                "insert_after": "project_name",
            },
            {
                "fieldname": "custom_project_passport",
                "label": "Project Passport",
                "fieldtype": "HTML",
                "insert_after": "custom_grovity_passport_section",
            },
            {
                "fieldname": "custom_grovity_project_control_section",
                "label": "Grovity Project Control",
                "fieldtype": "Section Break",
                "insert_after": "custom_project_passport",
            },
            {
                "fieldname": "custom_project_cost",
                "label": "Project Cost",
                "fieldtype": "Currency",
                "insert_after": "custom_collected_amount",
                "description": (
                    "Current project cost snapshot. "
                    "Detailed finance logic will be implemented "
                    "in the Finance phase."
                ),
            },
            {
                "fieldname": "custom_finance_status",
                "label": "Finance Status",
                "fieldtype": "Data",
                "insert_after": "custom_project_cost",
                "description": (
                    "Finance taxonomy will be finalized "
                    "in the Finance phase."
                ),
            },
            {
                "fieldname": "custom_legal_status",
                "label": "Legal Status",
                "fieldtype": "Data",
                "insert_after": "custom_finance_status",
                "description": (
                    "Legal taxonomy will be finalized "
                    "in the Legal and Contract Gates phase."
                ),
            },
        ]
    }

    create_custom_fields(
        custom_fields,
        update=True,
    )

    frappe.clear_cache(
        doctype="Project"
    )


def ensure_project_passport():
    ensure_project_passport_fields()
    frappe.clear_cache()
'''

project_passport_py = r'''
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

    if not frappe.has_permission(
        "Project",
        ptype="read",
        doc=doc,
        user=frappe.session.user,
    ):
        frappe.throw(
            _("Not permitted to view this Project."),
            frappe.PermissionError,
        )

    return doc


def _display_name(user):
    if not user:
        return ""

    return (
        frappe.db.get_value(
            "User",
            user,
            "full_name",
        )
        or user
    )


@frappe.whitelist()
def get_project_passport(project):
    doc = _get_readable_project(
        project
    )

    memberships = frappe.get_all(
        "Project Membership",
        filters={
            "project": project,
            "status": "Active",
        },
        fields=[
            "user",
            "membership_role",
        ],
        order_by="creation asc",
    )

    manager_users = [
        row.user
        for row in memberships
        if row.membership_role
        == "Project Manager"
    ]

    managers = [
        {
            "user": user,
            "name": _display_name(user),
        }
        for user in manager_users
    ]

    observers = sum(
        1
        for row in memberships
        if row.membership_role
        == "Observer"
    )

    team = sum(
        1
        for row in memberships
        if row.membership_role
        != "Observer"
    )

    finance_status = (
        doc.get(
            "custom_finance_status"
        )
        or _("Not configured")
    )

    legal_status = (
        doc.get(
            "custom_legal_status"
        )
        or _("Not configured")
    )

    deadline = (
        doc.get("expected_end_date")
        or doc.get("actual_end_date")
        or None
    )

    progress = flt(
        doc.get("percent_complete")
        or 0
    )

    contract_value = flt(
        doc.get(
            "custom_contract_value"
        )
        or 0
    )

    collected_amount = flt(
        doc.get(
            "custom_collected_amount"
        )
        or 0
    )

    project_cost = flt(
        doc.get(
            "custom_project_cost"
        )
        or 0
    )

    return {
        "project": doc.name,
        "project_name": (
            doc.get("project_name")
            or doc.name
        ),
        "managers": managers,
        "manager_display": (
            ", ".join(
                manager["name"]
                for manager in managers
            )
            or _("Unassigned")
        ),
        "progress": round(
            progress,
            1,
        ),
        "health": (
            doc.get(
                "custom_project_health"
            )
            or _("Not set")
        ),
        "deadline": deadline,
        "team_count": team,
        "observer_count": observers,
        "contract_value": contract_value,
        "collected_amount": (
            collected_amount
        ),
        "project_cost": project_cost,
        "finance_status": finance_status,
        "legal_status": legal_status,
    }
'''

project_control_js = r'''
(() => {
    const KANBAN_BOARD = "Grovity Task Board";

    function escapeValue(value) {
        return frappe.utils.escape_html(
            String(
                value ?? ""
            )
        );
    }

    function formatMoney(value) {
        try {
            return format_currency(
                value || 0
            );
        } catch (error) {
            return String(
                value || 0
            );
        }
    }

    function formatDate(value) {
        if (!value) {
            return __("Not set");
        }

        return frappe.datetime.str_to_user(
            value
        );
    }

    function open_task_view(
        frm,
        view,
        extra_filters = {}
    ) {
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
        const group = __(
            "Project Control"
        );

        frm.add_custom_button(
            __("Task List"),
            () => open_task_view(
                frm,
                "List"
            ),
            group
        );

        frm.add_custom_button(
            __("Kanban"),
            () => open_task_view(
                frm,
                "Kanban"
            ),
            group
        );

        frm.add_custom_button(
            __("Gantt"),
            () => open_task_view(
                frm,
                "Gantt"
            ),
            group
        );

        frm.add_custom_button(
            __("Milestones"),
            () => open_task_view(
                frm,
                "List",
                {
                    is_milestone: 1,
                }
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

    function passportCard(
        label,
        value
    ) {
        return `
            <div class="grovity-passport-card">
                <div class="grovity-passport-label">
                    ${escapeValue(label)}
                </div>
                <div class="grovity-passport-value">
                    ${value}
                </div>
            </div>
        `;
    }

    function render_project_passport(
        frm,
        passport
    ) {
        const field = (
            frm.fields_dict
            .custom_project_passport
        );

        if (
            !field
            || !field.$wrapper
        ) {
            return;
        }

        const cards = [
            passportCard(
                __("Manager"),
                escapeValue(
                    passport.manager_display
                )
            ),
            passportCard(
                __("Progress"),
                (
                    escapeValue(
                        passport.progress
                    )
                    + "%"
                )
            ),
            passportCard(
                __("Health"),
                escapeValue(
                    passport.health
                )
            ),
            passportCard(
                __("Deadline"),
                escapeValue(
                    formatDate(
                        passport.deadline
                    )
                )
            ),
            passportCard(
                __("Team"),
                escapeValue(
                    passport.team_count
                )
            ),
            passportCard(
                __("Observers"),
                escapeValue(
                    passport.observer_count
                )
            ),
            passportCard(
                __("Contract"),
                escapeValue(
                    formatMoney(
                        passport.contract_value
                    )
                )
            ),
            passportCard(
                __("Collected"),
                escapeValue(
                    formatMoney(
                        passport.collected_amount
                    )
                )
            ),
            passportCard(
                __("Cost"),
                escapeValue(
                    formatMoney(
                        passport.project_cost
                    )
                )
            ),
            passportCard(
                __("Finance Status"),
                escapeValue(
                    passport.finance_status
                )
            ),
            passportCard(
                __("Legal Status"),
                escapeValue(
                    passport.legal_status
                )
            ),
        ];

        field.$wrapper.html(`
            <style>
                .grovity-passport {
                    width: 100%;
                    margin: 4px 0 14px;
                }

                .grovity-passport-grid {
                    display: grid;
                    grid-template-columns:
                        repeat(
                            auto-fit,
                            minmax(150px, 1fr)
                        );
                    gap: 10px;
                }

                .grovity-passport-card {
                    min-height: 78px;
                    padding: 12px 14px;
                    border: 1px solid
                        var(--border-color);
                    border-radius: 10px;
                    background:
                        var(--card-bg);
                }

                .grovity-passport-label {
                    margin-bottom: 6px;
                    color:
                        var(--text-muted);
                    font-size: 11px;
                    font-weight: 600;
                    letter-spacing: .02em;
                    text-transform: uppercase;
                }

                .grovity-passport-value {
                    color:
                        var(--text-color);
                    font-size: 14px;
                    font-weight: 600;
                    line-height: 1.35;
                    overflow-wrap: anywhere;
                }
            </style>

            <div class="grovity-passport">
                <div class="grovity-passport-grid">
                    ${cards.join("")}
                </div>
            </div>
        `);
    }

    function load_project_passport(frm) {
        frappe.call({
            method: (
                "company_core."
                + "project_passport."
                + "get_project_passport"
            ),
            args: {
                project: frm.doc.name,
            },
            callback(r) {
                if (!r.message) {
                    return;
                }

                render_project_passport(
                    frm,
                    r.message
                );
            },
        });
    }

    frappe.ui.form.on(
        "Project",
        {
            refresh(frm) {
                if (frm.is_new()) {
                    return;
                }

                add_project_control_buttons(
                    frm
                );

                add_project_control_summary(
                    frm
                );

                load_project_passport(
                    frm
                );
            },
        }
    );
})();
'''

test_project_passport_py = r'''
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
'''

project_passport_benchmark_py = r'''
from __future__ import annotations

import statistics
import time

import frappe

from company_core.project_passport import (
    get_project_passport,
)
from company_core.project_passport_setup import (
    ensure_project_passport,
)


ITERATIONS = 40
WARMUPS = 5


def _percentile(
    values,
    percentile,
):
    ordered = sorted(
        values
    )

    rank = (
        len(ordered) - 1
    ) * percentile

    lower = int(rank)
    upper = min(
        lower + 1,
        len(ordered) - 1,
    )

    fraction = rank - lower

    return (
        ordered[lower]
        + (
            ordered[upper]
            - ordered[lower]
        )
        * fraction
    )


def run():
    frappe.set_user(
        "Administrator"
    )

    ensure_project_passport()

    suffix = frappe.generate_hash(
        length=8
    )

    email = (
        f"passport.perf.{suffix}"
        "@grovity.test"
    )

    created = {
        "user": None,
        "project": None,
        "membership": None,
    }

    try:
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": "Passport Perf",
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

        user.insert(
            ignore_permissions=True
        )

        created["user"] = user.name

        project = frappe.get_doc(
            {
                "doctype": "Project",
                "project_name": (
                    f"Passport PERF {suffix}"
                ),
                "status": "Open",
                "custom_project_status": "Active",
                "custom_project_health": "Healthy",
                "custom_contract_value": 100000,
                "custom_collected_amount": 45000,
                "custom_project_cost": 22000,
            }
        ).insert(
            ignore_permissions=True
        )

        created["project"] = project.name

        membership = frappe.get_doc(
            {
                "doctype": "Project Membership",
                "project": project.name,
                "user": email,
                "membership_role": "Project Manager",
                "status": "Active",
                "start_date": frappe.utils.today(),
            }
        ).insert(
            ignore_permissions=True
        )

        created["membership"] = (
            membership.name
        )

        frappe.db.commit()

        frappe.set_user(
            email
        )

        for _ in range(
            WARMUPS
        ):
            get_project_passport(
                project.name
            )

        samples = []

        for _ in range(
            ITERATIONS
        ):
            started = (
                time.perf_counter()
            )

            get_project_passport(
                project.name
            )

            samples.append(
                (
                    time.perf_counter()
                    - started
                )
                * 1000
            )

        avg = statistics.fmean(
            samples
        )

        p50 = _percentile(
            samples,
            0.50,
        )

        p95 = _percentile(
            samples,
            0.95,
        )

        maximum = max(
            samples
        )

        print("")
        print("=" * 72)
        print(
            "PHASE 2F PROJECT PASSPORT "
            "RUNTIME BENCHMARK"
        )
        print("=" * 72)
        print(
            f"Iterations : {ITERATIONS}"
        )
        print(
            f"Average    : {avg:.2f} ms"
        )
        print(
            f"P50        : {p50:.2f} ms"
        )
        print(
            f"P95        : {p95:.2f} ms"
        )
        print(
            f"Max        : {maximum:.2f} ms"
        )
        print("=" * 72)
        print("")

        return {
            "operation": (
                "Project Passport endpoint"
            ),
            "iterations": ITERATIONS,
            "avg_ms": round(
                avg,
                2,
            ),
            "p50_ms": round(
                p50,
                2,
            ),
            "p95_ms": round(
                p95,
                2,
            ),
            "max_ms": round(
                maximum,
                2,
            ),
        }

    finally:
        frappe.set_user(
            "Administrator"
        )

        if (
            created["membership"]
            and frappe.db.exists(
                "Project Membership",
                created["membership"],
            )
        ):
            frappe.delete_doc(
                "Project Membership",
                created["membership"],
                ignore_permissions=True,
                force=True,
            )

        if (
            created["project"]
            and frappe.db.exists(
                "Project",
                created["project"],
            )
        ):
            frappe.delete_doc(
                "Project",
                created["project"],
                ignore_permissions=True,
                force=True,
            )

        if (
            created["user"]
            and frappe.db.exists(
                "User",
                created["user"],
            )
        ):
            frappe.delete_doc(
                "User",
                created["user"],
                ignore_permissions=True,
                force=True,
            )

        frappe.db.commit()
'''


write_text(
    PKG_ROOT / "project_passport_setup.py",
    project_passport_setup_py,
)

write_text(
    PKG_ROOT / "project_passport.py",
    project_passport_py,
)

write_text(
    PROJECT_JS,
    project_control_js,
)

write_text(
    PKG_ROOT
    / "tests"
    / "test_project_passport.py",
    test_project_passport_py,
)

write_text(
    PKG_ROOT
    / "project_passport_benchmark.py",
    project_passport_benchmark_py,
)


print("\n=== STATIC CHECKS ===")

run(
    sys.executable,
    "-m",
    "compileall",
    "-q",
    str(PKG_ROOT),
)

node = shutil.which(
    "node"
)

if node:
    run(
        node,
        "--check",
        str(PROJECT_JS),
    )
else:
    print(
        "WARN: node not found; "
        "JavaScript syntax check skipped."
    )


print("\n=== APPLY PHASE 2F ===")

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
        "company_core."
        "project_passport_setup."
        "ensure_project_passport"
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


print("\n=== TARGETED PHASE 2F TESTS ===")

run(
    "bench",
    "--site",
    SITE,
    "run-tests",
    "--app",
    APP,
    "--module",
    (
        "company_core.tests."
        "test_project_passport"
    ),
    cwd=BENCH_ROOT,
)


print("\n=== FULL REGRESSION SUITE ===")

run(
    "bench",
    "--site",
    SITE,
    "run-tests",
    "--app",
    APP,
    cwd=BENCH_ROOT,
)


print("\n=== RUNTIME PERFORMANCE ===")

run(
    "bench",
    "--site",
    SITE,
    "execute",
    (
        "company_core."
        "project_passport_benchmark."
        "run"
    ),
    cwd=BENCH_ROOT,
)


print("\n" + "=" * 72)
print(
    "PHASE 2F APPLY SCRIPT "
    "FINISHED SUCCESSFULLY"
)
print(
    "Expected total after this phase: "
    "56 integration tests."
)
print(
    "Project Passport functional, "
    "security and runtime checks completed."
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
