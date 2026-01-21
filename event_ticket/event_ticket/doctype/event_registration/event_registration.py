# Copyright (c) 2024, Aadhil and contributors
# For license information, please see license.txt

import hashlib
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, random_string

from event_ticket.utils import generate_qr_image


class EventRegistration(Document):
	def before_insert(self):
		self.registration_date = now_datetime()

	def validate(self):
		self.total_attendees = len(self.attendees)
		self.calculate_amount()

	def onload(self):
		"""Format additional fields for display in grid"""
		self.format_attendee_additional_fields()

	def calculate_amount(self):
		"""Calculate total amount for paid events"""
		event = frappe.get_doc("Ticket Event", self.event)
		if event.is_paid_event and event.ticket_price:
			self.amount = event.ticket_price * len(self.attendees)
		else:
			self.amount = 0
			self.payment_status = "Not Applicable"

	def after_insert(self):
		self.generate_tickets()
		self.reload()
		self.send_confirmation_email()

	def generate_tickets(self):
		"""Generate ticket numbers, sequence numbers, and QR codes for each attendee"""
		event = frappe.get_doc("Ticket Event", self.event)

		for attendee in self.attendees:
			# Generate random ticket number
			ticket_number = self.generate_ticket_number()

			# Get sequence number based on gender
			sequence_number = self.get_next_sequence(event, attendee.gender)

			# Generate QR code data
			qr_data = self.generate_qr_data(ticket_number, event.event_code)

			# Update attendee record
			frappe.db.set_value(
				"Event Registration Attendee",
				attendee.name,
				{"ticket_number": ticket_number, "sequence_number": sequence_number, "qr_code": qr_data},
				update_modified=False,
			)

		# Update event registration count
		event.total_registrations = (event.total_registrations or 0) + len(self.attendees)
		event.save(ignore_permissions=True)

	def generate_ticket_number(self):
		"""Generate a unique random ticket number"""
		while True:
			ticket = f"TKT-{random_string(6).upper()}"
			if not frappe.db.exists("Event Registration Attendee", {"ticket_number": ticket}):
				return ticket

	def get_next_sequence(self, event, gender):
		"""Get next sequence number for the given gender"""
		# Get starting number (default 100)
		start = (event.sequence_start or 100) - 1

		if gender == "Male":
			event.male_sequence = (event.male_sequence or 0) + 1
			seq = start + event.male_sequence
			prefix = "M"
		else:
			event.female_sequence = (event.female_sequence or 0) + 1
			seq = start + event.female_sequence
			prefix = "F"

		event.save(ignore_permissions=True)
		return f"{prefix}-{seq:04d}"

	def generate_qr_data(self, ticket_number, event_code):
		"""Generate QR code data with verification hash"""
		# Create verification hash using encryption_key (auto-generated per site)
		secret = frappe.local.conf.get("encryption_key", frappe.local.conf.get("secret_key", ""))
		verification = hashlib.sha256(f"{ticket_number}{event_code}{secret}".encode()).hexdigest()[:8]

		qr_data = json.dumps({"t": ticket_number, "e": event_code, "v": verification})
		return qr_data

	def send_confirmation_email(self):
		"""Send confirmation email to contact person with PDF attachment"""
		if self.email_sent:
			return

		event = frappe.get_doc("Ticket Event", self.event)
		theme_color = event.theme_color or "#0066cc"

		# Reload to get updated attendee data
		self.reload()

		# Build email HTML (without inline images - QR codes are in PDF)
		tickets_html = self.build_email_tickets_html(event, theme_color)

		# Generate PDF attachment
		pdf_content = self.generate_ticket_pdf(event, theme_color)

		# Prepare context for email
		context = {
			"contact_person": self.contact_person,
			"event_name": event.event_name,
			"event_date": frappe.utils.format_datetime(event.start_date, "dd MMM yyyy, hh:mm a")
			if event.start_date
			else "",
			"venue": event.venue or "",
			"tickets_html": tickets_html,
			"registration_id": self.name,
			"theme_color": theme_color,
		}

		# Build email message
		subject = frappe.render_template(
			event.email_subject or "Your Registration for {{event_name}} is Confirmed", context
		)

		# Use custom email body if provided, otherwise use default
		if event.email_body:
			message = frappe.render_template(event.email_body, context)
		else:
			message = self.get_default_email_html(context, theme_color)

		try:
			frappe.sendmail(
				recipients=[self.email],
				subject=subject,
				message=message,
				reference_doctype=self.doctype,
				reference_name=self.name,
				attachments=[{"fname": f"tickets_{self.name}.pdf", "fcontent": pdf_content}],
				now=True,
			)

			self.db_set("email_sent", 1)
			self.db_set("email_sent_on", now_datetime())

		except Exception as e:
			frappe.log_error(f"Failed to send registration email: {e!s}", "Event Registration Email Error")

	def get_default_email_html(self, context, theme_color):
		"""Generate default email HTML"""
		return f"""
		<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
			<div style="background: {theme_color}; padding: 24px; text-align: center;">
				<h1 style="margin: 0; color: white; font-size: 20px;">Registration Confirmed</h1>
			</div>

			<div style="padding: 24px; background: #fff;">
				<p style="margin: 0 0 16px;">Dear {context["contact_person"]},</p>

				<p style="margin: 0 0 16px;">Thank you for registering for <strong>{context["event_name"]}</strong>. Your registration has been confirmed.</p>

				<div style="background: #f9f9f9; border-radius: 8px; padding: 16px; margin: 20px 0;">
					<h3 style="margin: 0 0 12px; color: {theme_color}; font-size: 14px;">Event Details</h3>
					<p style="margin: 4px 0; font-size: 14px;"><strong>Date:</strong> {context["event_date"] or "To be announced"}</p>
					<p style="margin: 4px 0; font-size: 14px;"><strong>Venue:</strong> {context["venue"] or "To be announced"}</p>
					<p style="margin: 4px 0; font-size: 14px;"><strong>Registration ID:</strong> {context["registration_id"]}</p>
				</div>

				<h3 style="margin: 24px 0 12px; color: {theme_color}; font-size: 14px;">Your Tickets</h3>
				{context["tickets_html"]}

				<div style="background: #e8f5e9; border-radius: 8px; padding: 12px 16px; margin: 20px 0;">
					<p style="margin: 0; color: #2e7d32; font-size: 13px;">
						<strong>PDF Attached:</strong> Your tickets with QR codes are attached to this email. Please present the QR code at the venue for check-in.
					</p>
				</div>

				<p style="margin: 20px 0 0; font-size: 13px; color: #666;">
					If you have any questions, please contact the event organizer.
				</p>
			</div>

			<div style="padding: 16px; background: #f5f5f5; text-align: center; font-size: 12px; color: #888;">
				<p style="margin: 0;">This is an automated message. Please do not reply to this email.</p>
			</div>
		</div>
		"""

	def build_email_tickets_html(self, event, theme_color):
		"""Build HTML tickets for email (QR codes are in PDF attachment only)"""
		tickets = []

		for attendee in self.attendees:
			# Build additional fields for email (only show_on_email = 1)
			additional_fields_html = self.get_additional_fields_html(attendee, event, "email", theme_color)

			ticket = f"""
			<div style="border: 1px solid #e5e5e5; border-radius: 8px; margin-bottom: 12px; overflow: hidden;">
				<div style="background: {theme_color}; color: white; padding: 12px 16px;">
					<strong style="font-size: 14px;">{attendee.attendee_name}</strong>
					<span style="float: right; opacity: 0.9; font-size: 13px;">{attendee.sequence_number}</span>
				</div>
				<div style="padding: 16px;">
					<table style="width: 100%; font-size: 13px; color: #555;" cellpadding="0" cellspacing="0">
						<tr>
							<td style="padding: 4px 0;"><strong>Ticket:</strong></td>
							<td style="padding: 4px 0; color: {theme_color}; font-family: monospace;">{attendee.ticket_number}</td>
						</tr>
						<tr>
							<td style="padding: 4px 0;"><strong>Sequence:</strong></td>
							<td style="padding: 4px 0;">{attendee.sequence_number}</td>
						</tr>
						<tr>
							<td style="padding: 4px 0;"><strong>Category:</strong></td>
							<td style="padding: 4px 0;">{attendee.gender}</td>
						</tr>
						{additional_fields_html}
					</table>
				</div>
			</div>
			"""
			tickets.append(ticket)

		return "".join(tickets)

	def generate_ticket_pdf(self, event, theme_color):
		"""Generate PDF ticket content"""
		import re

		from frappe.utils import format_datetime
		from frappe.utils.pdf import get_pdf

		# Clean event description
		event_description = ""
		if event.description:
			desc = event.description
			desc = re.sub(r'<div class="ql-editor[^"]*"[^>]*>', "", desc)
			desc = re.sub(r"</div>\s*$", "", desc)
			event_description = desc.strip()

		tickets_html = ""
		for attendee in self.attendees:
			qr_image = generate_qr_image(attendee.qr_code)

			# Build additional fields for PDF (only show_on_pdf = 1)
			additional_fields_html = self.get_additional_fields_html(attendee, event, "pdf", theme_color)

			tickets_html += f"""
			<div style="page-break-inside: avoid; border: 2px solid {theme_color}; border-radius: 8px; margin-bottom: 20px; overflow: hidden;">
				<div style="background: {theme_color}; color: white; padding: 16px 20px;">
					<h2 style="margin: 0; font-size: 18px; font-weight: 600;">{event.event_name}</h2>
					<p style="margin: 6px 0 0; opacity: 0.9; font-size: 12px;">
						{format_datetime(event.start_date, "dd MMM yyyy, hh:mm a") if event.start_date else "TBA"} | {event.venue or "Venue TBA"}
					</p>
				</div>
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
								<h3 style="margin: 0 0 12px; color: #222; font-size: 20px; font-weight: 600;">{attendee.attendee_name}</h3>
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
									{additional_fields_html}
								</table>
							</td>
						</tr>
					</table>
				</div>
				<div style="background: #f9f9f9; padding: 10px 20px; border-top: 1px solid #eee; font-size: 10px; color: #666;">
					Registration: {self.name} | {self.contact_person}
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
			<title>Event Tickets - {self.name}</title>
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
			<div style="text-align: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid {theme_color};">
				<h1 style="margin: 0 0 8px; color: {theme_color}; font-size: 22px; font-weight: 600;">Event Tickets</h1>
				<h2 style="margin: 0 0 6px; color: #222; font-size: 16px; font-weight: 500;">{event.event_name}</h2>
				<p style="margin: 0; color: #666; font-size: 12px;">
					{format_datetime(event.start_date, "EEEE, dd MMMM yyyy") if event.start_date else ""}{" - " + event.venue if event.venue else ""}
				</p>
			</div>
			{tickets_html}
			{description_html}
			<div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; text-align: center; font-size: 10px; color: #888;">
				<p style="margin: 0;">Present your QR code at the venue entrance for check-in.</p>
			</div>
		</body>
		</html>
		"""

		return get_pdf(
			html,
			options={
				"page-size": "A4",
				"margin-top": "10mm",
				"margin-right": "10mm",
				"margin-bottom": "10mm",
				"margin-left": "10mm",
			},
		)

	def build_tickets_html(self):
		"""Build HTML table of tickets with QR codes"""
		import base64

		rows = []
		for attendee in self.attendees:
			qr_image = generate_qr_image(attendee.qr_code)

			row = f"""
			<tr>
				<td style="padding: 10px; border: 1px solid #ddd;">
					<strong>{attendee.attendee_name}</strong><br>
					Ticket: {attendee.ticket_number}<br>
					Sequence: {attendee.sequence_number}
				</td>
				<td style="padding: 10px; border: 1px solid #ddd; text-align: center;">
					<img src="{qr_image}" width="100" height="100" alt="QR Code">
				</td>
			</tr>
			"""
			rows.append(row)

		html = f"""
		<table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
			<thead>
				<tr style="background: #f5f5f5;">
					<th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Attendee</th>
					<th style="padding: 10px; border: 1px solid #ddd; text-align: center;">QR Code</th>
				</tr>
			</thead>
			<tbody>
				{"".join(rows)}
			</tbody>
		</table>
		"""
		return html

	@frappe.whitelist()
	def resend_email(self):
		"""Resend confirmation email"""
		self.email_sent = 0
		self.send_confirmation_email()

	def get_ticket_pdf(self):
		"""
		Generate and return PDF tickets

		Returns:
			PDF bytes
		"""
		event = frappe.get_doc("Ticket Event", self.event)
		theme_color = event.theme_color or "#4CAF50"
		return self.generate_ticket_pdf(event, theme_color)

	def format_attendee_additional_fields(self):
		"""Format additional fields for all attendees for display in grid"""
		if not self.attendees:
			return

		try:
			# Get event registration fields
			event = frappe.get_doc("Ticket Event", self.event)
			if not event.registration_fields:
				return

			# Create a mapping of field_key to field_label
			field_labels = {}
			for field in event.registration_fields:
				field_labels[field.field_key] = field.field_label

			# Format each attendee's additional fields
			for attendee in self.attendees:
				if not attendee.additional_fields:
					continue

				# Parse the JSON if it's a string
				if isinstance(attendee.additional_fields, str):
					try:
						fields_data = json.loads(attendee.additional_fields)
					except json.JSONDecodeError:
						# Already formatted, skip
						continue
				else:
					fields_data = attendee.additional_fields

				if not fields_data or not isinstance(fields_data, dict):
					continue

				# Format the additional fields into readable text
				formatted_parts = []
				for key, value in fields_data.items():
					label = field_labels.get(key, key.replace("_", " ").title())

					# Handle boolean values
					if isinstance(value, bool):
						value = "Yes" if value else "No"

					formatted_parts.append(f"{label}: {value}")

				# Store as pipe-separated text for grid display
				attendee.additional_fields = " | ".join(formatted_parts)

		except Exception as e:
			frappe.log_error(f"Error formatting attendee additional_fields: {e!s}")

	def get_additional_fields_html(self, attendee, event, display_type="pdf", theme_color="#4CAF50"):
		"""
		Get HTML for additional fields based on display type

		Args:
			attendee: Event Registration Attendee document
			event: Ticket Event document
			display_type: 'pdf', 'email', or 'checkin'
			theme_color: Theme color for styling

		Returns:
			HTML string for additional fields
		"""
		from event_ticket.utils import format_additional_fields_as_html, get_additional_fields_for_display

		additional_fields = get_additional_fields_for_display(attendee, event, display_type)
		return format_additional_fields_as_html(additional_fields, display_type, theme_color)


# ==========================================
# Public API Methods (Whitelisted)
# ==========================================


@frappe.whitelist(allow_guest=True)
def download_tickets(registration_id):
	"""
	Public API to download PDF tickets

	Args:
		registration_id: Event Registration ID

	Returns:
		PDF file download
	"""
	try:
		if not frappe.db.exists("Event Registration", registration_id):
			frappe.throw(_("Registration not found"))

		registration = frappe.get_doc("Event Registration", registration_id)

		# Use the DocType method to generate PDF
		pdf = registration.get_ticket_pdf()

		# Return PDF as response
		frappe.local.response.filename = f"tickets_{registration_id}.pdf"
		frappe.local.response.filecontent = pdf
		frappe.local.response.type = "pdf"

	except Exception as e:
		frappe.log_error(f"PDF generation error: {e!s}", "Ticket PDF Error")
		frappe.throw(_("Error generating PDF"))
