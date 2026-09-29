
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
