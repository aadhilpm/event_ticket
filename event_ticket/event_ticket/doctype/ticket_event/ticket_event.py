# Copyright (c) 2024, Aadhil and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import random_string


class TicketEvent(Document):
	def before_insert(self):
		if not self.event_code:
			self.event_code = self.generate_event_code()

	def generate_event_code(self):
		"""Generate a unique event code"""
		# Try to create a code from event name
		base_code = "".join(word[0] for word in self.event_name.split()[:3]).upper()
		if len(base_code) < 3:
			base_code = self.event_name[:3].upper()

		# Add random suffix for uniqueness
		code = f"{base_code}-{random_string(4).upper()}"

		# Ensure uniqueness
		while frappe.db.exists("Ticket Event", code):
			code = f"{base_code}-{random_string(4).upper()}"

		return code

	def validate(self):
		self.validate_dates()
		self.generate_field_keys()

	def validate_dates(self):
		if self.start_date and self.end_date:
			if self.end_date < self.start_date:
				frappe.throw(_("End Date cannot be before Start Date"))

		if self.registration_start_date and self.registration_end_date:
			if self.registration_end_date < self.registration_start_date:
				frappe.throw(_("Registration End Date cannot be before Registration Start Date"))

	def generate_field_keys(self):
		"""Generate field keys for dynamic registration fields"""
		import re

		for field in self.registration_fields:
			if not field.field_key and field.field_label:
				field.field_key = re.sub(r"[^a-z0-9]+", "_", field.field_label.lower()).strip("_")

	def get_next_sequence(self, gender):
		"""Get next sequence number for the given gender"""
		# Get starting number (default 100)
		start = (self.sequence_start or 100) - 1

		if gender == "Male":
			self.male_sequence = (self.male_sequence or 0) + 1
			seq = start + self.male_sequence
			prefix = "M"
		else:
			self.female_sequence = (self.female_sequence or 0) + 1
			seq = start + self.female_sequence
			prefix = "F"

		self.save(ignore_permissions=True)
		return f"{prefix}-{seq:04d}"

	def get_registration_count(self):
		"""Get total number of attendees registered"""
		return frappe.db.count(
			"Event Registration Attendee",
			{
				"parent": [
					"in",
					frappe.db.get_all(
						"Event Registration",
						filters={"event": self.name, "docstatus": ["!=", 2]},
						pluck="name",
					),
				]
			},
		)

	def is_registration_allowed(self):
		"""Check if registration is allowed for this event"""
		if not self.registration_open:
			return False, _("Registration is not open for this event")

		if self.status not in ["Published"]:
			return False, _("Event is not published")

		from frappe.utils import now_datetime

		now = now_datetime()

		if self.registration_start_date and now < self.registration_start_date:
			return False, _("Registration has not started yet")

		if self.registration_end_date and now > self.registration_end_date:
			return False, _("Registration has ended")

		if self.max_capacity and self.max_capacity > 0:
			current_count = self.get_registration_count()
			if current_count >= self.max_capacity:
				return False, _("Event is fully booked")

		return True, None
