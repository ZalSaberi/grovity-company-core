frappe.ui.form.on("Event", {
    setup(frm) {
        if (frm.is_new() && !frm.doc.custom_grovity_managed) {
            if (!frm.doc.custom_grovity_kind) {
                frm.set_value("custom_grovity_kind", "Personal Plan");
            }
            if (!frm.doc.custom_calendar_owner) {
                frm.set_value("custom_calendar_owner", frappe.session.user);
            }
            frm.set_value("custom_blocks_availability", 1);
            frm.set_value("event_type", "Private");
        }
    },

    refresh(frm) {
        frm.add_custom_button(__("Meeting Requests"), () => {
            frappe.set_route("List", "Meeting Request");
        }, __("Grovity"));

        frm.add_custom_button(__("Calendar Preference"), () => {
            frappe.set_route("Form", "Grovity Calendar Preference", frappe.session.user);
        }, __("Grovity"));

        if (
            frm.doc.custom_grovity_managed &&
            frm.doc.custom_source_doctype &&
            frm.doc.custom_source_name
        ) {
            frm.add_custom_button(__("Open Source"), () => {
                frappe.set_route(
                    "Form",
                    frm.doc.custom_source_doctype,
                    frm.doc.custom_source_name
                );
            }, __("Grovity"));
        }
    },
});
