# Copyright (c) 2024, Aadhil and contributors
# For license information, please see license.txt

import frappe


def get_context(context):
	"""Get context for events listing page"""
	context.events = frappe.get_all(
		"Ticket Event",
		filters={"status": "Published"},
		fields=[
			"name",
			"event_name",
			"event_code",
			"start_date",
			"venue",
			"banner_image",
			"registration_open",
		],
		order_by="start_date asc",
	)
	context.title = "Events"
	context.no_cache = 1
