frappe.ui.form.on("Event Registration", {
	refresh: function (frm) {
		// Add custom button to resend email
		if (frm.doc.name && frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Resend Email"), function () {
				frappe.call({
					method: "event_ticket.event_ticket.doctype.event_registration.event_registration.resend_email",
					args: {
						name: frm.doc.name,
					},
					callback: function (r) {
						if (r.message) {
							frappe.msgprint(__("Email sent successfully"));
							frm.reload_doc();
						}
					},
				});
			});
		}
	},
});
