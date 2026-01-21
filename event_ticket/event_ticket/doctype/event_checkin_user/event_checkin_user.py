# Copyright (c) 2024, Aadhil and contributors
# For license information, please see license.txt

import base64
import hashlib
import json
from io import BytesIO

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, random_string


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
		"""Generate QR code for app login using Frappe's pyqrcode"""
		from pyqrcode import create as qrcreate

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

		# Generate QR code using pyqrcode (Frappe's dependency)
		qr = qrcreate(encoded_data, error="L")

		# Save to BytesIO as PNG
		buffer = BytesIO()
		qr.png(buffer, scale=8, module_color=[0, 0, 0], background=[255, 255, 255])
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


# ==========================================
# Public API Methods (Whitelisted)
# ==========================================


@frappe.whitelist(allow_guest=True)
def checkin_login(email, pin):
	"""
	Public API to authenticate check-in operator

	Args:
		email: Operator email
		pin: Operator PIN

	Returns:
		dict: API credentials and allowed events
	"""
	try:
		if not frappe.db.exists("Event Checkin User", email):
			return {"success": False, "error": _("Invalid credentials")}

		operator = frappe.get_doc("Event Checkin User", email)

		if not operator.is_active:
			return {"success": False, "error": _("Account is inactive")}

		# Verify PIN
		stored_pin = operator.get_password("pin")
		if stored_pin != pin:
			return {"success": False, "error": _("Invalid credentials")}

		# Get allowed events
		allowed_events = []
		if operator.allowed_events:
			for e in operator.allowed_events:
				event = frappe.get_doc("Ticket Event", e.event)
				allowed_events.append(
					{
						"event_code": event.name,
						"event_name": event.event_name,
						"start_date": str(event.start_date) if event.start_date else None,
						"venue": event.venue,
					}
				)
		else:
			# No restriction, get all published events
			events = frappe.get_all(
				"Ticket Event",
				filters={"status": "Published"},
				fields=["name", "event_name", "start_date", "venue"],
			)
			for event in events:
				allowed_events.append(
					{
						"event_code": event.name,
						"event_name": event.event_name,
						"start_date": str(event.start_date) if event.start_date else None,
						"venue": event.venue,
					}
				)

		return {
			"success": True,
			"operator_name": operator.operator_name,
			"api_key": operator.api_key,
			"api_secret": operator.get_password("api_secret"),
			"allowed_events": allowed_events,
		}

	except Exception as e:
		frappe.log_error(f"Check-in login error: {e!s}", "Check-in API Error")
		return {"success": False, "error": str(e)}


@frappe.whitelist(allow_guest=True)
def checkin(api_key, api_secret, ticket_number=None, qr_data=None):
	"""
	Public API to check-in an attendee

	Args:
		api_key: Operator API key
		api_secret: Operator API secret
		ticket_number: Ticket number (if manual entry)
		qr_data: QR code data (if scanned)

	Returns:
		dict: Check-in result
	"""
	try:
		# Authenticate operator
		operator = frappe.db.get_value(
			"Event Checkin User",
			{"api_key": api_key, "is_active": 1},
			["name", "operator_name"],
			as_dict=True,
		)

		if not operator:
			return {"success": False, "error": _("Invalid API credentials")}

		operator_doc = frappe.get_doc("Event Checkin User", operator.name)

		# Verify API secret
		if operator_doc.get_password("api_secret") != api_secret:
			return {"success": False, "error": _("Invalid API credentials")}

		# Parse QR data if provided
		if qr_data:
			try:
				qr_info = json.loads(qr_data)
				ticket_number = qr_info.get("t")
				event_code = qr_info.get("e")
				verification = qr_info.get("v")

				# Verify QR code authenticity
				secret = frappe.local.conf.get("encryption_key", frappe.local.conf.get("secret_key", ""))
				expected_verification = hashlib.sha256(
					f"{ticket_number}{event_code}{secret}".encode()
				).hexdigest()[:8]

				if verification != expected_verification:
					return {"success": False, "error": _("Invalid QR code")}

			except json.JSONDecodeError:
				return {"success": False, "error": _("Invalid QR code format")}

		if not ticket_number:
			return {"success": False, "error": _("Ticket number is required")}

		# Find attendee
		attendee = frappe.db.get_value(
			"Event Registration Attendee",
			{"ticket_number": ticket_number},
			["name", "parent", "attendee_name", "gender", "sequence_number", "checked_in"],
			as_dict=True,
		)

		if not attendee:
			return {"success": False, "error": _("Ticket not found")}

		# Get registration and event info
		registration = frappe.get_doc("Event Registration", attendee.parent)
		event = frappe.get_doc("Ticket Event", registration.event)

		# Check operator permission for this event
		if not operator_doc.can_checkin_event(event.name):
			return {"success": False, "error": _("Not authorized for this event")}

		# Get additional fields for checkin display
		from event_ticket.utils import get_additional_fields_for_display

		attendee_doc = frappe.get_doc("Event Registration Attendee", attendee.name)
		additional_fields_display = get_additional_fields_for_display(attendee_doc, event, "checkin")

		# Check if already checked in
		if attendee.checked_in:
			return {
				"success": False,
				"error": _("Already checked in"),
				"attendee": {
					"name": attendee.attendee_name,
					"ticket_number": ticket_number,
					"sequence_number": attendee.sequence_number,
					"already_checked_in": True,
					"additional_fields": additional_fields_display,
				},
			}

		# Perform check-in
		frappe.db.set_value(
			"Event Registration Attendee",
			attendee.name,
			{"checked_in": 1, "checkin_time": now_datetime(), "checked_in_by": operator.name},
		)

		return {
			"success": True,
			"message": _("Check-in successful"),
			"attendee": {
				"name": attendee.attendee_name,
				"ticket_number": ticket_number,
				"sequence_number": attendee.sequence_number,
				"gender": attendee.gender,
				"event_name": event.event_name,
				"additional_fields": additional_fields_display,
			},
		}

	except Exception as e:
		frappe.log_error(f"Check-in error: {e!s}", "Check-in API Error")
		return {"success": False, "error": str(e)}


