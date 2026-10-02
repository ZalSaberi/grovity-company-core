frappe.ui.form.on("Meeting Request", {
    refresh(frm) {
        frm.add_custom_button(__("Open Calendar"), () => {
            window.location.href = "/app/event/view/calendar/default";
        });

        if (frm.is_new()) return;

        const me = frappe.session.user;
        const privileged =
            me === "Administrator" ||
            frappe.user.has_role("Company Owner") ||
            frappe.user.has_role("System Manager");

        if (frm.doc.status === "Requested" && (me === frm.doc.target_user || privileged)) {
            frm.add_custom_button(__("Accept"), () => {
                call_action(
                    "company_core.calendar_service.accept_meeting_request",
                    { name: frm.doc.name },
                    frm
                );
            }, __("Respond"));

            frm.add_custom_button(__("Reject"), () => {
                frappe.prompt(
                    [{ fieldname: "note", fieldtype: "Small Text", label: __("Reason") }],
                    (v) => call_action(
                        "company_core.calendar_service.reject_meeting_request",
                        { name: frm.doc.name, note: v.note || "" },
                        frm
                    ),
                    __("Reject Meeting Request")
                );
            }, __("Respond"));

            frm.add_custom_button(__("Propose Alternative"), () => {
                frappe.prompt(
                    [
                        {
                            fieldname: "alternative_start",
                            fieldtype: "Datetime",
                            label: __("Alternative Start"),
                            reqd: 1,
                        },
                        {
                            fieldname: "alternative_end",
                            fieldtype: "Datetime",
                            label: __("Alternative End"),
                        },
                        { fieldname: "note", fieldtype: "Small Text", label: __("Note") },
                    ],
                    (v) => call_action(
                        "company_core.calendar_service.propose_alternative",
                        {
                            name: frm.doc.name,
                            alternative_start: v.alternative_start,
                            alternative_end: v.alternative_end || null,
                            note: v.note || "",
                        },
                        frm
                    ),
                    __("Propose Alternative")
                );
            }, __("Respond"));
        }

        if (
            frm.doc.status === "Alternative Proposed" &&
            (me === frm.doc.requester || privileged)
        ) {
            frm.add_custom_button(__("Accept Alternative"), () => {
                call_action(
                    "company_core.calendar_service.accept_meeting_request",
                    { name: frm.doc.name },
                    frm
                );
            });
        }

        if (
            ["Requested", "Alternative Proposed", "Scheduled"].includes(frm.doc.status) &&
            ([frm.doc.requester, frm.doc.target_user].includes(me) || privileged)
        ) {
            frm.add_custom_button(__("Cancel Request"), () => {
                call_action(
                    "company_core.calendar_service.cancel_meeting_request",
                    { name: frm.doc.name },
                    frm
                );
            });
        }

        if (frm.doc.scheduled_event) {
            frm.add_custom_button(__("Open Calendar Event"), () => {
                frappe.set_route("Form", "Event", frm.doc.scheduled_event);
            });
        }
    },
});

function call_action(method, args, frm) {
    frappe.call({
        method,
        args,
        freeze: true,
        callback: () => frm.reload_doc(),
    });
}
