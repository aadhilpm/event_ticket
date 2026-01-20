# Copyright (c) 2024, Aadhil and contributors
# For license information, please see license.txt

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import now_datetime


@frappe.whitelist(allow_guest=True)
def register(event, contact_person, email, attendees, mobile=None):
	"""
	Public API to register for an event

	Args:
		event: Event code/name
		contact_person: Name of contact person
		email: Contact email
		mobile: Contact mobile (optional)
		attendees: List of attendee dictionaries with:
			- attendee_name
			- gender
			- additional_fields (dict)
	"""
	try:
		# Validate event
		if not frappe.db.exists("Ticket Event", event):
			return {"success": False, "error": _("Event not found")}

		event_doc = frappe.get_doc("Ticket Event", event)

		# Check if registration is allowed
		is_allowed, error_message = event_doc.is_registration_allowed()
		if not is_allowed:
			return {"success": False, "error": error_message}

		# Parse attendees if string
		if isinstance(attendees, str):
			attendees = json.loads(attendees)

		if not attendees or len(attendees) == 0:
			return {"success": False, "error": _("At least one attendee is required")}

		# Check capacity
		if event_doc.max_capacity and event_doc.max_capacity > 0:
			current_count = event_doc.get_registration_count()
			if current_count + len(attendees) > event_doc.max_capacity:
				return {"success": False, "error": _("Not enough seats available")}

		# Create registration
		registration = frappe.get_doc(
			{
				"doctype": "Event Registration",
				"event": event,
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

	except Exception as e:
		frappe.log_error(f"Registration error: {e!s}", "Event Registration API Error")
		return {"success": False, "error": str(e)}


def generate_qr_image(qr_data):
	"""Generate QR code image as base64 SVG data URI using pyqrcode (Frappe built-in)"""
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


@frappe.whitelist(allow_guest=True)
def download_tickets(registration_id):
	"""
	Generate PDF tickets for download

	Args:
		registration_id: Registration ID
	"""
	try:
		if not frappe.db.exists("Event Registration", registration_id):
			frappe.throw(_("Registration not found"))

		registration = frappe.get_doc("Event Registration", registration_id)
		event = frappe.get_doc("Ticket Event", registration.event)

		# Generate HTML for PDF
		html = get_ticket_html(registration, event)

		# Generate PDF
		from frappe.utils.pdf import get_pdf

		pdf = get_pdf(
			html,
			options={
				"page-size": "A4",
				"margin-top": "10mm",
				"margin-right": "10mm",
				"margin-bottom": "10mm",
				"margin-left": "10mm",
			},
		)

		# Return PDF as response
		frappe.local.response.filename = f"tickets_{registration_id}.pdf"
		frappe.local.response.filecontent = pdf
		frappe.local.response.type = "pdf"

	except Exception as e:
		frappe.log_error(f"PDF generation error: {e!s}", "Ticket PDF Error")
		frappe.throw(_("Error generating PDF"))


def get_ticket_html(registration, event):
	"""Generate HTML for ticket PDF"""
	import html as html_lib
	import re

	from frappe.utils import format_datetime

	# Get theme color from event or use default
	theme_color = event.theme_color or "#0066cc"

	# Clean event description - strip Quill editor wrapper and keep content
	event_description = ""
	if event.description:
		desc = event.description
		# Remove Quill editor wrapper divs
		desc = re.sub(r'<div class="ql-editor[^"]*"[^>]*>', "", desc)
		desc = re.sub(r"</div>\s*$", "", desc)
		# Keep the cleaned HTML for rendering
		event_description = desc.strip()

	tickets_html = ""
	for attendee in registration.attendees:
		qr_image = generate_qr_image(attendee.qr_code)

		tickets_html += f"""
		<div style="page-break-inside: avoid; border: 2px solid {theme_color}; border-radius: 8px; margin-bottom: 20px; overflow: hidden;">
			<!-- Ticket Header -->
			<div style="background: {theme_color}; color: white; padding: 16px 20px;">
				<h2 style="margin: 0; font-size: 18px; font-weight: 600;">{html_lib.escape(event.event_name)}</h2>
				<p style="margin: 6px 0 0; opacity: 0.9; font-size: 12px;">
					{format_datetime(event.start_date, "dd MMM yyyy, hh:mm a") if event.start_date else "TBA"} | {html_lib.escape(event.venue) if event.venue else "Venue TBA"}
				</p>
			</div>

			<!-- Ticket Body -->
			<div style="padding: 20px; background: white;">
				<table style="width: 100%; border-collapse: collapse;">
					<tr>
						<td style="width: 130px; vertical-align: top; padding-right: 20px;">
							<div style="background: #f5f5f5; padding: 8px; border-radius: 6px; text-align: center;">
								<img src="{qr_image}" style="width: 110px; height: 110px; display: block; margin: 0 auto;" />
								<p style="margin: 6px 0 0; font-size: 9px; color: #888;">Scan at venue</p>
							</div>
						</td>
						<td style="vertical-align: top;">
							<h3 style="margin: 0 0 12px; color: #222; font-size: 20px; font-weight: 600;">{html_lib.escape(attendee.attendee_name)}</h3>

							<table style="font-size: 13px; color: #555;">
								<tr>
									<td style="padding: 4px 15px 4px 0; color: #888;">Ticket No</td>
									<td style="font-family: monospace; color: {theme_color}; font-weight: 600;">{attendee.ticket_number}</td>
								</tr>
								<tr>
									<td style="padding: 4px 15px 4px 0; color: #888;">Sequence</td>
									<td style="font-weight: 500;">{attendee.sequence_number}</td>
								</tr>
								<tr>
									<td style="padding: 4px 15px 4px 0; color: #888;">Category</td>
									<td>{attendee.gender}</td>
								</tr>
							</table>
						</td>
					</tr>
				</table>
			</div>

			<!-- Ticket Footer -->
			<div style="background: #f9f9f9; padding: 10px 20px; border-top: 1px solid #eee; font-size: 10px; color: #666;">
				Registration: {registration.name} | {html_lib.escape(registration.contact_person)}
			</div>
		</div>
		"""

	# Event description section
	description_html = ""
	if event_description:
		description_html = f"""
		<div style="margin-top: 25px; padding: 16px; background: #f9f9f9; border-radius: 6px; page-break-inside: avoid;">
			<h3 style="margin: 0 0 10px; color: {theme_color}; font-size: 14px; font-weight: 600;">Event Details</h3>
			<div style="margin: 0; color: #555; font-size: 12px; line-height: 1.5;">{event_description}</div>
		</div>
		"""

	html = f"""
	<!DOCTYPE html>
	<html>
	<head>
		<meta charset="utf-8">
		<title>Event Tickets - {registration.name}</title>
		<style>
			body {{
				font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
				margin: 0;
				padding: 25px;
				color: #333;
				background: #fff;
			}}
		</style>
	</head>
	<body>
		<!-- Header Section -->
		<div style="text-align: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid {theme_color};">
			<h1 style="margin: 0 0 8px; color: {theme_color}; font-size: 22px; font-weight: 600;">Event Tickets</h1>
			<h2 style="margin: 0 0 6px; color: #222; font-size: 16px; font-weight: 500;">{html_lib.escape(event.event_name)}</h2>
			<p style="margin: 0; color: #666; font-size: 12px;">
				{format_datetime(event.start_date, "EEEE, dd MMMM yyyy") if event.start_date else ""}{" - " + html_lib.escape(event.venue) if event.venue else ""}
			</p>
		</div>

		<!-- Tickets -->
		{tickets_html}

		<!-- Event Description -->
		{description_html}

		<!-- Footer -->
		<div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; text-align: center; font-size: 10px; color: #888;">
			<p style="margin: 0;">Present your QR code at the venue entrance for check-in.</p>
		</div>
	</body>
	</html>
	"""

	return html


# ============================================
# Check-in API for Flutter App
# ============================================


@frappe.whitelist(allow_guest=True)
def checkin_login(email, pin):
	"""
	Authenticate check-in operator

	Args:
		email: Operator email
		pin: Operator PIN

	Returns:
		api_key and api_secret if successful
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
	Check-in an attendee

	Args:
		api_key: Operator API key
		api_secret: Operator API secret
		ticket_number: Ticket number (if manual entry)
		qr_data: QR code data (if scanned)
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
			},
		}

	except Exception as e:
		frappe.log_error(f"Check-in error: {e!s}", "Check-in API Error")
		return {"success": False, "error": str(e)}


@frappe.whitelist(allow_guest=True)
def get_event_stats(api_key, api_secret, event_code):
	"""
	Get check-in statistics for an event

	Args:
		api_key: Operator API key
		api_secret: Operator API secret
		event_code: Event code
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

		# Check permission
		if not operator_doc.can_checkin_event(event_code):
			return {"success": False, "error": _("Not authorized for this event")}

		# Get event
		if not frappe.db.exists("Ticket Event", event_code):
			return {"success": False, "error": _("Event not found")}

		event = frappe.get_doc("Ticket Event", event_code)

		# Get registration IDs for this event
		registrations = frappe.get_all(
			"Event Registration", filters={"event": event_code, "status": ["!=", "Cancelled"]}, pluck="name"
		)

		if not registrations:
			return {
				"success": True,
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
	Search for attendees by name or ticket number

	Args:
		api_key: Operator API key
		api_secret: Operator API secret
		event_code: Event code
		query: Search query (name or ticket number)
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

		# Check permission
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