@frappe.whitelist(allow_guest=True)
def get_event_stats(api_key, api_secret, event_code):
	"""
	Public API to get check-in statistics for an event

	Args:
		api_key: Operator API key
		api_secret: Operator API secret
		event_code: Event code

	Returns:
		dict: Statistics including total, checked-in, pending attendees
	"""
	try:
		# Authenticate operator
		operator = frappe.db.get_value(
			"Event Checkin User", {"api_key": api_key, "is_active": 1}, ["name"], as_dict=True
		)

		if not operator:
			return {"success": False, "error": _("Invalid API credentials")}

		operator_doc = frappe.get_doc("Event Checkin User", operator.name)

		# Verify API secret
		if operator_doc.get_password("api_secret") != api_secret:
			return {"success": False, "error": _("Invalid API credentials")}

		# Check if event exists
		if not frappe.db.exists("Ticket Event", event_code):
			return {"success": False, "error": _("Event not found")}

		event = frappe.get_doc("Ticket Event", event_code)

		# Check operator permission for this event
		if not operator_doc.can_checkin_event(event_code):
			return {"success": False, "error": _("Not authorized for this event")}

		# Get registration IDs for this event
		registrations = frappe.get_all(
			"Event Registration", filters={"event": event_code, "status": ["!=", "Cancelled"]}, pluck="name"
		)

		if not registrations:
			return {
				"success": True,
				"event_name": event.event_name,
				"stats": {
					"total_attendees": 0,
					"checked_in": 0,
					"pending": 0,
					"male_total": 0,
					"male_checked_in": 0,
					"female_total": 0,
					"female_checked_in": 0,
				},
			}

		# Get attendee stats
		total = frappe.db.count("Event Registration Attendee", {"parent": ["in", registrations]})

		checked_in = frappe.db.count(
			"Event Registration Attendee", {"parent": ["in", registrations], "checked_in": 1}
		)

		male_total = frappe.db.count(
			"Event Registration Attendee", {"parent": ["in", registrations], "gender": "Male"}
		)

		male_checked_in = frappe.db.count(
			"Event Registration Attendee",
			{"parent": ["in", registrations], "gender": "Male", "checked_in": 1},
		)

		female_total = frappe.db.count(
			"Event Registration Attendee", {"parent": ["in", registrations], "gender": "Female"}
		)

		female_checked_in = frappe.db.count(
			"Event Registration Attendee",
			{"parent": ["in", registrations], "gender": "Female", "checked_in": 1},
		)

		return {
			"success": True,
			"event_name": event.event_name,
			"stats": {
				"total_attendees": total,
				"checked_in": checked_in,
				"pending": total - checked_in,
				"male_total": male_total,
				"male_checked_in": male_checked_in,
				"female_total": female_total,
				"female_checked_in": female_checked_in,
			},
		}

	except Exception as e:
		frappe.log_error(f"Get stats error: {e!s}", "Check-in API Error")
		return {"success": False, "error": str(e)}


@frappe.whitelist(allow_guest=True)
def search_attendee(api_key, api_secret, event_code, query):
	"""
	Public API to search for attendees by name or ticket number

	Args:
		api_key: Operator API key
		api_secret: Operator API secret
		event_code: Event code
		query: Search query (name or ticket number)

	Returns:
		dict: List of matching attendees
	"""
	try:
		# Authenticate operator
		operator = frappe.db.get_value(
			"Event Checkin User", {"api_key": api_key, "is_active": 1}, ["name"], as_dict=True
		)

		if not operator:
			return {"success": False, "error": _("Invalid API credentials")}

		operator_doc = frappe.get_doc("Event Checkin User", operator.name)

		# Verify API secret
		if operator_doc.get_password("api_secret") != api_secret:
			return {"success": False, "error": _("Invalid API credentials")}

		# Check if event exists
		if not frappe.db.exists("Ticket Event", event_code):
			return {"success": False, "error": _("Event not found")}

		# Check operator permission for this event
		if not operator_doc.can_checkin_event(event_code):
			return {"success": False, "error": _("Not authorized for this event")}

		# Get registration IDs for this event
		registrations = frappe.get_all(
			"Event Registration", filters={"event": event_code, "status": ["!=", "Cancelled"]}, pluck="name"
		)

		if not registrations:
			return {"success": True, "attendees": []}

		# Search attendees
		attendees = frappe.db.sql(
			"""
			SELECT
				era.attendee_name,
				era.ticket_number,
				era.sequence_number,
				era.gender,
				era.checked_in,
				era.checkin_time
			FROM `tabEvent Registration Attendee` era
			WHERE era.parent IN %(registrations)s
			AND (
				era.attendee_name LIKE %(query)s
				OR era.ticket_number LIKE %(query)s
				OR era.sequence_number LIKE %(query)s
			)
			ORDER BY era.attendee_name
			LIMIT 50
		""",
			{"registrations": registrations, "query": f"%{query}%"},
			as_dict=True,
		)

		return {"success": True, "attendees": attendees}

	except Exception as e:
		frappe.log_error(f"Search error: {e!s}", "Check-in API Error")
		return {"success": False, "error": str(e)}
