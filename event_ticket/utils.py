# Copyright (c) 2024, Aadhil and contributors
# For license information, please see license.txt

"""Utility functions for Event Ticket module"""

import json

import frappe


def generate_qr_image(qr_data):
	"""
	Generate QR code image as base64 SVG data URI using pyqrcode

	Args:
		qr_data: Data to encode in QR code (usually JSON string)

	Returns:
		Base64 encoded SVG data URI
	"""
	if not qr_data:
		frappe.log_error("Empty QR data provided", "QR Code Generation Error")
		return ""

	try:
		import base64
		from io import BytesIO

		from pyqrcode import create as qrcreate

		# Create QR code
		qr = qrcreate(qr_data)

		# Generate SVG
		stream = BytesIO()
		qr.svg(stream, scale=4, background="#ffffff", module_color="#000000")
		svg_data = stream.getvalue().decode()
		stream.close()

		# Return as base64 data URI
		svg_b64 = base64.b64encode(svg_data.encode()).decode()
		return f"data:image/svg+xml;base64,{svg_b64}"

	except ImportError as e:
		frappe.log_error(f"pyqrcode library not found: {e!s}", "QR Code Generation Error")
		return ""
	except Exception as e:
		frappe.log_error(f"QR generation error: {e!s}", "QR Code Generation Error")
		return ""


def get_additional_fields_for_display(attendee, event, display_type="pdf"):
	"""
	Get additional fields filtered by display type

	Args:
		attendee: Event Registration Attendee document or dict
		event: Ticket Event document
		display_type: 'pdf', 'email', or 'checkin'

	Returns:
		List of dicts with field labels and values
	"""
	if not hasattr(attendee, "additional_fields") or not attendee.additional_fields:
		return []

	if not hasattr(event, "registration_fields") or not event.registration_fields:
		return []

	try:
		# Parse the JSON
		fields_data = attendee.additional_fields
		if isinstance(fields_data, str):
			try:
				fields_data = json.loads(fields_data)
			except json.JSONDecodeError:
				return []

		if not fields_data or not isinstance(fields_data, dict):
			return []

		# Filter fields based on display type
		result = []
		for field in event.registration_fields:
			# Check the appropriate flag
			show_field = False
			if display_type == "pdf":
				show_field = field.get("show_on_pdf", 1)
			elif display_type == "email":
				show_field = field.get("show_on_email", 1)
			elif display_type == "checkin":
				show_field = field.get("show_to_checkin_user", 1)

			if show_field and field.field_key in fields_data:
				value = fields_data[field.field_key]

				# Handle boolean values
				if isinstance(value, bool):
					value = "Yes" if value else "No"

				result.append({"label": field.field_label, "value": value})

		return result

	except Exception as e:
		frappe.log_error(f"Error getting additional fields for {display_type}: {e!s}")
		return []


def format_additional_fields_as_html(additional_fields, display_type="pdf", theme_color="#4CAF50"):
	"""
	Format additional fields list as HTML

	Args:
		additional_fields: List of dicts with 'label' and 'value' keys
		display_type: 'pdf', 'email', or 'checkin'
		theme_color: Theme color for styling

	Returns:
		HTML string
	"""
	if not additional_fields:
		return ""

	if display_type == "pdf":
		# PDF format - table rows
		html_parts = []
		for field in additional_fields:
			html_parts.append(f"""
								<tr>
									<td style="padding: 4px 15px 4px 0; color: #888;">{frappe.utils.escape_html(field["label"])}</td>
									<td>{frappe.utils.escape_html(str(field["value"]))}</td>
								</tr>""")
		return "".join(html_parts)

	elif display_type == "email":
		# Email format - table rows
		html_parts = []
		for field in additional_fields:
			html_parts.append(f"""
				<tr>
					<td style="padding: 4px 0;"><strong>{frappe.utils.escape_html(field["label"])}:</strong></td>
					<td style="padding: 4px 0;">{frappe.utils.escape_html(str(field["value"]))}</td>
				</tr>""")
		return "".join(html_parts)

	elif display_type == "checkin":
		# Check-in format - simple list
		html_parts = ['<div style="margin-top: 10px;">']
		for field in additional_fields:
			html_parts.append(
				f'<div style="margin: 4px 0;"><strong>{frappe.utils.escape_html(field["label"])}:</strong> '
				f"{frappe.utils.escape_html(str(field['value']))}</div>"
			)
		html_parts.append("</div>")
		return "".join(html_parts)

	return ""
