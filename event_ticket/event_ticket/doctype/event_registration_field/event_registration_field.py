# Copyright (c) 2024, Aadhil and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document


class EventRegistrationField(Document):
	def before_save(self):
		if not self.field_key and self.field_label:
			# Generate field_key from field_label (snake_case)
			self.field_key = re.sub(r"[^a-z0-9]+", "_", self.field_label.lower()).strip("_")
