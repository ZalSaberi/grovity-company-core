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
