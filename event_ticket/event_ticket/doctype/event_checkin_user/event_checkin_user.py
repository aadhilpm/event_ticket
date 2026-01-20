# Copyright (c) 2024, Aadhil and contributors
# For license information, please see license.txt

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
