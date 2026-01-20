// Copyright (c) 2024, Aadhil and contributors
// For license information, please see license.txt

frappe.ui.form.on("Event Checkin User", {
	refresh: function (frm) {
		// Add custom button for regenerating API credentials
		if (!frm.is_new()) {
			frm.add_custom_button(
				__("Regenerate API Credentials"),
				function () {
					frappe.confirm(
						__(
							"Are you sure you want to regenerate API credentials? The operator will need to login again."
						),
						function () {
							frm.call({
								method: "regenerate_api_credentials",
								doc: frm.doc,
								freeze: true,
								freeze_message: __("Regenerating..."),
								callback: function (r) {
									if (r.message) {
										frappe.show_alert({
											message: r.message.message,
											indicator: "green",
										});
										frm.reload_doc();
									}
								},
							});
						}
					);
				},
				__("Actions")
			);
		}
	},

	generate_qr_button: function (frm) {
		if (frm.is_new()) {
			frappe.msgprint(__("Please save the document first before generating QR code."));
			return;
		}

		frm.call({
			method: "generate_login_qr_code",
			doc: frm.doc,
			freeze: true,
			freeze_message: __("Generating QR Code..."),
			callback: function (r) {
				if (r.message) {
					frm.reload_doc();
				}
			},
		});
	},
});
