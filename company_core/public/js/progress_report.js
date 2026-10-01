frappe.ui.form.on("Progress Report", {
    refresh(frm) {
        if (frm.is_new()) {
            return;
        }

        if (
            frm.doc.approval_status === "Draft"
            || frm.doc.approval_status === "Revision Requested"
        ) {
            frm.add_custom_button(
                __("Submit Report"),
                () => {
                    frappe.call({
                        method: (
                            "company_core.operations_service."
                            + "submit_progress_report"
                        ),
                        args: {report: frm.doc.name},
                        callback() {
                            frm.reload_doc();
                        },
                    });
                }
            );
        }

        if (frm.doc.approval_status === "Submitted") {
            frm.add_custom_button(
                __("Approve"),
                () => {
                    frappe.call({
                        method: (
                            "company_core.operations_service."
                            + "review_progress_report"
                        ),
                        args: {
                            report: frm.doc.name,
                            decision: "Approved",
                            comment: "",
                        },
                        callback() {
                            frm.reload_doc();
                        },
                    });
                },
                __("Review")
            );

            frm.add_custom_button(
                __("Request Revision"),
                () => {
                    frappe.prompt(
                        [
                            {
                                fieldname: "comment",
                                fieldtype: "Small Text",
                                label: __("Manager Comment"),
                                reqd: 1,
                            },
                        ],
                        (values) => {
                            frappe.call({
                                method: (
                                    "company_core.operations_service."
                                    + "review_progress_report"
                                ),
                                args: {
                                    report: frm.doc.name,
                                    decision: "Revision Requested",
                                    comment: values.comment,
                                },
                                callback() {
                                    frm.reload_doc();
                                },
                            });
                        },
                        __("Request Revision")
                    );
                },
                __("Review")
            );
        }
    },
});
