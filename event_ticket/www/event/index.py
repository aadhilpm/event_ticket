# Copyright (c) 2024, Aadhil and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.utils import format_datetime


def get_context(context):
	"""Get context for event registration page"""
	event_code = frappe.form_dict.get("event_code")

	if not event_code:
		context.event = None
		return

	# Get event
	if not frappe.db.exists("Ticket Event", event_code):
		context.event = None
		return

	event = frappe.get_doc("Ticket Event", event_code)
	context.event = event

	# Format dates for display
	context.start_date_formatted = format_datetime(event.start_date) if event.start_date else ""
	context.end_date_formatted = format_datetime(event.end_date) if event.end_date else ""

	# Check if registration is allowed
	is_allowed, error_message = event.is_registration_allowed()
	context.registration_allowed = is_allowed
	context.error_message = error_message

	# Get registration fields
	context.registration_fields = []
	for field in event.registration_fields:
		context.registration_fields.append(
			{
				"field_label": field.field_label,
				"field_key": field.field_key,
				"field_type": field.field_type,
				"options": field.options,
				"is_mandatory": field.is_mandatory,
			}
		)

	# Check if description has actual content (not just empty HTML tags)
	description_text = re.sub(r"<[^>]+>", "", event.description or "").strip()
	context.has_description = bool(description_text)

	context.title = event.event_name
	context.theme_color = event.theme_color or "#0066cc"
	context.no_cache = 1
