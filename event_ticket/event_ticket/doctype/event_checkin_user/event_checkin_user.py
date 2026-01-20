# Copyright (c) 2024, Aadhil and contributors
# For license information, please see license.txt

import base64
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import random_string


class EventCheckinUser(Document):
	def before_insert(self):
		self.generate_api_credentials()

	def validate(self):
		self.validate_pin()

	def validate_pin(self):
		"""Validate PIN is 4-6 digits"""
		if self.pin:
			pin = self.get_password("pin")
			if not pin.isdigit() or not (4 <= len(pin) <= 6):
				frappe.throw(_("PIN must be 4-6 digits"))

	def generate_api_credentials(self):
		"""Generate API key and secret for the operator"""
		if not self.api_key:
			self.api_key = random_string(20)
		if not self.api_secret:
			self.api_secret = random_string(40)

	@frappe.whitelist()
	def regenerate_api_credentials(self):
		"""Regenerate API credentials"""
		self.api_key = random_string(20)
		self.api_secret = random_string(40)
		self.save(ignore_permissions=True)
		return {"api_key": self.api_key, "message": _("API credentials regenerated successfully")}

	def can_checkin_event(self, event_code):
		"""Check if operator can check-in for the given event"""
		if not self.allowed_events:
			return True

		allowed_event_codes = [e.event for e in self.allowed_events]
		return event_code in allowed_event_codes

	@frappe.whitelist()
	def generate_login_qr_code(self):
		"""Generate QR code for app login"""
		try:
			from io import BytesIO

			import qrcode
		except ImportError:
			frappe.throw(_("qrcode library is not installed. Please run: pip install qrcode[pil]"))

		# Get site URL
		site_url = frappe.utils.get_url()

		# Get PIN (decrypted)
		pin = self.get_password("pin")

		# Create QR data as JSON
		qr_data = {
			"url": site_url,
			"email": self.operator_email,
			"pin": pin,
			"v": "1",  # version for future compatibility
		}

		# Encode as base64
		json_str = json.dumps(qr_data)
		encoded_data = base64.b64encode(json_str.encode()).decode()

		# Generate QR code
		qr = qrcode.QRCode(
			version=1,
			error_correction=qrcode.constants.ERROR_CORRECT_L,
			box_size=10,
			border=4,
		)
		qr.add_data(encoded_data)
		qr.make(fit=True)

		img = qr.make_image(fill_color="black", back_color="white")

		# Save to BytesIO
		buffer = BytesIO()
		img.save(buffer, format="PNG")
		buffer.seek(0)

		# Save as file
		file_name = f"login_qr_{self.operator_email.replace('@', '_').replace('.', '_')}.png"

		# Delete old QR code file if exists
		if self.login_qr_code:
			old_file = frappe.db.get_value("File", {"file_url": self.login_qr_code}, "name")
			if old_file:
				frappe.delete_doc("File", old_file, ignore_permissions=True)

		# Create new file
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name,
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
				"attached_to_field": "login_qr_code",
				"content": buffer.getvalue(),
				"is_private": 1,
			}
		)
		file_doc.save(ignore_permissions=True)

		# Update the field
		self.login_qr_code = file_doc.file_url
		self.save(ignore_permissions=True)

		frappe.msgprint(
			_(
				"Login QR Code generated successfully. You can now scan this QR code in the Event Check-in app."
			)
		)

		return {"file_url": file_doc.file_url}
