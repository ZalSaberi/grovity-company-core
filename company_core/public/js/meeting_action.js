frappe.ui.form.on("Meeting Action", {
    refresh(frm) {
        if (
            frm.is_new()
            || frm.doc.linked_task
            || frm.doc.status === "Cancelled"
        ) {
            return;
        }

        frm.add_custom_button(
            __("Create Task"),
            () => {
                frappe.call({
                    method: (
                        "company_core.operations_service."
                        + "create_task_from_action"
                    ),
                    args: {action: frm.doc.name},
                    callback(r) {
                        if (r.message) {
                            frappe.set_route(
                                "Form",
                                "Task",
                                r.message
                            );
                        }
                    },
                });
            }
        );
    },
});
