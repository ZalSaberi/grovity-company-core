frappe.ui.form.on("Project Meeting", {
    refresh(frm) {
        if (frm.is_new()) {
            return;
        }

        if (!frm.doc.pm_confirmation) {
            frm.add_custom_button(
                __("Confirm as PM"),
                () => {
                    frappe.call({
                        method: (
                            "company_core.operations_service."
                            + "confirm_meeting_as_pm"
                        ),
                        args: {meeting: frm.doc.name},
                        callback() {
                            frm.reload_doc();
                        },
                    });
                },
                __("Confirmations")
            );
        }

        if (
            frm.doc.pm_confirmation
            && !frm.doc.summary_published
        ) {
            frm.add_custom_button(
                __("Publish Summary"),
                () => {
                    frappe.confirm(
                        __("Publish the meeting summary to all meeting participants?"),
                        () => {
                            frappe.call({
                                method: (
                                    "company_core.operations_service."
                                    + "publish_meeting_summary"
                                ),
                                args: {meeting: frm.doc.name},
                                freeze: true,
                                freeze_message: __("Publishing meeting summary..."),
                                callback(r) {
                                    if (r.message) {
                                        frappe.msgprint({
                                            title: __("Meeting Summary Published"),
                                            indicator: "green",
                                            message: __(
                                                "Summary recipients: {0}<br>Action notifications: {1}",
                                                [
                                                    r.message.summary_recipients || 0,
                                                    r.message.action_notifications || 0,
                                                ]
                                            ),
                                        });
                                    }
                                    frm.reload_doc();
                                },
                            });
                        }
                    );
                },
                __("Notifications")
            );
        }

        if (
            frm.doc.pm_confirmation
            && !frm.doc.ceo_confirmation
        ) {
            frm.add_custom_button(
                __("Confirm as CEO"),
                () => {
                    frappe.call({
                        method: (
                            "company_core.operations_service."
                            + "confirm_meeting_as_ceo"
                        ),
                        args: {meeting: frm.doc.name},
                        callback() {
                            frm.reload_doc();
                        },
                    });
                },
                __("Confirmations")
            );
        }
    },
});
