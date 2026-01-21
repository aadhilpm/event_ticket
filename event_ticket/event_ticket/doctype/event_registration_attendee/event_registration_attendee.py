# Copyright (c) 2024, Aadhil and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document


class EventRegistrationAttendee(Document):
	def before_print(self, settings=None):
		"""Format additional fields for printing"""
		self.format_additional_fields()

	def format_additional_fields(self):
		"""Format additional_fields JSON into readable text"""
		if not self.additional_fields:
			return

		try:
			# Parse the JSON if it's a string
			if isinstance(self.additional_fields, str):
				try:
					fields_data = json.loads(self.additional_fields)
				except json.JSONDecodeError:
					# If it's already formatted text, leave it as is
					return
			else:
				fields_data = self.additional_fields

			if not fields_data or not isinstance(fields_data, dict):
				return

			# Get the event to fetch field labels
			parent_doc = frappe.get_doc("Event Registration", self.parent)
			event = frappe.get_doc("Ticket Event", parent_doc.event)

			# Create a mapping of field_key to field_label
			field_labels = {}
			for field in event.registration_fields:
				field_labels[field.field_key] = field.field_label

			# Format the additional fields into readable text
			formatted_parts = []
			for key, value in fields_data.items():
				label = field_labels.get(key, key.replace("_", " ").title())

				# Handle boolean values
				if isinstance(value, bool):
					value = "Yes" if value else "No"

				formatted_parts.append(f"{label}: {value}")

			# Store as comma-separated text for grid display
			self.additional_fields = " | ".join(formatted_parts)

		except Exception as e:
			frappe.log_error(f"Error formatting additional_fields: {e!s}")


@frappe.whitelist()
def get_formatted_additional_fields(attendee_name, event):
	"""Get formatted additional fields for display"""
	try:
		attendee = frappe.get_doc("Event Registration Attendee", attendee_name)

		if not attendee.additional_fields:
			return ""

		# Parse the JSON
		if isinstance(attendee.additional_fields, str):
			try:
				fields_data = json.loads(attendee.additional_fields)
			except json.JSONDecodeError:
				# Already formatted
				return attendee.additional_fields
		else:
			fields_data = attendee.additional_fields

		if not fields_data or not isinstance(fields_data, dict):
			return ""

		# Get the event to fetch field labels
		event_doc = frappe.get_doc("Ticket Event", event)

		# Create a mapping of field_key to field_label
		field_labels = {}
		for field in event_doc.registration_fields:
			field_labels[field.field_key] = field.field_label

		# Format the additional fields into readable text
		formatted_parts = []
		for key, value in fields_data.items():
			label = field_labels.get(key, key.replace("_", " ").title())

			# Handle boolean values
			if isinstance(value, bool):
				value = "Yes" if value else "No"

			formatted_parts.append(f"{label}: {value}")

		return " | ".join(formatted_parts)

	except Exception as e:
		frappe.log_error(f"Error formatting additional_fields: {e!s}")
		return ""
