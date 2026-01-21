# Copyright (c) 2024, Aadhil and contributors
# For license information, please see license.txt

import json

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

	def create_public_registration(self, contact_person, email, mobile, attendees):
		"""
		Create a registration from public API

		Args:
			contact_person: Name of contact person
			email: Contact email
			mobile: Contact mobile
			attendees: List of attendee dictionaries

		Returns:
			dict: Registration result with success status
		"""
		import json

		from event_ticket.utils import generate_qr_image

		# Check if registration is allowed
		is_allowed, error_message = self.is_registration_allowed()
		if not is_allowed:
			return {"success": False, "error": error_message}

		if not attendees or len(attendees) == 0:
			return {"success": False, "error": _("At least one attendee is required")}

		# Check capacity
		if self.max_capacity and self.max_capacity > 0:
			current_count = self.get_registration_count()
			if current_count + len(attendees) > self.max_capacity:
				return {"success": False, "error": _("Not enough seats available")}

		# Create registration
		registration = frappe.get_doc(
			{
				"doctype": "Event Registration",
				"event": self.name,
				"contact_person": contact_person,
				"email": email,
				"mobile": mobile,
				"attendees": [],
			}
		)

		# Add attendees
		for attendee in attendees:
			additional_fields = attendee.get("additional_fields", {})
			if isinstance(additional_fields, str):
				additional_fields = json.loads(additional_fields)

			registration.append(
				"attendees",
				{
					"attendee_name": attendee.get("attendee_name"),
					"gender": attendee.get("gender"),
					"additional_fields": json.dumps(additional_fields) if additional_fields else None,
				},
			)

		registration.insert(ignore_permissions=True)

		# Reload to get generated ticket data
		registration.reload()

		# Build attendee response with QR images
		attendees_data = []
		for attendee in registration.attendees:
			qr_image = generate_qr_image(attendee.qr_code)
			attendees_data.append(
				{
					"attendee_name": attendee.attendee_name,
					"ticket_number": attendee.ticket_number,
					"sequence_number": attendee.sequence_number,
					"gender": attendee.gender,
					"qr_image": qr_image,
				}
			)

		return {
			"success": True,
			"registration_id": registration.name,
			"attendees": attendees_data,
			"message": _("Registration successful"),
		}


# ==========================================
# Public API Methods (Whitelisted)
# ==========================================


@frappe.whitelist(allow_guest=True)
def register(event, contact_person, email, attendees, mobile=None):
	"""
	Public API to register for an event

	Args:
		event: Event code/name
		contact_person: Name of contact person
		email: Contact email
		mobile: Contact mobile (optional)
		attendees: List of attendee dictionaries

	Returns:
		dict: Registration result with success status
	"""
	try:
		# Validate event exists
		if not frappe.db.exists("Ticket Event", event):
			return {"success": False, "error": _("Event not found")}

		event_doc = frappe.get_doc("Ticket Event", event)

		# Parse attendees if string
		if isinstance(attendees, str):
			attendees = json.loads(attendees)

		# Use DocType method to create registration
		result = event_doc.create_public_registration(
			contact_person=contact_person, email=email, mobile=mobile, attendees=attendees
		)

		return result

	except Exception as e:
		frappe.log_error(f"Registration error: {e!s}", "Event Registration API Error")
		return {"success": False, "error": str(e)}
